import json

import pytest

from fixtures.make_pdf import make_pdf
from tutor_any_lecture.acquire.importer import import_transcript
from tutor_any_lecture.cli import main
from tutor_any_lecture.slides import Page, extract_pdf
from tutor_any_lecture.suspects import flag_suspects
from tutor_any_lecture.textstats import cjk_runs
from tutor_any_lecture.transcript import Segment, Transcript
from tutor_any_lecture.unit import UnitPaths

SLIDE = "A martingale has constant expectation"
VTT = "WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nThe martingail property holds\n"


def make_unit(tmp_path):
    unit = tmp_path / "unit"
    vtt = tmp_path / "lecture.vtt"
    vtt.write_text(VTT, encoding="utf-8", newline="\n")
    import_transcript(vtt, unit, None, False)
    extract_pdf(make_pdf(tmp_path, [SLIDE + "\n1/1"]), unit)
    return unit


def test_flags_near_miss():
    transcript = Transcript([Segment(12.0, 15.0, "the martingail property holds")], "en")
    found = flag_suspects(transcript, [Page(1, None, SLIDE)], "en")
    assert len(found) == 1
    assert found[0]["time"] == 12.0
    assert found[0]["heard"] == "martingail" and found[0]["nearest"] == "martingale"
    assert found[0]["ratio"] == pytest.approx(0.9)



def test_inflections_of_a_slide_term_are_not_suspects():
    transcript = Transcript(
        [Segment(0.0, 4.0, "the payments were includes"), Segment(5.0, 8.0, "a schedual of payment")], "en"
    )
    found = flag_suspects(transcript, [Page(1, None, "Annuity payment schedule\nincluded")], "en")
    assert [s["heard"] for s in found] == ["schedual"]


def test_no_slide_terms_no_suspects():
    transcript = Transcript([Segment(0.0, 2.0, "the martingail property")], None)
    assert flag_suspects(transcript, [Page(1, None, "a b c")], "") == []
    assert flag_suspects(transcript, [], "") == []


def test_ignores_diacritics_only():
    transcript = Transcript([Segment(0.0, 4.0, "by the Poincare inequality we get a bound")], "en")
    assert flag_suspects(transcript, [Page(1, None, "The Poincaré inequality")], "en") == []


def test_one_entry_per_segment_and_token():
    transcript = Transcript(
        [Segment(1.0, 4.0, "The martingail and the Martingail"), Segment(5.0, 6.0, "martingail again")],
        None,
    )
    found = flag_suspects(transcript, [Page(1, None, SLIDE)], "")
    assert [(s["time"], s["heard"]) for s in found] == [(1.0, "martingail"), (5.0, "martingail")]


def test_transcript_unchanged(tmp_path):
    unit = make_unit(tmp_path)
    paths = UnitPaths(unit)
    before = paths.transcript.read_bytes()
    assert main(["slides", "suspects", "--unit", str(unit)]) == 0
    assert paths.transcript.read_bytes() == before
    found = json.loads(paths.suspects.read_text(encoding="utf-8"))
    assert [(s["time"], s["heard"], s["nearest"]) for s in found] == [(1.0, "martingail", "martingale")]


def test_cli_suspects_needs_transcript(tmp_path):
    assert main(["slides", "suspects", "--unit", str(tmp_path)]) == 1
    assert not UnitPaths(tmp_path).suspects.exists()


def test_cjk_punctuation_ends_a_run():
    assert cjk_runs("ブラック・ショールズ") == [("ブラック", "katakana"), ("ショールズ", "katakana")]
    assert cjk_runs("ブラック゠ショールズ") == [("ブラック", "katakana"), ("ショールズ", "katakana")]


ZH_PAGE = Page(1, "1", "随机微积分\n布朗运动、伊藤引理\n期权定价\n1/1")
ZH_SEGMENTS = [(10.0, 14.0, "今天讲布朗运动和伊藤引理"), (95.0, 100.0, "然后用它们来推导弃权定价的公式")]
ZH_SUSPECT = {"time": 95.0, "heard": "弃权定价", "nearest": "期权定价", "ratio": 0.75}


def test_chinese_mishearing_is_flagged():
    # 期权 (option) and 弃权 (abstain) are both read qiquan; the slide says option pricing.
    transcript = Transcript([Segment(*s) for s in ZH_SEGMENTS], "zh")
    assert flag_suspects(transcript, [ZH_PAGE], "zh") == [ZH_SUSPECT]


def test_japanese_and_korean_mishearings_are_flagged():
    # 確率 and 確立 are both read kakuritsu.
    ja = Transcript([Segment(3.0, 6.0, "確立過程を定義します")], "ja")
    assert flag_suspects(ja, [Page(1, None, "確率過程の定義")], "ja") == [
        {"time": 3.0, "heard": "確立過程", "nearest": "確率過程", "ratio": 0.75}]
    ko = Transcript([Segment(7.0, 9.0, "확율과정은 시간에 따라 변한다")], "ko")
    assert flag_suspects(ko, [Page(1, None, "확률과정")], "ko") == [
        {"time": 7.0, "heard": "확율과정", "nearest": "확률과정", "ratio": 0.75}]


def test_cjk_terms_said_right_are_not_suspects():
    transcript = Transcript([Segment(0.0, 5.0, "我们讲布朗运动，然后讲伊藤引理和期权定价")], "zh")
    assert flag_suspects(transcript, [ZH_PAGE], "zh") == []


def test_short_cjk_terms_are_never_compared():
    transcript = Transcript([Segment(0.0, 3.0, "方叉和期望")], "zh")
    assert flag_suspects(transcript, [Page(1, None, "方差 期望")], "zh") == []


def test_cli_suspects_on_a_chinese_deck(tmp_path, capsys):
    unit = tmp_path / "课程 资料" / "第1周"
    vtt = tmp_path / "讲座.vtt"
    vtt.write_text(
        "WEBVTT\n\n00:00:10.000 --> 00:00:14.000\n" + ZH_SEGMENTS[0][2]
        + "\n\n00:01:35.000 --> 00:01:40.000\n" + ZH_SEGMENTS[1][2] + "\n",
        encoding="utf-8", newline="\n",
    )
    import_transcript(vtt, unit, None, False)
    paths = UnitPaths(unit)
    paths.pages.parent.mkdir(parents=True, exist_ok=True)
    pages = [{"n": ZH_PAGE.n, "label": ZH_PAGE.label, "text": ZH_PAGE.text, "image": None}]
    paths.pages.write_text(json.dumps(pages, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    before = paths.transcript.read_bytes()
    capsys.readouterr()
    assert main(["slides", "suspects", "--unit", str(unit)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok" and out["suspects"] == 1
    assert json.loads(paths.suspects.read_text(encoding="utf-8")) == [ZH_SUSPECT]
    assert paths.transcript.read_bytes() == before
