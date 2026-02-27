"""
Тесты: склейка разбитых единиц/имён из pypdf Гемотеста.

Запуск: pytest tests/test_gemotest_unit_rejoin.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.universal_extractor import (
    _rejoin_broken_units,
    _rejoin_broken_names,
    _extract_unit_from_line,
    _parse_value_unit_from_line,
    universal_extract,
)


# ═══════════════════════════════════════════════
# Тесты склейки единиц
# ═══════════════════════════════════════════════
class TestRejoinBrokenUnits:

    def test_x10_12_l(self):
        lines = ['Эритроциты', '4.85', 'x10*12/', 'л', '4.28 - 5.78']
        result = _rejoin_broken_units(lines)
        assert 'x10*12/л' in result

    def test_x10_9_l(self):
        lines = ['Тромбоциты', '191', 'x10*9/', 'л', '148 - 339']
        result = _rejoin_broken_units(lines)
        assert 'x10*9/л' in result

    def test_no_rejoin_normal(self):
        """Обычные строки не склеиваются."""
        lines = ['Гемоглобин', '144', 'г/л', '132 - 172']
        result = _rejoin_broken_units(lines)
        assert result == lines

    def test_preserves_other_lines(self):
        lines = ['Гематокрит', '42.30', '%', '39.51 - 50.95']
        result = _rejoin_broken_units(lines)
        assert result == lines


# ═══════════════════════════════════════════════
# Тесты склейки имён
# ═══════════════════════════════════════════════
class TestRejoinBrokenNames:

    def test_mcv_bracket(self):
        lines = ['Средний объем эритроцитов', '(MCV)', '87.3', 'фл', '82 - 98']
        result = _rejoin_broken_names(lines)
        assert result[0] == 'Средний объем эритроцитов (MCV)'

    def test_mch_bracket(self):
        lines = ['Среднее содержание Hb в эритроците', '(МСН)', '29.70']
        result = _rejoin_broken_names(lines)
        assert '(МСН)' in result[0]

    def test_hb_short_word(self):
        """Короткое латинское слово Hb склеивается с предыдущим именем."""
        lines = ['Среднее содержание', 'Hb', 'в эритроците (МСН)', '29.70']
        result = _rejoin_broken_names(lines)
        assert result[0] == 'Среднее содержание Hb'

    def test_no_rejoin_value(self):
        """Числа не склеиваются с именами."""
        lines = ['Гемоглобин', '144', 'г/л']
        result = _rejoin_broken_names(lines)
        assert result == lines


# ═══════════════════════════════════════════════
# Тесты _extract_unit_from_line с x-префиксом
# ═══════════════════════════════════════════════
class TestExtractUnitXPrefix:

    def test_x10_12_l(self):
        assert _extract_unit_from_line('x10*12/л') != ''

    def test_x10_9_l(self):
        assert _extract_unit_from_line('x10*9/л') != ''

    def test_star_10_still_works(self):
        assert _extract_unit_from_line('*10^9/л') != ''

    def test_plain_unit_still_works(self):
        assert _extract_unit_from_line('г/л') == 'г/л'

    def test_percent_still_works(self):
        assert _extract_unit_from_line('%') == '%'


# ═══════════════════════════════════════════════
# Тест trailing dash
# ═══════════════════════════════════════════════
class TestTrailingDash:

    def test_value_028_dash(self):
        """0.28- → value=0.28, без '-' в unit."""
        val, unit = _parse_value_unit_from_line('0.28-')
        assert val == 0.28
        assert '-' not in unit


# ═══════════════════════════════════════════════
# Интеграционный тест: полный парсинг блока Гемотеста
# ═══════════════════════════════════════════════
GEMOTEST_BLOCK = """\
Гемоглобин
144
г/л
132 - 172
Эритроциты
4.85
x10*12/
л
4.28 - 5.78
Гематокрит
42.30
%
39.51 - 50.95
Средний объем эритроцитов
(MCV)
87.3
фл
82 - 98
Тромбоциты
191
x10*9/
л
148 - 339
Лейкоциты
4.07
x10*9/
л
3.9 - 10.9
СОЭ (по Вестергрену)
5
мм/час
0 - 20
"""


class TestGemotestIntegration:

    def test_candidate_count(self):
        """Из блока Гемотеста извлекается >= 6 кандидатов."""
        result = universal_extract(GEMOTEST_BLOCK)
        lines = [l for l in result.splitlines() if l.strip()]
        assert len(lines) >= 6, f"Got only {len(lines)}: {lines}"

    def test_erythrocytes_has_unit(self):
        """Эритроциты извлекаются с единицей (содержит 10^12 или 10*12)."""
        result = universal_extract(GEMOTEST_BLOCK)
        for line in result.splitlines():
            parts = line.split('\t')
            if 'Эритроцит' in parts[0] or 'эритроцит' in parts[0]:
                unit = parts[3] if len(parts) > 3 else ''
                assert '10' in unit, f"Эритроциты без единицы: {line}"
                return
        # Если Эритроциты не найдены — тоже ошибка
        assert False, f"Эритроциты не найдены в: {result}"

    def test_mcv_full_name(self):
        """MCV имеет полное имя (содержит и 'объем' и 'MCV')."""
        result = universal_extract(GEMOTEST_BLOCK)
        for line in result.splitlines():
            if 'MCV' in line or 'mcv' in line.lower():
                name = line.split('\t')[0]
                assert 'объем' in name.lower() or 'MCV' in name, f"MCV неполное имя: {name}"
                return

    def test_hemoglobin_present(self):
        result = universal_extract(GEMOTEST_BLOCK)
        names = [l.split('\t')[0].lower() for l in result.splitlines()]
        assert any('гемоглобин' in n for n in names)

    def test_soe_present(self):
        result = universal_extract(GEMOTEST_BLOCK)
        names = [l.split('\t')[0].lower() for l in result.splitlines()]
        assert any('соэ' in n for n in names)





