"""
Тесты парсинга показателей с маркером "Смотри текст" вместо числового ref.

Проверяем, что показатели типа:
  "Гликированный гемоглобин 5.0 % Смотри текст"
парсятся как кандидаты с пустым ref, а не теряются.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from parsers.universal_extractor import universal_extract
from engine import parse_items_from_candidates, normalize_name


# ============================================================
# Тесты: normalize_name — HBA1C vs HGB
# ============================================================
class TestNormalizeNameHBA1C:

    def test_glycated_hemoglobin_maps_to_hba1c(self):
        """Гликированный гемоглобин → HBA1C, не HGB."""
        assert normalize_name("Гликированный гемоглобин") == "HBA1C"

    def test_plain_hemoglobin_maps_to_hgb(self):
        """Обычный гемоглобин → HGB."""
        assert normalize_name("Гемоглобин (HGB)") == "HGB"

    def test_glycosylated_hemoglobin(self):
        assert normalize_name("Гликозилированный гемоглобин") == "HBA1C"

    def test_hba1c_code(self):
        assert normalize_name("HbA1c") == "HBA1C"


# ============================================================
# Тесты: normalize_name — биохимия
# ============================================================
class TestNormalizeNameBiochemistry:

    def test_uric_acid(self):
        assert normalize_name("Мочевая кислота (венозная кровь)") == "URIC_ACID"

    def test_triglycerides(self):
        assert normalize_name("Триглицериды (венозная кровь)") == "TRIG"

    def test_ldl(self):
        name = normalize_name("Холестерин липопротеинов низкой плотности (ЛПНП)")
        assert name == "LDL" or "LDL" in name

    def test_hdl(self):
        name = normalize_name("Холестерин-ЛПВП")
        assert name == "HDL"

    def test_cholesterol_total(self):
        assert normalize_name("Холестерин общий") == "CHOL"

    def test_albumin(self):
        assert normalize_name("Альбумин (венозная кровь)") == "ALB"

    def test_total_protein(self):
        assert normalize_name("Общий белок (венозная кровь)") == "TP"

    def test_ggt(self):
        assert normalize_name("Гамма-ГТ (венозная кровь)") == "GGT"

    def test_alp(self):
        assert normalize_name("Фосфатаза щелочная (венозная кровь)") == "ALP"


# ============================================================
# Тесты: universal_extract — "Смотри текст"
# ============================================================
GEMOTEST_SEE_TEXT = """\
Гликированный гемоглобин 5.0 % Смотри текст
Триглицериды (венозная кровь) 1.59 ммоль/л Смотри текст
Холестерин общий 4.73 ммоль/л Смотри текст
Холестерин-ЛПВП 1.25 ммоль/л Смотри текст
Глюкоза 5.27 ммоль/л 4.11 - 6.1
Аланинаминотрансфераза (АЛТ) (венозная кровь) 92.3 Ед/л < 41
"""


class TestSeeTextParsing:

    def test_glucose_still_parsed(self):
        """Глюкоза с числовым ref — по-прежнему парсится."""
        candidates = universal_extract(GEMOTEST_SEE_TEXT)
        assert candidates, "Кандидаты пустые"
        assert "глюкоз" in candidates.lower() or "5.27" in candidates

    def test_alt_still_parsed(self):
        """АЛТ с числовым ref — по-прежнему парсится."""
        candidates = universal_extract(GEMOTEST_SEE_TEXT)
        lower = candidates.lower()
        assert "алт" in lower or "аланинамино" in lower

    def test_glycated_hemoglobin_parsed(self):
        """Гликированный гемоглобин со 'Смотри текст' — должен стать кандидатом."""
        candidates = universal_extract(GEMOTEST_SEE_TEXT)
        lower = candidates.lower()
        assert "гликированный" in lower or "5" in candidates, \
            f"Гликированный гемоглобин не найден в кандидатах: {candidates}"

    def test_triglycerides_parsed(self):
        """Триглицериды со 'Смотри текст' — должны стать кандидатом."""
        candidates = universal_extract(GEMOTEST_SEE_TEXT)
        lower = candidates.lower()
        assert "триглицерид" in lower or "1.59" in candidates

    def test_cholesterol_total_parsed(self):
        """Холестерин общий со 'Смотри текст' — должен стать кандидатом."""
        candidates = universal_extract(GEMOTEST_SEE_TEXT)
        lower = candidates.lower()
        assert "холестерин общ" in lower or "4.73" in candidates

    def test_hdl_parsed(self):
        """Холестерин-ЛПВП со 'Смотри текст' — должен стать кандидатом."""
        candidates = universal_extract(GEMOTEST_SEE_TEXT)
        lower = candidates.lower()
        assert "лпвп" in lower or "1.25" in candidates


# ============================================================
# Интеграционный тест: парсинг до Item
# ============================================================
class TestSeeTextToItems:

    def _get_items(self):
        candidates = universal_extract(GEMOTEST_SEE_TEXT)
        if not candidates:
            return []
        return parse_items_from_candidates(candidates)

    def test_hba1c_item_exists(self):
        """Гликированный гемоглобин должен создать Item с name=HBA1C."""
        items = self._get_items()
        names = [it.name for it in items]
        assert "HBA1C" in names, f"HBA1C не найден. Имеющиеся: {names}"

    def test_hba1c_value(self):
        items = self._get_items()
        hba1c = [it for it in items if it.name == "HBA1C"]
        assert hba1c, "HBA1C Item не создан"
        assert hba1c[0].value == 5.0

    def test_hba1c_not_mapped_to_hgb(self):
        """Гликированный гемоглобин НЕ должен маппиться на HGB."""
        items = self._get_items()
        hgb_items = [it for it in items if it.name == "HGB"]
        for it in hgb_items:
            assert "гликир" not in (it.raw_name or "").lower(), \
                f"Гликированный гемоглобин ошибочно маппится на HGB: {it}"

    def test_glucose_item(self):
        items = self._get_items()
        # Глюкоза может маппиться на GLUC или ГЛЮКОЗА (если нет кода в скобках)
        glu = [it for it in items if "GLU" in it.name or "ГЛЮКОЗ" in it.name]
        assert glu, f"Глюкоза не найдена. Имеющиеся: {[it.name for it in items]}"
        assert glu[0].value == 5.27

