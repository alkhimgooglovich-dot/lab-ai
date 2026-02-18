"""
Тесты preprocessing изображений для OCR.
Минимальный набор: корректность работы, формат, размеры, fallback.
"""
import pytest
from PIL import Image
import io

from ocr_preprocess import preprocess_image_bytes, get_image_info


def _make_test_image(width=800, height=600, mode="RGB", fmt="JPEG") -> bytes:
    """Создаёт тестовое изображение заданного размера."""
    img = Image.new(mode, (width, height), color=(128, 128, 128))
    # Добавляем немного "текста" — чёрные полоски (имитация строк)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    for y in range(100, height - 50, 40):
        draw.rectangle([50, y, width - 50, y + 8], fill=(20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _make_grayscale_image(width=800, height=600) -> bytes:
    img = Image.new("L", (width, height), color=128)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestPreprocessBasic:
    """Базовые тесты: не падает, возвращает корректный результат."""

    def test_jpeg_returns_png_bytes(self):
        raw = _make_test_image(800, 600, "RGB", "JPEG")
        result, mime = preprocess_image_bytes(raw, "image/jpeg")
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert mime == "image/png"

    def test_png_returns_png_bytes(self):
        raw = _make_test_image(800, 600, "RGB", "PNG")
        result, mime = preprocess_image_bytes(raw, "image/png")
        assert isinstance(result, bytes)
        assert mime == "image/png"

    def test_result_is_valid_image(self):
        raw = _make_test_image(800, 600)
        result, _ = preprocess_image_bytes(raw, "image/jpeg")
        img = Image.open(io.BytesIO(result))
        assert img.width > 0
        assert img.height > 0
        assert img.format == "PNG"

    def test_grayscale_input_works(self):
        """Grayscale изображение на входе не должно падать."""
        raw = _make_grayscale_image(800, 600)
        result, mime = preprocess_image_bytes(raw, "image/png")
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestPreprocessUpscale:
    """Тесты upscale: маленькие изображения увеличиваются."""

    def test_small_image_upscaled(self):
        raw = _make_test_image(600, 400)
        result, _ = preprocess_image_bytes(raw, "image/jpeg", min_width=1200)
        img = Image.open(io.BytesIO(result))
        assert img.width >= 1200

    def test_large_image_not_upscaled(self):
        raw = _make_test_image(2000, 1500)
        result, _ = preprocess_image_bytes(raw, "image/jpeg", min_width=1200)
        img = Image.open(io.BytesIO(result))
        assert img.width == 2000  # не менялся

    def test_upscale_preserves_aspect_ratio(self):
        raw = _make_test_image(600, 400)  # ratio = 1.5
        result, _ = preprocess_image_bytes(raw, "image/jpeg", min_width=1200)
        img = Image.open(io.BytesIO(result))
        ratio = img.width / img.height
        assert abs(ratio - 1.5) < 0.05  # допуск на округление


class TestPreprocessGrayscale:
    """Тесты: результат в grayscale."""

    def test_output_is_grayscale(self):
        raw = _make_test_image(800, 600, "RGB")
        result, _ = preprocess_image_bytes(raw, "image/jpeg", enable_grayscale=True)
        img = Image.open(io.BytesIO(result))
        assert img.mode == "L"

    def test_disable_grayscale(self):
        raw = _make_test_image(800, 600, "RGB")
        result, _ = preprocess_image_bytes(
            raw, "image/jpeg",
            enable_grayscale=False, enable_upscale=False
        )
        img = Image.open(io.BytesIO(result))
        assert img.mode == "RGB"


class TestPreprocessFlags:
    """Тесты: отключение отдельных операций через флаги."""

    def test_all_disabled_still_works(self):
        raw = _make_test_image(800, 600)
        result, mime = preprocess_image_bytes(
            raw, "image/jpeg",
            enable_grayscale=False,
            enable_autocontrast=False,
            enable_upscale=False,
            enable_sharpen=False,
        )
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert mime == "image/png"

    def test_only_sharpen(self):
        raw = _make_test_image(800, 600)
        result, _ = preprocess_image_bytes(
            raw, "image/jpeg",
            enable_grayscale=False,
            enable_autocontrast=False,
            enable_upscale=False,
            enable_sharpen=True,
            sharpen_factor=2.0,
        )
        assert isinstance(result, bytes)


class TestGetImageInfo:
    """Тесты вспомогательной функции."""

    def test_info_returns_correct_dims(self):
        raw = _make_test_image(640, 480, "RGB", "JPEG")
        info = get_image_info(raw)
        assert info["width"] == 640
        assert info["height"] == 480
        assert info["mode"] == "RGB"
        assert info["format"] == "JPEG"

