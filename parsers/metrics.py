"""
B1-метрики качества OCR и парсинга.

Все функции — чистые, детерминированные, без внешних зависимостей.
"""

import re
from typing import List, Any

# ─── Биомаркеры (копия из line_scorer, чтобы не тянуть зависимость) ───
_BIOMARKER_CODES = {
    "WBC", "RBC", "HGB", "HCT", "PLT", "MCV", "MCH", "MCHC",
    "RDW", "PDW", "MPV", "PCT",
    "NEU", "LYM", "MONO", "EOS", "BAS",
    "NE", "LY", "MO", "EO", "BA",
    "ALT", "AST", "GGT", "ALP",
    "TBIL", "DBIL", "IBIL",
    "CREA", "UREA", "CRP", "CRPN",
    "GLUC", "GLU", "HBA1C",
    "CHOL", "HDL", "LDL", "TRIG",
    "TSH", "FT3", "FT4", "T3", "T4",
    "FE", "FERR", "VIT",
    "ESR",
}

# Шумовые символы/паттерны (OCR-мусор)
_NOISE_RE = re.compile(r"[�□■▪▫●○◆◇★☆]{2,}|[|]{3,}|[*]{3,}|[#]{3,}|[~]{3,}")

# Числовой кандидат: строка, содержащая число (потенциальный показатель)
_NUMERIC_RE = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)?")


def _is_noise_line(line: str) -> bool:
    """Строка считается шумовой, если содержит мусорные символы или очень короткая/пустая."""
    stripped = line.strip()
    if not stripped:
        return True
    if _NOISE_RE.search(stripped):
        return True
    # Строка из одних спецсимволов (не буквы и не цифры)
    if not re.search(r"[A-Za-zА-Яа-яЁё0-9]", stripped):
        return True
    return False


def _is_biomarker_line(line: str) -> bool:
    """Строка содержит известный код биомаркера."""
    upper = line.upper()
    for code in _BIOMARKER_CODES:
        if re.search(r"(?<![A-Za-zА-Яа-яЁё])" + re.escape(code) + r"(?![A-Za-zА-Яа-яЁё])", upper):
            return True
    return False


def _has_digit(line: str) -> bool:
    """Строка содержит хотя бы одну цифру."""
    return bool(re.search(r"\d", line))


# ════════════════════════════════════════
# A) compute_ocr_quality_metrics
# ════════════════════════════════════════

def compute_ocr_quality_metrics(text: str) -> dict:
    """
    Анализирует OCR-текст и возвращает метрики качества.

    Параметры:
        text: сырой текст из OCR / text-layer

    Возвращает dict:
        line_count              — общее количество строк
        avg_line_len            — средняя длина строки
        digit_line_ratio        — доля строк с цифрами
        biomarker_line_ratio    — доля строк с биомаркерами
        noise_line_ratio        — доля шумовых строк
        numeric_candidates_count — количество строк-кандидатов (цифра + не шум)
    """
    if not text or not text.strip():
        return {
            "line_count": 0,
            "avg_line_len": 0.0,
            "digit_line_ratio": 0.0,
            "biomarker_line_ratio": 0.0,
            "noise_line_ratio": 0.0,
            "numeric_candidates_count": 0,
        }

    lines = text.splitlines()
    line_count = len(lines)

    total_len = sum(len(ln) for ln in lines)
    avg_line_len = round(total_len / max(1, line_count), 2)

    digit_count = 0
    biomarker_count = 0
    noise_count = 0
    numeric_candidates = 0

    for ln in lines:
        is_noise = _is_noise_line(ln)
        if is_noise:
            noise_count += 1
            continue

        if _has_digit(ln):
            digit_count += 1
            numeric_candidates += 1

        if _is_biomarker_line(ln):
            biomarker_count += 1

    return {
        "line_count": line_count,
        "avg_line_len": avg_line_len,
        "digit_line_ratio": round(digit_count / max(1, line_count), 4),
        "biomarker_line_ratio": round(biomarker_count / max(1, line_count), 4),
        "noise_line_ratio": round(noise_count / max(1, line_count), 4),
        "numeric_candidates_count": numeric_candidates,
    }


# ════════════════════════════════════════
# B) compute_parse_metrics
# ════════════════════════════════════════

def compute_parse_metrics(
    items: list,
    *,
    quality_dict: dict | None = None,
) -> dict:
    """
    Считает метрики по результатам парсинга.

    Параметры:
        items: список Item (или любых объектов с .value, .name)
        quality_dict: dict из evaluate_parse_quality (если есть — берём оттуда
                      valid_value_count, suspicious_count, sanity_outlier_count,
                      duplicate_dropped_count)

    Возвращает dict:
        parsed_items          — общее количество items
        valid_value_count     — показатели с value != None
        suspicious_count      — подозрительные (из quality_dict или 0)
        sanity_outlier_count  — отброшенные sanity (из quality_dict или 0)
        dedup_dropped_count   — отброшенные дубли (из quality_dict или 0)
    """
    parsed_items = len(items) if items else 0

    if quality_dict:
        valid_value_count = quality_dict.get("valid_value_count", 0)
        suspicious_count = quality_dict.get("suspicious_count", 0)
        sanity_outlier_count = quality_dict.get("sanity_outlier_count", 0)
        dedup_dropped_count = quality_dict.get("duplicate_dropped_count", 0)
    else:
        valid_value_count = sum(
            1 for it in (items or [])
            if getattr(it, "value", None) is not None
        )
        suspicious_count = 0
        sanity_outlier_count = 0
        dedup_dropped_count = 0

    return {
        "parsed_items": parsed_items,
        "valid_value_count": valid_value_count,
        "suspicious_count": suspicious_count,
        "sanity_outlier_count": sanity_outlier_count,
        "dedup_dropped_count": dedup_dropped_count,
    }


# ════════════════════════════════════════
# C) compute_parse_score
# ════════════════════════════════════════

def compute_parse_score(ocr: dict, parse: dict) -> float:
    """
    Вычисляет итоговый score качества парсинга (0..100).

    Формула B1:
        coverage_ratio = parsed_items / max(1, numeric_candidates_count)
        vv = min(1.0, valid_value_count / 12)
        noise = noise_line_ratio
        score01 = 0.6 * min(1.0, coverage_ratio) + 0.3 * vv + 0.1 * (1.0 - noise)
        score = round(100 * clamp(score01, 0, 1), 1)

    Не зависит от LLM или внешних сервисов.
    """
    numeric_cand = ocr.get("numeric_candidates_count", 0)
    parsed_items = parse.get("parsed_items", 0)
    valid_value_count = parse.get("valid_value_count", 0)
    noise = ocr.get("noise_line_ratio", 0.0)

    coverage_ratio = parsed_items / max(1, numeric_cand)
    vv = min(1.0, valid_value_count / 12)

    score01 = (
        0.6 * min(1.0, coverage_ratio)
        + 0.3 * vv
        + 0.1 * (1.0 - noise)
    )
    score = round(100.0 * max(0.0, min(1.0, score01)), 1)
    return score

