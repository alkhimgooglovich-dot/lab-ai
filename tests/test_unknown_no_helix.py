"""
Тест Этапа 5.1: при UNKNOWN helix-парсер НЕ вызывается.

Запуск: pytest tests/test_unknown_no_helix.py -v
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.lab_detector import detect_lab, LabType


class TestUnknownNeverCallsHelix:
    """Гарантируем: UNKNOWN → universal, helix НЕ вызывается."""

    def test_unknown_detection_for_generic_text(self):
        """Обычный текст без сигнатур → UNKNOWN."""
        text = "Гемоглобин 145 г/л 120-160\nЛейкоциты 5.2 10^9/л 4.0-9.0"
        result = detect_lab(text)
        assert result.lab_type == LabType.UNKNOWN

    def test_unknown_does_not_call_helix_parser(self):
        """При UNKNOWN _smart_to_candidates НЕ вызывает helix_table_to_candidates."""
        from engine import _smart_to_candidates

        text = "Гемоглобин 145 г/л 120-160\nЛейкоциты 5.2 10^9/л 4.0-9.0"

        with patch("engine.helix_table_to_candidates") as mock_helix:
            _smart_to_candidates(text)
            mock_helix.assert_not_called()

    def test_universal_fallback_does_not_call_helix(self):
        """Если universal тоже пуст → всё равно helix НЕ вызывается."""
        from engine import _smart_to_candidates

        text = "какой-то абсолютно неразборчивый текст ъъъъ"

        with patch("engine.helix_table_to_candidates") as mock_helix:
            result = _smart_to_candidates(text)
            mock_helix.assert_not_called()
            assert result == ""

    def test_helix_called_only_when_detected_as_helix(self):
        """helix_table_to_candidates вызывается ТОЛЬКО при LabType.HELIX."""
        from engine import _smart_to_candidates

        # Текст с Helix-сигнатурами
        helix_text = "helix.ru\nИсследование\tРезультат\nWBC\t5.0"

        with patch("engine.helix_table_to_candidates", return_value="WBC\t5.0\t10^9/л\t\t") as mock_helix:
            _smart_to_candidates(helix_text)
            mock_helix.assert_called_once()



