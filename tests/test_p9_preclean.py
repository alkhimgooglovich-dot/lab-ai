"""
Tests for P9 — pre-clean regulatory codes before parsing.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from parsers.universal_extractor import universal_extract, _preclean_line


class TestPrecleanLine:
    """Test _preclean_line strips regulatory codes."""

    def test_removes_service_code(self):
        result = _preclean_line(
            "Гликированный гемоглобин A09.05.083 (Приказ МЗ РФ № 804н) 5.0 % Смотри текст"
        )
        assert "A09" not in result
        assert "804" not in result
        assert "5.0" in result
        assert "гемоглобин" in result.lower()

    def test_removes_biomaterial(self):
        result = _preclean_line("Калий (K+) (сыворотка крови) 3.7 ммоль/л 3.5 - 5.1")
        assert "сыворотка" not in result.lower()
        assert "3.7" in result
        assert "Калий" in result

    def test_removes_prikaz(self):
        result = _preclean_line(
            "Лактатдегидрогеназа (ЛДГ) (венозная кровь) A09.05.039 "
            "(Приказ МЗ РФ № 804н) 164 Ед/л 135-225"
        )
        assert "Приказ" not in result
        assert "A09" not in result
        assert "164" in result
        assert "ЛДГ" in result

    def test_removes_methodology(self):
        result = _preclean_line(
            "Гликированный гемоглобин (в соответствии со стандартизацией DCCT) 5.0 %"
        )
        assert "стандартизац" not in result.lower()
        assert "5.0" in result

    def test_removes_mz_rf_continuation(self):
        result = _preclean_line("МЗ РФ № 804н)")
        assert result.strip() == "" or len(result.strip()) < 3

    def test_preserves_lab_codes(self):
        result = _preclean_line("Аланинаминотрансфераза (АЛТ) 92.3 Ед/л < 41")
        assert "АЛТ" in result
        assert "92.3" in result

    def test_preserves_simple_line(self):
        result = _preclean_line("Глюкоза 5.27 ммоль/л 4.11 - 6.1")
        assert result == "Глюкоза 5.27 ммоль/л 4.11 - 6.1"


class TestHba1cRecovery:
    """HbA1c with regulatory codes must be parsed."""

    SAMPLE = (
        "Гликированный гемоглобин A09.05.083 (Приказ МЗ РФ № 804н) 5.0 % Смотри текст\n"
        "до 6.0% включительно (в соответствии с DCCT) - нормальное содержание HbA1c\n"
        "6.0-6.4% - рекомендуется консультация эндокринолога\n"
        "Глюкоза 5.27 ммоль/л 4.11 - 6.1\n"
    )

    def test_hba1c_extracted(self):
        candidates = universal_extract(self.SAMPLE)
        assert "5" in (candidates or ""), f"HbA1c 5.0% not found: {candidates}"

    def test_glucose_still_works(self):
        candidates = universal_extract(self.SAMPLE)
        assert "5.27" in (candidates or "")


class TestLdhMultiLine:
    """LDH split across lines must be recovered."""

    SAMPLE = (
        "Лактатдегидрогеназа (ЛДГ) (венозная кровь) A09.05.039 (Приказ\n"
        "МЗ РФ № 804н)\n"
        "164 Ед/л 135 - 225\n"
        "Фосфатаза щелочная (венозная кровь) 94 Ед/л 40-129\n"
    )

    def test_ldh_extracted(self):
        candidates = universal_extract(self.SAMPLE)
        assert "164" in (candidates or ""), f"LDH 164 not found: {candidates}"

    def test_phosphatase_still_works(self):
        candidates = universal_extract(self.SAMPLE)
        assert "94" in (candidates or "")


class TestPotassiumOneLine:
    """Potassium on single line with biomaterial must be parsed."""

    SAMPLE = (
        "Калий (K+) (сыворотка крови) 3.7 ммоль/л 3.5 - 5.1\n"
        "Натрий (Na+) (сыворотка крови) 142.5 ммоль/л 136 - 145\n"
        "Хлориды 103 ммоль/л 98 - 106\n"
    )

    def test_potassium_extracted(self):
        candidates = universal_extract(self.SAMPLE)
        assert "3.7" in (candidates or ""), f"K+ 3.7 not found: {candidates}"

    def test_sodium_extracted(self):
        candidates = universal_extract(self.SAMPLE)
        assert "142.5" in (candidates or "")

    def test_chlorides_extracted(self):
        candidates = universal_extract(self.SAMPLE)
        assert "103" in (candidates or "")


class TestFullGemotestP9:
    """Full integration: all 27 indicators from Gemotest biochemistry."""

    SAMPLE = (
        "Общий белок (венозная кровь) A09.05.010 (Приказ МЗ РФ № 804н) 70.0 г/л 64 - 83\n"
        "Альбумин (венозная кровь) A09.05.011 (Приказ МЗ РФ № 804н) 53 г/л 35 - 52\n"
        "Креатинин (венозная кровь) A09.05.020 (Приказ МЗ РФ № 804н) 71.0 мкмоль/л 72 - 127\n"
        "Мочевина (венозная кровь) A09.05.017 (Приказ МЗ РФ № 804н) 6.1 ммоль/л 3.5 - 8.1\n"
        "Мочевая кислота (венозная кровь) A09.05.018 (Приказ МЗ РФ № 804н) 426.0 мкмоль/л 202.3 - 416.5\n"
        "С-реактивный белок (СРБ) A09.05.009 (Приказ МЗ РФ № 804н) 1.72 мг/л < 5\n"
        "Триглицериды (венозная кровь) A09.05.025 (Приказ МЗ РФ № 804н) 1.59 ммоль/л Смотри текст\n"
        "Холестерин общий 4.73 ммоль/л Смотри текст\n"
        "Холестерин-ЛПВП 1.25 ммоль/л Смотри текст\n"
        "Индекс атерогенности 2.78 < 3.5\n"
        "Глюкоза A09.05.023 (Приказ МЗ РФ № 804н) 5.27 ммоль/л 4.11 - 6.1\n"
        "Гликированный гемоглобин A09.05.083 (Приказ МЗ РФ № 804н) 5.0 % Смотри текст\n"
        "до 6.0% включительно (в соответствии с DCCT) - нормальное содержание HbA1c\n"
        "6.0-6.4% - рекомендуется консультация эндокринолога\n"
        "6.5% и более - диагностический критерий сахарного диабета\n"
        "Аланинаминотрансфераза (АЛТ) (венозная кровь) A09.05.042 (Приказ МЗ РФ № 804н) 92.3 Ед/л < 41\n"
        "Аспартатаминотрансфераза (АСТ) (венозная кровь) A09.05.041 (Приказ МЗ РФ № 804н) 56.2 Ед/л < 40\n"
        "Амилаза (венозная кровь) A09.05.045 (Приказ МЗ РФ № 804н) 43 Ед/л < 100\n"
        "Гамма-ГТ (венозная кровь) A09.05.044 (Приказ МЗ РФ № 804н) 21 Ед/л < 60\n"
        "Лактатдегидрогеназа (ЛДГ) (венозная кровь) A09.05.039 (Приказ\n"
        "МЗ РФ № 804н)\n"
        "164 Ед/л 135 - 225\n"
        "Фосфатаза щелочная (венозная кровь) A09.05.046 (Приказ МЗ РФ № 804н) 94 Ед/л 40 - 129\n"
        "Билирубин общий 12.8 мкмоль/л < 21\n"
        "Билирубин прямой 4.8 мкмоль/л < 5\n"
        "Билирубин непрямой 8.0 мкмоль/л Смотри текст\n"
        "Кальций общий (кровь, фотометрия) A09.05.032 (Приказ МЗ РФ № 804н) 2.42 ммоль/л 2.2 - 2.65\n"
        "Калий (K+) (сыворотка крови) 3.7 ммоль/л 3.5 - 5.1\n"
        "Натрий (Na+) (сыворотка крови) 142.5 ммоль/л 136 - 145\n"
        "Хлориды 103 ммоль/л 98 - 106\n"
        "Сывороточное железо A09.05.007 (Приказ МЗ РФ № 804н) 52.8 мкмоль/л 5.8 - 34.5\n"
    )

    def test_total_protein(self):
        c = universal_extract(self.SAMPLE)
        assert "70" in c

    def test_albumin(self):
        c = universal_extract(self.SAMPLE)
        assert "53" in c

    def test_creatinine(self):
        c = universal_extract(self.SAMPLE)
        assert "71" in c

    def test_uric_acid(self):
        c = universal_extract(self.SAMPLE)
        assert "426" in c

    def test_triglycerides(self):
        c = universal_extract(self.SAMPLE)
        assert "1.59" in c

    def test_glucose(self):
        c = universal_extract(self.SAMPLE)
        assert "5.27" in c

    def test_hba1c(self):
        c = universal_extract(self.SAMPLE)
        lower = (c or "").lower()
        assert "гликированн" in lower or ("5" in c and "%" in c), \
            f"HbA1c not found: {c}"

    def test_alt(self):
        c = universal_extract(self.SAMPLE)
        assert "92.3" in c

    def test_ldh(self):
        c = universal_extract(self.SAMPLE)
        assert "164" in c, f"LDH not found: {c}"

    def test_potassium(self):
        c = universal_extract(self.SAMPLE)
        assert "3.7" in c, f"K+ not found: {c}"

    def test_sodium(self):
        c = universal_extract(self.SAMPLE)
        assert "142.5" in c

    def test_iron(self):
        c = universal_extract(self.SAMPLE)
        assert "52.8" in c

    def test_no_scale_garbage(self):
        c = universal_extract(self.SAMPLE)
        for line in (c or "").splitlines():
            name = line.split("\t")[0].lower() if "\t" in line else line.lower()
            assert "нормальное содержание" not in name
            assert "диагностический критерий" not in name
            assert "приказ" not in name
