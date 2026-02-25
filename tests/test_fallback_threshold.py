"""
Тесты: fallback-логика в _smart_to_candidates.

Если специализированный парсер (МЕДСИ/HELIX) возвращает < 5 кандидатов,
система переключается на universal_extract.

Запуск: pytest tests/test_fallback_threshold.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch
from engine import _smart_to_candidates
from parsers.lab_detector import LabType, LabDetectionResult


# Мок для detect_lab — возвращает MEDSI
def _mock_detect_medsi(text):
    return LabDetectionResult(LabType.MEDSI, confidence=0.9, matched_signatures=["medsi.ru"])


# Мок для detect_lab — возвращает HELIX
def _mock_detect_helix(text):
    return LabDetectionResult(LabType.HELIX, confidence=0.9, matched_signatures=["helix.ru"])


# Текст, который universal_extract может распарсить
PARSEABLE_TEXT = """\
Гемоглобин 144 г/л 132 - 172
Эритроциты 4.85 *10^12/л 4.28 - 5.78
Гематокрит 42.30 % 39.51 - 50.95
Тромбоциты 191 *10^9/л 148 - 339
Лейкоциты 4.07 *10^9/л 3.9 - 10.9
СОЭ 5 мм/час 0 - 20
"""


class TestMedsiFallback:
    """МЕДСИ с < 5 кандидатами → fallback на universal."""

    @patch("parsers.medsi_extractor.medsi_inline_to_candidates", return_value="СОЭ\t5\t0-20\tмм/час\nMCV\t87.3\t82-98\tфл")
    @patch("parsers.lab_detector.detect_lab", side_effect=_mock_detect_medsi)
    def test_medsi_few_candidates_falls_to_universal(self, mock_detect, mock_medsi):
        """МЕДСИ вернул 2 кандидата → universal должен дать больше."""
        result = _smart_to_candidates(PARSEABLE_TEXT)
        lines = result.strip().splitlines() if result else []
        # universal должен извлечь >= 5 из PARSEABLE_TEXT
        assert len(lines) >= 5, f"Expected >= 5 candidates, got {len(lines)}"

    @patch("parsers.medsi_extractor.medsi_inline_to_candidates", return_value="a\t1\t0-1\tx\nb\t2\t0-2\tx\nc\t3\t0-3\tx\nd\t4\t0-4\tx\ne\t5\t0-5\tx")
    @patch("parsers.lab_detector.detect_lab", side_effect=_mock_detect_medsi)
    def test_medsi_enough_candidates_no_fallback(self, mock_detect, mock_medsi):
        """МЕДСИ вернул 5 кандидатов → fallback НЕ нужен."""
        result = _smart_to_candidates(PARSEABLE_TEXT)
        lines = result.strip().splitlines() if result else []
        # Должен вернуть 5 кандидатов от МЕДСИ, не от universal
        assert len(lines) == 5
        assert lines[0].startswith("a\t")


class TestHelixFallback:
    """HELIX с < 5 кандидатами → fallback на universal."""

    @patch("engine.helix_table_to_candidates", return_value="WBC\t5.0\t4-10\t*10^9/л")
    @patch("parsers.lab_detector.detect_lab", side_effect=_mock_detect_helix)
    def test_helix_few_candidates_falls_to_universal(self, mock_detect, mock_helix):
        """HELIX вернул 1 кандидат → universal должен дать больше."""
        result = _smart_to_candidates(PARSEABLE_TEXT)
        lines = result.strip().splitlines() if result else []
        assert len(lines) >= 5, f"Expected >= 5 candidates, got {len(lines)}"


class TestNoFallbackWhenEmpty:
    """Пустой результат от специализированного парсера → fallback."""

    @patch("parsers.medsi_extractor.medsi_inline_to_candidates", return_value="")
    @patch("parsers.lab_detector.detect_lab", side_effect=_mock_detect_medsi)
    def test_medsi_empty_falls_to_universal(self, mock_detect, mock_medsi):
        """МЕДСИ вернул пустоту → universal."""
        result = _smart_to_candidates(PARSEABLE_TEXT)
        lines = result.strip().splitlines() if result else []
        assert len(lines) >= 5

