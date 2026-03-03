"""
Tests for Citilab-style PDF pre-cleaning functions.

Validates:
1. _strip_prefix_unit — removes unit prefix glued to biomarker name
2. _strip_trailing_lab_code — removes lab service code from ref range
3. _strip_asterisk_marker — removes * after out-of-range values
4. Full integration via universal_extract() on real Citilab text
5. Safety: normal lab formats (Helix/Gemotest) are NOT damaged
"""

import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from parsers.universal_extractor import (
    _strip_prefix_unit,
    _strip_trailing_lab_code,
    _strip_asterisk_marker,
    _preclean_citilab_format,
    universal_extract,
)


# ═══════════════════════════════════════════════
# 1. _strip_prefix_unit
# ═══════════════════════════════════════════════

class TestStripPrefixUnit:

    def test_10_9_prefix(self):
        assert _strip_prefix_unit("10^9/лЛейкоциты (WBC) 5.76 3.89 - 9.231001") == \
            "Лейкоциты (WBC) 5.76 3.89 - 9.231001"

    def test_10_12_prefix(self):
        assert _strip_prefix_unit("10^12/лЭритроциты (RBC) 5.32* 3.74 - 5.311001") == \
            "Эритроциты (RBC) 5.32* 3.74 - 5.311001"

    def test_g_per_l_prefix(self):
        assert _strip_prefix_unit("г/лГемоглобин (HGB, Hb) 148.00 118.30 - 165.701001") == \
            "Гемоглобин (HGB, Hb) 148.00 118.30 - 165.701001"

    def test_percent_prefix(self):
        assert _strip_prefix_unit("%Гематокрит (HCT) 43.70 35.89 - 50.641001") == \
            "Гематокрит (HCT) 43.70 35.89 - 50.641001"

    def test_fl_prefix(self):
        assert _strip_prefix_unit("флСредний объем эритроцита (MCV) 82.10* 88.05 - 104.071001") == \
            "Средний объем эритроцита (MCV) 82.10* 88.05 - 104.071001"

    def test_pg_prefix(self):
        assert _strip_prefix_unit("пгСреднее содержание Hb в эритроците (MCH) 27.80 27.75 - 34.521001") == \
            "Среднее содержание Hb в эритроците (MCH) 27.80 27.75 - 34.521001"

    def test_mmol_per_l_prefix(self):
        assert _strip_prefix_unit("ммоль/лКалий (К+) 4.78 3.50 - 5.1058") == \
            "Калий (К+) 4.78 3.50 - 5.1058"

    def test_umol_per_l_prefix(self):
        assert _strip_prefix_unit("мкмоль/лЖелезо сывороточное 23.8 5.8 - 34.530") == \
            "Железо сывороточное 23.8 5.8 - 34.530"

    def test_u_per_l_prefix(self):
        assert _strip_prefix_unit("Ед/лКреатинфосфокиназа 188.0 39.0 - 308.043") == \
            "Креатинфосфокиназа 188.0 39.0 - 308.043"

    def test_no_prefix_normal_line(self):
        """Normal lines must NOT be changed."""
        line = "Гемоглобин (HGB) 148 г/л 118.30 - 165.70"
        assert _strip_prefix_unit(line) == line

    def test_no_prefix_value_after_unit(self):
        """Unit followed by lowercase → NOT stripped (not a biomarker start)."""
        line = "г/лвенозная кровь"
        assert _strip_prefix_unit(line) == line

    def test_no_prefix_glucose(self):
        """Normal Glucose line must not be changed."""
        line = "Глюкоза 6.07 ммоль/л 4.56 - 6.38"
        assert _strip_prefix_unit(line) == line

    def test_no_false_positive_for_percent_in_middle(self):
        """Percent sign in middle of line should be safe."""
        line = "Нейтрофилы (Ne), % 44.40 40.80 - 70.39"
        assert _strip_prefix_unit(line) == line

    def test_no_strip_on_index_aterogennosti(self):
        """'Индекс атерогенности' starts with uppercase but has no unit prefix."""
        line = "Индекс атерогенности 1.21 < 3.001091"
        assert _strip_prefix_unit(line) == line


# ═══════════════════════════════════════════════
# 2. _strip_trailing_lab_code
# ═══════════════════════════════════════════════

class TestStripTrailingLabCode:

    def test_2dec_range_long_code(self):
        assert _strip_trailing_lab_code("Лейкоциты (WBC) 5.76 3.89 - 9.231001") == \
            "Лейкоциты (WBC) 5.76 3.89 - 9.23"

    def test_2dec_range_short_code(self):
        assert _strip_trailing_lab_code("Калий (К+) 4.78 3.50 - 5.1058") == \
            "Калий (К+) 4.78 3.50 - 5.10"

    def test_2dec_range_code_2digits(self):
        assert _strip_trailing_lab_code("Магний 1.03 0.66 - 0.9951") == \
            "Магний 1.03 0.66 - 0.99"

    def test_1dec_range_long_code(self):
        assert _strip_trailing_lab_code("Железо сывороточное 23.8 5.8 - 34.530") == \
            "Железо сывороточное 23.8 5.8 - 34.5"

    def test_1dec_range_code_43(self):
        assert _strip_trailing_lab_code("Креатинфосфокиназа 188.0 39.0 - 308.043") == \
            "Креатинфосфокиназа 188.0 39.0 - 308.0"

    def test_1dec_range_code_single_digit(self):
        """62.0 - 106.04 → 62.0 - 106.0 (code='4')"""
        assert _strip_trailing_lab_code("Креатинин в крови 77.0 62.0 - 106.04") == \
            "Креатинин в крови 77.0 62.0 - 106.0"

    def test_comparison_less_than(self):
        assert _strip_trailing_lab_code("Индекс атерогенности 1.21 < 3.001091") == \
            "Индекс атерогенности 1.21 < 3.00"

    def test_2dec_range_code_5(self):
        assert _strip_trailing_lab_code("Холестерин общий 3.45 3.20 - 5.205") == \
            "Холестерин общий 3.45 3.20 - 5.20"

    def test_2dec_range_code_6(self):
        assert _strip_trailing_lab_code("Триглицериды 0.70 0.10 - 2.306") == \
            "Триглицериды 0.70 0.10 - 2.30"

    def test_2dec_range_code_16(self):
        assert _strip_trailing_lab_code("Билирубин общий 10.90 2.50 - 21.0016") == \
            "Билирубин общий 10.90 2.50 - 21.00"

    def test_2dec_range_code_12(self):
        assert _strip_trailing_lab_code("АСТ 17.8 5.0 - 40.012") == \
            "АСТ 17.8 5.0 - 40.0"

    def test_1dec_range_code_1(self):
        assert _strip_trailing_lab_code("Глюкоза 6.07 4.56 - 6.381") == \
            "Глюкоза 6.07 4.56 - 6.38"

    def test_normal_range_not_damaged(self):
        """Normal reference range should NOT be changed."""
        line = "Гемоглобин 148 118.30 - 165.70"
        assert _strip_trailing_lab_code(line) == line

    def test_normal_range_1dec_not_damaged(self):
        line = "АЛТ 16.7 5.0 - 41.0"
        assert _strip_trailing_lab_code(line) == line

    def test_normal_comparison_not_damaged(self):
        line = "Индекс атерогенности 1.21 < 3.00"
        assert _strip_trailing_lab_code(line) == line

    def test_no_ref_line_not_damaged(self):
        line = "Гемоглобин (HGB) 148 г/л"
        assert _strip_trailing_lab_code(line) == line

    def test_3dec_range_code(self):
        """'0.010 - 0.0901001' → low has 3 dec (0.010), high has 3 dec (0.090) + code 1001."""
        assert _strip_trailing_lab_code("Базофилы 0.040 0.010 - 0.0901001") == \
            "Базофилы 0.040 0.010 - 0.090"


# ═══════════════════════════════════════════════
# 3. _strip_asterisk_marker
# ═══════════════════════════════════════════════

class TestStripAsteriskMarker:

    def test_asterisk_before_space(self):
        assert _strip_asterisk_marker("5.32* 3.74 - 5.31") == "5.32 3.74 - 5.31"

    def test_asterisk_end_of_line(self):
        assert _strip_asterisk_marker("82.10*") == "82.10"

    def test_asterisk_before_letter(self):
        assert _strip_asterisk_marker("1.03*some") == "1.03some"

    def test_no_asterisk(self):
        line = "5.76 3.89 - 9.23"
        assert _strip_asterisk_marker(line) == line

    def test_asterisk_in_10_pow_not_touched(self):
        """'*10^9' patterns should NOT be damaged."""
        line = "4.5 *10^9/л"
        assert _strip_asterisk_marker(line) == line

    def test_multiple_asterisks(self):
        assert _strip_asterisk_marker("5.32* 82.10* 1.03*") == "5.32 82.10 1.03"


# ═══════════════════════════════════════════════
# 4. _preclean_citilab_format (orchestrator)
# ═══════════════════════════════════════════════

class TestPrecleanCitilabFormat:

    def test_full_citilab_line(self):
        lines = ["10^9/лЛейкоциты (WBC) 5.76 3.89 - 9.231001"]
        result = _preclean_citilab_format(lines)
        assert result == ["Лейкоциты (WBC) 5.76 3.89 - 9.23"]

    def test_asterisk_and_prefix(self):
        lines = ["10^12/лЭритроциты (RBC) 5.32* 3.74 - 5.311001"]
        result = _preclean_citilab_format(lines)
        assert result == ["Эритроциты (RBC) 5.32 3.74 - 5.31"]

    def test_normal_line_unchanged(self):
        lines = ["Глюкоза 6.07 ммоль/л 4.56 - 6.38"]
        result = _preclean_citilab_format(lines)
        assert result == ["Глюкоза 6.07 ммоль/л 4.56 - 6.38"]


# ═══════════════════════════════════════════════
# 5. Integration test: universal_extract on real Citilab text
# ═══════════════════════════════════════════════

CITILAB_REAL_TEXT = """\
10^9/лЛейкоциты (WBC) 5.76 3.89 - 9.231001
10^12/лЭритроциты (RBC) 5.32* 3.74 - 5.311001
г/лГемоглобин (HGB, Hb) 148.00 118.30 - 165.701001
%Гематокрит (HCT) 43.70 35.89 - 50.641001
флСредний объем эритроцита (MCV) 82.10* 88.05 - 104.071001
пгСреднее содержание Hb в эритроците (MCH) 27.80 27.75 - 34.521001
г/лСредняя концентрация Hb в эритроцитах (MCHC) 339.00 314.50 - 347.401001
флИндекс распределения эритроцитов (RDW-SD) 37.90* 38.56 - 50.281001
%Индекс распределения эритроцитов (RDW-CV) 12.50 11.43 - 13.901001
10^9/лТромбоциты (PLT) 174.00 141.30 - 389.701001
флСредний объем тромбоцита (MPV) 9.10 9.10 - 12.601001
%Тромбокрит (PCT) 0.16 0.14 - 0.341001
флИндекс распред. тромбоцитов (PDW) 9.60 9.30 - 16.701001
10^9/лНейтрофилы (Ne), абсолютное количество 2.55 0.78 - 6.041001
%Нейтрофилы (Ne), % 44.40 40.80 - 70.391001
10^9/лЛимфоциты (LYMF), абсолютное количество 2.37 1.01 - 2.751001
%Лимфоциты (LYMF), % 41.10 20.11 - 46.791001
10^9/лМоноциты (MON), абсолютное количество 0.59 0.29 - 0.721001
%Моноциты (MON), % 10.20 4.26 - 11.081001
10^9/лЭозинофилы (Eo), абсолютное количество 0.21 0.04 - 0.581001
%Эозинофилы (Eo), % 3.60 0.73 - 8.861001
10^9/лБазофилы (Ba), абсолютное количество 0.040 0.010 - 0.0901001
%Базофилы (Ba), % 0.70 0.20 - 1.501001
10^9/лНезрелые гранулоциты, абсолютное количество 0.01 0.00 - 0.041001
%Незрелые гранулоциты % 0.20 0.00 - 0.501001
10^9/лНормобласты, абсолютное количество 0.00 0.00 - 0.031001
%Нормобласты % 0.00 0.00 - 0.201001
ммоль/лКалий (К+) 4.78 3.50 - 5.1058
ммоль/лНатрий (Na+) 140.00 135.00 - 145.0058
ммоль/лХлор (Cl-) 102.6 98.0 - 107.058
ммоль/лМагний 1.03* 0.66 - 0.9951
мкмоль/лЖелезо сывороточное 23.8 5.8 - 34.530
Ед/лКреатинфосфокиназа 188.0 39.0 - 308.043
Индекс атерогенности 1.21 < 3.001091
ммоль/лХолестерин общий 3.45 3.20 - 5.205
ммоль/лТриглицериды 0.70 0.10 - 2.306
мкмоль/лБилирубин общий 10.90 2.50 - 21.0016
Ед/лАСТ (аспартатаминотрансфераза) 17.8 5.0 - 40.012
Ед/лАЛТ (аланинаминотрансфераза) 16.7 5.0 - 41.013
мкмоль/лКреатинин в крови 77.0 62.0 - 106.04
ммоль/лГлюкоза 6.07 4.56 - 6.381
г/лОбщий белок в крови 71.3 64.0 - 83.019
ммоль/лМочевина 5.90 2.76 - 8.072
"""


def _parse_candidates(tsv_output: str) -> dict:
    """Parse TSV output into dict: name → (value_str, ref_str, unit)."""
    result = {}
    for line in tsv_output.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            name = parts[0].strip()
            value = parts[1].strip()
            ref = parts[2].strip() if len(parts) > 2 else ""
            unit = parts[3].strip() if len(parts) > 3 else ""
            result[name] = (value, ref, unit)
    return result


class TestIntegrationCitilab:

    def setup_method(self):
        self.output = universal_extract(CITILAB_REAL_TEXT)
        self.candidates = _parse_candidates(self.output)

    def test_leukocytes_found(self):
        matches = [k for k in self.candidates if "ейкоцит" in k and "WBC" in k]
        assert matches, f"Лейкоциты (WBC) not found in: {list(self.candidates.keys())}"
        name = matches[0]
        val, ref, _ = self.candidates[name]
        assert val == "5.76"
        assert "9.23" in ref
        assert "1001" not in ref

    def test_erythrocytes_found(self):
        matches = [k for k in self.candidates if "ритроцит" in k and "RBC" in k]
        assert matches, f"Эритроциты (RBC) not found in: {list(self.candidates.keys())}"
        name = matches[0]
        val, ref, _ = self.candidates[name]
        assert val == "5.32"
        assert "5.31" in ref
        assert "1001" not in ref

    def test_hemoglobin_found(self):
        matches = [k for k in self.candidates if "емоглобин" in k and "HGB" in k]
        assert matches, f"Гемоглобин not found in: {list(self.candidates.keys())}"
        name = matches[0]
        val, ref, _ = self.candidates[name]
        assert val == "148"
        assert "118.3" in ref or "118.30" in ref
        assert "165.7" in ref or "165.70" in ref
        assert "1001" not in ref

    def test_potassium_found(self):
        matches = [k for k in self.candidates if "алий" in k]
        assert matches, f"Калий not found in: {list(self.candidates.keys())}"
        name = matches[0]
        val, ref, _ = self.candidates[name]
        assert val == "4.78"
        assert "5.10" in ref or "5.1" in ref
        assert "58" not in ref.replace("5.10", "").replace("5.1", "")

    def test_creatinine_found(self):
        matches = [k for k in self.candidates if "реатинин" in k]
        assert matches, f"Креатинин not found in: {list(self.candidates.keys())}"
        name = matches[0]
        val, ref, _ = self.candidates[name]
        assert val == "77"
        assert "106.0" in ref or "106" in ref
        assert ref.endswith("106.0") or ref.endswith("106")

    def test_atherogenic_index_found(self):
        matches = [k for k in self.candidates if "атерогенн" in k.lower()]
        assert matches, f"Индекс атерогенности not found in: {list(self.candidates.keys())}"
        name = matches[0]
        val, ref, _ = self.candidates[name]
        assert val == "1.21"
        assert "3.00" in ref or "<3" in ref
        assert "1091" not in ref

    def test_glucose_found(self):
        matches = [k for k in self.candidates if "люкоз" in k]
        assert matches, f"Глюкоза not found in: {list(self.candidates.keys())}"
        name = matches[0]
        val, ref, _ = self.candidates[name]
        assert val == "6.07"
        assert "6.38" in ref

    def test_total_protein_found(self):
        matches = [k for k in self.candidates if "белок" in k.lower()]
        assert matches, f"Общий белок not found in: {list(self.candidates.keys())}"

    def test_at_least_30_candidates(self):
        """Citilab text has 42 biomarkers, we should extract at least 30."""
        assert len(self.candidates) >= 30, \
            f"Only {len(self.candidates)} candidates found, expected >= 30"


# ═══════════════════════════════════════════════
# 6. Safety: normal lab format lines should NOT be damaged
# ═══════════════════════════════════════════════

NORMAL_LINES_TEXT = """\
Гемоглобин (HGB) 148 г/л 118.30 - 165.70
Глюкоза 6.07 ммоль/л 4.56 - 6.38
АЛТ 16.7 Ед/л 5.0 - 41.0
Эритроциты 4.5 *10^9/л 3.7 - 5.3
Холестерин общий 4.73 ммоль/л 3.20 - 5.20
"""


class TestSafetyNormalFormat:

    def test_normal_lines_not_damaged(self):
        """_preclean_citilab_format should not alter normal lab format lines."""
        lines = [ln for ln in NORMAL_LINES_TEXT.strip().splitlines() if ln.strip()]
        cleaned = _preclean_citilab_format(lines)
        assert cleaned == lines

    def test_universal_extract_normal_format(self):
        """universal_extract should still parse normal format correctly."""
        output = universal_extract(NORMAL_LINES_TEXT)
        candidates = _parse_candidates(output)
        hgb = [k for k in candidates if "емоглобин" in k]
        assert hgb, "Гемоглобин should be parsed from normal format"
        glucose = [k for k in candidates if "люкоз" in k]
        assert glucose, "Глюкоза should be parsed from normal format"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
