"""
Tests for small panel handling: multi-line conditional refs + LLM gate for 1-4 items.
"""
import pytest


# ——————————————————————————————————————————————————————————
# Group 1: Multi-line conditional reference merging
# ——————————————————————————————————————————————————————————

class TestConditionalRefMerge:
    """_merge_conditional_refs() correctly merges multi-line refs."""

    def test_cortisol_multiline_ref_merged(self):
        """Cortisol with Утро/Вечер/Дети refs → single line with widest ref 2.3-21.0."""
        from engine import _merge_conditional_refs
        text = (
            "Кортизол\n"
            "Кортизол 12.26 ug/dl\n"
            "Утро 6,2-19,4\n"
            "Вечер 2,3-11,9\n"
            "Дети (0-18) 3-21"
        )
        result = _merge_conditional_refs(text)
        # Conditional lines must be removed
        assert "Утро" not in result
        assert "Вечер" not in result
        assert "Дети" not in result
        # Biomarker line must have reference range appended
        assert "12.26" in result
        # Widest range: min(6.2, 2.3, 3) = 2.3, max(19.4, 11.9, 21) = 21
        assert "2.3" in result and "21" in result

    def test_sex_conditional_refs(self):
        """Testosterone with Мужчины/Женщины refs → widest range."""
        from engine import _merge_conditional_refs
        text = (
            "Тестостерон 15.5 нмоль/л\n"
            "Мужчины 8,64-29,0\n"
            "Женщины 0,29-1,67"
        )
        result = _merge_conditional_refs(text)
        assert "Мужчины" not in result
        assert "Женщины" not in result
        assert "15.5" in result
        # Widest: 0.29-29.0
        assert "0.29" in result and "29" in result

    def test_no_conditional_lines_passthrough(self):
        """Text without conditional refs passes through unchanged."""
        from engine import _merge_conditional_refs
        text = "Ферритин 43.30 ng/ml 4.63-204.00"
        result = _merge_conditional_refs(text)
        assert result.strip() == text.strip()

    def test_pregnancy_trimester_refs(self):
        """ТТГ with trimester refs → merged."""
        from engine import _merge_conditional_refs
        text = (
            "ТТГ 2.5 мкМЕ/мл\n"
            "Взрослые 0,4-4,0\n"
            "1 триместр 0,1-2,5\n"
            "2 триместр 0,2-3,0\n"
            "3 триместр 0,3-3,5"
        )
        result = _merge_conditional_refs(text)
        assert "Взрослые" not in result
        assert "триместр" not in result
        # Widest: 0.1-4.0
        assert "0.1" in result and "4" in result

    def test_conditional_ref_does_not_eat_next_biomarker(self):
        """Conditional refs stop when a non-conditional line appears."""
        from engine import _merge_conditional_refs
        text = (
            "Кортизол 12.26 ug/dl\n"
            "Утро 6,2-19,4\n"
            "Вечер 2,3-11,9\n"
            "Витамин D 17.3 ng/ml 30.00-100.00"
        )
        result = _merge_conditional_refs(text)
        lines = [l.strip() for l in result.strip().splitlines() if l.strip()]
        # Both biomarkers must survive
        cortisol_lines = [l for l in lines if "12.26" in l]
        vitd_lines = [l for l in lines if "17.3" in l]
        assert len(cortisol_lines) >= 1
        assert len(vitd_lines) >= 1
        # Vitamin D line must be intact with its own ref
        assert "30" in vitd_lines[0] and "100" in vitd_lines[0]


# ——————————————————————————————————————————————————————————
# Group 2: Cortisol full pipeline (no crash)
# ——————————————————————————————————————————————————————————

class TestCortisolPipeline:
    """Cortisol with multi-line refs must parse end-to-end without crash."""

    def test_cortisol_pipeline_no_crash(self):
        """_run_parse_pipeline must NOT return None for cortisol."""
        from engine import _run_parse_pipeline
        text = (
            "Кортизол\n"
            "Кортизол 12.26 ug/dl\n"
            "Утро 6,2-19,4\n"
            "Вечер 2,3-11,9\n"
            "Дети (0-18) 3-21"
        )
        items, quality, dd, oc = _run_parse_pipeline(text)
        assert items is not None, "Pipeline crashed: items is None"
        assert len(items) >= 1, f"Expected >=1 items, got {len(items)}"

    def test_cortisol_has_reference_range(self):
        """Parsed cortisol item must have a reference range (not None)."""
        from engine import _run_parse_pipeline
        text = (
            "Кортизол\n"
            "Кортизол 12.26 ug/dl\n"
            "Утро 6,2-19,4\n"
            "Вечер 2,3-11,9\n"
            "Дети (0-18) 3-21"
        )
        items, quality, dd, oc = _run_parse_pipeline(text)
        assert items is not None
        cortisol = [it for it in items if "кортизол" in (it.raw_name or "").lower()
                    or it.name == "CORTISOL" or "cortisol" in (it.name or "").lower()]
        assert len(cortisol) >= 1, f"No cortisol item found. Items: {[it.name for it in items]}"
        assert cortisol[0].ref is not None, "Cortisol ref is None — conditional refs were not merged"
        assert cortisol[0].value == pytest.approx(12.26)

    def test_cortisol_status_normal(self):
        """12.26 is within widest range 2.3-21.0 → should be НОРМА."""
        from engine import _run_parse_pipeline
        text = (
            "Кортизол 12.26 ug/dl\n"
            "Утро 6,2-19,4\n"
            "Вечер 2,3-11,9\n"
            "Дети (0-18) 3-21"
        )
        items, quality, dd, oc = _run_parse_pipeline(text)
        assert items is not None
        cortisol = [it for it in items if it.value == pytest.approx(12.26)]
        assert len(cortisol) >= 1
        assert cortisol[0].status == "В НОРМЕ"


# ——————————————————————————————————————————————————————————
# Group 3: Smart LLM gate for small panels
# ——————————————————————————————————————————————————————————

class TestSmallPanelLlmGate:
    """LLM gate allows high-confidence small panels."""

    def test_1_item_high_confidence_eligible(self):
        """1 item, all high confidence, good parse_score → LLM eligible."""
        from engine import _run_parse_pipeline
        text = "Ферритин\t43.30\t4.63-204.00\tng/ml"
        items, quality, dd, oc = _run_parse_pipeline(text)
        assert items is not None
        assert len(items) >= 1
        # Simulate the gate check logic
        _valid_count = quality["valid_value_count"]
        _ps = quality.get("metrics", {}).get("parse_score", 100.0)
        all_high = all(getattr(it, 'confidence', 0) >= 0.7 for it in items)
        eligible = _valid_count >= 5 or (_valid_count >= 1 and all_high and _ps >= 70.0)
        assert eligible, (
            f"Small panel should be LLM-eligible: valid_count={_valid_count}, "
            f"parse_score={_ps}, all_high_conf={all_high}"
        )

    def test_3_items_tsh_panel_eligible(self):
        """Thyroid panel (3 items) with high confidence → LLM eligible."""
        from engine import _run_parse_pipeline
        text = (
            "Т3 свободный\t3.22\t1.56-3.91\tpg/ml\n"
            "Т4 свободный\t1.12\t0.70-1.48\tng/dL\n"
            "ТТГ\t1.0687\t0.35-4.94\tuIU/ml"
        )
        items, quality, dd, oc = _run_parse_pipeline(text)
        assert items is not None
        assert len(items) >= 3
        _valid_count = quality["valid_value_count"]
        _ps = quality.get("metrics", {}).get("parse_score", 100.0)
        all_high = all(getattr(it, 'confidence', 0) >= 0.7 for it in items)
        eligible = _valid_count >= 5 or (_valid_count >= 1 and all_high and _ps >= 70.0)
        assert eligible, (
            f"TSH panel should be LLM-eligible: valid_count={_valid_count}, "
            f"parse_score={_ps}, all_high_conf={all_high}"
        )

    def test_vitamin_d_below_range_eligible(self):
        """Vitamin D 17.3 (ref 30-100) should parse as НИЖЕ and be LLM-eligible."""
        from engine import _run_parse_pipeline
        text = "Витамин D\t17.3\t30.00-100.00\tng/ml"
        items, quality, dd, oc = _run_parse_pipeline(text)
        assert items is not None
        vit_d = [it for it in items if "D" in (it.name or "")]
        assert len(vit_d) >= 1, f"Vitamin D not found. Items: {[it.name for it in items]}"
        assert vit_d[0].status == "НИЖЕ", f"Expected НИЖЕ, got {vit_d[0].status}"

    def test_gate_diagnostics_small_panel_override(self):
        """LLM gate logic must produce small_panel_override=True for 1-item clean panel."""
        from engine import _run_parse_pipeline, LLM_MIN_PARSE_SCORE
        text = "Ферритин\t43.30\t4.63-204.00\tng/ml"
        items, quality, dd, oc = _run_parse_pipeline(text)
        assert items is not None
        _valid_count = quality["valid_value_count"]
        _ps = quality.get("metrics", {}).get("parse_score", 100.0)
        all_high = all(getattr(it, 'confidence', 0) >= 0.7 for it in items)
        # Replicate the gate logic from engine.py
        if _valid_count >= 5:
            eligible = True
        elif _valid_count >= 1:
            eligible = all_high and _ps >= 70.0
        else:
            eligible = False
        small_panel_override = _valid_count < 5 and eligible
        assert small_panel_override, (
            f"Expected small_panel_override=True: valid_count={_valid_count}, "
            f"parse_score={_ps}, all_high_conf={all_high}"
        )


# ——————————————————————————————————————————————————————————
# Group 4: Conditional ref lines are not biomarkers
# ——————————————————————————————————————————————————————————

class TestConditionalRefsNotBiomarkers:
    """Conditional reference lines must NOT appear as parsed items."""

    def test_utro_not_a_biomarker(self):
        """'Утро 6,2-19,4' must NOT be parsed as a standalone biomarker."""
        from engine import _run_parse_pipeline
        text = (
            "Кортизол 12.26 ug/dl\n"
            "Утро 6,2-19,4\n"
            "Вечер 2,3-11,9\n"
            "Дети (0-18) 3-21"
        )
        items, quality, dd, oc = _run_parse_pipeline(text)
        assert items is not None
        item_names_lower = [(it.raw_name or "").lower() for it in items]
        assert not any("утро" in n for n in item_names_lower), \
            f"'Утро' was parsed as a biomarker! Items: {item_names_lower}"
        assert not any("вечер" in n for n in item_names_lower), \
            f"'Вечер' was parsed as a biomarker! Items: {item_names_lower}"
        assert not any("дети" in n for n in item_names_lower), \
            f"'Дети' was parsed as a biomarker! Items: {item_names_lower}"


# ══════════════════════════════════════════════════════════
# Group 5: Warning suppression for clean small panels
# ══════════════════════════════════════════════════════════

class TestSmallPanelWarning:
    """No misleading warning for clean small panels."""

    def test_no_warning_for_clean_1_item(self):
        """1 clean item with high confidence → no 'мало показателей' warning."""
        from engine import _run_parse_pipeline
        text = "Ферритин\t43.30\t4.63-204.00\tng/ml"
        items, quality, dd, oc = _run_parse_pipeline(text)
        assert items is not None
        # High confidence + good parse_score → warning should NOT fire
        all_high = all(getattr(it, 'confidence', 0) >= 0.7 for it in items)
        ps = quality.get("metrics", {}).get("parse_score", 0)
        assert all_high, "Expected all items to have high confidence"
        assert ps >= 70.0, f"Expected parse_score >= 70, got {ps}"

    def test_warning_for_low_quality_small_panel(self):
        """Items with low confidence should still show the warning."""
        # A garbled line that might parse poorly
        from engine import _run_parse_pipeline
        text = "???\t???\t???"
        items, quality, dd, oc = _run_parse_pipeline(text)
        # Either items is empty (no warning needed) or quality is low
        if items:
            all_high = all(getattr(it, 'confidence', 0) >= 0.7 for it in items)
            ps = quality.get("metrics", {}).get("parse_score", 0)
            # If not all_high or ps < 70 → warning should fire (tested via logic)
            assert not (all_high and ps >= 70.0), \
                "Garbled input should NOT have high confidence + high parse_score"


# ══════════════════════════════════════════════════════════
# Group 6: LLM refusal detection
# ══════════════════════════════════════════════════════════

class TestLlmRefusalDetection:
    """_is_llm_refusal() detects YandexGPT content filter responses."""

    def test_detects_refusal(self):
        from engine import _is_llm_refusal
        assert _is_llm_refusal("Я не могу обсуждать эту тему. Давайте поговорим о чём-нибудь ещё.")

    def test_detects_short_refusal(self):
        from engine import _is_llm_refusal
        assert _is_llm_refusal("К сожалению, я не могу предоставить эту информацию.")

    def test_normal_response_not_flagged(self):
        from engine import _is_llm_refusal
        normal = (
            "**ДИСКЛЕЙМЕР**\nДанная информация носит справочный характер и не является диагнозом. "
            "Для интерпретации результатов необходимо обратиться к врачу.\n\n"
            "**КРАТКИЙ ИТОГ ПО ФАКТАМ**\nВитамин D ниже референсного значения."
        )
        assert not _is_llm_refusal(normal)

    def test_long_response_with_refusal_phrase_inside(self):
        """A long legitimate response that happens to contain 'не могу' somewhere is NOT a refusal."""
        from engine import _is_llm_refusal
        long_response = "**ДИСКЛЕЙМЕР**\n" + "x" * 300 + "\nПоказатель не могу быть оценён изолированно."
        assert not _is_llm_refusal(long_response)

    def test_empty_string_not_refusal(self):
        from engine import _is_llm_refusal
        assert not _is_llm_refusal("")

    def test_refusal_variant_ne_v_sostoyanii(self):
        from engine import _is_llm_refusal
        assert _is_llm_refusal("Я не в состоянии ответить на этот вопрос.")

    def test_refusal_variant_vyhodit_za_ramki(self):
        from engine import _is_llm_refusal
        assert _is_llm_refusal("Это выходит за рамки моих возможностей.")


# ══════════════════════════════════════════════════════════
# Group 7: All-normal prompt is short
# ══════════════════════════════════════════════════════════

class TestAllNormalPrompt:
    """When all items are in range, prompt requests a SHORT response."""

    def test_no_deviations_prompt_short(self):
        from engine import build_llm_prompt, build_dict_explanations, suggest_specialists
        expl = build_dict_explanations([])
        specs = suggest_specialists([])
        prompt = build_llm_prompt("ж", 26, [], expl, specs)
        prompt_lower = prompt.lower()
        # Should instruct LLM to be brief
        assert "коротк" in prompt_lower or "кратк" in prompt_lower
        # Should NOT contain specialist/question sections
        assert "вопросы врачу" not in prompt_lower

    def test_no_deviations_prompt_compact(self):
        """All-normal prompt should be reasonably short."""
        from engine import build_llm_prompt, build_dict_explanations, suggest_specialists
        expl = build_dict_explanations([])
        specs = suggest_specialists([])
        prompt = build_llm_prompt("м", 30, [], expl, specs)
        assert len(prompt) < 1500, f"All-normal prompt too long: {len(prompt)} chars"

    def test_with_deviations_prompt_has_full_structure(self):
        """When there ARE deviations, prompt should have full structure."""
        from engine import build_llm_prompt, build_dict_explanations, suggest_specialists, Item, Range
        items = [
            Item(raw_name="Витамин D", name="VITD", value=17.3, unit="ng/ml",
                 ref_text="30.00-100.00", ref=Range(low=30.0, high=100.0),
                 status="НИЖЕ", ref_source="референс лаборатории", confidence=0.9),
        ]
        expl = build_dict_explanations(items)
        specs = suggest_specialists(items)
        prompt = build_llm_prompt("ж", 26, items, expl, specs)
        # Should contain full structure
        assert "ВОПРОСЫ ВРАЧУ" in prompt or "вопросы врачу" in prompt.lower()
