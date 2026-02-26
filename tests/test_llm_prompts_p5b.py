"""
Тесты для LLM-промптов и дисклеймеров P5-B.

Проверяем юридическую безопасность формулировок:
- SYSTEM_PROMPT не содержит запрещённых формулировок
- SYSTEM_PROMPT содержит все обязательные ограничения
- build_llm_prompt формирует корректную структуру
- build_fallback_text содержит дисклеймер и не содержит запрещённых слов
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine import (
    SYSTEM_PROMPT,
    build_llm_prompt,
    build_fallback_text,
    Item,
    Range,
    EXPLAIN_DICT,
    suggest_specialists,
    build_dict_explanations,
)


# ============================================================
# Тесты: SYSTEM_PROMPT — юридическая безопасность
# ============================================================
class TestSystemPromptSafety:

    def test_contains_info_resource(self):
        """SYSTEM_PROMPT должен указывать, что это информационный ресурс."""
        low = SYSTEM_PROMPT.lower()
        assert "информационн" in low

    def test_contains_no_license(self):
        """SYSTEM_PROMPT должен указывать на отсутствие лицензии."""
        low = SYSTEM_PROMPT.lower()
        assert "лицензи" in low

    def test_forbids_diagnosis(self):
        """SYSTEM_PROMPT должен запрещать диагнозы."""
        low = SYSTEM_PROMPT.lower()
        assert "диагноз" in low
        assert "запрещено" in low or "категорически" in low

    def test_forbids_treatment(self):
        """SYSTEM_PROMPT должен запрещать лечение."""
        low = SYSTEM_PROMPT.lower()
        assert "лечени" in low

    def test_forbids_medications(self):
        """SYSTEM_PROMPT должен запрещать лекарства."""
        low = SYSTEM_PROMPT.lower()
        assert "лекарств" in low or "дозировк" in low

    def test_allows_explanation(self):
        """SYSTEM_PROMPT должен разрешать объяснения."""
        low = SYSTEM_PROMPT.lower()
        assert "объяснять" in low or "разрешено" in low

    def test_uses_soft_formulations(self):
        """SYSTEM_PROMPT должен содержать мягкие формулировки."""
        low = SYSTEM_PROMPT.lower()
        assert "может быть связано" in low
        assert "имеет смысл" in low


# ============================================================
# Тесты: build_llm_prompt — структура
# ============================================================
class TestBuildLlmPrompt:

    def _make_items(self):
        return [
            Item(raw_name="АЛТ", name="ALT", value=92.3, unit="Ед/л",
                 ref_text="<41", ref=Range(low=None, high=41.0),
                 status="ВЫШЕ", ref_source="референс лаборатории", confidence=0.9),
        ]

    def test_contains_patient_info(self):
        items = self._make_items()
        expl = build_dict_explanations(items)
        specs = suggest_specialists(items)
        prompt = build_llm_prompt("м", 60, items, expl, specs)
        assert "пол м" in prompt.lower()
        assert "60" in prompt

    def test_contains_deviation_data(self):
        items = self._make_items()
        expl = build_dict_explanations(items)
        specs = suggest_specialists(items)
        prompt = build_llm_prompt("м", 60, items, expl, specs)
        assert "92.3" in prompt
        assert "ВЫШЕ" in prompt

    def test_contains_section_headers(self):
        items = self._make_items()
        expl = build_dict_explanations(items)
        specs = suggest_specialists(items)
        prompt = build_llm_prompt("м", 60, items, expl, specs)
        assert "ДИСКЛЕЙМЕР" in prompt
        assert "КРАТКИЙ ИТОГ" in prompt
        assert "СПЕЦИАЛИСТ" in prompt.upper()

    def test_contains_info_resource_reminder(self):
        """Промпт должен напоминать LLM о том, что это информационный ресурс."""
        items = self._make_items()
        expl = build_dict_explanations(items)
        specs = suggest_specialists(items)
        prompt = build_llm_prompt("м", 60, items, expl, specs)
        low = prompt.lower()
        assert "информационн" in low

    def test_no_deviations(self):
        """При отсутствии отклонений — промпт не падает."""
        expl = build_dict_explanations([])
        prompt = build_llm_prompt("ж", 30, [], expl, [])
        assert "отклонений" in prompt.lower()


# ============================================================
# Тесты: build_fallback_text — юридическая безопасность
# ============================================================
class TestBuildFallbackText:

    def _make_items(self):
        return [
            Item(raw_name="АЛТ", name="ALT", value=92.3, unit="Ед/л",
                 ref_text="<41", ref=Range(low=None, high=41.0),
                 status="ВЫШЕ", ref_source="референс лаборатории", confidence=0.9),
            Item(raw_name="АСТ", name="AST", value=56.2, unit="Ед/л",
                 ref_text="<40", ref=Range(low=None, high=40.0),
                 status="ВЫШЕ", ref_source="референс лаборатории", confidence=0.9),
        ]

    def test_contains_disclaimer(self):
        items = self._make_items()
        text = build_fallback_text("м", 60, items, items)
        low = text.lower()
        assert "дисклеймер" in low
        assert "справочн" in low

    def test_no_forbidden_words(self):
        """Fallback не должен содержать слов, подразумевающих диагноз/лечение."""
        items = self._make_items()
        text = build_fallback_text("м", 60, items, items)
        low = text.lower()
        # Не должно быть категоричных медицинских формулировок
        assert "вам необходимо" not in low
        assert "срочно" not in low
        assert "диагноз:" not in low
        assert "лечение:" not in low

    def test_contains_specialist_recommendation(self):
        items = self._make_items()
        text = build_fallback_text("м", 60, items, items)
        low = text.lower()
        assert "специалист" in low or "терапевт" in low

    def test_contains_explain_info(self):
        """Fallback должен включать пояснения из EXPLAIN_DICT."""
        items = self._make_items()
        text = build_fallback_text("м", 60, items, items)
        # ALT есть в EXPLAIN_DICT
        assert "АЛТ" in text or "ALT" in text or "аланинамин" in text.lower()

    def test_empty_items(self):
        text = build_fallback_text("м", 60, [], [])
        assert "не удалось распознать" in text.lower()

    def test_no_deviations(self):
        items = [
            Item(raw_name="Глюкоза", name="GLUC", value=5.27, unit="ммоль/л",
                 ref_text="4.11-6.1", ref=Range(low=4.11, high=6.1),
                 status="В НОРМЕ", ref_source="референс лаборатории", confidence=0.9),
        ]
        text = build_fallback_text("м", 60, items, [])
        assert "отклонений не обнаружено" in text.lower()

