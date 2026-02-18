"""
Preprocessing изображений перед OCR.
Операции: grayscale → autocontrast → upscale (если маленькое) → лёгкий sharpen.
"""
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import io
from typing import Tuple

# Пороги
MIN_WIDTH = 1200          # если ширина меньше — upscale
MAX_WIDTH = 4000          # если больше — не upscale (чтобы не раздувать)
SHARPEN_FACTOR = 1.3      # мягкий sharpen (1.0 = без изменений)


def preprocess_image_bytes(
    image_bytes: bytes,
    mime_type: str,
    *,
    enable_grayscale: bool = True,
    enable_autocontrast: bool = True,
    enable_upscale: bool = True,
    enable_sharpen: bool = True,
    min_width: int = MIN_WIDTH,
    sharpen_factor: float = SHARPEN_FACTOR,
) -> Tuple[bytes, str]:
    """
    Принимает сырые байты изображения, возвращает обработанные байты + mime_type.

    Returns:
        (processed_bytes, output_mime_type)
        output_mime_type всегда "image/png" (для максимальной совместимости OCR).
    """
    img = Image.open(io.BytesIO(image_bytes))

    # 1. Grayscale — убираем цветовой шум
    if enable_grayscale:
        img = img.convert("L")  # "L" = grayscale
    else:
        img = img.convert("RGB")

    # 2. Autocontrast — выравниваем гистограмму яркости
    if enable_autocontrast:
        img = ImageOps.autocontrast(img, cutoff=1)

    # 3. Upscale — если изображение маленькое, увеличиваем
    if enable_upscale and img.width < min_width and img.width < MAX_WIDTH:
        scale = min_width / img.width
        new_size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(new_size, Image.LANCZOS)

    # 4. Лёгкий sharpen — подчёркиваем края букв
    if enable_sharpen and sharpen_factor > 1.0:
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(sharpen_factor)

    # Сохраняем как PNG (lossless, OCR-friendly)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), "image/png"


def get_image_info(image_bytes: bytes) -> dict:
    """Вспомогательная: размеры и формат для логирования."""
    img = Image.open(io.BytesIO(image_bytes))
    return {
        "width": img.width,
        "height": img.height,
        "mode": img.mode,
        "format": img.format,
    }

