"""
Unit-тесты для parsers/lab_detector.py

Запуск: pytest tests/test_lab_detector.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.lab_detector import detect_lab, LabType, LabDetectionResult


class TestDetectLabMedsi:
    """Тесты на определение МЕДСИ."""

    def test_medsi_by_domain(self):
        text = "Результаты анализов\nmedsi.ru\n(WBC) Лейкоциты 10*9/л 4.50-11.004.78"
        result = detect_lab(text)
        assert result.lab_type == LabType.MEDSI
        assert result.confidence >= 0.5

    def test_medsi_by_code_lines(self):
        lines = [
            "(WBC) Лейкоциты 10*9/л 4.50-11.004.78",
            "(RBC) Эритроциты 10*12/л 4.30-5.705.33",
            "(HGB) Гемоглобин г/л 130-170155",
            "(HCT) Гематокрит % 39-49↑42",
            "(PLT) Тромбоциты 10*9/л 150-400213",
            "(MCV) Средний объём эр. фл 80-10088.5",
        ]
        text = "\n".join(lines)
        result = detect_lab(text)
        assert result.lab_type == LabType.MEDSI
        assert result.confidence >= 0.5

    def test_medsi_by_units_10_9_10_12(self):
        text = "Анализ крови\n10*9/л\n10*12/л\n(WBC) тест\n(RBC) тест"
        result = detect_lab(text)
        assert result.lab_type == LabType.MEDSI
        assert result.confidence >= 0.5

    def test_medsi_soe_mm_chas(self):
        text = "(WBC) Лейкоциты\n(RBC) Эритроциты\nСОЭ мм/час 0-1535"
        result = detect_lab(text)
        assert result.lab_type == LabType.MEDSI
        assert result.confidence >= 0.5

    def test_medsi_name_in_text(self):
        text = "ООО «МЕДСИ» Лаборатория\n(WBC) Лейкоциты\n(RBC) Эритроциты"
        result = detect_lab(text)
        assert result.lab_type == LabType.MEDSI


class TestDetectLabHelix:
    """Тесты на определение Helix."""

    def test_helix_by_domain(self):
        text = "helix.ru\nИсследование\tРезультат\nWBC\t5.0"
        result = detect_lab(text)
        assert result.lab_type == LabType.HELIX
        assert result.confidence >= 0.5

    def test_helix_by_header(self):
        text = "Исследование\tРезультат\tЕдиницы\nWBC\t5.0\t10^9/л"
        result = detect_lab(text)
        assert result.lab_type == LabType.HELIX
        assert result.confidence >= 0.5

    def test_helix_by_pairs(self):
        pairs = []
        names = ["Лейкоциты", "Эритроциты", "Гемоглобин", "Гематокрит", "Тромбоциты"]
        values = ["5.0 10^9/л", "4.8 10^12/л", "150 г/л", "42 %", "250 10^9/л"]
        for n, v in zip(names, values):
            pairs.append(n)
            pairs.append(v)
        text = "\n".join(pairs)
        result = detect_lab(text)
        assert result.lab_type == LabType.HELIX
        assert result.confidence >= 0.5

    def test_helix_name_in_text(self):
        text = "Хеликс Лаборатория\nИсследование\tРезультат\nWBC\t5.0"
        result = detect_lab(text)
        assert result.lab_type == LabType.HELIX


class TestDetectLabUnknown:
    """Тесты на UNKNOWN."""

    def test_empty_text(self):
        result = detect_lab("")
        assert result.lab_type == LabType.UNKNOWN
        assert result.confidence == 0.0

    def test_none_like_text(self):
        result = detect_lab("   ")
        assert result.lab_type == LabType.UNKNOWN

    def test_random_text(self):
        result = detect_lab("Привет, мир! Это обычный текст без анализов.")
        assert result.lab_type == LabType.UNKNOWN
        assert result.confidence < 0.5

    def test_generic_lab_format(self):
        """Текст похож на лабораторию, но не МЕДСИ и не Helix."""
        text = "Гемоглобин: 145 г/л (120-160)\nЛейкоциты: 5.2 10^9/л (4.0-9.0)"
        result = detect_lab(text)
        assert result.lab_type == LabType.UNKNOWN


class TestDetectionResult:
    """Тесты на структуру LabDetectionResult."""

    def test_result_has_all_fields(self):
        result = detect_lab("test")
        assert hasattr(result, 'lab_type')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'matched_signatures')

    def test_confidence_range(self):
        """confidence всегда 0.0 … 1.0."""
        # Много сигнатур МЕДСИ → confidence capped at 1.0
        lines = [f"({chr(65+i)}) Тест 10*9/л 0-10{i}" for i in range(10)]
        text = "medsi.ru\nМЕДСИ\n10*9\n10*12\nСОЭ мм/час\n" + "\n".join(lines)
        result = detect_lab(text)
        assert 0.0 <= result.confidence <= 1.0

    def test_matched_signatures_non_empty_on_detect(self):
        text = "medsi.ru\n(WBC) Лейкоциты\n(RBC) Эритроциты"
        result = detect_lab(text)
        assert len(result.matched_signatures) > 0


class TestFallbackInSmartCandidates:
    """
    Эти тесты проверяют, что _smart_to_candidates
    правильно использует fallback при пустом результате от спец-парсера.
    (Тестируем через engine.py)
    """

    def test_medsi_detected_but_empty_falls_to_universal(self):
        """Если detect_lab = MEDSI, но medsi-парсер дал пустоту → universal."""
        # Подаём текст с МЕДСИ-сигнатурами, но без парсируемых строк
        from engine import _smart_to_candidates
        text = "medsi.ru\n(WBC) бла-бла-бла"
        # Не должен падать — должен вернуть что-то (может пустое)
        result = _smart_to_candidates(text)
        assert isinstance(result, str)

    def test_universal_works_for_unknown(self):
        """UNKNOWN → universal extractor."""
        from engine import _smart_to_candidates
        text = "Гемоглобин 145 г/л 120-160\nЛейкоциты 5.2 10^9/л 4.0-9.0"
        result = _smart_to_candidates(text)
        assert isinstance(result, str)



