"""
B5-B: тесты на секцию «Диагностика качества» в отчёте.

Тестируем функцию build_quality_section_text (а не PDF напрямую),
чтобы тесты были быстрыми и не требовали Playwright.
"""
import pytest
from parsers.report_helpers import (
    build_quality_section_text,
    build_quality_section_html,
    build_user_quality_note,
)


# ── Хелперы для создания тестовых quality-словарей ──────────────────────

def _quality(
    parse_score=75.0,
    reasons=None,
    reason_summary="",
    rerun=None,
    llm_gate=None,
):
    """Создаёт словарь quality с блоком metrics."""
    metrics = {
        "schema_version": "1.0",
        "parse_score": parse_score,
        "reasons": reasons or [],
        "reason_summary": reason_summary,
    }
    if rerun is not None:
        metrics["rerun"] = rerun
    if llm_gate is not None:
        metrics["llm_gate"] = llm_gate
    return {"metrics": metrics, "valid_value_count": 10}


# ══════════════════════════════════════════════════════════════════════════
# Тест 1: parse_score отображается
# ══════════════════════════════════════════════════════════════════════════

class TestPdfContainsParseScore:
    def test_score_in_text(self):
        q = _quality(parse_score=82.5)
        text = build_quality_section_text(q)
        assert "82.5/100" in text
        assert "Качество" in text

    def test_score_zero(self):
        q = _quality(parse_score=0)
        text = build_quality_section_text(q)
        assert "0/100" in text


# ══════════════════════════════════════════════════════════════════════════
# Тест 2: reason_summary отображается
# ══════════════════════════════════════════════════════════════════════════

class TestPdfContainsReasonSummary:
    def test_reasons_present(self):
        q = _quality(
            reasons=["HIGH_NOISE", "LOW_COVERAGE"],
            reason_summary="HIGH_NOISE, LOW_COVERAGE",
        )
        text = build_quality_section_text(q)
        assert "Замечания" in text
        assert "шума" in text.lower() or "шум" in text.lower()  # HIGH_NOISE
        assert "распознанных" in text.lower() or "успешно" in text.lower()  # LOW_COVERAGE

    def test_no_reasons(self):
        q = _quality(reasons=[], reason_summary="")
        text = build_quality_section_text(q)
        assert "нет критичных замечаний" in text


# ══════════════════════════════════════════════════════════════════════════
# Тест 3: LLM gate status отображается
# ══════════════════════════════════════════════════════════════════════════

class TestPdfContainsLlmGateStatus:
    def test_skip_low_score(self):
        q = _quality(llm_gate={
            "decision": "SKIP_LOW_SCORE",
            "parse_score": 40.0,
            "min_parse_score": 55,
        })
        text = build_quality_section_text(q)
        assert "пропущена" in text
        assert "качество" in text.lower() or "score" in text.lower()

    def test_skip_low_values(self):
        q = _quality(llm_gate={"decision": "SKIP_LOW_VALUES"})
        text = build_quality_section_text(q)
        assert "пропущена" in text
        assert "валидных" in text.lower() or "показателей" in text.lower()

    def test_call(self):
        q = _quality(llm_gate={"decision": "CALL"})
        text = build_quality_section_text(q)
        assert "выполнена" in text


# ══════════════════════════════════════════════════════════════════════════
# Тест 4: rerun info отображается
# ══════════════════════════════════════════════════════════════════════════

class TestPdfContainsRerunInfo:
    def test_rerun_performed(self):
        q = _quality(rerun={
            "performed": True,
            "score_before": 35.0,
            "score_after": 62.0,
            "chosen": "rerun",
        })
        text = build_quality_section_text(q)
        assert "выполнен" in text
        assert "35" in text
        assert "62" in text
        assert "rerun" in text

    def test_rerun_not_performed(self):
        q = _quality(rerun={"performed": False})
        text = build_quality_section_text(q)
        assert "не потребовался" in text


# ══════════════════════════════════════════════════════════════════════════
# Тест 5: backward compatibility — metrics отсутствуют
# ══════════════════════════════════════════════════════════════════════════

class TestNoCrashWhenMetricsMissing:
    def test_no_metrics_key(self):
        """quality без блока metrics → не падает."""
        q = {"valid_value_count": 10}
        text = build_quality_section_text(q)
        assert "Нет данных" in text

    def test_empty_quality(self):
        """Полностью пустой quality → не падает."""
        text = build_quality_section_text({})
        assert "Нет данных" in text

    def test_metrics_none(self):
        """metrics = None → не падает."""
        q = {"metrics": None}
        text = build_quality_section_text(q)
        assert "Нет данных" in text


# ══════════════════════════════════════════════════════════════════════════
# Тест 6: HTML версия
# ══════════════════════════════════════════════════════════════════════════

class TestHtmlVersion:
    def test_html_contains_paragraphs(self):
        q = _quality(parse_score=90.0)
        html = build_quality_section_html(q)
        assert "<p>" in html
        assert "90" in html


# ══════════════════════════════════════════════════════════════════════════
# Тест 7: user quality note
# ══════════════════════════════════════════════════════════════════════════

class TestUserQualityNote:
    def test_skip_low_values_note(self):
        q = _quality(llm_gate={"decision": "SKIP_LOW_VALUES"})
        note = build_user_quality_note(q)
        assert "не выполнена" in note

    def test_reasons_recommendation(self):
        q = _quality(reasons=["HIGH_NOISE"])
        note = build_user_quality_note(q)
        assert "Рекомендация" in note

    def test_no_note_when_all_ok(self):
        q = _quality(llm_gate={"decision": "CALL"}, reasons=[])
        note = build_user_quality_note(q)
        assert note == ""

    def test_no_note_when_no_metrics(self):
        note = build_user_quality_note({})
        assert note == ""

