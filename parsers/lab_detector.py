"""
Детектор формата лаборатории (data-driven).

detect_lab(text) → LabDetectionResult
detect_lab_format(text) → str  (legacy-обёртка)

Поддерживаемые лаборатории определяются конфигом в parsers/lab_signatures.py.
Добавление новой лаборатории = одна запись в LAB_SIGNATURES.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List


# ─── Enum типов лабораторий ───
class LabType(Enum):
    HELIX = "helix"
    MEDSI = "medsi"
    INVITRO = "invitro"
    UNKNOWN = "unknown"


# ─── Результат детекции ───
@dataclass
class LabDetectionResult:
    lab_type: LabType
    confidence: float = 0.0
    matched_signatures: List[str] = field(default_factory=list)


# Алиас обратной совместимости (из патча)
DetectResult = LabDetectionResult


# ─── Вспомогательные функции для callable-сигнатур ───

def _check_medsi_format(text: str) -> bool:
    """Делегирует в medsi_extractor.is_medsi_format."""
    from parsers.medsi_extractor import is_medsi_format
    return is_medsi_format(text)


def _count_medsi_code_lines(text: str) -> int:
    """Считает строки (CODE) — маркер МЕДСИ."""
    return sum(1 for line in text.splitlines()
               if re.match(r'^\(\w+\)', line.strip()))


def _count_helix_pairs(text: str) -> int:
    """Считает двухстрочные пары имя→значение (маркер Helix)."""
    lines = text.splitlines()
    count = 0
    for i in range(len(lines) - 1):
        name_line = lines[i].strip()
        val_line = lines[i + 1].strip()
        if (name_line
            and re.search(r'[A-Za-zА-Яа-я]{3,}', name_line)
            and not re.match(r'^\d', name_line)
            and val_line
            and re.match(r'^[↑↓+]?\s*\d', val_line)):
            count += 1
    return count


# ─── Реестр callable-проверок ───
_CALLABLE_CHECKS = {
    "is_medsi_format": _check_medsi_format,
    "helix_pairs": lambda text: _count_helix_pairs(text) >= 5,
}


# ─── Главная функция детекции (data-driven) ───

def detect_lab(text: str) -> LabDetectionResult:
    """
    Data-driven детекция лаборатории.

    Алгоритм:
    1. Загружаем конфиг сигнатур из parsers.lab_signatures.LAB_SIGNATURES
    2. Для каждой лаборатории суммируем веса совпавших сигнатур
    3. confidence = min(raw_score, 1.0)
    4. Выбираем лабораторию с максимальным raw_score
    5. Если confidence < threshold → UNKNOWN
    """
    if not text or not text.strip():
        return LabDetectionResult(LabType.UNKNOWN, confidence=0.0)

    from parsers.lab_signatures import LAB_SIGNATURES

    text_lower = text.lower()

    # Собираем score для каждой лаборатории
    results = []  # list of (LabType, raw_score, confidence, matched_sigs, threshold)

    for lab_config in LAB_SIGNATURES:
        lab_type = lab_config["lab_type"]
        threshold = lab_config["threshold"]
        sigs = lab_config["signatures"]

        raw_score = 0.0
        matched = []

        for sig in sigs:
            weight = sig["weight"]

            is_callable = sig.get("callable", False)
            is_regex = sig.get("regex", False)
            pattern = sig["pattern"]

            hit = False

            if is_callable:
                # Вызываем функцию из реестра
                fn = _CALLABLE_CHECKS.get(pattern)
                if fn:
                    hit = fn(text)
            elif is_regex:
                min_count = sig.get("min_count", 1)
                count = len(re.findall(pattern, text, re.MULTILINE | re.IGNORECASE))
                hit = count >= min_count
            else:
                # Простой поиск подстроки (регистронезависимо)
                hit = pattern.lower() in text_lower

            if hit:
                raw_score += weight
                matched.append(f"{sig['kind']}:{pattern}")

        # confidence = raw_score, capped at 1.0
        confidence = min(raw_score, 1.0)

        results.append((lab_type, raw_score, confidence, matched, threshold))

    # Фильтруем: оставляем только тех, чей confidence >= threshold
    valid = [(lt, rs, conf, m, th) for lt, rs, conf, m, th in results if conf >= th]

    if not valid:
        return LabDetectionResult(LabType.UNKNOWN, confidence=0.0)

    # Выбираем лабораторию с максимальным raw_score (при равенстве — первая в конфиге)
    valid.sort(key=lambda x: (x[1], x[2]), reverse=True)
    best = valid[0]

    return LabDetectionResult(
        lab_type=best[0],
        confidence=best[2],
        matched_signatures=best[3]
    )


# ─── Legacy-обёртка (обратная совместимость) ───

def detect_lab_format(raw_text: str) -> str:
    """
    Legacy-обёртка. Возвращает строку для старого кода.
    'medsi' | 'helix' | 'generic'
    """
    result = detect_lab(raw_text)
    mapping = {
        LabType.MEDSI:   "medsi",
        LabType.HELIX:   "helix",
        LabType.INVITRO: "generic",   # пока нет отдельного парсера
        LabType.UNKNOWN: "generic",
    }
    return mapping.get(result.lab_type, "generic")
