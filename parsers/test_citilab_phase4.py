"""
Phase 4 tests: normalize_name for Citilab % indicators, HbA1c, RDW, LDL.

Validates:
1. NE%, LY%, MO%, EO%, BA% — correct % detection from Citilab format
2. HBA1C — comma-in-parens fallback: (HBA1c, DCCT/NGSP) → HBA1C
3. RDW-SD / RDW-CV — hyphen+digit in parenthesized code
4. LDL — "- прямое определение" stripped, "определение" filtered as garbage
5. Full pipeline integration for all of the above

Run: pytest parsers/test_citilab_phase4.py -v
"""

import sys
from pathlib import Path
from collections import defaultdict

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import normalize_name, _is_garbage_name, parse_items_from_candidates
from parsers.universal_extractor import (
    universal_extract,
    _strip_direct_determination,
    _preclean_citilab_format,
)


# ═══════════════════════════════════════════════════════════
# 1. normalize_name: % indicators from Citilab
# ═══════════════════════════════════════════════════════════

class TestNormalizeNamePercentIndicators:

    def test_neutrophils_pct(self):
        assert normalize_name("Нейтрофилы (Ne), %") == "NE%"

    def test_neutrophils_abs(self):
        assert normalize_name("Нейтрофилы (Ne), абсолютное количество") == "NE"

    def test_lymphocytes_pct(self):
        assert normalize_name("Лимфоциты (LYMF), %") == "LY%"

    def test_lymphocytes_abs(self):
        assert normalize_name("Лимфоциты (LYMF), абсолютное количество") == "LY"

    def test_monocytes_pct(self):
        assert normalize_name("Моноциты (MON), %") == "MO%"

    def test_monocytes_abs(self):
        assert normalize_name("Моноциты (MON), абсолютное количество") == "MO"

    def test_eosinophils_pct(self):
        assert normalize_name("Эозинофилы (Eo), %") == "EO%"

    def test_eosinophils_abs(self):
        assert normalize_name("Эозинофилы (Eo), абсолютное количество") == "EO"

    def test_basophils_pct(self):
        assert normalize_name("Базофилы (Ba), %") == "BA%"

    def test_basophils_abs(self):
        assert normalize_name("Базофилы (Ba), абсолютное количество") == "BA"

    def test_no_false_positive_plain_ne(self):
        """Без ', %' → обычный абсолютный код."""
        assert normalize_name("Нейтрофилы (Ne)") == "NE"

    def test_pct_without_space_after_comma(self):
        assert normalize_name("Нейтрофилы (Ne),%") == "NE%"


# ═══════════════════════════════════════════════════════════
# 2. normalize_name: HbA1c with comma in parentheses
# ═══════════════════════════════════════════════════════════

class TestNormalizeNameHbA1c:

    def test_hba1c_dcct_ngsp(self):
        assert normalize_name("Гликозилированный гемоглобин (HBA1c, DCCT/NGSP)") == "HBA1C"

    def test_hba1c_ifcc(self):
        assert normalize_name("Гликозилированный гемоглобин (HBA1c, IFCC)") == "HBA1C"

    def test_hba1c_standalone_parens(self):
        """Single code without comma — direct match."""
        assert normalize_name("Гликированный гемоглобин (HBA1C)") == "HBA1C"

    def test_hba1c_russian_name_only(self):
        """No parenthesized code — falls through to RUS_NAME_MAP."""
        assert normalize_name("Гликозилированный гемоглобин") == "HBA1C"


# ═══════════════════════════════════════════════════════════
# 3. normalize_name: RDW with hyphen in code
# ═══════════════════════════════════════════════════════════

class TestNormalizeNameRDW:

    def test_rdw_sd(self):
        assert normalize_name("Индекс распределения эритроцитов (RDW-SD)") == "RDW-SD"

    def test_rdw_cv(self):
        assert normalize_name("Индекс распределения эритроцитов (RDW-CV)") == "RDW-CV"

    def test_p_lcr(self):
        assert normalize_name("P-LCR (P-LCR)") == "P-LCR"


# ═══════════════════════════════════════════════════════════
# 4. LDL: "- прямое определение" handling
# ═══════════════════════════════════════════════════════════

class TestLDLDirectDetermination:

    def test_strip_direct_determination_full(self):
        line = "Липопротеины низкой плотности (ЛПНП, LDL) - прямое определение 1.83 0.10 - 4.14"
        expected = "Липопротеины низкой плотности (ЛПНП, LDL) 1.83 0.10 - 4.14"
        assert _strip_direct_determination(line) == expected

    def test_strip_direct_determination_trailing(self):
        line = "Липопротеины низкой плотности (ЛПНП, LDL) - прямое"
        expected = "Липопротеины низкой плотности (ЛПНП, LDL)"
        assert _strip_direct_determination(line) == expected

    def test_strip_direct_determination_start_of_next_line(self):
        line = "определение 1.83 0.10 - 4.14"
        expected = "1.83 0.10 - 4.14"
        assert _strip_direct_determination(line) == expected

    def test_strip_direct_determination_safe_on_normal(self):
        line = "Холестерин общий 3.45 3.20 - 5.20"
        assert _strip_direct_determination(line) == line

    def test_opredelenie_is_garbage(self):
        assert _is_garbage_name("определение") is True

    def test_pryamoe_opredelenie_is_garbage(self):
        assert _is_garbage_name("прямое определение") is True

    def test_ldl_name_not_garbage(self):
        name = "Липопротеины низкой плотности (ЛПНП, LDL)"
        assert _is_garbage_name(name) is False

    def test_normalize_ldl_with_comma(self):
        assert normalize_name("Липопротеины низкой плотности (ЛПНП, LDL)") == "LDL"

    def test_preclean_citilab_ldl_line(self):
        lines = [
            "ммоль/лЛипопротеины низкой плотности (ЛПНП, LDL) - прямое определение 1.83 0.10 - 4.141090"
        ]
        result = _preclean_citilab_format(lines)
        assert len(result) == 1
        assert "прямое" not in result[0]
        assert "определение" not in result[0]
        assert "1.83" in result[0]
        assert "(ЛПНП, LDL)" in result[0]


# ═══════════════════════════════════════════════════════════
# 5. Full pipeline integration: % indicators
# ═══════════════════════════════════════════════════════════

CITILAB_LEUKO_TEXT = """\
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
"""


def _build_lookup(items):
    by_name = defaultdict(list)
    for item in items:
        by_name[item.name].append(item)
    return by_name


class TestPipelinePercentIndicators:

    @pytest.fixture(autouse=True)
    def setup(self):
        candidates = universal_extract(CITILAB_LEUKO_TEXT)
        self.items = parse_items_from_candidates(candidates)
        self.by_name = _build_lookup(self.items)
        self.all_names = sorted(self.by_name.keys())

    def test_ne_pct_present(self):
        assert "NE%" in self.by_name, f"NE% not found. Available: {self.all_names}"
        it = self.by_name["NE%"][0]
        assert it.value == pytest.approx(44.4, abs=0.1)

    def test_ne_abs_present(self):
        assert "NE" in self.by_name, f"NE not found. Available: {self.all_names}"
        it = self.by_name["NE"][0]
        assert it.value == pytest.approx(2.55, abs=0.1)

    def test_ly_pct_present(self):
        assert "LY%" in self.by_name, f"LY% not found. Available: {self.all_names}"
        it = self.by_name["LY%"][0]
        assert it.value == pytest.approx(41.1, abs=0.1)

    def test_mo_pct_present(self):
        assert "MO%" in self.by_name, f"MO% not found. Available: {self.all_names}"
        it = self.by_name["MO%"][0]
        assert it.value == pytest.approx(10.2, abs=0.1)

    def test_eo_pct_present(self):
        assert "EO%" in self.by_name, f"EO% not found. Available: {self.all_names}"
        it = self.by_name["EO%"][0]
        assert it.value == pytest.approx(3.6, abs=0.1)

    def test_ba_pct_present(self):
        assert "BA%" in self.by_name, f"BA% not found. Available: {self.all_names}"
        it = self.by_name["BA%"][0]
        assert it.value == pytest.approx(0.7, abs=0.1)

    def test_all_five_pct_codes(self):
        expected_pct = {"NE%", "LY%", "MO%", "EO%", "BA%"}
        found_pct = expected_pct & set(self.all_names)
        missing = expected_pct - found_pct
        assert not missing, f"Missing % indicators: {missing}. Available: {self.all_names}"


# ═══════════════════════════════════════════════════════════
# 6. Full pipeline integration: HbA1c
# ═══════════════════════════════════════════════════════════

CITILAB_HBA1C_TEXT = """\
A09.05.083 Исследование уровня гликированного гемоглобина в крови1050
%Гликозилированный гемоглобин (HBA1c, DCCT/NGSP) 6.12* 4.80 - 5.901050
ммоль/мольГликозилированный гемоглобин (HBA1c, IFCC) 43.39* 29.00 - 42.001050
"""


class TestPipelineHbA1c:

    @pytest.fixture(autouse=True)
    def setup(self):
        candidates = universal_extract(CITILAB_HBA1C_TEXT)
        self.items = parse_items_from_candidates(candidates)
        self.by_name = _build_lookup(self.items)
        self.all_names = sorted(self.by_name.keys())

    def test_hba1c_present(self):
        assert "HBA1C" in self.by_name, f"HBA1C not found. Available: {self.all_names}"

    def test_hba1c_dcct_value(self):
        hba1c_items = self.by_name.get("HBA1C", [])
        dcct = [it for it in hba1c_items if it.value is not None and abs(it.value - 6.12) < 0.1]
        assert dcct, (
            f"HBA1C with value ≈6.12 not found. "
            f"HBA1C values: {[(it.value, it.ref) for it in hba1c_items]}"
        )
        it = dcct[0]
        assert it.ref is not None
        assert it.ref.low == pytest.approx(4.80, abs=0.01)
        assert it.ref.high == pytest.approx(5.90, abs=0.01)
        assert it.status == "ВЫШЕ"


# ═══════════════════════════════════════════════════════════
# 7. Full pipeline integration: RDW-SD / RDW-CV
# ═══════════════════════════════════════════════════════════

CITILAB_RDW_TEXT = """\
флИндекс распределения эритроцитов (RDW-SD) 37.90* 38.56 - 50.281001
%Индекс распределения эритроцитов (RDW-CV) 12.50 11.43 - 13.901001
"""


class TestPipelineRDW:

    @pytest.fixture(autouse=True)
    def setup(self):
        candidates = universal_extract(CITILAB_RDW_TEXT)
        self.items = parse_items_from_candidates(candidates)
        self.by_name = _build_lookup(self.items)
        self.all_names = sorted(self.by_name.keys())

    def test_rdw_sd_present(self):
        assert "RDW-SD" in self.by_name, f"RDW-SD not found. Available: {self.all_names}"
        it = self.by_name["RDW-SD"][0]
        assert it.value == pytest.approx(37.9, abs=0.1)
        assert it.ref is not None
        assert it.ref.low == pytest.approx(38.56, abs=0.1)
        assert it.ref.high == pytest.approx(50.28, abs=0.1)

    def test_rdw_cv_present(self):
        assert "RDW-CV" in self.by_name, f"RDW-CV not found. Available: {self.all_names}"
        it = self.by_name["RDW-CV"][0]
        assert it.value == pytest.approx(12.5, abs=0.1)
        assert it.ref is not None
        assert it.ref.low == pytest.approx(11.43, abs=0.1)
        assert it.ref.high == pytest.approx(13.90, abs=0.1)


# ═══════════════════════════════════════════════════════════
# 8. Full pipeline integration: LDL
# ═══════════════════════════════════════════════════════════

CITILAB_LDL_TEXT = """\
ммоль/лЛипопротеины низкой плотности (ЛПНП, LDL) - прямое определение 1.83 0.10 - 4.141090
ммоль/лХолестерин общий 3.45 3.20 - 5.205
"""


class TestPipelineLDL:

    @pytest.fixture(autouse=True)
    def setup(self):
        candidates = universal_extract(CITILAB_LDL_TEXT)
        self.items = parse_items_from_candidates(candidates)
        self.by_name = _build_lookup(self.items)
        self.all_names = sorted(self.by_name.keys())

    def test_ldl_present(self):
        assert "LDL" in self.by_name, f"LDL not found. Available: {self.all_names}"
        it = self.by_name["LDL"][0]
        assert it.value == pytest.approx(1.83, abs=0.01)
        assert it.ref is not None
        assert it.ref.low == pytest.approx(0.10, abs=0.01)
        assert it.ref.high == pytest.approx(4.14, abs=0.01)

    def test_opredelenie_not_present(self):
        for name in self.all_names:
            assert "определение" not in name.lower(), (
                f"'определение' found as biomarker name: {name}"
            )
        for name in self.all_names:
            assert "ОПРЕДЕЛЕНИЕ" not in name, (
                f"'ОПРЕДЕЛЕНИЕ' found as biomarker name: {name}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
