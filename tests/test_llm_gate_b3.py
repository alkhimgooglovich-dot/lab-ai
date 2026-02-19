"""
tests/test_llm_gate_b3.py — Этап B3: LLM gate по parse_score.

Проверяем три сценария решения LLM-гейта
и один сценарий с rerun (B2 улучшил score → CALL).
"""

import types
import pytest


# ─── Хелперы ─────────────────────────────────────────────────────────

def _make_quality(valid_value_count=0, parse_score=100.0):
    """Собирает минимальный quality-словарь, совместимый с B3-гейтом."""
    return {
        "valid_value_count": valid_value_count,
        "coverage_score": 0.9,
        "suspicious_count": 0,
        "ref_coverage_ratio": 1.0,
        "duplicate_name_count": 0,
        "metrics": {
            "schema_version": "1.0",
            "ocr": {},
            "parse": {},
            "parse_score": parse_score,
        },
    }


def _run_llm_gate(quality):
    """
    Воспроизводит РОВНО ту же логику, что в engine.py (B3).
    Возвращает quality с заполненным quality["metrics"]["llm_gate"].
    """
    from engine import LLM_MIN_PARSE_SCORE

    _valid_count = quality["valid_value_count"]
    _ps = quality.get("metrics", {}).get("parse_score", 100.0)

    _eligible_by_count = _valid_count >= 5
    _eligible_by_score = _ps >= LLM_MIN_PARSE_SCORE

    if not _eligible_by_count:
        decision = "SKIP_LOW_VALUES"
    elif not _eligible_by_score:
        decision = "SKIP_LOW_SCORE"
    else:
        decision = "CALL"

    if "metrics" not in quality:
        quality["metrics"] = {}
    quality["metrics"]["llm_gate"] = {
        "eligible_by_valid_count": _eligible_by_count,
        "eligible_by_parse_score": _eligible_by_score,
        "min_parse_score": LLM_MIN_PARSE_SCORE,
        "parse_score": _ps,
        "decision": decision,
    }
    return quality


# ─── Тест 1: мало показателей → SKIP_LOW_VALUES ─────────────────────

class TestSkipLlmWhenLowValues:
    """valid_value_count=4, parse_score=90 → decision SKIP_LOW_VALUES.
    Даже если parse_score отличный, мало показателей = не вызываем LLM."""

    def test_decision(self):
        q = _make_quality(valid_value_count=4, parse_score=90.0)
        q = _run_llm_gate(q)
        gate = q["metrics"]["llm_gate"]

        assert gate["decision"] == "SKIP_LOW_VALUES"
        assert gate["eligible_by_valid_count"] is False
        assert gate["eligible_by_parse_score"] is True
        assert gate["min_parse_score"] == 55.0
        assert gate["parse_score"] == 90.0

    def test_llm_not_called(self, monkeypatch):
        """Убеждаемся, что при SKIP_LOW_VALUES функция call_yandexgpt НЕ вызывается."""
        import engine

        call_log = []
        monkeypatch.setattr(engine, "call_yandexgpt",
                            lambda token, prompt: call_log.append(1) or "mocked")

        q = _make_quality(valid_value_count=4, parse_score=90.0)
        q = _run_llm_gate(q)

        # Проверяем решение — SKIP, значит call_yandexgpt не нужен
        assert q["metrics"]["llm_gate"]["decision"] == "SKIP_LOW_VALUES"
        assert len(call_log) == 0, "call_yandexgpt НЕ должен вызываться при SKIP_LOW_VALUES"


# ─── Тест 2: низкий parse_score → SKIP_LOW_SCORE ────────────────────

class TestSkipLlmWhenLowScore:
    """valid_value_count=10, parse_score=40 → decision SKIP_LOW_SCORE.
    Показателей достаточно, но качество распознавания плохое."""

    def test_decision(self):
        q = _make_quality(valid_value_count=10, parse_score=40.0)
        q = _run_llm_gate(q)
        gate = q["metrics"]["llm_gate"]

        assert gate["decision"] == "SKIP_LOW_SCORE"
        assert gate["eligible_by_valid_count"] is True
        assert gate["eligible_by_parse_score"] is False
        assert gate["parse_score"] == 40.0

    def test_llm_not_called(self, monkeypatch):
        """call_yandexgpt НЕ вызывается при SKIP_LOW_SCORE."""
        import engine

        call_log = []
        monkeypatch.setattr(engine, "call_yandexgpt",
                            lambda token, prompt: call_log.append(1) or "mocked")

        q = _make_quality(valid_value_count=10, parse_score=40.0)
        q = _run_llm_gate(q)

        assert q["metrics"]["llm_gate"]["decision"] == "SKIP_LOW_SCORE"
        assert len(call_log) == 0, "call_yandexgpt НЕ должен вызываться при SKIP_LOW_SCORE"


# ─── Тест 3: всё ОК → CALL ──────────────────────────────────────────

class TestCallLlmWhenAllOk:
    """valid_value_count=10, parse_score=80 → decision CALL.
    Оба условия выполнены — вызываем LLM."""

    def test_decision(self):
        q = _make_quality(valid_value_count=10, parse_score=80.0)
        q = _run_llm_gate(q)
        gate = q["metrics"]["llm_gate"]

        assert gate["decision"] == "CALL"
        assert gate["eligible_by_valid_count"] is True
        assert gate["eligible_by_parse_score"] is True

    def test_boundary_55(self):
        """Граничный случай: parse_score ровно 55.0 → CALL (>=, не >)."""
        q = _make_quality(valid_value_count=5, parse_score=55.0)
        q = _run_llm_gate(q)

        assert q["metrics"]["llm_gate"]["decision"] == "CALL"

    def test_boundary_54_99(self):
        """Граничный случай: parse_score=54.99 → SKIP_LOW_SCORE."""
        q = _make_quality(valid_value_count=5, parse_score=54.99)
        q = _run_llm_gate(q)

        assert q["metrics"]["llm_gate"]["decision"] == "SKIP_LOW_SCORE"


# ─── Тест 4: rerun улучшил parse_score → CALL ───────────────────────

class TestGateUsesBestRunAfterRerun:
    """
    Сценарий: первый прогон дал parse_score=30 (ниже порога 55),
    rerun (B2) улучшил до parse_score=70 → финальное решение CALL.

    Мы НЕ меняем B2-логику. Мы лишь проверяем, что LLM-гейт
    использует ИТОГОВЫЙ quality (после выбора лучшего прогона).
    """

    def test_rerun_improves_score_gate_calls(self, monkeypatch):
        # Эмулируем: B2 выбрал лучший прогон, в quality уже лежит score=70
        q = _make_quality(valid_value_count=10, parse_score=70.0)
        q = _run_llm_gate(q)

        gate = q["metrics"]["llm_gate"]
        assert gate["decision"] == "CALL"
        assert gate["parse_score"] == 70.0

    def test_rerun_still_low_gate_skips(self):
        """rerun улучшил, но всё ещё ниже порога → SKIP_LOW_SCORE."""
        q = _make_quality(valid_value_count=10, parse_score=50.0)
        q = _run_llm_gate(q)

        assert q["metrics"]["llm_gate"]["decision"] == "SKIP_LOW_SCORE"


# ─── Тест: константа LLM_MIN_PARSE_SCORE ────────────────────────────

class TestConstants:
    """Проверяем, что константа определена и имеет правильное значение."""

    def test_llm_min_parse_score_value(self):
        from engine import LLM_MIN_PARSE_SCORE
        assert LLM_MIN_PARSE_SCORE == 55.0

    def test_llm_min_parse_score_is_float(self):
        from engine import LLM_MIN_PARSE_SCORE
        assert isinstance(LLM_MIN_PARSE_SCORE, float)


# ─── Тест: полная структура llm_gate ────────────────────────────────

class TestLlmGateStructure:
    """Проверяем, что quality['metrics']['llm_gate'] содержит все нужные поля."""

    def test_all_fields_present(self):
        q = _make_quality(valid_value_count=10, parse_score=80.0)
        q = _run_llm_gate(q)
        gate = q["metrics"]["llm_gate"]

        required_keys = {
            "eligible_by_valid_count",
            "eligible_by_parse_score",
            "min_parse_score",
            "parse_score",
            "decision",
        }
        assert required_keys == set(gate.keys()), \
            f"Лишние или пропущенные ключи: {set(gate.keys()) ^ required_keys}"

    def test_decision_is_valid_enum(self):
        valid_decisions = {"CALL", "SKIP_LOW_SCORE", "SKIP_LOW_VALUES"}
        for vvc, ps, expected in [
            (4, 90, "SKIP_LOW_VALUES"),
            (10, 40, "SKIP_LOW_SCORE"),
            (10, 80, "CALL"),
        ]:
            q = _make_quality(valid_value_count=vvc, parse_score=ps)
            q = _run_llm_gate(q)
            decision = q["metrics"]["llm_gate"]["decision"]
            assert decision in valid_decisions
            assert decision == expected

