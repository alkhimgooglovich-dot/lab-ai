"""
Детектор формата лаборатории.

detect_lab(text) → LabDetectionResult

Поддерживаемые форматы:
  - HELIX  — Хеликс / ИнВитро (двухстрочный, табуляции)
  - MEDSI  — МЕДСИ (inline ref+value)
  - UNKNOWN — все остальные → universal extractor
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple
import re


class LabType(Enum):
    HELIX = "helix"
    MEDSI = "medsi"
    UNKNOWN = "unknown"


@dataclass
class LabDetectionResult:
    lab_type: LabType
    confidence: float          # 0.0 … 1.0
    matched_signatures: list   # какие сигнатуры сработали (для отладки)


# ─── Сигнатуры ───

# МЕДСИ: домены, ключевые слова, шаблоны кодов
_MEDSI_DOMAINS = ["medsi.ru", "мeдси", "МЕДСИ", "Медси"]
_MEDSI_CODE_RE = re.compile(r"^\s*\([A-Za-zА-Яа-я\-#%0-9]+\)\s")

# HELIX: домены, ключевые слова, паттерны таблиц
_HELIX_DOMAINS = ["helix.ru", "хеликс", "Хеликс", "HELIX", "Helix"]
_HELIX_HEADER_RE = re.compile(
    r"(Исследование|Тест)\s*\t\s*Результат"
)


def _count_medsi_code_lines(text: str) -> int:
    """Считает строки, начинающиеся с (CODE) — маркер МЕДСИ."""
    return sum(1 for line in text.splitlines() if _MEDSI_CODE_RE.match(line))


def _count_helix_pairs(text: str) -> int:
    """Считает двухстрочные пары Helix: имя → число."""
    lines = text.splitlines()
    count = 0
    for i in range(len(lines) - 1):
        name_line = lines[i].strip()
        val_line = lines[i + 1].strip()
        if (
            name_line
            and re.search(r"[A-Za-zА-Яа-я]{3,}", name_line)
            and not re.match(r"^\d", name_line)
            and val_line
            and re.match(r"^[↑↓+]?\s*\d", val_line)
        ):
            count += 1
    return count


def detect_lab(text: str) -> LabDetectionResult:
    """
    Определяет формат лаборатории по тексту.

    Стратегия:
      1. Проверяем сигнатуры (домен/название).
      2. Проверяем структурные паттерны (коды, табуляции).
      3. Считаем confidence по количеству совпавших сигнатур.
      4. Возвращаем LabDetectionResult.

    Порог: confidence >= 0.5 → считаем определённой.
    """
    if not text or not text.strip():
        return LabDetectionResult(
            lab_type=LabType.UNKNOWN,
            confidence=0.0,
            matched_signatures=[]
        )

    matches: List[Tuple[LabType, str, float]] = []
    # (lab_type, описание_сигнатуры, вес)

    text_lower = text.lower()

    # ─── МЕДСИ: доменные/именные сигнатуры ───
    for sig in _MEDSI_DOMAINS:
        if sig.lower() in text_lower:
            matches.append((LabType.MEDSI, f"domain:{sig}", 0.5))
            break  # одного домена достаточно

    # МЕДСИ: структурные — строки с (CODE)
    medsi_code_count = _count_medsi_code_lines(text)
    if medsi_code_count >= 5:
        matches.append((LabType.MEDSI, f"code_lines:{medsi_code_count}", 0.5))
    elif medsi_code_count >= 2:
        matches.append((LabType.MEDSI, f"code_lines:{medsi_code_count}", 0.3))

    # МЕДСИ: «10*9» + «10*12» одновременно
    if "10*9" in text and "10*12" in text:
        matches.append((LabType.MEDSI, "units:10*9+10*12", 0.3))

    # МЕДСИ: СОЭ + мм/час
    if "СОЭ" in text and "мм/час" in text:
        matches.append((LabType.MEDSI, "soe_mm_chas", 0.2))

    # ─── HELIX: доменные/именные сигнатуры ───
    for sig in _HELIX_DOMAINS:
        if sig.lower() in text_lower:
            matches.append((LabType.HELIX, f"domain:{sig}", 0.5))
            break

    # HELIX: заголовок таблицы
    for line in text.splitlines()[:30]:
        if _HELIX_HEADER_RE.search(line):
            matches.append((LabType.HELIX, "header:Исследование\\tРезультат", 0.5))
            break

    # HELIX: двухстрочные пары
    helix_pairs = _count_helix_pairs(text)
    if helix_pairs >= 5:
        matches.append((LabType.HELIX, f"pairs:{helix_pairs}", 0.5))
    elif helix_pairs >= 3:
        matches.append((LabType.HELIX, f"pairs:{helix_pairs}", 0.2))

    # ─── Подсчёт confidence для каждого типа ───
    if not matches:
        return LabDetectionResult(
            lab_type=LabType.UNKNOWN,
            confidence=0.0,
            matched_signatures=[]
        )

    # Суммируем веса по типу
    scores = {}
    sigs_by_type = {}
    for lab_type, sig_name, weight in matches:
        scores[lab_type] = scores.get(lab_type, 0.0) + weight
        sigs_by_type.setdefault(lab_type, []).append(sig_name)

    # Выбираем тип с максимальным score
    best_type = max(scores, key=scores.get)
    raw_conf = scores[best_type]
    confidence = min(raw_conf, 1.0)  # cap at 1.0

    # Если confidence < 0.5 → UNKNOWN
    if confidence < 0.5:
        return LabDetectionResult(
            lab_type=LabType.UNKNOWN,
            confidence=confidence,
            matched_signatures=sigs_by_type.get(best_type, [])
        )

    return LabDetectionResult(
        lab_type=best_type,
        confidence=confidence,
        matched_signatures=sigs_by_type[best_type]
    )
