"""
B5-A: Preflight-решение о режиме OCR.

Детерминированная функция — без ML, без внешних сервисов.
Решает, нужен ли adaptive_threshold=True на ПЕРВОМ прогоне OCR.
"""

from typing import Optional


# Расширения изображений (не PDF)
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

# MIME-типы изображений
_IMAGE_MIMETYPES = {
    "image/jpeg", "image/jpg", "image/png", "image/webp",
    "image/bmp", "image/tiff",
}


def choose_ocr_mode_preflight(
    file_bytes: bytes,
    filename: str = "",
    content_type: str = "",
    pdf_direct_text: Optional[str] = None,
) -> dict:
    """
    Определяет режим OCR ДО первого вызова.

    Аргументы:
        file_bytes:      сырые байты файла
        filename:        имя файла (может быть пустым)
        content_type:    MIME-тип (может быть пустым)
        pdf_direct_text: текст, извлечённый из PDF через pypdf (None если не PDF)

    Возвращает:
        {
            "adaptive_threshold": bool,
            "reason": str,   # код причины для диагностики
        }
    """
    name_lower = (filename or "").lower()

    # ─── Правило 1: вход — изображение (не PDF) ───
    is_image_by_mime = content_type in _IMAGE_MIMETYPES
    is_image_by_ext = any(name_lower.endswith(ext) for ext in _IMAGE_EXTENSIONS)

    if is_image_by_mime or is_image_by_ext:
        return {
            "adaptive_threshold": True,
            "reason": "IMAGE_LIKE_INPUT",
        }

    # ─── Правило 2: PDF, но текстовый слой пустой/очень короткий ───
    is_pdf = (
        content_type == "application/pdf"
        or name_lower.endswith(".pdf")
    )

    if is_pdf and pdf_direct_text is not None:
        stripped = pdf_direct_text.strip()
        # Если pypdf вернул меньше 20 символов — считаем что текстовый слой пустой
        if len(stripped) < 20:
            return {
                "adaptive_threshold": True,
                "reason": "PDF_EMPTY_TEXT_LAYER",
            }

    # ─── По умолчанию: обычный режим ───
    return {
        "adaptive_threshold": False,
        "reason": "PRE_FLIGHT_DEFAULT",
    }

