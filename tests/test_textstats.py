import re
import unicodedata
from pathlib import Path

import pytest

from tutor_any_lecture.textstats import (
    CJK_CLASS,
    CJK_RE,
    char_jaccard,
    cjk_runs,
    cjk_script,
    containment,
    join_lines,
    ngrams,
    units,
    unsegmented,
    unspaced,
)

# synthetic: "compound interest is interest that comes from interest"
THAI = "ดอกเบี้ยทบต้นคือดอกเบี้ยที่เกิดจากดอกเบี้ย"


def test_units_cjk_vs_en():
    assert units("离散复利 compound", "zh") == 4 and units("compound interest grows", "en") == 3


def test_units_excludes_latex_code_urls():
    # counted words: The, rate, is, 5, at, b
    assert units("The rate $r$ is 5% at https://example.org/a b `x = 1`", "en") == 6


def test_ngrams_and_containment():
    assert ngrams("Compound interest grows fast.", "en") == {"compound interest", "interest grows", "grows fast"}
    assert ngrams("离散复利", "zh") == {"离散复", "散复利"}
    assert containment("Interest grows", "Compound interest grows fast.", "en") == 1.0
    # A = {离散复, 散复利, 复利很, 利很快}; two of the four are in B
    assert containment("离散复利很快", "离散复利", "zh") == 0.5


def test_char_jaccard_keeps_punctuation():
    # 19 and 20 distinct 3-grams, 18 shared, 21 in the union
    assert char_jaccard("What is a martingale?", "What is a martingale ?") == pytest.approx(18 / 21)



def test_word_jaccard_is_gone():
    from tutor_any_lecture import textstats

    assert not hasattr(textstats, "jaccard")


def test_no_cross_module_private_imports():
    package = Path(__file__).resolve().parents[1] / "src" / "tutor_any_lecture"
    files = sorted(package.rglob("*.py"))
    assert files
    pattern = re.compile(r"from \.[\w.]* import .*\b_[a-z]")
    offenders = [
        f"{f.name}:{n}"
        for f in files
        for n, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1)
        if pattern.search(line)
    ]
    assert offenders == []


@pytest.mark.parametrize("text, expected", [
    (THAI, True),
    ("ດອກເບ້ຍທົບຕົ້ນ", True),
    ("ការប្រាក់សមាស", True),
    ("အတိုးနှုန်း", True),
    ("चक्रवृद्धि ब्याज", True),
    ("Compound interest", False),
    ("Die Zinsen für Ärzte", False),
    ("сложные проценты", False),
    ("ανατοκισμός", False),
    ("الفائدة المركبة", False),
    ("ריבית דריבית", False),
    ("复利就是利滚利", False),
    ("人々は複利を学ぶ", False),
    ("복리 이자", False),
    (unicodedata.normalize("NFD", "café crème"), False),
    ("", False),
    ("Compound interest, or ดอก in Thai", False),
])
def test_scripts_the_checks_cannot_split(text, expected):
    assert unsegmented(text) is expected


@pytest.mark.parametrize("ch, script", [
    ("布", "han"),
    ("\U0002000B", "han"),  # 𠀋, beyond U+FFFF
    ("﨑", "han"),  # 﨑, a compatibility ideograph
    ("々", "han"),
    ("〇", "han"),
    ("ひ", "hiragana"),
    ("ー", "katakana"),
    ("ｶ", "katakana"),  # ｶ, halfwidth
    ("한", "hangul"),
    ("・", None),
    ("、", None),
    ("A", None),
    ("1", None),
])
def test_one_table_of_cjk_ranges(ch, script):
    assert cjk_script(ch) == script
    assert CJK_RE.pattern == "[" + CJK_CLASS + "]"
    assert units("人々は〇", "ja") == 4
    assert units("𠀋﨑", "zh") == 2


def test_unspaced_scripts():
    assert all(unspaced(ch) for ch in ("漢", "か", "カ", "，", "。", "３"))
    assert not any(unspaced(ch) for ch in ("한", "A", "1", " "))


def test_cjk_ranges_are_defined_once():
    package = Path(__file__).resolve().parents[1] / "src" / "tutor_any_lecture"
    files = [f for f in sorted(package.rglob("*.py")) if f.name != "textstats.py"]
    assert files
    pattern = re.compile(r"(?i)0x0*(3040|3400|4e00|ac00)\b|\\u(3040|3400|4e00|ac00)|[぀㐀一가]-")
    offenders = [
        f"{f.name}:{n}"
        for f in files
        for n, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1)
        if pattern.search(line)
    ]
    assert offenders == []


def test_cjk_runs_split_at_script_changes():
    assert cjk_runs("確率過程の定義 GBM2") == [("確率過程", "han"), ("の", "hiragana"), ("定義", "han"), ("GBM", None)]
    assert cjk_runs("확률과정은 시간에") == [("확률과정은", "hangul"), ("시간에", "hangul")]


def test_korean_is_counted_in_syllables():
    assert units("확률과정은 시간에 따라", "ko") == 10
    assert cjk_script("한") == "hangul"
    assert unspaced("한") is False


def test_join_lines():
    assert join_lines(["布朗", " 运动 ", "", "GBM", "확률", "과정"]) == "布朗运动 GBM 확률 과정"
    assert join_lines(["利率是３", "％"]) == "利率是３％"
