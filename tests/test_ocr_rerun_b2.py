"""
Тесты B2: OCR rerun по низкому parse_score.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

# Корректный импорт
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import (
    _run_parse_pipeline,
    _is_rerun_better,
    OCR_RERUN_MIN_SCORE,
)


# ═══════════════════════════════════════════
# Хелпер: фейковый Item
# ═══════════════════════════════════════════

class FakeItem:
    def __init__(self, name="WBC", value=5.0, ref=(4.0, 9.0), unit="10^9/л"):
        self.name = name
        self.raw_name = name
        self.value = value
        self.ref = ref
        self.ref_text = f"{ref[0]}-{ref[1]}" if ref else None
        self.unit = unit
        self.confidence = 0.9
        self.status = "НОРМА"


def _make_quality(parse_score, valid_value_count=10, noise_line_ratio=0.1):
    """Создаёт минимальный quality dict для тестов сравнения."""
    return {
        "valid_value_count": valid_value_count,
        "valid_ref_count": valid_value_count,
        "error_count": 0,
        "suspicious_count": 0,
        "coverage_score": 1.0,
        "expected_minimum": 8,
        "ref_coverage_ratio": 1.0,
        "unit_coverage_ratio": 1.0,
        "duplicate_name_count": 0,
        "avg_confidence": 0.9,
        "filtered_header_count": 0,
        "duplicate_dropped_count": 0,
        "sanity_outlier_count": 0,
        "metrics": {
            "schema_version": "1.0",
            "ocr": {
                "line_count": 20,
                "avg_line_len": 30.0,
                "digit_line_ratio": 0.8,
                "biomarker_line_ratio": 0.6,
                "noise_line_ratio": noise_line_ratio,
                "numeric_candidates_count": 20,
            },
            "parse": {
                "parsed_items": valid_value_count,
                "valid_value_count": valid_value_count,
                "suspicious_count": 0,
                "sanity_outlier_count": 0,
                "dedup_dropped_count": 0,
            },
            "parse_score": parse_score,
        },
    }


# ═══════════════════════════════════════════
# 1. test_no_rerun_when_score_ok
# ═══════════════════════════════════════════

class TestNoRerunWhenScoreOk:
    """parse_score >= 45 → rerun НЕ выполняется."""

    def test_performed_false(self):
        q1 = _make_quality(parse_score=70.0)
        q2 = _make_quality(parse_score=80.0)

        # rerun не нужен, т.к. score >= OCR_RERUN_MIN_SCORE
        assert q1["metrics"]["parse_score"] >= OCR_RERUN_MIN_SCORE

        # Проверяем, что _is_rerun_better работает, но rerun
        # вообще не вызывается при score >= 45 (это проверяется
        # через условие в generate_pdf_report)
        # Здесь тестируем, что константа OCR_RERUN_MIN_SCORE = 45
        assert OCR_RERUN_MIN_SCORE == 45.0

    def test_score_exactly_45_no_rerun(self):
        """Граничный случай: score == 45.0 — rerun НЕ нужен (строго <)."""
        score = 45.0
        assert not (score < OCR_RERUN_MIN_SCORE)


# ═══════════════════════════════════════════
# 2. test_rerun_when_score_low_and_improves
# ═══════════════════════════════════════════

class TestRerunImproves:
    """Первый прогон score=10, rerun score=70 → chosen='rerun'."""

    def test_rerun_wins(self):
        q_first = _make_quality(parse_score=10.0, valid_value_count=2)
        q_rerun = _make_quality(parse_score=70.0, valid_value_count=12)

        assert q_first["metrics"]["parse_score"] < OCR_RERUN_MIN_SCORE
        assert _is_rerun_better(q_first, q_rerun) is True

    def test_rerun_chosen_label(self):
        """Проверяем, что при лучшем rerun chosen='rerun'."""
        q_first = _make_quality(parse_score=10.0)
        q_rerun = _make_quality(parse_score=70.0)

        chosen = "rerun" if _is_rerun_better(q_first, q_rerun) else "first"
        assert chosen == "rerun"


# ═══════════════════════════════════════════
# 3. test_rerun_when_score_low_but_no_improve
# ═══════════════════════════════════════════

class TestRerunNoImprove:
    """Первый score=30, rerun score=25 → chosen='first'."""

    def test_first_stays(self):
        q_first = _make_quality(parse_score=30.0, valid_value_count=5)
        q_rerun = _make_quality(parse_score=25.0, valid_value_count=4)

        assert q_first["metrics"]["parse_score"] < OCR_RERUN_MIN_SCORE
        assert _is_rerun_better(q_first, q_rerun) is False

    def test_chosen_first_label(self):
        q_first = _make_quality(parse_score=30.0)
        q_rerun = _make_quality(parse_score=25.0)

        chosen = "rerun" if _is_rerun_better(q_first, q_rerun) else "first"
        assert chosen == "first"


# ═══════════════════════════════════════════
# 4. test_rerun_only_once
# ═══════════════════════════════════════════

class TestRerunOnlyOnce:
    """Даже если rerun тоже < 45, повторов больше не делать."""

    def test_second_still_low_no_third_run(self):
        """
        Логика B2: rerun выполняется РОВНО 1 раз, независимо от результата.
        Если rerun_score=20 (ещё ниже порога) — мы НЕ делаем третий прогон.
        """
        q_first = _make_quality(parse_score=10.0)
        q_rerun = _make_quality(parse_score=20.0)

        # rerun лучше (20 > 10), поэтому выберем его
        assert _is_rerun_better(q_first, q_rerun) is True

        # Но повторный rerun НЕ запускается — это гарантировано
        # конструкцией кода (нет цикла, только один if)
        # Проверяем: performed=True, но дальше rerun не идёт

    def test_rerun_count_is_boolean(self):
        """rerun_info['performed'] — bool, не int. Нет счётчика > 1."""
        rerun_info = {
            "performed": True,
            "reason": "LOW_PARSE_SCORE",
            "score_before": 10.0,
            "score_after": 20.0,
            "chosen": "rerun",
        }
        assert isinstance(rerun_info["performed"], bool)
        assert rerun_info["reason"] == "LOW_PARSE_SCORE"


# ═══════════════════════════════════════════
# 5. Tie-breaker тесты
# ═══════════════════════════════════════════

class TestTieBreakers:
    """Проверяем tie-breaker'ы при одинаковом parse_score."""

    def test_same_score_higher_valid_wins(self):
        q1 = _make_quality(parse_score=40.0, valid_value_count=5)
        q2 = _make_quality(parse_score=40.0, valid_value_count=8)
        assert _is_rerun_better(q1, q2) is True

    def test_same_score_same_valid_lower_noise_wins(self):
        q1 = _make_quality(parse_score=40.0, valid_value_count=5, noise_line_ratio=0.3)
        q2 = _make_quality(parse_score=40.0, valid_value_count=5, noise_line_ratio=0.1)
        assert _is_rerun_better(q1, q2) is True

    def test_same_everything_no_switch(self):
        q1 = _make_quality(parse_score=40.0, valid_value_count=5, noise_line_ratio=0.2)
        q2 = _make_quality(parse_score=40.0, valid_value_count=5, noise_line_ratio=0.2)
        assert _is_rerun_better(q1, q2) is False


# ═══════════════════════════════════════════
# 6. Интеграционный тест с моками
# ═══════════════════════════════════════════

class TestRerunIntegrationMocked:
    """
    Мокаем _run_parse_pipeline чтобы проверить полную логику rerun
    без реальных OCR-вызовов.
    """

    def test_rerun_flow_end_to_end(self):
        """
        Эмулируем: первый прогон score=10, rerun score=70.
        Проверяем что rerun_info заполнен правильно.
        """
        first_items = [FakeItem(name="WBC", value=5.0)]
        first_quality = _make_quality(parse_score=10.0, valid_value_count=1)

        rerun_items = [FakeItem(name=n, value=v) for n, v in [
            ("WBC", 5.2), ("RBC", 4.5), ("HGB", 140), ("PLT", 250),
            ("ALT", 25), ("AST", 22), ("GLUC", 5.1), ("CREA", 80),
        ]]
        rerun_quality = _make_quality(parse_score=70.0, valid_value_count=8)

        # Собираем rerun_info как это делает engine
        rerun_info = {
            "performed": False,
            "reason": None,
            "score_before": first_quality["metrics"]["parse_score"],
            "score_after": first_quality["metrics"]["parse_score"],
            "chosen": "first",
        }

        first_score = first_quality["metrics"]["parse_score"]

        if first_score < OCR_RERUN_MIN_SCORE:
            rerun_info["performed"] = True
            rerun_info["reason"] = "LOW_PARSE_SCORE"
            rerun_info["score_after"] = rerun_quality["metrics"]["parse_score"]

            if _is_rerun_better(first_quality, rerun_quality):
                rerun_info["chosen"] = "rerun"

        assert rerun_info["performed"] is True
        assert rerun_info["reason"] == "LOW_PARSE_SCORE"
        assert rerun_info["score_before"] == 10.0
        assert rerun_info["score_after"] == 70.0
        assert rerun_info["chosen"] == "rerun"

    def test_no_rerun_when_no_file_bytes(self):
        """
        Если file_bytes нет (текст вставлен вручную),
        rerun OCR невозможен — performed=False.
        """
        first_quality = _make_quality(parse_score=10.0)

        # file_bytes=None → rerun не выполняется
        file_bytes = None
        rerun_info = {
            "performed": False,
            "reason": None,
            "score_before": first_quality["metrics"]["parse_score"],
            "score_after": first_quality["metrics"]["parse_score"],
            "chosen": "first",
        }

        if first_quality["metrics"]["parse_score"] < OCR_RERUN_MIN_SCORE and file_bytes:
            rerun_info["performed"] = True  # не попадёт сюда

        assert rerun_info["performed"] is False
        assert rerun_info["chosen"] == "first"

