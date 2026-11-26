import json
import re

import pytest

from conftest import fx
from tutor_any_lecture import drawing
from tutor_any_lecture.cli import main
from tutor_any_lecture.drawing import build_scene, text_width, wrap
from tutor_any_lecture.palette import load_palette

KIND_STYLES = {
    "definition": ("rectangle", 2, "solid", None),
    "theorem": ("rectangle", 4, "solid", None),
    "method": ("rectangle", 2, "solid", {"type": 3}),
    "example": ("ellipse", 2, "solid", None),
    "pitfall": ("rectangle", 2, "dashed", None),
}
COMMON_KEYS = {
    "id", "type", "x", "y", "width", "height", "angle", "strokeColor", "backgroundColor", "fillStyle",
    "strokeWidth", "strokeStyle", "roughness", "opacity", "groupIds", "frameId", "roundness", "seed",
    "version", "versionNonce", "isDeleted", "boundElements", "updated", "link", "locked",
}
TEXT_KEYS = {"text", "originalText", "fontSize", "fontFamily", "lineHeight", "textAlign", "verticalAlign", "containerId"}
ARROW_KEYS = {"points", "startBinding", "endBinding", "startArrowhead", "endArrowhead", "lastCommittedPoint"}


def node(node_id, kind="definition", label=None, **extra):
    return {"id": node_id, "label": label or node_id.upper(), "type": kind, **extra}


def edge(src, dst, verb="uses"):
    return {"from": src, "to": dst, "verb": verb}


def shape(scene, node_id):
    return next(e for e in scene["elements"] if (e.get("customData") or {}).get("node") == node_id)


def by_id(scene, element_id):
    return next(e for e in scene["elements"] if e["id"] == element_id)


def node_shapes(scene):
    return [e for e in scene["elements"] if "node" in (e.get("customData") or {})]


def arrows(scene):
    return [e for e in scene["elements"] if e["type"] == "arrow"]


def legend(scene):
    return [e for e in scene["elements"] if e["id"].startswith("legend-")]


def style(element):
    return (element["type"], element["strokeWidth"], element["strokeStyle"], element["roundness"])


def size(element):
    return (element["width"], element["height"])


def right(element):
    return element["x"] + element["width"]


def bottom(element):
    return element["y"] + element["height"]


def centre(element):
    return (element["x"] + element["width"] / 2, element["y"] + element["height"] / 2)


def overlap(a, b):
    return a["x"] < right(b) and b["x"] < right(a) and a["y"] < bottom(b) and b["y"] < bottom(a)


def approx(value):
    return pytest.approx(value, abs=0.02)


# ---- L1: text --------------------------------------------------------------------


def test_text_width_counts_wide_characters_as_one_em():
    assert text_width("ab引", 20) == 44.0
    assert text_width("，", 16) == 16.0
    assert text_width("ｶ", 20) == 12.0


def test_wrap_breaks_at_spaces_and_between_wide_characters():
    assert wrap("Effective annual rate of interest compounded", 220, 20) == [
        "Effective annual", "rate of interest", "compounded"]
    assert wrap("实际年利率与名义利率的比较方法", 220, 20) == ["实际年利率与名义利率的", "比较方法"]
    assert wrap("Itô 引理", 220, 20) == ["Itô 引理"]
    assert wrap("Supercalifragilisticexpialidocious", 220, 20) == ["Supercalifragilist", "icexpialidocious"]


def test_wrap_collapses_whitespace():
    assert wrap("  Effective \n\t annual  ", 220, 20) == ["Effective annual"]


# ---- L2: boxes and the layout ------------------------------------------------------


def test_box_sizes():
    for kind, expected in (("definition", (136, 55)), ("example", (193, 78))):
        scene = build_scene({"nodes": [node("i", kind, "Interest")], "edges": []})
        assert size(shape(scene, "i")) == expected
    scene = build_scene({"nodes": [node("i", "definition", "Interest", order=1)], "edges": []})
    assert size(shape(scene, "i")) == (184, 55)


def test_main_line_runs_down_in_order():
    m = {
        "nodes": [node("a", order=3), node("b", order=1), node("c", order=2)],
        "edges": [edge("b", "c"), edge("c", "a")],
    }
    scene = build_scene(m)
    shapes = [shape(scene, i) for i in ("b", "c", "a")]
    assert [s["id"] for s in shapes] == ["node-1", "node-2", "node-3"]
    assert len({centre(s)[0] for s in shapes}) == 1
    for above, below in zip(shapes, shapes[1:]):
        assert below["y"] == approx(bottom(above) + 100)


def test_side_nodes_sit_beside_their_anchor():
    m = {
        "nodes": [
            node("a", order=1, label="Present value"),
            node("b", order=2, label="Rate"),
            node("x", "example"),
            node("y", "pitfall"),
            node("z", "method"),
            node("w"),
        ],
        "edges": [edge("x", "a"), edge("b", "y"), edge("y", "z")],
    }
    scene = build_scene(m)
    a, b, x, y, z, w = (shape(scene, i) for i in "abxyzw")
    column = max(a["width"], b["width"])
    assert centre(x)[1] == approx(centre(a)[1])
    assert x["x"] == approx(column + 200)
    assert y["x"] == approx(column + 200)
    assert z["x"] == approx(right(y) + 200)
    assert centre(y)[1] == approx(centre(b)[1]) and centre(z)[1] == approx(centre(b)[1])
    assert w["x"] == 0
    assert w["y"] == approx(max(bottom(b), bottom(y), bottom(z)) + 100)
    shapes = node_shapes(scene)
    assert not any(overlap(p, q) for n, p in enumerate(shapes) for q in shapes[n + 1:])


def test_view_without_a_main_line_is_a_grid():
    m = {"nodes": [node(i, label="Same") for i in ("p", "q", "r", "s")], "edges": []}
    scene = build_scene(m)
    p, q, r, s = (shape(scene, i) for i in "pqrs")
    assert p["y"] == q["y"] == r["y"] == 0
    assert q["x"] == approx(right(p) + 200)
    assert s["x"] == 0
    assert s["y"] == approx(bottom(p) + 100)


def test_view_draws_only_its_nodes():
    m = {
        "nodes": [node("a", order=1), node("b", order=2), node("c", "example")],
        "edges": [edge("a", "b"), edge("b", "c")],
        "views": [{"id": "v1", "nodes": ["a", "c"]}, {"id": "v2", "nodes": ["b", "c"]}],
    }
    scene = build_scene(m, "v1")
    assert sorted(s["customData"]["node"] for s in node_shapes(scene)) == ["a", "c"]
    assert arrows(scene) == []
    with pytest.raises(ValueError, match="unknown view: nope"):
        build_scene(m, "nope")


# ---- S1: kinds, key, colours ------------------------------------------------------


def test_kinds_are_told_apart_by_shape_and_stroke():
    m = {"nodes": [node(kind[:3], kind) for kind in KIND_STYLES], "edges": []}
    scene = build_scene(m)
    tuples = []
    for kind, expected in KIND_STYLES.items():
        found = style(shape(scene, kind[:3]))
        assert found == expected
        tuples.append(found)
    assert len({repr(t) for t in tuples}) == 5
    ink = load_palette()["ink"]
    assert all(e["strokeColor"] == ink for e in scene["elements"])


def test_key_nodes_get_the_highlight_fill(monkeypatch):
    m = {"nodes": [node("k", key=True), node("f", key=False), node("n")], "edges": [edge("k", "f")]}
    palette = load_palette()
    scene = build_scene(m)
    assert shape(scene, "k")["backgroundColor"] == palette["highlight"]
    assert shape(scene, "f")["backgroundColor"] == "transparent"
    assert shape(scene, "n")["backgroundColor"] == "transparent"
    assert scene["appState"]["viewBackgroundColor"] == palette["paper"]

    other = dict(palette, ink="#010203", highlight="#040506", paper="#070809")
    monkeypatch.setattr(drawing, "load_palette", lambda: other)
    scene = build_scene(m)
    assert all(e["strokeColor"] == "#010203" for e in scene["elements"])
    assert shape(scene, "k")["backgroundColor"] == "#040506"
    assert scene["appState"]["viewBackgroundColor"] == "#070809"


# ---- S2: edges ----------------------------------------------------------------------


def test_edges_are_bound_arrows_with_the_verb():
    m = {"nodes": [node("a", order=1), node("b", order=2)], "edges": [edge("b", "a", "grows faster than")]}
    scene = build_scene(m)
    a, b = shape(scene, "a"), shape(scene, "b")
    (arrow,) = arrows(scene)
    start = (arrow["x"], arrow["y"])
    end = (arrow["x"] + arrow["points"][-1][0], arrow["y"] + arrow["points"][-1][1])
    assert start == (approx(centre(b)[0]), approx(b["y"] - 6))
    assert end[1] == approx(bottom(a) + 6)
    assert arrow["startBinding"] == {"elementId": b["id"], "focus": 0, "gap": 6}
    assert arrow["endBinding"] == {"elementId": a["id"], "focus": 0, "gap": 6}
    assert {"type": "arrow", "id": arrow["id"]} in a["boundElements"]
    assert {"type": "arrow", "id": arrow["id"]} in b["boundElements"]
    assert (arrow["strokeWidth"], arrow["strokeStyle"], arrow["roundness"]) == (2, "solid", None)
    assert (arrow["startArrowhead"], arrow["endArrowhead"], arrow["lastCommittedPoint"]) == (None, "arrow", None)
    (label_link,) = arrow["boundElements"]
    label = by_id(scene, label_link["id"])
    assert label["originalText"] == "grows faster than"
    assert label["containerId"] == arrow["id"]
    assert label["fontSize"] == 16


def test_skip_edges_go_round_the_column():
    m = {
        "nodes": [node("p", order=1), node("q", order=2), node("r", order=3)],
        "edges": [edge("p", "q"), edge("p", "r", "leads to")],
    }
    scene = build_scene(m)
    skip = next(a for a in arrows(scene) if a["customData"] == {"from": "p", "to": "r"})
    assert len(skip["points"]) == 4
    absolute_x = [skip["x"] + px for px, _ in skip["points"]]
    assert absolute_x[1] == approx(-60) and absolute_x[2] == approx(-60)
    assert absolute_x[0] == approx(shape(scene, "p")["x"] - 6)
    assert absolute_x[3] == approx(shape(scene, "r")["x"] - 6)
    label = by_id(scene, skip["boundElements"][0]["id"])
    assert centre(label)[0] == approx(-60)
    plain = next(a for a in arrows(scene) if a["customData"] == {"from": "p", "to": "q"})
    assert len(plain["points"]) == 2


def test_self_edge_is_not_drawn():
    m = {"nodes": [node("a", order=1)], "edges": [edge("a", "a")]}
    scene = build_scene(m)
    assert arrows(scene) == []
    assert shape(scene, "a")["boundElements"] == [{"type": "text", "id": "node-1-text"}]


# ---- F1: the scene ------------------------------------------------------------------


def test_scene_is_a_complete_excalidraw_file():
    m = {
        "nodes": [
            node("a", order=1, key=True), node("b", "theorem", order=2), node("c", "method", order=3),
            node("x", "example"), node("y", "pitfall"), node("loose"),
        ],
        "edges": [edge("a", "b"), edge("a", "c", "leads to"), edge("x", "b", "illustrates"), edge("y", "c")],
    }
    scene = build_scene(m)
    assert set(scene) == {"type", "version", "source", "elements", "appState", "files"}
    assert (scene["type"], scene["version"], scene["source"], scene["files"]) == (
        "excalidraw", 2, "tutor-any-lecture", {})
    assert scene["appState"] == {"viewBackgroundColor": load_palette()["paper"], "gridSize": None}
    elements = scene["elements"]
    ids = [e["id"] for e in elements]
    assert len(set(ids)) == len(ids)
    assert all(re.fullmatch(r"[A-Za-z0-9-]+", i) for i in ids)
    assert [e["seed"] for e in elements] == list(range(1, len(elements) + 1))
    index = {e["id"]: e for e in elements}
    for e in elements:
        assert COMMON_KEYS <= set(e), e["id"]
        assert (e["version"], e["versionNonce"], e["updated"], e["angle"], e["groupIds"], e["frameId"],
                e["isDeleted"], e["link"], e["locked"]) == (1, 0, 1, 0, [], None, False, None, False)
        assert (e["fillStyle"], e["roughness"], e["opacity"]) == ("solid", 1, 100)
        if e["type"] == "text":
            assert TEXT_KEYS <= set(e)
            assert e["boundElements"] is None
            assert (e["fontFamily"], e["lineHeight"]) == (2, 1.25)
            assert e["text"].replace("\n", " ") == " ".join(e["originalText"].split())
            if e["containerId"] is not None:
                container = index[e["containerId"]]
                assert {"type": "text", "id": e["id"]} in container["boundElements"]
                assert container["boundElements"][0] == {"type": "text", "id": e["id"]}
        else:
            assert isinstance(e["boundElements"], list)
        if e["type"] == "arrow":
            assert ARROW_KEYS <= set(e)
            for binding in (e["startBinding"], e["endBinding"]):
                assert {"type": "arrow", "id": e["id"]} in index[binding["elementId"]]["boundElements"]
        for link in e["boundElements"] or []:
            target = index[link["id"]]
            if link["type"] == "text":
                assert target["containerId"] == e["id"]
            else:
                assert e["id"] in (target["startBinding"]["elementId"], target["endBinding"]["elementId"])
    # node shapes and their texts first, in layout order; then arrows and labels; then the legend
    groups = [i.split("-")[0] for i in ids]
    assert groups == sorted(groups, key=["node", "edge", "legend"].index)
    assert all(ids[n + 1] == ids[n] + "-text" for n in range(0, len(ids), 2))
    assert [shape(scene, i)["id"] for i in ("a", "b", "x", "c", "y", "loose")] == [
        f"node-{k}" for k in range(1, 7)]


# ---- the command (F2, C1, K2, S3) ----------------------------------------------------


def render_argv(unit, *extra):
    return ["map", "render", "--unit", str(unit), *extra]


def unit_at(tmp_path, week=1):
    return tmp_path / "课程 资料" / f"第{week}周"


def write_map(unit, m):
    unit.mkdir(parents=True, exist_ok=True)
    text = json.dumps(m, ensure_ascii=False, indent=2) + "\n"
    (unit / "map.json").write_text(text, encoding="utf-8", newline="\n")


def write_plan(unit, language):
    plan = json.loads(fx("units", "ok", "plan.json").read_text(encoding="utf-8"))
    plan["note_language"] = language
    text = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    (unit / "plan.json").write_text(text, encoding="utf-8", newline="\n")


def read_scene(path):
    return json.loads(path.read_text(encoding="utf-8"))


def map_with_edge(verb):
    return {
        "nodes": [
            {"id": "a", "label": "A", "type": "definition"},
            {"id": "b", "label": "B", "type": "method"},
        ],
        "edges": [{"from": "a", "to": "b", "verb": verb}],
    }


def map_with_views():
    m = map_with_edge("uses")
    m["nodes"][0]["order"] = 1
    m["nodes"].append(node("c", "example"))
    m["edges"].append(edge("b", "c", "shows"))
    m["views"] = [{"id": "a", "nodes": ["a", "b"]}, {"id": "b", "nodes": ["b", "c"]}]
    return m


DUPLICATE_ORDER = {"nodes": [node("a", order=1), node("b", order=1)], "edges": [edge("a", "b")]}


@pytest.mark.parametrize("m", [{"nodes": 5}, map_with_edge(""), DUPLICATE_ORDER],
                         ids=["schema", "no-verb", "duplicate-order"])
def test_render_checks_the_map_like_mermaid(tmp_path, capsys, m):
    drawn, exported = unit_at(tmp_path, 1), unit_at(tmp_path, 2)
    write_map(drawn, m)
    write_map(exported, m)
    capsys.readouterr()
    render_code = main(render_argv(drawn))
    render = capsys.readouterr()
    mermaid_code = main(["map", "mermaid", "--unit", str(exported)])
    mermaid = capsys.readouterr()
    assert render_code == mermaid_code == 1
    assert render.err == mermaid.err and render.err
    assert render.out == mermaid.out == ""
    for unit in (drawn, exported):
        assert list(unit.glob("*.excalidraw*")) == [] and list(unit.glob("*.mmd")) == []


def test_legend_names_the_five_kinds(tmp_path, capsys):
    m = {"nodes": [node("a", order=1), node("x", "example", label="A long example label to wrap")],
         "edges": [edge("x", "a")]}

    def legend_of(unit):
        assert main(render_argv(unit, "--force")) == 0
        return legend(read_scene(unit / "map.excalidraw"))

    unit = unit_at(tmp_path)
    write_map(unit, m)
    english = ["definition", "theorem", "method", "example", "pitfall"]
    items = legend_of(unit)
    assert [e["text"] for e in items if e["type"] == "text"] == english
    write_plan(unit, "zh")
    assert [e["text"] for e in legend_of(unit) if e["type"] == "text"] == ["定义", "定理", "方法", "例子", "易错点"]
    write_plan(unit, "ja")
    assert [e["text"] for e in legend_of(unit) if e["type"] == "text"] == english
    (unit / "plan.json").unlink()
    m["nodes"][0]["key"] = True
    write_map(unit, m)
    items = legend_of(unit)
    assert [e["text"] for e in items if e["type"] == "text"] == [*english, "key idea"]
    shapes = [e for e in items if e["type"] != "text"]
    assert [style(e) for e in shapes] == [*KIND_STYLES.values(), ("rectangle", 2, "solid", None)]
    assert shapes[-1]["backgroundColor"] == load_palette()["highlight"]
    assert all(e["backgroundColor"] == "transparent" for e in shapes[:-1])
    assert all(e["boundElements"] == [] for e in shapes)
    texts = [e for e in items if e["type"] == "text"]
    assert all((e["textAlign"], e["verticalAlign"], e["containerId"], e["fontSize"]) == ("left", "top", None, 16)
               for e in texts)
    for sample, text in zip(shapes, texts):
        assert (sample["width"], sample["height"]) == (48, 32)
        assert text["x"] == approx(right(sample) + 12) and text["y"] == approx(sample["y"] + 6)
    for text, sample in zip(texts, shapes[1:]):
        assert sample["x"] == approx(right(text) + 40)
    scene = read_scene(unit / "map.excalidraw")
    lowest = max(bottom(e) for e in node_shapes(scene))
    assert all(e["y"] == approx(lowest + 100) for e in shapes)
    leftmost = min([e["x"] for e in node_shapes(scene)]
                   + [a["x"] + px for a in arrows(scene) for px, _ in a["points"]])
    assert shapes[0]["x"] == approx(leftmost)


def test_malformed_plan_ends_in_one_line(tmp_path, capsys):
    unit = unit_at(tmp_path)
    write_map(unit, map_with_edge("uses"))
    (unit / "plan.json").write_text("{", encoding="utf-8", newline="\n")
    capsys.readouterr()
    assert main(render_argv(unit)) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("plan.json") and captured.err.count("\n") == 1
    assert list(unit.glob("*.excalidraw*")) == []


def test_drawing_is_deterministic(tmp_path):
    m = map_with_views()
    m["nodes"][1]["key"] = True
    del m["views"]
    first, second = unit_at(tmp_path, 1), unit_at(tmp_path, 2)
    for unit in (first, second):
        write_map(unit, m)
        assert main(render_argv(unit)) == 0
    data = (first / "map.excalidraw").read_bytes()
    assert data == (second / "map.excalidraw").read_bytes()
    assert data.decode("utf-8") == json.dumps(json.loads(data), ensure_ascii=False, indent=2) + "\n"


def test_obsidian_form_wraps_the_same_scene(tmp_path):
    m = map_with_views()
    del m["views"]
    m["nodes"][1]["label"] = "实际年利率"
    plain, vault = unit_at(tmp_path, 1), unit_at(tmp_path, 2)
    write_map(plain, m)
    write_map(vault, m)
    assert main(render_argv(plain)) == 0
    assert main(render_argv(vault, "--obsidian")) == 0
    assert (vault / "map.excalidraw.md").exists() and not (vault / "map.excalidraw").exists()
    text = (vault / "map.excalidraw.md").read_text(encoding="utf-8")
    assert text.startswith("---\n\nexcalidraw-plugin: parsed\ntags: [excalidraw]\n\n---\n")
    assert text.endswith("%%\n")
    scene = read_scene(plain / "map.excalidraw")
    texts = [e for e in scene["elements"] if e["type"] == "text"]
    listing = "".join(f"{e['originalText']} ^{e['id']}\n\n" for e in texts)
    assert text.split("## Text Elements\n", 1)[1].startswith(listing)
    body = text.split("```json\n", 1)[1].split("\n```\n%%", 1)[0]
    assert json.loads(body) == scene


def test_cli_map_render_writes_one_file_per_view(tmp_path, capsys):
    unit = unit_at(tmp_path)
    write_map(unit, map_with_views())
    capsys.readouterr()
    assert main(render_argv(unit)) == 0
    expected = [unit / "map-a.excalidraw", unit / "map-b.excalidraw"]
    out = json.loads(capsys.readouterr().out)
    assert out == {"paths": [str(p) for p in expected]}
    assert all(p.is_absolute() and p.is_file() for p in expected)
    assert sorted(s["customData"]["node"] for s in node_shapes(read_scene(expected[1]))) == ["b", "c"]
    assert not (unit / "map.excalidraw").exists()
    assert main(render_argv(unit, "--view", "a")) == 0
    assert json.loads(capsys.readouterr().out) == {"path": str(unit / "map.excalidraw")}
    plain = unit_at(tmp_path, 2)
    write_map(plain, map_with_edge("uses"))
    assert main(render_argv(plain)) == 0
    assert json.loads(capsys.readouterr().out) == {"path": str(plain / "map.excalidraw")}
    assert sorted(p.name for p in plain.glob("*.excalidraw*")) == ["map.excalidraw"]


def test_cli_map_render_unknown_view_exits_2(tmp_path, capsys):
    unit = unit_at(tmp_path)
    write_map(unit, map_with_views())
    capsys.readouterr()
    assert main(render_argv(unit, "--view", "nope")) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "unknown view: nope\n"
    assert list(unit.glob("*.excalidraw*")) == []


def test_cli_map_render_view_id_must_be_a_file_name(tmp_path, capsys):
    unit = unit_at(tmp_path)
    m = map_with_views()
    m["views"].append({"id": "a/b", "nodes": ["a"]})
    write_map(unit, m)
    capsys.readouterr()
    assert main(render_argv(unit)) == 1
    render = capsys.readouterr()
    assert main(["map", "mermaid", "--unit", str(unit)]) == 1
    assert render.err == capsys.readouterr().err and "a/b" in render.err and render.err.count("\n") == 1
    assert list(unit.glob("*.excalidraw*")) == []


def test_cli_map_render_keeps_an_edited_drawing(tmp_path, capsys):
    unit = unit_at(tmp_path)
    write_map(unit, map_with_views())
    assert main(render_argv(unit)) == 0
    edited = unit / "map-b.excalidraw"
    edited.write_text("{}\n", encoding="utf-8", newline="\n")
    (unit / "map-a.excalidraw").unlink()
    capsys.readouterr()
    assert main(render_argv(unit)) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"{edited} already exists; rerun with --force to replace it\n"
    assert edited.read_bytes() == b"{}\n"
    assert not (unit / "map-a.excalidraw").exists()  # every target is checked before the first write
    assert main(render_argv(unit, "--force")) == 0
    assert read_scene(edited)["type"] == "excalidraw"


# ---- D1: the documents ---------------------------------------------------------------


def test_documents_describe_map_render():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    skill = root / "skills" / "tutor-any-lecture"

    def read(*parts):
        return skill.joinpath(*parts).read_text(encoding="utf-8")

    text = read("SKILL.md")
    assert "`tutor-any-lecture map render --unit DIR`" in text
    assert "--obsidian" in text and "and the drawings of map render" in text
    assert "excalidraw-concept-map" not in text
    text = read("references", "teaching.md")
    assert '"key"?' in text and "map-<view>.excalidraw" in text and "--force" in text
    text = read("references", "gate.md")
    assert "for `map mermaid` or `map render`" in text and "an `order` used twice" in text
    assert "map-<view>.excalidraw" in read("references", "output-targets", "markdown.md")
    assert "tutor-any-lecture map render --unit DIR --obsidian" in read("references", "output-targets", "obsidian.md")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    newest = changelog.split("\n## ", 2)[1]
    assert "editable Excalidraw drawings" in newest
