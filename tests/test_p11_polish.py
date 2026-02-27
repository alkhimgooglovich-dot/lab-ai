"""
Tests for P11 — final polish before launch.
"""
import sys, re
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from parsers.universal_extractor import universal_extract, _strip_gemotest_markers
from engine import normalize_name, EXPLAIN_DICT, SPECIALIST_MAP, SYSTEM_PROMPT, RUS_NAME_MAP, ALIASES


class TestStripGemotestMarkers:
    """Gemotest +/- markers must be stripped from values."""

    def test_plus_before_unit(self):
        lines = ["Альбумин 53+ г/л 35 - 52"]
        result = _strip_gemotest_markers(lines)
        assert "53+" not in result[0]
        assert "53 г/л" in result[0] or "53  г/л" in result[0]

    def test_minus_before_unit(self):
        lines = ["Креатинин 71.0- мкмоль/л 72 - 127"]
        result = _strip_gemotest_markers(lines)
        assert "71.0-" not in result[0] or "71.0- " not in result[0]
        assert "71.0 мкмоль" in result[0] or "71.0  мкмоль" in result[0]

    def test_range_not_broken(self):
        lines = ["3.5 - 5.1"]
        result = _strip_gemotest_markers(lines)
        assert "3.5 - 5.1" in result[0] or "3.5-5.1" in result[0]

    def test_ref_range_preserved(self):
        lines = ["Глюкоза 5.27 ммоль/л 4.11 - 6.1"]
        result = _strip_gemotest_markers(lines)
        assert "4.11" in result[0]
        assert "6.1" in result[0]

    def test_less_than_preserved(self):
        lines = ["СРБ 1.72 мг/л < 5"]
        result = _strip_gemotest_markers(lines)
        assert "< 5" in result[0]

    def test_plus_at_end_of_line(self):
        lines = ["53+"]
        result = _strip_gemotest_markers(lines)
        assert result[0] == "53"

    def test_minus_at_end_of_line(self):
        lines = ["71.0-"]
        result = _strip_gemotest_markers(lines)
        assert result[0] == "71.0"

    def test_compact_range_not_broken(self):
        lines = ["3.5-5.1"]
        result = _strip_gemotest_markers(lines)
        assert "3.5" in result[0] and "5.1" in result[0]


class TestNormalizeNameBiochem:
    """Biochemistry names must map to canonical codes."""

    def test_creatinine(self):
        assert normalize_name("Креатинин") == "CREA"

    def test_alt_cyrillic(self):
        assert normalize_name("Аланинаминотрансфераза (АЛТ)") == "ALT"

    def test_ast_cyrillic(self):
        assert normalize_name("Аспартатаминотрансфераза (АСТ)") == "AST"

    def test_uric_acid(self):
        assert normalize_name("Мочевая кислота") == "URIC_ACID"

    def test_albumin(self):
        assert normalize_name("Альбумин") == "ALB"

    def test_total_protein(self):
        assert normalize_name("Общий белок") == "TP"

    def test_glucose(self):
        assert normalize_name("Глюкоза") == "GLUC"

    def test_crp(self):
        assert normalize_name("С-реактивный белок (СРБ)") == "CRP"

    def test_triglycerides(self):
        assert normalize_name("Триглицериды") == "TRIG"

    def test_cholesterol_total(self):
        assert normalize_name("Холестерин общий") == "CHOL"

    def test_hdl(self):
        assert normalize_name("Холестерин-ЛПВП") == "HDL"

    def test_ldl(self):
        n = normalize_name("Холестерин липопротеинов низкой плотности (ЛПНП)")
        assert n == "LDL"

    def test_hba1c(self):
        assert normalize_name("Гликированный гемоглобин") == "HBA1C"

    def test_ldh_cyrillic(self):
        assert normalize_name("Лактатдегидрогеназа (ЛДГ)") == "LDH"

    def test_iron(self):
        assert normalize_name("Сывороточное железо") == "FE"

    def test_potassium(self):
        assert normalize_name("Калий (K+)") == "K"

    def test_sodium(self):
        assert normalize_name("Натрий (Na+)") == "NA"


class TestExplainDictCompleteness:
    """All biochemistry codes must have explanations."""

    REQUIRED_CODES = ["ALT", "AST", "CREA", "UREA", "CRP", "GLUC",
                       "ALB", "URIC_ACID", "FE", "TRIG", "CHOL",
                       "HDL", "LDL", "HBA1C", "LDH", "TP"]

    def test_all_required_codes_in_explain_dict(self):
        for code in self.REQUIRED_CODES:
            assert code in EXPLAIN_DICT, f"{code} missing from EXPLAIN_DICT"


class TestSpecialistMapCompleteness:
    """Key biochemistry codes must have specialist recommendations."""

    REQUIRED_CODES = ["ALT", "AST", "CREA", "URIC_ACID", "FE", "HBA1C"]

    def test_all_required_codes_in_specialist_map(self):
        for code in self.REQUIRED_CODES:
            assert code in SPECIALIST_MAP, f"{code} missing from SPECIALIST_MAP"


class TestSystemPromptBans:
    """SYSTEM_PROMPT must ban diet/lifestyle/control words."""

    def test_bans_dieta(self):
        low = SYSTEM_PROMPT.lower()
        assert "диет" in low

    def test_bans_racion(self):
        low = SYSTEM_PROMPT.lower()
        assert "рацион" in low or "питани" in low

    def test_bans_mery(self):
        low = SYSTEM_PROMPT.lower()
        assert "мер" in low or "контрол" in low


class TestFullGemotestP11:
    """Integration: real pypdf text with +/- markers."""

    SAMPLE = """\
Альбумин 53+ г/л 35 - 52
Креатинин 71.0- мкмоль/л 72 - 127
Мочевая кислота 426.0+ мкмоль/л 202.3 - 416.5
Аланинаминотрансфераза (АЛТ) 92.3+ Ед/л < 41
Аспартатаминотрансфераза (АСТ) 56.2+ Ед/л < 40
Сывороточное железо 52.8+ мкмоль/л 5.8 - 34.5
Глюкоза 5.27 ммоль/л 4.11 - 6.1
"""

    def test_albumin_unit_not_plus(self):
        c = universal_extract(self.SAMPLE)
        for line in (c or "").splitlines():
            if "53" in line and "\t" in line:
                parts = line.split("\t")
                if len(parts) >= 4:
                    assert parts[3].strip() != "+", f"Unit is '+': {line}"

    def test_creatinine_unit_not_minus(self):
        c = universal_extract(self.SAMPLE)
        for line in (c or "").splitlines():
            if "71" in line and "\t" in line:
                parts = line.split("\t")
                if len(parts) >= 4:
                    assert parts[3].strip() != "-", f"Unit is '-': {line}"

    def test_glucose_value_correct(self):
        c = universal_extract(self.SAMPLE)
        assert "5.27" in (c or "")

    def test_ref_ranges_preserved(self):
        c = universal_extract(self.SAMPLE)
        assert "35" in (c or "") and "52" in (c or "")
