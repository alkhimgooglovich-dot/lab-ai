"""
Preprocessing изображений перед OCR.
Операции: grayscale → autocontrast → deskew → upscale (если маленькое) → sharpen → (adaptive threshold).
"""
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import io
from typing import Tuple

import numpy as np
import cv2

# Пороги
MIN_WIDTH = 1200          # если ширина меньше — upscale
MAX_WIDTH = 4000          # если больше — не upscale (чтобы не раздувать)
SHARPEN_FACTOR = 1.3      # мягкий sharpen (1.0 = без изменений)

# Deskew
DESKEW_MAX_ANGLE = 15.0   # максимальный угол коррекции (градусы)
                           # если наклон > 15° — скорее всего ошибка детекции, пропускаем

# Adaptive threshold
ADAPTIVE_BLOCK_SIZE = 35   # размер блока для adaptive threshold (нечётное число)
ADAPTIVE_C = 10            # константа вычитания из среднего


def _deskew_image(img: Image.Image, max_angle: float = DESKEW_MAX_ANGLE) -> Image.Image:
    """
    Определяет наклон текста и выравнивает изображение.
    Fail-safe: при ошибке возвращает оригинал.
    """
    try:
        # PIL → numpy
        arr = np.array(img)

        # Для определения угла нужен grayscale
        if len(arr.shape) == 3:
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        else:
            gray = arr.copy()

        # Canny edges
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)

        # Hough lines
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=100,
            minLineLength=gray.shape[1] // 8,  # минимум 1/8 ширины
            maxLineGap=10,
        )

        if lines is None or len(lines) == 0:
            return img  # линий нет — возвращаем как есть

        # Вычисляем углы всех найденных линий
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 - x1 == 0:
                continue
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            # Берём только «почти горизонтальные» линии (±45°)
            if abs(angle) < 45:
                angles.append(angle)

        if not angles:
            return img

        # Медианный угол — устойчив к выбросам
        median_angle = float(np.median(angles))

        # Слишком маленький угол — не крутим
        if abs(median_angle) < 0.1:
            return img

        # Слишком большой угол — вероятно ошибка
        if abs(median_angle) > max_angle:
            return img

        # Поворачиваем
        h, w = arr.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        rotated = cv2.warpAffine(
            arr, M, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,  # заполняем края копией
        )

        return Image.fromarray(rotated)

    except Exception:
        return img  # fail-safe


def _adaptive_threshold(
    img: Image.Image,
    block_size: int = ADAPTIVE_BLOCK_SIZE,
    c: int = ADAPTIVE_C,
) -> Image.Image:
    """
    Мягкая бинаризация через adaptive threshold.
    Fail-safe: при ошибке возвращает оригинал.
    """
    try:
        arr = np.array(img)

        # Нужен grayscale
        if len(arr.shape) == 3:
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        else:
            gray = arr.copy()

        # Adaptive threshold
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block_size,
            c,
        )

        return Image.fromarray(binary)

    except Exception:
        return img  # fail-safe


def preprocess_image_bytes(
    image_bytes: bytes,
    mime_type: str,
    *,
    enable_grayscale: bool = True,
    enable_autocontrast: bool = True,
    enable_upscale: bool = True,
    enable_sharpen: bool = True,
    enable_deskew: bool = True,
    enable_adaptive_threshold: bool = False,
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

    # 3. Deskew — выравнивание наклона
    if enable_deskew:
        img = _deskew_image(img)

    # 4. Upscale — если изображение маленькое, увеличиваем
    if enable_upscale and img.width < min_width and img.width < MAX_WIDTH:
        scale = min_width / img.width
        new_size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(new_size, Image.LANCZOS)

    # 5. Лёгкий sharpen — подчёркиваем края букв
    if enable_sharpen and sharpen_factor > 1.0:
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(sharpen_factor)

    # 6. Adaptive threshold — мягкая бинаризация
    if enable_adaptive_threshold:
        img = _adaptive_threshold(img)

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

