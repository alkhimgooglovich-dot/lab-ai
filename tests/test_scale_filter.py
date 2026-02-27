"""
Тесты фильтрации шкальных аннотаций (scale annotations).

Проверяем, что строки-пояснения к шкалам НЕ парсятся как показатели,
а реальные показатели — парсятся корректно.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from parsers.line_scorer import is_noise, score_line
from parsers.universal_extractor import universal_extract, _is_scale_annotation


# ============================================================
# Тесты: _is_scale_annotation — должны быть True
# ============================================================
class TestScaleAnnotationPositive:

    def test_normal_level(self):
        assert _is_scale_annotation("Нормальный уровень <1,70")

    def test_moderate_elevated(self):
        assert _is_scale_annotation("Умеренно-повышенный 1,70-2,25")

    def test_elevated(self):
        assert _is_scale_annotation("Повышенный 2,26-5,65")

    def test_high_level(self):
        assert _is_scale_annotation("Высокий уровень >5,65")

    def test_risk_absent(self):
        assert _is_scale_annotation(">1.45 ммоль/л - риск отсутствует")

    def test_moderate_risk(self):
        assert _is_scale_annotation("0.9-1,45 ммоль/л - умеренный риск")

    def test_high_risk(self):
        assert _is_scale_annotation("<0.9 ммоль/л - высокий риск")

    def test_normal_hba1c(self):
        assert _is_scale_annotation("нормальное содержание HbA1c")

    def test_diagnostic_criterion(self):
        assert _is_scale_annotation("диагностический критерий сахарного диабета")

    def test_consultation_recommended(self):
        assert _is_scale_annotation("рекомендуется консультация эндокринолога для исключения нарушений")

    def test_research_method(self):
        assert is_noise("Исследование проведено методом сертифицированным NGSP и IFCC")


# ============================================================
# Тесты: _is_scale_annotation — должны быть False (реальные показатели)
# ============================================================
class TestScaleAnnotationNegative:

    def test_real_glucose(self):
        assert not _is_scale_annotation("Глюкоза 5.27 ммоль/л 4.11 - 6.1")

    def test_real_cholesterol(self):
        assert not _is_scale_annotation("Холестерин общий 4.73 ммоль/л")

    def test_real_alt(self):
        assert not _is_scale_annotation("Аланинаминотрансфераза (АЛТ) (венозная кровь)")

    def test_real_creatinine(self):
        assert not _is_scale_annotation("Креатинин (венозная кровь) 71.0 мкмоль/л 72 - 127")

    def test_real_uric_acid(self):
        assert not _is_scale_annotation("Мочевая кислота (венозная кровь)")

    def test_real_iron(self):
        assert not _is_scale_annotation("Сывороточное железо 52.8 мкмоль/л 5.8 - 34.5")


# ============================================================
# Тесты: is_noise — шкальные строки должны быть шумом
# ============================================================
class TestIsNoiseScaleLines:

    def test_normal_level_is_noise(self):
        assert is_noise("Нормальный уровень <1,70")

    def test_moderate_elevated_is_noise(self):
        assert is_noise("Умеренно-повышенный 1,70-2,25")

    def test_high_level_is_noise(self):
        assert is_noise("Высокий уровень >5,65")

    def test_clinical_recommendations_is_noise(self):
        assert is_noise("Клинические рекомендации 2021 (Российское ассоциация эндокринологов):")


# ============================================================
# Тесты: score_line — шкальные строки score < 0.3
# ============================================================
class TestScoreLineScale:

    def test_normal_level_low_score(self):
        assert score_line("Нормальный уровень <1,70") < 0.3

    def test_moderate_elevated_low_score(self):
        assert score_line("Умеренно-повышенный 1,70-2,25") < 0.3

    def test_risk_absent_low_score(self):
        assert score_line(">1.45 ммоль/л - риск отсутствует") < 0.3


# ============================================================
# Интеграционный тест: Гемотест-подобный текст
# ============================================================
GEMOTEST_SAMPLE = """\
Триглицериды (венозная кровь) 1.59 ммоль/л Смотри текст
Нормальный уровень <1,70
Умеренно-повышенный 1,70-2,25
Повышенный 2,26-5,65
Высокий уровень >5,65
Холестерин липопротеинов низкой плотности (ЛПНП) (венозная кровь) 3.36 ммоль/л Смотри текст
Нормальный уровень <2,59
Умеренно-повышенный 2,59-3,34
Повышенный 3,37-4,12
Высокий уровень >4,14
Холестерин общий 4.73 ммоль/л Смотри текст
Нормальный уровень <5,18
Умеренно-повышенный 5,18-6,19
Высокий уровень >6.22
Холестерин-ЛПВП 1.25 ммоль/л Смотри текст
>1.45 ммоль/л - риск отсутствует
0.9-1,45 ммоль/л - умеренный риск
<0.9 ммоль/л - высокий риск
Индекс атерогенности 2.78 < 3.5
Глюкоза 5.27 ммоль/л 4.11 - 6.1
Гликированный гемоглобин 5.0 % Смотри текст
Клинические рекомендации 2021 (Российское ассоциация эндокринологов):
до 6.0% включительно (в соответствии с DCCT) - нормальное содержание HbA1c
6.0-6.4% - рекомендуется консультация эндокринолога для исключения нарушений углеводного обмена
6.5% и более - диагностический критерий сахарного диабета
Аланинаминотрансфераза (АЛТ) (венозная кровь) 92.3 Ед/л < 41
Аспартатаминотрансфераза (АСТ) (венозная кровь) 56.2 Ед/л < 40
"""


class TestGemotestIntegration:
    """
    Интеграционный тест: из Гемотест-подобного текста
    шкальные строки НЕ должны попасть в кандидаты.
    """

    def test_no_scale_annotations_in_candidates(self):
        """Ни одна шкальная аннотация не должна стать кандидатом."""
        candidates = universal_extract(GEMOTEST_SAMPLE)
        lines = candidates.strip().splitlines() if candidates else []

        bad_names = [
            "нормальный уровень", "умеренно-повышенный", "повышенный",
            "высокий уровень", "риск отсутствует", "умеренный риск",
            "высокий риск", "нормальное содержание", "диагностический критерий",
            "рекомендуется консультация", "клинические рекомендации",
        ]

        for line in lines:
            name = line.split("\t")[0].lower() if "\t" in line else line.lower()
            for bad in bad_names:
                assert bad not in name, f"Фантомная строка в кандидатах: {line}"

    def test_real_indicators_preserved(self):
        """Реальные показатели должны остаться."""
        candidates = universal_extract(GEMOTEST_SAMPLE)
        text_lower = candidates.lower() if candidates else ""

        # Эти показатели ДОЛЖНЫ быть в кандидатах
        assert "глюкоза" in text_lower, "Глюкоза пропала из кандидатов"
        assert "индекс атерогенности" in text_lower, "Индекс атерогенности пропал"

    def test_alt_preserved(self):
        """АЛТ должен остаться."""
        candidates = universal_extract(GEMOTEST_SAMPLE)
        text_lower = candidates.lower() if candidates else ""
        assert "алт" in text_lower or "аланинамино" in text_lower, "АЛТ пропал из кандидатов"

    def test_ast_preserved(self):
        """АСТ должен остаться."""
        candidates = universal_extract(GEMOTEST_SAMPLE)
        text_lower = candidates.lower() if candidates else ""
        assert "аст" in text_lower or "аспартат" in text_lower, "АСТ пропал из кандидатов"


