"""
Tests for P6 final garbage cleanup.

Verifies:
  - Scale annotation lines with units at start are filtered
  - Garbage names (МЗ РФ, DCCT, biomaterial-only) are rejected
  - "See Text" indicators on separate lines are parsed
  - SYSTEM_PROMPT bans diet/lifestyle mentions
"""

import sys, re
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from parsers.universal_extractor import universal_extract, _is_scale_annotation, _looks_like_name_line
from parsers.line_scorer import is_noise
from engine import SYSTEM_PROMPT, build_llm_prompt, _is_garbage_name


class TestScaleAnnotationExtended:
    """Extended scale annotation detection."""

    def test_mmol_risk_absent(self):
        assert _is_scale_annotation("ммоль/л - риск отсутствует 0.9 -1,45")

    def test_mmol_moderate_risk(self):
        assert _is_scale_annotation("ммоль/л - умеренный риск")

    def test_mmol_high_risk(self):
        assert _is_scale_annotation("ммоль/л - высокий риск")

    def test_dcct_line(self):
        assert _is_scale_annotation("до 6.0% включительно (в соответствии с DCCT) - нормальное содержание HbA1c")

    def test_ngsp_line(self):
        assert _is_scale_annotation("Исследование проведено методом сертифицированным NGSP и IFCC")

    def test_6_0_6_4_explanation(self):
        assert _is_scale_annotation("6.0-6.4% - рекомендуется консультация эндокринолога")

    def test_6_5_and_more(self):
        assert _is_scale_annotation("6.5% и более - диагностический критерий сахарного диабета")

    def test_real_glucose_not_filtered(self):
        assert not _is_scale_annotation("Глюкоза 5.27 ммоль/л 4.11 - 6.1")

    def test_real_alt_not_filtered(self):
        assert not _is_scale_annotation("Аланинаминотрансфераза (АЛТ) (венозная кровь) 92.3 Ед/л < 41")


class TestGarbageName:
    """Test _is_garbage_name function."""

    def test_mz_rf(self):
        assert _is_garbage_name("МЗ РФ")

    def test_dcct_hba(self):
        assert _is_garbage_name("DCCT) - HbA")

    def test_prikaz(self):
        assert _is_garbage_name("Приказ МЗ РФ № 804н")

    def test_biomaterial_parenthesis(self):
        assert _is_garbage_name("(сыворотка крови)")

    def test_biomaterial_venous(self):
        assert _is_garbage_name("(венозная кровь)")

    def test_empty(self):
        assert _is_garbage_name("")

    def test_single_char(self):
        assert _is_garbage_name("A")

    def test_valid_glucose(self):
        assert not _is_garbage_name("Глюкоза")

    def test_valid_alt(self):
        assert not _is_garbage_name("Аланинаминотрансфераза (АЛТ)")

    def test_valid_ldh(self):
        assert not _is_garbage_name("Лактатдегидрогеназа (ЛДГ)")

    def test_valid_crp(self):
        assert not _is_garbage_name("С-реактивный белок (СРБ)")


class TestLooksLikeNameLine:
    """Test biomaterial rejection in _looks_like_name_line."""

    def test_serum_not_name(self):
        assert not _looks_like_name_line("(сыворотка крови)")

    def test_venous_blood_not_name(self):
        assert not _looks_like_name_line("(венозная кровь)")

    def test_whole_blood_not_name(self):
        assert not _looks_like_name_line("(цельная кровь)")

    def test_valid_name_is_name(self):
        assert _looks_like_name_line("Креатинин (венозная кровь)")

    def test_valid_name_alt(self):
        assert _looks_like_name_line("Аланинаминотрансфераза (АЛТ) (венозная кровь)")


class TestNoiseExtended:
    """Extended noise detection in line_scorer."""

    def test_mmol_dash_noise(self):
        assert is_noise("ммоль/л - риск отсутствует")

    def test_soglasno_noise(self):
        assert is_noise("в соответствии с DCCT")

    def test_vkluchitelno_noise(self):
        assert is_noise("включительно — нормальное содержание")


class TestSeeTextSeparateLine:
    """Test parsing when 'Смотри текст' is on a separate line."""

    SAMPLE = """\
Триглицериды (венозная кровь) 1.59 ммоль/л
Смотри текст
Глюкоза 5.27 ммоль/л 4.11 - 6.1
"""

    def test_triglycerides_parsed(self):
        candidates = universal_extract(self.SAMPLE)
        lower = candidates.lower() if candidates else ""
        assert "триглицерид" in lower or "1.59" in candidates, \
            f"Triglycerides not found in candidates: {candidates}"

    def test_glucose_still_parsed(self):
        candidates = universal_extract(self.SAMPLE)
        lower = candidates.lower() if candidates else ""
        assert "глюкоз" in lower or "5.27" in candidates


class TestSystemPromptLegal:
    """SYSTEM_PROMPT must ban diet/lifestyle mentions."""

    def test_bans_diet(self):
        low = SYSTEM_PROMPT.lower()
        assert "питани" in low or "диет" in low, \
            "SYSTEM_PROMPT must mention diet ban"

    def test_bans_lifestyle(self):
        low = SYSTEM_PROMPT.lower()
        assert "образ" in low or "нагрузк" in low or "корректиров" in low, \
            "SYSTEM_PROMPT must mention lifestyle/correction ban"

    def test_bans_reduction(self):
        low = SYSTEM_PROMPT.lower()
        assert "снижен" in low or "повышен" in low, \
            "SYSTEM_PROMPT must ban suggesting ways to reduce/increase levels"


FULL_GEMOTEST_SAMPLE = """\
Общий белок (венозная кровь) 70 г/л 64-83
Альбумин (венозная кровь) 53 г/л 35-52
Креатинин (венозная кровь) 71 мкмоль/л 72-127
Мочевина (венозная кровь) 6.1 ммоль/л 3.5-8.1
Мочевая кислота (венозная кровь) 426 мкмоль/л 202.3-416.5
С-реактивный белок (СРБ) 1.72 мг/л <5
Индекс атерогенности 2.78 <3.5
Глюкоза 5.27 ммоль/л 4.11 - 6.1
Аланинаминотрансфераза (АЛТ) (венозная кровь) 92.3 Ед/л < 41
Аспартатаминотрансфераза (АСТ) (венозная кровь) 56.2 Ед/л < 40
Амилаза (венозная кровь) 43 Ед/л <100
Гамма-ГТ (венозная кровь) 21 Ед/л <60
Фосфатаза щелочная (венозная кровь) 94 Ед/л 40-129
Билирубин общий 12.8 мкмоль/л <21
Билирубин прямой 4.8 мкмоль/л <5
Кальций общий (кровь, фотометрия) 2.42 ммоль/л 2.2-2.65
Хлориды 103 ммоль/л 98-106
Сывороточное железо 52.8 мкмоль/л 5.8-34.5
МЗ РФ 164 Ед/л 135-225
ммоль/л - риск отсутствует 0.9-1,45
DCCT) - HbA 1 6.0-6.4
(сыворотка крови) 3.7 ммоль/л 3.5-5.1
Триглицериды (венозная кровь) 1.59 ммоль/л
Смотри текст
Холестерин общий 4.73 ммоль/л Смотри текст
Холестерин-ЛПВП 1.25 ммоль/л Смотри текст
Гликированный гемоглобин 5.0 % Смотри текст
"""


class TestFullGemotestCleanup:
    """Integration test: full Gemotest sample after P6 cleanup."""

    def test_no_mz_rf_in_candidates(self):
        candidates = universal_extract(FULL_GEMOTEST_SAMPLE)
        for line in (candidates or "").splitlines():
            name = line.split("\t")[0] if "\t" in line else line
            assert "мз рф" not in name.lower(), f"МЗ РФ found in candidates: {line}"

    def test_no_dcct_in_candidates(self):
        candidates = universal_extract(FULL_GEMOTEST_SAMPLE)
        for line in (candidates or "").splitlines():
            name = line.split("\t")[0] if "\t" in line else line
            assert "dcct" not in name.lower(), f"DCCT found in candidates: {line}"

    def test_no_risk_absent_in_candidates(self):
        candidates = universal_extract(FULL_GEMOTEST_SAMPLE)
        for line in (candidates or "").splitlines():
            name = line.split("\t")[0] if "\t" in line else line
            assert "риск отсутствует" not in name.lower(), f"Risk absent found: {line}"

    def test_no_biomaterial_only_name(self):
        candidates = universal_extract(FULL_GEMOTEST_SAMPLE)
        for line in (candidates or "").splitlines():
            name = line.split("\t")[0] if "\t" in line else line
            assert name.strip() != "(сыворотка крови)", f"Biomaterial-only name: {line}"

    def test_glucose_present(self):
        candidates = universal_extract(FULL_GEMOTEST_SAMPLE)
        assert "глюкоз" in (candidates or "").lower()

    def test_alt_present(self):
        candidates = universal_extract(FULL_GEMOTEST_SAMPLE)
        lower = (candidates or "").lower()
        assert "алт" in lower or "аланинамин" in lower

    def test_see_text_cholesterol_parsed(self):
        candidates = universal_extract(FULL_GEMOTEST_SAMPLE)
        lower = (candidates or "").lower()
        assert "холестерин общ" in lower or "4.73" in candidates


