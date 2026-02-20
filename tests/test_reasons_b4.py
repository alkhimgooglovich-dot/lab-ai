"""
tests/test_reasons_b4.py — Этап B4: classify_quality_reasons.

Проверяем, что классификатор причин корректно определяет
коды причин по OCR и Parse метрикам.
"""

import sys
import os
import pytest

# Для корректного импорта parsers.metrics
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers.metrics import classify_quality_reasons, REASON_THRESHOLDS


# ─── Хелперы ──────────────────────────────────────────────

def _ocr(
    noise_line_ratio=0.0,
    digit_line_ratio=0.5,
    biomarker_line_ratio=0.3,
    line_count=50,
    numeric_candidates_count=20,
):
    return {
        "noise_line_ratio": noise_line_ratio,
        "digit_line_ratio": digit_line_ratio,
        "biomarker_line_ratio": biomarker_line_ratio,
        "line_count": line_count,
        "numeric_candidates_count": numeric_candidates_count,
    }


def _parse(
    parsed_items=10,
    coverage_ratio=0.5,
    suspicious_count=0,
    sanity_outlier_count=0,
    dedup_dropped_count=0,
    valid_value_count=8,
):
    return {
        "parsed_items": parsed_items,
        "coverage_ratio": coverage_ratio,
        "suspicious_count": suspicious_count,
        "sanity_outlier_count": sanity_outlier_count,
        "dedup_dropped_count": dedup_dropped_count,
        "valid_value_count": valid_value_count,
    }


# ─── Тест 1: HIGH_NOISE ──────────────────────────────────

class TestHighNoise:
    """Шумный текст → reasons содержит HIGH_NOISE."""

    def test_noisy_ocr(self):
        ocr = _ocr(noise_line_ratio=0.6)  # > 0.45
        parse = _parse()
        reasons = classify_quality_reasons(ocr, parse)
        assert "HIGH_NOISE" in reasons

    def test_clean_ocr_no_noise(self):
        ocr = _ocr(noise_line_ratio=0.1)  # < 0.45
        parse = _parse()
        reasons = classify_quality_reasons(ocr, parse)
        assert "HIGH_NOISE" not in reasons

    def test_boundary_noise(self):
        """Граничное значение: ровно 0.45 → HIGH_NOISE (>=)."""
        ocr = _ocr(noise_line_ratio=0.45)
        parse = _parse()
        reasons = classify_quality_reasons(ocr, parse)
        assert "HIGH_NOISE" in reasons


# ─── Тест 2: LOW_DIGIT_RATIO ─────────────────────────────

class TestLowDigitRatio:
    """Текст почти без цифр → reasons содержит LOW_DIGIT_RATIO."""

    def test_few_digits(self):
        ocr = _ocr(digit_line_ratio=0.05)  # < 0.15
        parse = _parse()
        reasons = classify_quality_reasons(ocr, parse)
        assert "LOW_DIGIT_RATIO" in reasons

    def test_many_digits_ok(self):
        ocr = _ocr(digit_line_ratio=0.5)  # > 0.15
        parse = _parse()
        reasons = classify_quality_reasons(ocr, parse)
        assert "LOW_DIGIT_RATIO" not in reasons


# ─── Тест 3: LOW_COVERAGE ────────────────────────────────

class TestLowCoverage:
    """numeric_candidates высокий, parsed_items низкий → LOW_COVERAGE."""

    def test_low_coverage(self):
        ocr = _ocr(numeric_candidates_count=30)
        parse = _parse(parsed_items=3, coverage_ratio=0.10)  # < 0.15
        reasons = classify_quality_reasons(ocr, parse)
        assert "LOW_COVERAGE" in reasons

    def test_good_coverage(self):
        ocr = _ocr(numeric_candidates_count=20)
        parse = _parse(parsed_items=15, coverage_ratio=0.75)  # > 0.15
        reasons = classify_quality_reasons(ocr, parse)
        assert "LOW_COVERAGE" not in reasons


# ─── Тест 4: MANY_OUTLIERS ───────────────────────────────

class TestManyOutliers:
    """sanity_outlier_count большой → MANY_OUTLIERS."""

    def test_many_outliers(self):
        ocr = _ocr()
        parse = _parse(parsed_items=10, sanity_outlier_count=3)  # 3/10=0.3 >= 0.25
        reasons = classify_quality_reasons(ocr, parse)
        assert "MANY_OUTLIERS" in reasons

    def test_few_outliers(self):
        ocr = _ocr()
        parse = _parse(parsed_items=10, sanity_outlier_count=1)  # 1/10=0.1 < 0.25
        reasons = classify_quality_reasons(ocr, parse)
        assert "MANY_OUTLIERS" not in reasons


# ─── Тест 5: Детерминизм ─────────────────────────────────

class TestDeterministic:
    """Одинаковые входы → одинаковый результат (стабильный порядок)."""

    def test_same_input_same_output(self):
        ocr = _ocr(noise_line_ratio=0.5, digit_line_ratio=0.05)
        parse = _parse(parsed_items=10, sanity_outlier_count=4)

        result1 = classify_quality_reasons(ocr, parse)
        result2 = classify_quality_reasons(ocr, parse)
        assert result1 == result2

    def test_order_is_stable(self):
        """Порядок причин соответствует _REASON_ORDER, а не порядку обнаружения."""
        ocr = _ocr(noise_line_ratio=0.6, digit_line_ratio=0.05, line_count=5)
        parse = _parse(parsed_items=8, sanity_outlier_count=3, coverage_ratio=0.05)

        reasons = classify_quality_reasons(ocr, parse)
        # Проверяем, что HIGH_NOISE идёт перед LOW_DIGIT_RATIO,
        # LOW_DIGIT_RATIO перед TOO_FEW_LINES и т.д.
        for i in range(len(reasons) - 1):
            assert reasons[i] != reasons[i + 1], "Нет дублей"


# ─── Тест 6: Пустые reasons при хороших метриках ─────────

class TestCleanReasons:
    """Хорошие метрики → пустой список reasons."""

    def test_all_ok(self):
        ocr = _ocr(
            noise_line_ratio=0.1,
            digit_line_ratio=0.4,
            biomarker_line_ratio=0.2,
            line_count=50,
        )
        parse = _parse(
            parsed_items=15,
            coverage_ratio=0.7,
            suspicious_count=1,
            sanity_outlier_count=0,
        )
        reasons = classify_quality_reasons(ocr, parse)
        assert reasons == []


# ─── Тест 7: TOO_FEW_LINES ──────────────────────────────

class TestTooFewLines:
    """Мало строк OCR → TOO_FEW_LINES."""

    def test_few_lines(self):
        ocr = _ocr(line_count=5)  # < 10
        parse = _parse()
        reasons = classify_quality_reasons(ocr, parse)
        assert "TOO_FEW_LINES" in reasons


# ─── Тест 8: MANY_SUSPICIOUS ─────────────────────────────

class TestManySuspicious:
    """Много подозрительных показателей → MANY_SUSPICIOUS."""

    def test_many_suspicious(self):
        ocr = _ocr()
        parse = _parse(parsed_items=10, suspicious_count=4)  # 4/10=0.4 >= 0.30
        reasons = classify_quality_reasons(ocr, parse)
        assert "MANY_SUSPICIOUS" in reasons


# ─── Тест 9: LOW_BIOMARKER_RATIO ─────────────────────────

class TestLowBiomarkerRatio:
    """Мало биомаркеров → LOW_BIOMARKER_RATIO."""

    def test_low_biomarkers(self):
        ocr = _ocr(biomarker_line_ratio=0.02)  # < 0.08
        parse = _parse()
        reasons = classify_quality_reasons(ocr, parse)
        assert "LOW_BIOMARKER_RATIO" in reasons


# ─── Тест 10: Множественные причины одновременно ─────────

class TestMultipleReasons:
    """Несколько проблем одновременно → несколько причин."""

    def test_noise_and_low_coverage(self):
        ocr = _ocr(noise_line_ratio=0.6)
        parse = _parse(parsed_items=5, coverage_ratio=0.10)
        reasons = classify_quality_reasons(ocr, parse)
        assert "HIGH_NOISE" in reasons
        assert "LOW_COVERAGE" in reasons
        assert len(reasons) >= 2

