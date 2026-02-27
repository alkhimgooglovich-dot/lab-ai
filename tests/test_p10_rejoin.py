"""
Tests for P10 — line rejoining for fragmented pypdf output.

Uses REAL text from Gemotest biochemistry PDF.
"""

import sys, re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from parsers.universal_extractor import (
    universal_extract,
    _rejoin_fragmented_lines,
    _is_discardable_fragment,
)


class TestDiscardableFragment:
    """Test identification of discardable line fragments."""

    def test_service_code(self):
        assert _is_discardable_fragment("A09.05.010")

    def test_service_code_extended(self):
        assert _is_discardable_fragment("A09.05.022.002")

    def test_multi_service_code(self):
        assert _is_discardable_fragment("A09.05.034, A09.05.031, A09.05.030")

    def test_prikaz(self):
        assert _is_discardable_fragment("(Приказ МЗ РФ")

    def test_mz_rf(self):
        assert _is_discardable_fragment("МЗ РФ")

    def test_804n(self):
        assert _is_discardable_fragment("804н)")

    def test_number_sign(self):
        assert _is_discardable_fragment("№")

    def test_biomaterial_venous(self):
        assert _is_discardable_fragment("(венозная кровь)")

    def test_biomaterial_serum(self):
        assert _is_discardable_fragment("(сыворотка крови)")

    def test_date(self):
        assert _is_discardable_fragment("Дата исследования: 18.02.2026;")

    def test_clinical_recs(self):
        assert _is_discardable_fragment(
            "Клинические рекомендации 2021 (Российская ассоциация эндокринологов):"
        )

    def test_scale(self):
        assert _is_discardable_fragment("Нормальный уровень       < 1,70")

    def test_diagnostic(self):
        assert _is_discardable_fragment(
            "6.5% и более - диагностический критерий сахарного диабета"
        )

    def test_methodology(self):
        assert _is_discardable_fragment(
            "Исследование проведено методом сертифицированным NGSP и IFCC"
        )

    def test_real_name_NOT_discardable(self):
        assert not _is_discardable_fragment("Калий")

    def test_value_NOT_discardable(self):
        assert not _is_discardable_fragment("3.7")

    def test_unit_NOT_discardable(self):
        assert not _is_discardable_fragment("ммоль/л")

    def test_ref_NOT_discardable(self):
        assert not _is_discardable_fragment("3.5 - 5.1")


class TestRejoinFragmentedLines:
    """Test rejoining of fragmented pypdf output."""

    def test_potassium(self):
        lines = [
            "Калий", "(K+)", "(сыворотка крови)", "  ", " ",
            "3.7", "ммоль/л", "3.5 - 5.1",
        ]
        rejoined = _rejoin_fragmented_lines(lines)
        joined = " ".join(rejoined)
        assert "Калий" in joined
        assert "3.7" in joined
        assert "3.5 - 5.1" in joined or "3.5" in joined

    def test_sodium(self):
        lines = [
            "Натрий", "(Na+)", "(сыворотка крови)", "  ", " ",
            "142.5", "ммоль/л", "136 - 145",
        ]
        rejoined = _rejoin_fragmented_lines(lines)
        joined = " ".join(rejoined)
        assert "Натрий" in joined
        assert "142.5" in joined

    def test_ldh(self):
        lines = [
            "Лактатдегидрогеназа (ЛДГ) (венозная кровь)", "  ",
            "A09.05.039", " ", "(Приказ", "МЗ РФ", "№", "804н)",
            "164", "Ед/л", "135 - 225",
        ]
        rejoined = _rejoin_fragmented_lines(lines)
        joined = " ".join(rejoined)
        assert "164" in joined
        assert "Лактатдегидрогеназа" in joined or "ЛДГ" in joined

    def test_hba1c(self):
        lines = [
            "Гликированный гемоглобин", "  ",
            "A09.05.083", " ", "(Приказ МЗ РФ", "№", "804н)",
            "5.0", "%", "Смотри текст",
        ]
        rejoined = _rejoin_fragmented_lines(lines)
        joined = " ".join(rejoined)
        assert "5.0" in joined
        assert "гемоглобин" in joined.lower()

    def test_simple_glucose(self):
        lines = [
            "Глюкоза", "  ", "A09.05.023", " ", "(Приказ МЗ РФ", "№", "804н)",
            "5.27", "ммоль/л", "4.11 - 6.1",
        ]
        rejoined = _rejoin_fragmented_lines(lines)
        joined = " ".join(rejoined)
        assert "Глюкоза" in joined
        assert "5.27" in joined

    def test_alt_with_flag(self):
        lines = [
            "Аланинаминотрансфераза (АЛТ) (венозная кровь)", "  ",
            "A09.05.042", " ", "(Приказ МЗ РФ", "№", "804н)",
            "92.3+", "Ед/л", "< 41",
        ]
        rejoined = _rejoin_fragmented_lines(lines)
        joined = " ".join(rejoined)
        assert "92.3" in joined
        assert "АЛТ" in joined

    def test_bilirubin_total(self):
        lines = ["Билирубин общий", "  ", " ", "12.8", "мкмоль/л", "< 21"]
        rejoined = _rejoin_fragmented_lines(lines)
        joined = " ".join(rejoined)
        assert "Билирубин общий" in joined
        assert "12.8" in joined

    def test_single_line_passthrough(self):
        """Single-line format (Helix) should pass through unchanged."""
        lines = ["Калий (K+) 3.7 ммоль/л 3.5 - 5.1"]
        rejoined = _rejoin_fragmented_lines(lines)
        assert len(rejoined) == 1
        assert "Калий" in rejoined[0]
        assert "3.7" in rejoined[0]

    def test_no_garbage_in_output(self):
        lines = [
            "Калий", "(K+)", "(сыворотка крови)", "",
            "A09.05.034", "(Приказ", "МЗ РФ", "№", "804н)",
            "3.7", "ммоль/л", "3.5 - 5.1",
        ]
        rejoined = _rejoin_fragmented_lines(lines)
        joined = " ".join(rejoined).lower()
        assert "приказ" not in joined
        assert "a09." not in joined
        assert "мз рф" not in joined
        assert "сыворотка" not in joined


# ─── REAL pypdf output from Gemotest page 2 ───

REAL_PYPDF_PAGE2 = """\
Биохимия 21
Гликированный гемоглобин
  
A09.05.083
 
(Приказ МЗ РФ 
№ 
804н)
5.0
%
Смотри текст
Дата исследования: 18.02.2026; 
Клинические рекомендации 2021 (Российское ассоциация эндокринологов):
до 6.0% включительно  (в соответствии с DCCT) - нормальное содержание HbA1c
6.0-6.4% - рекомендуется консультация эндокринолога для исключения нарушений углеводного обмена
6.5% и более - диагностический критерий сахарного диабета
Исследование проведено методом сертифицированным NGSP и IFCC
Аланинаминотрансфераза (АЛТ) (венозная кровь)
  
A09.05.042
 
(Приказ МЗ РФ 
№ 
804н)
92.3+
Ед/л
< 41
Дата исследования: 18.02.2026; 
Аспартатаминотрансфераза (АСТ) (венозная кровь)
  
A09.05.041
 
(Приказ МЗ РФ 
№ 
804н)
56.2+
Ед/л
< 40
Дата исследования: 18.02.2026; 
Амилаза (венозная кровь)
  
A09.05.045
 
(Приказ МЗ РФ 
№ 
804н)
43
Ед/л
< 100
Дата исследования: 18.02.2026; 
Гамма-ГТ (венозная кровь)
  
A09.05.044
 
(Приказ МЗ РФ 
№ 
804н)
21
Ед/л
< 60
Дата исследования: 18.02.2026; 
Лактатдегидрогеназа (ЛДГ) (венозная кровь)
  
A09.05.039
 
(Приказ 
МЗ РФ 
№ 
804н)
164
Ед/л
135 - 225
Дата исследования: 18.02.2026; 
Фосфатаза щелочная (венозная кровь)
  
A09.05.046
 
(Приказ МЗ РФ 
№ 
804н)
94
Ед/л
40 - 129
Дата исследования: 18.02.2026; 
Билирубин непрямой: билирубин общий, билирубин прямой (венозная кровь)
  
A09.05.022.002
 
(Приказ МЗ РФ 
№ 
804н)
Дата исследования: 18.02.2026; 
Билирубин общий
  
 
12.8
мкмоль/л
< 21
Билирубин прямой
  
 
4.8
мкмоль/л
< 5
Билирубин непрямой
  
 
8.0
мкмоль/л
Смотри текст
Расчетный показатель. Нормальные значения - 75% концентрации Общего билирубина (Исключение - физиологическая желтуха новорожденных)
Кальций общий (кровь, фотометрия)
  
A09.05.032
 
(Приказ МЗ РФ 
№ 
804н)
2.42
ммоль/л
2.2 - 2.65
Дата исследования: 18.02.2026; 
Электролиты: калий (К+), натрий (Na+), хлориды
  
A09.05.034, A09.05.031, A09.05.030
 
(Приказ МЗ РФ 
№ 
804н)
Дата исследования: 18.02.2026; 
Калий 
(K+) 
(сыворотка крови)
  
 
3.7
ммоль/л
3.5 - 5.1
Натрий 
(Na+) 
(сыворотка крови)
  
 
142.5
ммоль/л
136 - 145
Хлориды
  
 
103
ммоль/л
98 - 106
Сывороточное железо
  
A09.05.007
 
(Приказ МЗ РФ 
№ 
804н)
52.8+
мкмоль/л
5.8 - 34.5
Дата исследования: 18.02.2026;"""


class TestRealPypdfPage2:
    """Integration test with REAL pypdf output from Gemotest page 2."""

    def test_hba1c(self):
        c = universal_extract(REAL_PYPDF_PAGE2)
        # :g format turns 5.0 → "5", so check for tab-delimited value
        assert "\t5\t" in (c or "") or "5.0" in (c or ""), f"HbA1c not found in:\n{c}"

    def test_alt(self):
        c = universal_extract(REAL_PYPDF_PAGE2)
        assert "92.3" in (c or ""), f"ALT not found in:\n{c}"

    def test_ast(self):
        c = universal_extract(REAL_PYPDF_PAGE2)
        assert "56.2" in (c or ""), f"AST not found in:\n{c}"

    def test_ldh(self):
        c = universal_extract(REAL_PYPDF_PAGE2)
        assert "164" in (c or ""), f"LDH not found in:\n{c}"

    def test_potassium(self):
        c = universal_extract(REAL_PYPDF_PAGE2)
        assert "3.7" in (c or ""), f"K+ not found in:\n{c}"

    def test_sodium(self):
        c = universal_extract(REAL_PYPDF_PAGE2)
        assert "142.5" in (c or ""), f"Na+ not found in:\n{c}"

    def test_iron(self):
        c = universal_extract(REAL_PYPDF_PAGE2)
        assert "52.8" in (c or ""), f"Iron not found in:\n{c}"

    def test_bilirubin_total(self):
        c = universal_extract(REAL_PYPDF_PAGE2)
        assert "12.8" in (c or ""), f"Bilirubin total not found in:\n{c}"

    def test_calcium(self):
        c = universal_extract(REAL_PYPDF_PAGE2)
        assert "2.42" in (c or ""), f"Calcium not found in:\n{c}"

    def test_amylase(self):
        c = universal_extract(REAL_PYPDF_PAGE2)
        assert "43" in (c or ""), f"Amylase not found in:\n{c}"

    def test_gamma_gt(self):
        c = universal_extract(REAL_PYPDF_PAGE2)
        assert "21" in (c or ""), f"Gamma-GT not found in:\n{c}"

    def test_alkaline_phosphatase(self):
        c = universal_extract(REAL_PYPDF_PAGE2)
        assert "94" in (c or ""), f"ALP not found in:\n{c}"

    def test_chlorides(self):
        c = universal_extract(REAL_PYPDF_PAGE2)
        assert "103" in (c or ""), f"Chlorides not found in:\n{c}"

    def test_no_garbage_names(self):
        c = universal_extract(REAL_PYPDF_PAGE2)
        for line in (c or "").splitlines():
            name = line.split("\t")[0].lower() if "\t" in line else line.lower()
            assert "приказ" not in name, f"Garbage in name: {line}"
            assert "a09." not in name, f"Service code in name: {line}"
            assert "мз рф" not in name, f"МЗ РФ in name: {line}"
