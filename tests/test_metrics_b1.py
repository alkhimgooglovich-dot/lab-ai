"""
Тесты для B1-метрик (parsers/metrics.py).
"""

import sys
import os
import pytest

# Для корректного импорта parsers.metrics
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers.metrics import (
    compute_ocr_quality_metrics,
    compute_parse_metrics,
    compute_parse_score,
)


# ══════════════════════════════════════════
# Хелпер: фейковый Item
# ══════════════════════════════════════════

class FakeItem:
    def __init__(self, name="WBC", value=5.0, ref=None, unit=None):
        self.name = name
        self.value = value
        self.ref = ref
        self.unit = unit
        self.raw_name = name
        self.ref_text = None
        self.confidence = 0.9
        self.status = "НОРМА"


# ══════════════════════════════════════════
# 1. Пустой текст
# ══════════════════════════════════════════

class TestEmptyTextMetrics:
    def test_empty_string(self):
        ocr = compute_ocr_quality_metrics("")
        assert ocr["line_count"] == 0
        assert ocr["numeric_candidates_count"] == 0

    def test_none_like_empty(self):
        ocr = compute_ocr_quality_metrics("   ")
        assert ocr["line_count"] == 0  # только пробелы → strip() даёт пустоту
        assert ocr["numeric_candidates_count"] == 0

    def test_score_from_empty(self):
        ocr = compute_ocr_quality_metrics("")
        parse = compute_parse_metrics([])
        score = compute_parse_score(ocr, parse)
        assert 0 <= score <= 100


# ══════════════════════════════════════════
# 2. Шумный текст
# ══════════════════════════════════════════

class TestNoisyTextMetrics:
    def test_high_noise_ratio(self):
        noisy = "\n".join([
            "|||||||||||",
            "***********",
            "???????????",
            "□□□□□□□□□□□",
            "WBC 5.2 10^9/л 4.0-9.0",  # единственная полезная строка
        ])
        ocr = compute_ocr_quality_metrics(noisy)
        # 4 из 5 строк — шум
        assert ocr["noise_line_ratio"] >= 0.5

    def test_garbage_symbols(self):
        garbage = "�\n" * 10 + "HGB 140 г/л"
        ocr = compute_ocr_quality_metrics(garbage)
        assert ocr["noise_line_ratio"] > 0.5


# ══════════════════════════════════════════
# 3. Синтетический набор 10 показателей
# ══════════════════════════════════════════

class TestSyntheticParseRows10:
    def test_parsed_items_10(self):
        items = [FakeItem(name=f"MARKER_{i}", value=float(i)) for i in range(10)]
        parse = compute_parse_metrics(items)
        assert parse["parsed_items"] == 10

    def test_valid_from_quality_dict(self):
        items = [FakeItem() for _ in range(10)]
        qd = {
            "valid_value_count": 8,
            "suspicious_count": 1,
            "sanity_outlier_count": 1,
            "duplicate_dropped_count": 0,
        }
        parse = compute_parse_metrics(items, quality_dict=qd)
        assert parse["parsed_items"] == 10
        assert parse["valid_value_count"] == 8
        assert parse["suspicious_count"] == 1
        assert parse["sanity_outlier_count"] == 1


# ══════════════════════════════════════════
# 4. Порядок score: хороший > плохого
# ══════════════════════════════════════════

class TestScoreOrdering:
    def test_good_beats_bad(self):
        # Хороший OCR: 20 строк с цифрами, биомаркеры, мало шума
        good_text = "\n".join([
            f"WBC 5.2 10^9/л 4.0-9.0",
            f"RBC 4.5 10^12/л 3.9-5.0",
            f"HGB 140 г/л 120-160",
            f"HCT 42 % 36-48",
            f"PLT 250 10^9/л 150-400",
            f"ALT 25 Ед/л 0-40",
            f"AST 22 Ед/л 0-40",
            f"GLUC 5.1 ммоль/л 3.9-6.1",
            f"CREA 80 мкмоль/л 44-106",
            f"UREA 5.0 ммоль/л 2.1-8.2",
            f"CRP 1.2 мг/л 0-5",
            f"CHOL 4.8 ммоль/л 0-5.2",
        ])
        ocr_good = compute_ocr_quality_metrics(good_text)

        good_items = [FakeItem(name=n, value=v) for n, v in [
            ("WBC", 5.2), ("RBC", 4.5), ("HGB", 140), ("HCT", 42),
            ("PLT", 250), ("ALT", 25), ("AST", 22), ("GLUC", 5.1),
            ("CREA", 80), ("UREA", 5.0), ("CRP", 1.2), ("CHOL", 4.8),
        ]]
        parse_good = compute_parse_metrics(good_items)
        score_good = compute_parse_score(ocr_good, parse_good)

        # Плохой OCR: много шума, мало полезного
        bad_text = "\n".join([
            "|||||||",
            "????????",
            "***",
            "□□□□",
            "──────",
            "WBC 5.2",
        ])
        ocr_bad = compute_ocr_quality_metrics(bad_text)
        bad_items = [FakeItem(name="WBC", value=5.2)]
        parse_bad = compute_parse_metrics(bad_items)
        score_bad = compute_parse_score(ocr_bad, parse_bad)

        assert score_good > score_bad


# ══════════════════════════════════════════
# 5. score всегда в [0, 100]
# ══════════════════════════════════════════

class TestScoreRange:
    @pytest.mark.parametrize("parsed,valid,candidates,noise", [
        (0, 0, 0, 0.0),
        (100, 100, 10, 0.0),
        (5, 3, 100, 1.0),
        (0, 0, 0, 1.0),
        (50, 50, 50, 0.5),
        (1, 1, 1, 0.0),
    ])
    def test_score_in_range(self, parsed, valid, candidates, noise):
        ocr = {"numeric_candidates_count": candidates, "noise_line_ratio": noise}
        parse = {"parsed_items": parsed, "valid_value_count": valid}
        score = compute_parse_score(ocr, parse)
        assert 0 <= score <= 100, f"score={score} out of range"


# ══════════════════════════════════════════
# 6. Дополнительно: biomarker_line_ratio
# ══════════════════════════════════════════

class TestBiomarkerDetection:
    def test_biomarker_lines_detected(self):
        text = "WBC 5.2\nRBC 4.5\nКакой-то текст\nHGB 140"
        ocr = compute_ocr_quality_metrics(text)
        assert ocr["biomarker_line_ratio"] > 0.5

    def test_no_biomarkers(self):
        text = "Привет мир\nТест строка\nЕщё строка"
        ocr = compute_ocr_quality_metrics(text)
        assert ocr["biomarker_line_ratio"] == 0.0

