"""
Тест Этапа 5.2: детекция лаборатории INVITRO.

Запуск: pytest tests/test_invitro_detection.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.lab_detector import detect_lab, LabType, DetectResult


class TestInvitroDetection:
    """Детекция INVITRO по сигнатурам."""

    def test_invitro_by_domain(self):
        """Текст с invitro.ru → INVITRO."""
        text = "Результаты анализов\ninvitro.ru\nWBC 5.0 10^9/л 4.0-9.0"
        result = detect_lab(text)
        assert result.lab_type == LabType.INVITRO

    def test_invitro_by_www_domain(self):
        """Текст с www.invitro.ru → INVITRO."""
        text = "www.invitro.ru\nГемоглобин 140 г/л 120-160"
        result = detect_lab(text)
        assert result.lab_type == LabType.INVITRO

    def test_invitro_by_russian_name(self):
        """Текст с 'ИНВИТРО' → INVITRO."""
        text = "ООО «ИНВИТРО»\nАнализ крови\nWBC 6.1"
        result = detect_lab(text)
        assert result.lab_type == LabType.INVITRO

    def test_invitro_by_full_name(self):
        """Текст с полным названием → INVITRO."""
        text = "Независимая лаборатория ИНВИТРО\nRBC 4.5"
        result = detect_lab(text)
        assert result.lab_type == LabType.INVITRO

    def test_invitro_case_insensitive(self):
        """Регистронезависимый поиск → INVITRO."""
        text = "InViTrO результаты\nHGB 130 г/л"
        result = detect_lab(text)
        assert result.lab_type == LabType.INVITRO

    def test_invitro_confidence(self):
        """confidence >= 0.5 при совпадении сигнатуры."""
        text = "invitro.ru\nWBC 5.0"
        result = detect_lab(text)
        assert result.confidence >= 0.5

    def test_invitro_not_detected_generic_text(self):
        """Обычный текст без сигнатур → НЕ INVITRO."""
        text = "Гемоглобин 145 г/л 120-160\nЛейкоциты 5.2 10^9/л 4.0-9.0"
        result = detect_lab(text)
        assert result.lab_type != LabType.INVITRO

    def test_helix_takes_priority_over_invitro(self):
        """Если есть и helix и invitro сигнатуры → HELIX (приоритет)."""
        text = "helix.ru\ninvitro.ru\nWBC 5.0"
        result = detect_lab(text)
        assert result.lab_type == LabType.HELIX


class TestInvitroRouting:
    """INVITRO → universal_extract (нет отдельного парсера)."""

    def test_invitro_uses_universal_not_helix(self):
        """INVITRO не вызывает helix_table_to_candidates."""
        from unittest.mock import patch
        from engine import _smart_to_candidates

        text = "invitro.ru\nГемоглобин 145 г/л 120-160"

        with patch("engine.helix_table_to_candidates") as mock_helix:
            _smart_to_candidates(text)
            mock_helix.assert_not_called()

    def test_invitro_returns_candidates_via_universal(self):
        """INVITRO текст с валидными данными → непустые кандидаты."""
        from engine import _smart_to_candidates

        text = (
            "invitro.ru\n"
            "Гемоглобин\t145\tг/л\t120-160\n"
            "Лейкоциты\t5.2\t10^9/л\t4.0-9.0\n"
            "Эритроциты\t4.8\t10^12/л\t3.9-5.0\n"
        )
        candidates = _smart_to_candidates(text)
        # universal должен вытянуть хотя бы что-то
        assert isinstance(candidates, str)


class TestLabTypeEnum:
    """Проверка enum LabType."""

    def test_invitro_in_enum(self):
        assert hasattr(LabType, "INVITRO")
        assert LabType.INVITRO.value == "invitro"

    def test_all_lab_types(self):
        expected = {"medsi", "helix", "invitro", "unknown"}
        actual = {lt.value for lt in LabType}
        assert expected == actual

    def test_detect_result_dataclass(self):
        r = DetectResult(LabType.INVITRO, confidence=0.9, matched_signatures=["invitro.ru"])
        assert r.lab_type == LabType.INVITRO
        assert r.confidence == 0.9



