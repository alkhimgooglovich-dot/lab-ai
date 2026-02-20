"""
B5-A: Тесты preflight-решения о режиме OCR.

Запуск:
    pytest tests/test_ocr_preflight_b5a.py -v

Что тестируем:
1) Картинка (PNG/JPEG) → adaptive_threshold=True, reason=IMAGE_LIKE_INPUT
2) PDF с пустым текстовым слоем → adaptive_threshold=True, reason=PDF_EMPTY_TEXT_LAYER
3) PDF с нормальным текстом → adaptive_threshold=False, reason=PRE_FLIGHT_DEFAULT
4) Preflight НЕ ломает rerun (B2) — если после preflight score всё ещё плохой
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.ocr_preflight import choose_ocr_mode_preflight


# ╔══════════════════════════════════════════════════════════════════╗
# ║ Тест 1: Вход — изображение → adaptive_threshold=True           ║
# ╚══════════════════════════════════════════════════════════════════╝

class TestPreflightImageInput:
    """Если на вход подают картинку — сразу включаем adaptive_threshold."""

    def test_png_by_mimetype(self):
        result = choose_ocr_mode_preflight(
            file_bytes=b"\x89PNG\r\n",
            filename="scan.png",
            content_type="image/png",
        )
        assert result["adaptive_threshold"] is True
        assert result["reason"] == "IMAGE_LIKE_INPUT"

    def test_jpeg_by_mimetype(self):
        result = choose_ocr_mode_preflight(
            file_bytes=b"\xff\xd8\xff",
            filename="photo.jpg",
            content_type="image/jpeg",
        )
        assert result["adaptive_threshold"] is True
        assert result["reason"] == "IMAGE_LIKE_INPUT"

    def test_webp_by_extension(self):
        result = choose_ocr_mode_preflight(
            file_bytes=b"RIFF",
            filename="screenshot.webp",
            content_type="",
        )
        assert result["adaptive_threshold"] is True
        assert result["reason"] == "IMAGE_LIKE_INPUT"

    def test_image_by_mime_only(self):
        """MIME image/* но без расширения — всё равно считаем картинкой."""
        result = choose_ocr_mode_preflight(
            file_bytes=b"\x89PNG\r\n",
            filename="upload",  # без расширения
            content_type="image/png",
        )
        assert result["adaptive_threshold"] is True
        assert result["reason"] == "IMAGE_LIKE_INPUT"


# ╔══════════════════════════════════════════════════════════════════╗
# ║ Тест 2: PDF с пустым текстовым слоем → adaptive_threshold=True  ║
# ╚══════════════════════════════════════════════════════════════════╝

class TestPreflightPdfEmptyText:
    """PDF, у которого pypdf вернул пустой/очень короткий текст."""

    def test_empty_text(self):
        result = choose_ocr_mode_preflight(
            file_bytes=b"%PDF-1.4",
            filename="scan.pdf",
            content_type="application/pdf",
            pdf_direct_text="",
        )
        assert result["adaptive_threshold"] is True
        assert result["reason"] == "PDF_EMPTY_TEXT_LAYER"

    def test_whitespace_only(self):
        result = choose_ocr_mode_preflight(
            file_bytes=b"%PDF-1.4",
            filename="scan.pdf",
            content_type="application/pdf",
            pdf_direct_text="   \n  \t  ",
        )
        assert result["adaptive_threshold"] is True
        assert result["reason"] == "PDF_EMPTY_TEXT_LAYER"

    def test_very_short_text(self):
        """Текст < 20 символов — считаем пустым."""
        result = choose_ocr_mode_preflight(
            file_bytes=b"%PDF-1.4",
            filename="scan.pdf",
            content_type="application/pdf",
            pdf_direct_text="Стр 1",  # 5 символов
        )
        assert result["adaptive_threshold"] is True
        assert result["reason"] == "PDF_EMPTY_TEXT_LAYER"


# ╔══════════════════════════════════════════════════════════════════╗
# ║ Тест 3: PDF с нормальным текстом → adaptive_threshold=False    ║
# ╚══════════════════════════════════════════════════════════════════╝

class TestPreflightPdfWithText:
    """PDF с нормальным текстовым слоем — не включаем preflight."""

    def test_normal_text(self):
        long_text = "Общий анализ крови\nWBC 6.5 4.0-9.0 10^9/л\nRBC 4.5 3.8-5.1 10^12/л"
        result = choose_ocr_mode_preflight(
            file_bytes=b"%PDF-1.4",
            filename="results.pdf",
            content_type="application/pdf",
            pdf_direct_text=long_text,
        )
        assert result["adaptive_threshold"] is False
        assert result["reason"] == "PRE_FLIGHT_DEFAULT"

    def test_pdf_without_direct_text_check(self):
        """Если pdf_direct_text=None (pypdf не вызывали) — default."""
        result = choose_ocr_mode_preflight(
            file_bytes=b"%PDF-1.4",
            filename="results.pdf",
            content_type="application/pdf",
            pdf_direct_text=None,
        )
        assert result["adaptive_threshold"] is False
        assert result["reason"] == "PRE_FLIGHT_DEFAULT"


# ╔══════════════════════════════════════════════════════════════════╗
# ║ Тест 4: Preflight НЕ ломает rerun (B2)                        ║
# ╚══════════════════════════════════════════════════════════════════╝

class TestPreflightDoesNotBreakRerun:
    """
    Даже если preflight включил adaptive_threshold=True,
    rerun (B2) должен остаться доступным, если score < 45.

    Тестируем через monkeypatch функции engine.
    """

    def test_rerun_still_possible_after_preflight(self):
        """
        Сценарий:
        - Файл = PNG (preflight → adaptive_threshold=True)
        - Первый OCR возвращает мало данных (score < 45)
        - Проверяем, что preflight не блокирует возможность rerun

        Мы тестируем только choose_ocr_mode_preflight — она НЕ влияет на rerun.
        Rerun решается в engine.py по parse_score, а preflight только выбирает
        режим ПЕРВОГО прогона.
        """
        # Preflight для PNG
        preflight = choose_ocr_mode_preflight(
            file_bytes=b"\x89PNG",
            filename="bad_scan.png",
            content_type="image/png",
        )
        assert preflight["adaptive_threshold"] is True

        # Проверяем что preflight вернул только режим, а не решение о rerun
        assert "rerun" not in preflight
        assert "score" not in preflight

        # Preflight не содержит ничего, что могло бы заблокировать rerun
        # Rerun решается отдельно в engine.py по OCR_RERUN_MIN_SCORE


# ╔══════════════════════════════════════════════════════════════════╗
# ║ Тест 5: Диагностика в quality["metrics"]                       ║
# ╚══════════════════════════════════════════════════════════════════╝

class TestPreflightDiagnostics:
    """Проверяем, что результат preflight имеет правильную структуру."""

    def test_result_structure(self):
        result = choose_ocr_mode_preflight(
            file_bytes=b"\x89PNG",
            filename="test.png",
            content_type="image/png",
        )
        assert "adaptive_threshold" in result
        assert "reason" in result
        assert isinstance(result["adaptive_threshold"], bool)
        assert isinstance(result["reason"], str)

    def test_reason_is_known_code(self):
        """Все возвращаемые reason должны быть из известного набора."""
        known_reasons = {
            "PRE_FLIGHT_DEFAULT",
            "IMAGE_LIKE_INPUT",
            "PDF_EMPTY_TEXT_LAYER",
        }

        test_cases = [
            (b"\x89PNG", "test.png", "image/png", None),
            (b"%PDF", "doc.pdf", "application/pdf", ""),
            (b"%PDF", "doc.pdf", "application/pdf", "Полный текст анализов крови с показателями"),
        ]

        for fb, fn, ct, pdt in test_cases:
            result = choose_ocr_mode_preflight(fb, fn, ct, pdf_direct_text=pdt)
            assert result["reason"] in known_reasons, (
                f"Неизвестный reason={result['reason']} для {fn}"
            )

