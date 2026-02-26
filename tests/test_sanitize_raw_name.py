"""
Тесты очистки raw_name от мусорных фрагментов
(коды приказов МЗ РФ, биоматериал, коды услуг).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine import sanitize_raw_name


class TestSanitizeRawName:
    """Тесты функции sanitize_raw_name."""

    def test_removes_prikaz(self):
        """Удаляет (Приказ МЗ РФ № 804н)."""
        s = "Аланинаминотрансфераза (АЛТ) (венозная кровь) A09.05.042 (Приказ МЗ РФ № 804н)"
        result = sanitize_raw_name(s)
        assert "Приказ" not in result
        assert "804н" not in result

    def test_removes_service_code(self):
        """Удаляет коды A09.05.XXX."""
        s = "Лактатдегидрогеназа (ЛДГ) (венозная кровь) A09.05.039 (Приказ МЗ РФ № 804н)"
        result = sanitize_raw_name(s)
        assert "A09" not in result

    def test_removes_biomaterial(self):
        """Удаляет (венозная кровь)."""
        s = "Креатинин (венозная кровь)"
        result = sanitize_raw_name(s)
        assert "венозная" not in result
        assert result.strip() == "Креатинин"

    def test_removes_serum(self):
        """Удаляет (сыворотка крови)."""
        s = "Калий (K+) (сыворотка крови)"
        result = sanitize_raw_name(s)
        assert "сыворотка" not in result

    def test_preserves_marker_code_alt(self):
        """Сохраняет (АЛТ) — код показателя."""
        s = "Аланинаминотрансфераза (АЛТ) (венозная кровь) A09.05.042"
        result = sanitize_raw_name(s)
        assert "(АЛТ)" in result

    def test_preserves_marker_code_ldg(self):
        """Сохраняет (ЛДГ) — код показателя."""
        s = "Лактатдегидрогеназа (ЛДГ) (венозная кровь) A09.05.039"
        result = sanitize_raw_name(s)
        assert "(ЛДГ)" in result

    def test_preserves_marker_code_crp(self):
        """Сохраняет (СРБ) — код показателя."""
        s = "С-реактивный белок (СРБ) A09.05.009 (Приказ МЗ РФ № 804н)"
        result = sanitize_raw_name(s)
        assert "(СРБ)" in result
        assert "Приказ" not in result

    def test_removes_date(self):
        """Удаляет 'Дата исследования: ...'."""
        s = "Глюкоза A09.05.023 (Приказ МЗ РФ № 804н) Дата исследования: 17.02.2026;"
        result = sanitize_raw_name(s)
        assert "Дата" not in result
        assert "17.02" not in result

    def test_multiple_service_codes(self):
        """Удаляет несколько кодов через запятую."""
        s = "Индекс атерогенности: холестерин общий, ЛПВП (венозная кровь) A09.05.026, A09.05.004 (Приказ МЗ РФ № 804н)"
        result = sanitize_raw_name(s)
        assert "A09" not in result
        assert "Приказ" not in result
        assert "Индекс атерогенности" in result

    def test_clean_result_no_trailing_junk(self):
        """Результат не содержит висячих запятых и пробелов."""
        s = "Общий белок (венозная кровь) A09.05.010 (Приказ МЗ РФ № 804н)"
        result = sanitize_raw_name(s)
        assert not result.endswith(",")
        assert not result.endswith(";")
        assert not result.endswith(" ")

    def test_simple_name_unchanged(self):
        """Простое имя без мусора — не меняется."""
        s = "Глюкоза"
        assert sanitize_raw_name(s) == "Глюкоза"

    def test_empty_string(self):
        """Пустая строка → пустая строка."""
        assert sanitize_raw_name("") == ""

    def test_ldh_full_gemotest_line(self):
        """Полная строка ЛДГ из Гемотест — должна очиститься до человеческого вида."""
        s = "Лактатдегидрогеназа (ЛДГ) (венозная кровь) A09.05.039 (Приказ МЗ РФ № 804н)"
        result = sanitize_raw_name(s)
        assert "Лактатдегидрогеназа" in result
        assert "(ЛДГ)" in result
        assert "A09" not in result
        assert "Приказ" not in result
        assert "венозная" not in result

    def test_photometry_biomaterial(self):
        """Удаляет (кровь, фотометрия)."""
        s = "Кальций общий (кровь, фотометрия) A09.05.032"
        result = sanitize_raw_name(s)
        assert "фотометрия" not in result
        assert "Кальций общий" in result

