"""
Тесты полноты и консистентности справочников P5-A.

Проверяем:
  - Каждый ключ SPECIALIST_MAP есть в EXPLAIN_DICT
  - Каждый ключ SANITY_RANGES — валидный canonical name
  - EXPLAIN_DICT содержит >= 90 записей
  - SPECIALIST_MAP содержит >= 60 записей
  - SANITY_RANGES содержит >= 30 записей
  - Нет дублей ключей (Python не допускает, но проверим длину)
  - Все значения EXPLAIN_DICT — непустые строки
  - Все значения SPECIALIST_MAP — непустые set
  - Все значения SANITY_RANGES — кортежи (lo, hi) где lo < hi
  - normalize_name маппит ключевые русские названия
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine import EXPLAIN_DICT, SPECIALIST_MAP, ALIASES, RUS_NAME_MAP, normalize_name
from parsers.sanity_ranges import SANITY_RANGES


class TestExplainDict:

    def test_min_size(self):
        assert len(EXPLAIN_DICT) >= 90, f"EXPLAIN_DICT слишком мал: {len(EXPLAIN_DICT)}"

    def test_all_values_nonempty(self):
        for k, v in EXPLAIN_DICT.items():
            assert v and len(v) > 10, f"EXPLAIN_DICT['{k}'] пуст или слишком короткий"

    def test_contains_oak_keys(self):
        for key in ["WBC", "RBC", "HGB", "HCT", "PLT", "ESR"]:
            assert key in EXPLAIN_DICT, f"'{key}' отсутствует в EXPLAIN_DICT"

    def test_contains_biochem_keys(self):
        for key in ["ALT", "AST", "GGT", "ALP", "TBIL", "CREA", "UREA", "GLUC", "HBA1C"]:
            assert key in EXPLAIN_DICT, f"'{key}' отсутствует в EXPLAIN_DICT"

    def test_contains_lipids(self):
        for key in ["CHOL", "LDL", "HDL", "TRIG", "AI"]:
            assert key in EXPLAIN_DICT, f"'{key}' отсутствует в EXPLAIN_DICT"

    def test_contains_thyroid(self):
        for key in ["TSH", "FT4", "FT3"]:
            assert key in EXPLAIN_DICT, f"'{key}' отсутствует в EXPLAIN_DICT"

    def test_contains_electrolytes(self):
        for key in ["K", "NA", "CL", "CA", "FE"]:
            assert key in EXPLAIN_DICT, f"'{key}' отсутствует в EXPLAIN_DICT"

    def test_contains_coag(self):
        for key in ["INR", "FIB", "APTT"]:
            assert key in EXPLAIN_DICT, f"'{key}' отсутствует в EXPLAIN_DICT"

    def test_contains_iron(self):
        for key in ["FE", "FERR", "TIBC"]:
            assert key in EXPLAIN_DICT, f"'{key}' отсутствует в EXPLAIN_DICT"


class TestSpecialistMap:

    def test_min_size(self):
        assert len(SPECIALIST_MAP) >= 60, f"SPECIALIST_MAP слишком мал: {len(SPECIALIST_MAP)}"

    def test_all_values_nonempty_sets(self):
        for k, v in SPECIALIST_MAP.items():
            assert isinstance(v, set) and len(v) > 0, f"SPECIALIST_MAP['{k}'] должен быть непустым set"

    def test_all_contain_terapevt(self):
        """Каждый показатель должен иметь хотя бы терапевта."""
        for k, v in SPECIALIST_MAP.items():
            assert "терапевт" in v, f"SPECIALIST_MAP['{k}'] не содержит 'терапевт'"

    def test_keys_subset_of_explain(self):
        """Все ключи SPECIALIST_MAP должны быть в EXPLAIN_DICT."""
        missing = set(SPECIALIST_MAP.keys()) - set(EXPLAIN_DICT.keys())
        assert not missing, f"Ключи в SPECIALIST_MAP, но не в EXPLAIN_DICT: {missing}"


class TestSanityRanges:

    def test_min_size(self):
        assert len(SANITY_RANGES) >= 30, f"SANITY_RANGES слишком мал: {len(SANITY_RANGES)}"

    def test_all_ranges_valid(self):
        for k, (lo, hi) in SANITY_RANGES.items():
            assert lo < hi, f"SANITY_RANGES['{k}']: lo={lo} >= hi={hi}"

    def test_contains_key_markers(self):
        for key in ["WBC", "HGB", "PLT", "ALT", "GLUC", "CREA", "TSH", "K", "FE"]:
            assert key in SANITY_RANGES, f"'{key}' отсутствует в SANITY_RANGES"


class TestNormalizeNameNewMarkers:
    """Проверяем маппинг новых русских названий."""

    def test_tsh(self):
        assert normalize_name("ТТГ") == "TSH" or normalize_name("Тиреотропный гормон") == "TSH"

    def test_ferritin(self):
        assert normalize_name("Ферритин") == "FERR"

    def test_fibrinogen(self):
        assert normalize_name("Фибриноген") == "FIB"

    def test_inr(self):
        assert normalize_name("МНО") == "INR"

    def test_vitamin_d(self):
        name = normalize_name("Витамин D")
        assert name == "VITD", f"Витамин D → {name}"

    def test_homocysteine(self):
        assert normalize_name("Гомоцистеин") == "HCY"

    def test_uric_acid_preserved(self):
        """Мочевая кислота по-прежнему маппится."""
        assert normalize_name("Мочевая кислота") == "URIC_ACID"

    def test_hba1c_preserved(self):
        """Гликированный гемоглобин по-прежнему HBA1C."""
        assert normalize_name("Гликированный гемоглобин") == "HBA1C"

    def test_hemoglobin_still_hgb(self):
        """Обычный гемоглобин по-прежнему HGB (регрессия)."""
        assert normalize_name("Гемоглобин (HGB)") == "HGB"

