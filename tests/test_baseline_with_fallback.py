"""
Тест: baseline не сломался при наличии fallback-модуля.

Проверяем, что:
  1. Импорт fallback-модуля не ломает baseline.
  2. parse_with_fallback на Helix PDF возвращает тот же результат, что и чистый baseline.
  3. evaluate_parse_quality на baseline-результатах показывает высокое качество.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine import (
    try_extract_text_from_pdf_bytes,
    helix_table_to_candidates,
    parse_items_from_candidates,
    parse_with_fallback,
)
from parsers.quality import evaluate_parse_quality
from parsers.fallback_generic import fallback_parse_candidates


TEST_PDF = PROJECT_ROOT / "tests" / "fixtures" / "0333285a-adec-4b5d-9c25-52811a5c1747.pdf"

# Ожидаемые значения — те же, что и в baseline
EXPECTED_VALUES = {
    "WBC": 8.23,
    "RBC": 4.0,
    "HGB": 120.0,
    "HCT": 34.7,
    "ESR": 28.0,
    "PLT": 199.0,
    "NE%": 77.0,
    "LY%": 18.0,
}


def _extract_candidates() -> str:
    """Извлекает кандидатов из PDF через baseline-путь."""
    pdf_bytes = TEST_PDF.read_bytes()
    raw_text = try_extract_text_from_pdf_bytes(pdf_bytes)
    candidates = helix_table_to_candidates(raw_text)
    return candidates


class TestBaselineWithFallback:
    """Проверяем, что fallback не ломает baseline."""

    def test_fallback_import_does_not_break_baseline(self):
        """Импорт fallback-модуля не должен вызывать ошибок."""
        # Если этот тест проходит, значит импорт fallback не сломал engine
        items = _extract_candidates()
        parsed = parse_items_from_candidates(items)
        assert len(parsed) >= 15

    def test_parse_with_fallback_returns_baseline_result(self):
        """
        На Helix PDF parse_with_fallback должен вернуть
        тот же результат, что и чистый baseline.
        """
        candidates = _extract_candidates()

        # Чистый baseline
        baseline_items = parse_items_from_candidates(candidates)

        # Через fallback-оркестратор
        fallback_items = parse_with_fallback(candidates)

        # Количество не должно быть хуже
        assert len(fallback_items) >= len(baseline_items), (
            f"parse_with_fallback вернул меньше показателей: "
            f"{len(fallback_items)} < {len(baseline_items)}"
        )

        # Проверяем ключевые значения
        def _find(items, name):
            return next((it for it in items if it.name == name), None)

        for name, expected_val in EXPECTED_VALUES.items():
            fb_item = _find(fallback_items, name)
            assert fb_item is not None, f"{name} пропал после parse_with_fallback"
            assert fb_item.value == expected_val, (
                f"{name}: baseline={expected_val}, "
                f"parse_with_fallback={fb_item.value}"
            )

    def test_baseline_quality_is_good(self):
        """
        На Helix PDF качество baseline должно быть отличным:
        coverage_score >= 1.0, suspicious_count == 0.
        """
        candidates = _extract_candidates()
        items = parse_items_from_candidates(candidates)
        quality = evaluate_parse_quality(items)

        assert quality["coverage_score"] >= 1.0, (
            f"coverage_score слишком низкий: {quality['coverage_score']}"
        )
        assert quality["suspicious_count"] == 0, (
            f"Обнаружены подозрительные значения: {quality['suspicious_count']}"
        )
        assert quality["error_count"] == 0, (
            f"Обнаружены ошибки парсинга: {quality['error_count']}"
        )

    def test_fallback_not_activated_on_good_baseline(self):
        """
        На Helix PDF fallback НЕ должен активироваться,
        т.к. baseline достаточно хорош.
        """
        candidates = _extract_candidates()

        baseline_items = parse_items_from_candidates(candidates)
        quality = evaluate_parse_quality(baseline_items)

        # Условие активации fallback:
        #   coverage_score < 0.6 OR suspicious_count > 0
        # На хорошем PDF обе проверки должны быть False
        assert quality["coverage_score"] >= 0.6, (
            f"coverage_score слишком низкий: {quality['coverage_score']}"
        )
        assert quality["suspicious_count"] == 0, (
            f"suspicious_count != 0: {quality['suspicious_count']}"
        )

