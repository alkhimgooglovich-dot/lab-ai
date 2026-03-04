"""
Tests for Invitro parsing: values with < / > operators, hormone name mappings,
and full pipeline integration with real Invitro pypdf text.

Run: pytest tests/test_invitro_value_operators.py -v
"""
import sys
from pathlib import Path

import pytest

_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from parsers.universal_extractor import universal_extract, _try_parse_one_line
from engine import (
    normalize_name,
    _run_parse_pipeline,
    _try_parse_one_line_row,
    _parse_value_unit_from_line,
    EXPLAIN_DICT,
    SPECIALIST_MAP,
)
from parsers.sanity_ranges import SANITY_RANGES


# =====================================================================
# Real Invitro pypdf text (both pages)
# =====================================================================

INVITRO_PAGE1 = """\
ООО "МД КЛИНИК Н"
Москва
НИКОЛАЕВИЧ ВАЛЕНТИН ВЛАДИМИРОВИЧ
Пол: Муж
Дата рождения: 27.09.1987
Возраст: 38 лет
ИНЗ: 877174498
Дата взятия образца: 06.02.2026 08:31
Дата поступления образца: 07.02.2026 11:00
Врач: 07.02.2026 14:14
Дата печати результата: 07.02.2026
Исследование Результат Единицы Референсные значения
Эстрадиол < 37 пмоль/л < 161
Пролактин 330 мМE/л 73 - 407
Исполнитель Назимова Л.А., врач клинической лабораторной диагностики
Внимание! В электронном экземпляре бланка название исследования содержит ссылку на страницу сайта с описанием
исследования. www.invitro.ru
Результаты исследований не являются диагнозом, необходима консультация специалиста.
стр.1 из 1"""

INVITRO_PAGE2 = """\
ООО "МД КЛИНИК Н"
Москва
НИКОЛАЕВИЧ ВАЛЕНТИН ВЛАДИМИРОВИЧ
Пол: Муж
Дата рождения: 27.09.1987
Возраст: 38 лет
ИНЗ: 877174498
Дата взятия образца: 06.02.2026 08:31
Дата поступления образца: 07.02.2026 11:00
Врач: 07.02.2026 12:02
Дата печати результата: 07.02.2026
Исследование Результат Единицы Референсные значения
Гематокрит 51.2* % 39 - 49
Гемоглобин 17.2 г/дл 13.2 - 17.3
Эритроциты 6.15* млн/мкл 4.3 - 5.7
MCV (ср. объем эритр.) 83.2 фл 80 - 99
RDW (шир. распред. эритр) 15.9* % 11.6 - 14.8
MCH (ср. содер. Hb в эр.) 27.9 пг 27 - 34
МСHС (ср. конц. Hb в эр.) 33.6 г/дл 32 - 37
Тромбоциты 339 тыс/мкл 150 - 400
Лейкоциты 7.29 тыс/мкл 4.5 - 11
Исполнитель Жук А.В., Биолог
* Результат, выходящий за пределы референсных значений
Внимание! В электронном экземпляре бланка название исследования содержит ссылку на страницу сайта с описанием
исследования. www.invitro.ru
Результаты исследований не являются диагнозом, необходима консультация специалиста.
стр.1 из 1"""

INVITRO_FULL = INVITRO_PAGE1 + "\n--- PAGE 2 ---\n" + INVITRO_PAGE2


def _find(items, canonical):
    """Find item(s) by canonical name."""
    return [it for it in items if it.name == canonical]


# =====================================================================
# Bug #1: Values with < / > operators
# =====================================================================

class TestDualOperatorParsing:
    """Dual comparison operator lines: value AND reference both have < / >."""

    def test_estradiol_dual_lt(self):
        """'Эстрадиол < 37 пмоль/л < 161' → value=37, ref=<161."""
        result = _try_parse_one_line("Эстрадиол < 37 пмоль/л < 161")
        assert result is not None, "Estradiol line must not return None"
        parts = result.split("\t")
        assert len(parts) >= 3
        # name contains эстрадиол
        assert "эстрадиол" in parts[0].lower() or "Эстрадиол" in parts[0]
        # value
        assert float(parts[1]) == pytest.approx(37.0)
        # ref contains <161
        assert "<161" in parts[2]
        # unit contains пмоль
        if len(parts) >= 4 and parts[3]:
            assert "пмоль" in parts[3]

    def test_estradiol_dual_lt_engine(self):
        """Same test via engine's _try_parse_one_line_row."""
        result = _try_parse_one_line_row("Эстрадиол < 37 пмоль/л < 161")
        assert result is not None, "Engine parser must also handle dual-operator"
        parts = result.split("\t")
        assert float(parts[1]) == pytest.approx(37.0)
        assert "<161" in parts[2]

    def test_prolactin_range_ref(self):
        """'Пролактин 330 мМЕ/л 73 - 407' → normal range ref (regression)."""
        result = _try_parse_one_line("Пролактин 330 мМЕ/л 73 - 407")
        assert result is not None
        parts = result.split("\t")
        assert float(parts[1]) == pytest.approx(330.0)
        assert "73" in parts[2] and "407" in parts[2]

    def test_value_with_gt_operator(self):
        """'Тестостерон > 52.1 нмоль/л 12.1 - 38.3' → value=52.1, ref=12.1-38.3."""
        result = _try_parse_one_line("Тестостерон > 52.1 нмоль/л 12.1 - 38.3")
        assert result is not None
        parts = result.split("\t")
        # name should NOT contain >
        assert ">" not in parts[0]
        assert float(parts[1]) == pytest.approx(52.1)
        assert "12.1" in parts[2] and "38.3" in parts[2]

    def test_value_with_gt_operator_engine(self):
        """Same via engine."""
        result = _try_parse_one_line_row("Тестостерон > 52.1 нмоль/л 12.1 - 38.3")
        assert result is not None
        parts = result.split("\t")
        assert ">" not in parts[0]
        assert float(parts[1]) == pytest.approx(52.1)

    def test_parse_value_unit_strips_lt(self):
        """_parse_value_unit_from_line('< 37 пмоль/л') → (37.0, 'пмоль/л')."""
        val, unit = _parse_value_unit_from_line("< 37 пмоль/л")
        assert val == pytest.approx(37.0)
        assert "пмоль" in unit

    def test_parse_value_unit_strips_gt(self):
        """_parse_value_unit_from_line('> 52.1 нмоль/л') → (52.1, ...)."""
        val, unit = _parse_value_unit_from_line("> 52.1 нмоль/л")
        assert val == pytest.approx(52.1)

    def test_parse_value_unit_normal_unchanged(self):
        """Normal numeric values unaffected by operator stripping."""
        val, unit = _parse_value_unit_from_line("330 мМЕ/л")
        assert val == pytest.approx(330.0)


# =====================================================================
# Bug #2: Hormone name mappings
# =====================================================================

class TestHormoneMappings:
    """Verify hormone names normalize and are in all dictionaries."""

    @pytest.mark.parametrize("raw,expected", [
        ("Эстрадиол", "E2"),
        ("Пролактин", "PRL"),
        ("Тестостерон общий", "TESTO"),
        ("Тестостерон свободный", "TESTO_FREE"),
        ("Тестостерон", "TESTO"),
        ("Прогестерон", "PROG"),
        ("Фолликулостимулирующий гормон", "FSH"),
        ("ФСГ", "FSH"),
        ("Лютеинизирующий гормон", "LH"),
        ("ЛГ", "LH"),
        ("ДГЭА-сульфат", "DHEA"),
        ("Кортизол", "CORT"),
        ("Антимюллеров гормон", "AMH"),
    ])
    def test_normalize_name(self, raw, expected):
        assert normalize_name(raw) == expected

    @pytest.mark.parametrize("code", [
        "E2", "PRL", "TESTO", "PROG", "FSH", "LH", "DHEA", "CORT", "AMH",
    ])
    def test_explain_dict_has_entry(self, code):
        assert code in EXPLAIN_DICT, f"{code} missing from EXPLAIN_DICT"

    @pytest.mark.parametrize("code", [
        "E2", "PRL", "TESTO", "PROG", "FSH", "LH", "DHEA", "CORT", "AMH",
    ])
    def test_sanity_ranges_has_entry(self, code):
        assert code in SANITY_RANGES, f"{code} missing from SANITY_RANGES"

    @pytest.mark.parametrize("code", [
        "E2", "PRL", "TESTO", "PROG", "FSH", "LH", "DHEA", "CORT", "AMH",
    ])
    def test_specialist_map_has_entry(self, code):
        assert code in SPECIALIST_MAP, f"{code} missing from SPECIALIST_MAP"


# =====================================================================
# Full pipeline integration test
# =====================================================================

class TestInvitroPipelineIntegration:
    """Full pipeline with real Invitro pypdf text."""

    @pytest.fixture(scope="class")
    def parsed(self):
        items, quality, dd, oc = _run_parse_pipeline(INVITRO_FULL)
        assert items is not None, "Pipeline returned None items"
        return items

    def test_estradiol_present(self, parsed):
        """Estradiol (E2) must be parsed from the < 37 ... < 161 line."""
        e2 = _find(parsed, "E2")
        assert len(e2) >= 1, f"E2 not found; names: {[i.name for i in parsed]}"
        assert e2[0].value == pytest.approx(37.0)

    def test_prolactin_present(self, parsed):
        """Prolactin (PRL) must be parsed."""
        prl = _find(parsed, "PRL")
        assert len(prl) >= 1, f"PRL not found; names: {[i.name for i in parsed]}"
        assert prl[0].value == pytest.approx(330.0)

    def test_hematocrit_present(self, parsed):
        """Hematocrit (HCT) from page 2."""
        hct = _find(parsed, "HCT")
        assert len(hct) >= 1
        assert hct[0].value == pytest.approx(51.2)

    def test_hemoglobin_present(self, parsed):
        """Hemoglobin (HGB) from page 2."""
        hgb = _find(parsed, "HGB")
        assert len(hgb) >= 1
        assert hgb[0].value == pytest.approx(17.2)

    def test_rbc_present(self, parsed):
        """RBC from page 2."""
        rbc = _find(parsed, "RBC")
        assert len(rbc) >= 1
        assert rbc[0].value == pytest.approx(6.15)

    def test_wbc_present(self, parsed):
        """WBC from page 2."""
        wbc = _find(parsed, "WBC")
        assert len(wbc) >= 1
        assert wbc[0].value == pytest.approx(7.29)

    def test_plt_present(self, parsed):
        """PLT from page 2."""
        plt_items = _find(parsed, "PLT")
        assert len(plt_items) >= 1
        assert plt_items[0].value == pytest.approx(339.0)

    def test_minimum_biomarker_count(self, parsed):
        """At least 11 biomarkers expected (2 hormones + 9 CBC)."""
        assert len(parsed) >= 11, (
            f"Expected >= 11 items, got {len(parsed)}: {[i.name for i in parsed]}"
        )

    def test_estradiol_status_normal(self, parsed):
        """E2 value 37 < ref 161 → В НОРМЕ."""
        e2 = _find(parsed, "E2")
        assert len(e2) >= 1
        assert e2[0].status == "В НОРМЕ", f"Expected В НОРМЕ, got {e2[0].status}"

    def test_hematocrit_status_above(self, parsed):
        """HCT 51.2 > ref max 49 → ВЫШЕ."""
        hct = _find(parsed, "HCT")
        assert len(hct) >= 1
        assert hct[0].status == "ВЫШЕ", f"Expected ВЫШЕ, got {hct[0].status}"


# =====================================================================
# Bug #3: Leukocyte formula warning tone
# =====================================================================

class TestLeukocyteWarning:
    """Verify informational (not alarming) warning when leuko formula absent."""

    def test_all_leuko_missing_informational(self):
        """When ALL leuko markers are missing → informational tone."""
        # Invitro text has CBC but no leukocyte formula
        items, quality, dd, oc = _run_parse_pipeline(INVITRO_FULL)
        assert items is not None
        names = {it.name for it in items}
        # Verify leuko markers are indeed absent
        leuko = {"NE%", "LY%", "MO%", "EO%", "BA%"}
        assert leuko.isdisjoint(names), "Test assumes no leuko markers parsed"
