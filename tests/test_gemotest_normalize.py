"""
Тесты: нормализация имён Гемотеста — % показатели, МСН, МСНС, СРБ.

Запуск: pytest tests/test_gemotest_normalize.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import normalize_name, clean_raw_name, parse_items_from_candidates, assign_confidence, deduplicate_items


class TestPercentNormalization:
    """% показатели получают коды с % (NE%, EO% и т.д.)"""

    def test_neutrophils_pct(self):
        assert normalize_name(clean_raw_name("Нейтрофилы сегментоядерные %")) == "NE%"

    def test_neutrophils_abs(self):
        """Абсолютные нейтрофилы → NE_SEG (не NE%)."""
        result = normalize_name(clean_raw_name("Нейтрофилы сегментоядерные"))
        assert result == "NE_SEG"

    def test_eosinophils_pct(self):
        assert normalize_name(clean_raw_name("Эозинофилы %")) == "EO%"

    def test_eosinophils_abs(self):
        assert normalize_name(clean_raw_name("Эозинофилы")) == "EO"

    def test_basophils_pct(self):
        assert normalize_name(clean_raw_name("Базофилы %")) == "BA%"

    def test_monocytes_pct(self):
        assert normalize_name(clean_raw_name("Моноциты %")) == "MO%"

    def test_lymphocytes_pct(self):
        assert normalize_name(clean_raw_name("Лимфоциты %")) == "LY%"

    def test_pct_and_abs_not_deduped(self):
        """% и абсолютные версии не дедуплицируются."""
        candidates = "Нейтрофилы сегментоядерные\t1.99\t1.5-6.8\tx10^9/л\nНейтрофилы сегментоядерные %\t48.8\t37.95-71.44\t%"
        items = parse_items_from_candidates(candidates)
        assign_confidence(items)
        result = deduplicate_items(items)
        if isinstance(result, tuple):
            result = result[0]
        names = [it.name for it in result]
        assert len(result) == 2, f"Expected 2 items, got {len(result)}: {names}"


class TestMchMchcNormalization:
    """МСН и МСНС не маппятся в RBC."""

    def test_mch_full_name(self):
        name = "Среднее содержание Hb в эритроците (МСН)"
        result = normalize_name(clean_raw_name(name))
        assert result == "MCH", f"Got {result}"

    def test_mchc_full_name(self):
        name = "Средняя концентрация Hb в эритроцитах (МСНС)"
        result = normalize_name(clean_raw_name(name))
        assert result == "MCHC", f"Got {result}"

    def test_mch_partial(self):
        """Частичное имя 'в эритроците (МСН)' тоже должно дать MCH."""
        name = "в эритроците (МСН)"
        result = normalize_name(clean_raw_name(name))
        assert result == "MCH", f"Got {result}"

    def test_mchc_partial(self):
        name = "в эритроцитах (МСНС)"
        result = normalize_name(clean_raw_name(name))
        assert result == "MCHC", f"Got {result}"

    def test_rbc_still_rbc(self):
        """Эритроциты по-прежнему → RBC."""
        assert normalize_name(clean_raw_name("Эритроциты")) == "RBC"


class TestCrpNormalization:

    def test_crp_full(self):
        assert normalize_name(clean_raw_name("С-реактивный белок (СРБ)")) == "CRP"

    def test_crp_short(self):
        assert normalize_name(clean_raw_name("С-реактивный белок")) == "CRP"


class TestNoiseFiltering:
    """ГОСТ-строки не попадают в итоговые кандидаты."""

    def test_gost_filtered(self):
        candidates = "Гемоглобин\t144\t132-172\tг/л\nГОСТ Р ИСО\t9001\t9001-2015\t-2015"
        items = parse_items_from_candidates(candidates)
        names = [it.name for it in items]
        for name in names:
            assert "ГОСТ" not in name and "9001" not in str(name), f"ГОСТ мусор в items: {names}"





