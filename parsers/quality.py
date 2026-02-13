"""
Модуль оценки качества парсинга.

evaluate_parse_quality(items) -> dict с метриками:
  - parsed_count: сколько показателей с value != None
  - error_count: сколько "ОШИБКА ПАРСИНГА" / None значений
  - suspicious_count: value содержит пробелы / '^' '*' '/' или ref+value склейка
  - coverage_score: parsed_count / expected_minimum
"""

import re
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from engine import Item


# Минимальное ожидаемое количество строк для ОАК
OAK_EXPECTED_MINIMUM = 15


def evaluate_parse_quality(items: List["Item"], expected_minimum: int = OAK_EXPECTED_MINIMUM) -> dict:
    """
    Оценивает качество результатов парсинга.

    Args:
        items: список Item из baseline-парсера (или fallback).
        expected_minimum: минимальное ожидаемое число показателей (для ОАК >= 15).

    Returns:
        dict с ключами:
            parsed_count   — показатели, у которых value != None
            error_count    — показатели без значения (value is None или status содержит ошибку)
            suspicious_count — показатели с подозрительным значением
            coverage_score — parsed_count / expected_minimum (0..1+)
    """
    parsed_count = 0
    error_count = 0
    suspicious_count = 0

    for it in items:
        # --- parsed vs error ---
        if it.value is not None:
            parsed_count += 1
        else:
            error_count += 1
            continue  # дальше проверять нечего

        # --- suspicious: проверяем raw-текст value и ref ---
        # Получаем строковое представление value для проверки "склеек"
        val_str = f"{it.value:g}" if it.value is not None else ""
        ref_str = it.ref_text or ""

        # 1) Значение содержит пробелы (например "28 8" вместо "28")
        #    Проверяем по raw_name / ref_text, т.к. value уже float
        #    Если ref_text содержит value внутри (склейка), это подозрительно
        if ref_str and val_str:
            # ref+value склейка: "150-400213" (ref "150-400" + value "213")
            combined = ref_str.replace("-", "").replace(".", "")
            if len(combined) > 10 and not re.match(r"^\d{1,5}(\.\d+)?-\d{1,5}(\.\d+)?$",
                                                     ref_str.replace(" ", "")):
                suspicious_count += 1
                continue

        # 2) raw_name содержит подозрительные символы, указывающие на мусор
        raw = it.raw_name or ""
        if any(ch in raw for ch in ['^', '*', '/']):
            # Исключение: если это известные единицы типа *10^9/л
            if not re.search(r"\*10\^\d+", raw):
                suspicious_count += 1
                continue

        # 3) ref_text выглядит неправильно (содержит пробелы в числах)
        if ref_str:
            # Ожидаем: "3.80-5.10" или "<=20" и т.п.
            cleaned_ref = ref_str.replace(" ", "").replace("–", "-").replace("—", "-")
            # Если оригинальный ref_text после очистки отличается от чистого формата
            if " " in ref_str.strip():
                parts = ref_str.strip().split()
                # "150 - 400" — нормально (пробелы вокруг дефиса)
                # "150-400213" — подозрительно
                if len(parts) > 3:
                    suspicious_count += 1
                    continue

    coverage_score = parsed_count / max(expected_minimum, 1)

    return {
        "parsed_count": parsed_count,
        "error_count": error_count,
        "suspicious_count": suspicious_count,
        "coverage_score": round(coverage_score, 3),
    }

