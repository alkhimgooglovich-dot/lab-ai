"""
Universal Extractor v2 — главный парсер для ЛЮБЫХ лабораторий.

universal_extract(raw_text) → str (TSV-кандидаты: name\\tvalue\\tref\\tunit)

Архитектура:
    1. Для МЕДСИ: делегируем в medsi_inline_to_candidates (не дублируем).
    2. Pass 1 (однострочный): ищем строки с числом + диапазоном.
    3. Pass 2 (двухстрочный): пары «имя» → «число + единица + ref».
    4. Слияние + скоринг: фильтруем по score >= 0.4.
    5. Дедупликация по ключу (имя, значение).

Порог отсечения кандидата: score >= 0.4
"""

import re
import sys
from pathlib import Path
from typing import Optional, Tuple, List, Set

# Чтобы можно было импортировать из корня проекта
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from parsers.line_scorer import score_line, is_noise, has_ref_pattern, has_numeric_value, has_known_biomarker
from parsers.unit_dictionary import normalize_unit, is_valid_unit


# ──────────────────────────────────────────────
# Паттерн "Смотри текст" / "см. текст" / "see text"
# Показатель БЕЗ числового референса (ref = "")
# ──────────────────────────────────────────────
_SEE_TEXT_PATTERN = re.compile(
    r"\b(?:смотри\s+текст|см\.?\s*текст|see\s+text)\b", re.IGNORECASE
)

# P13: Расширенный паттерн — включает "см. интерпретацию" (Citilab HDL)
_SEE_TEXT_BROAD = re.compile(
    r"\b(?:смотри\s+текст|см\.?\s*текст|see\s+text"
    r"|см\.?\s*интерпретаци[юи])\b",
    re.IGNORECASE,
)


# ──────────────────────────────────────────────
# Вспомогательные функции (не дублируем engine.py,
# но используем минимальные обёртки для автономности)
# ──────────────────────────────────────────────

def _normalize_scientific_notation(s: str) -> str:
    """Нормализует варианты записи степени: 10*9, 10~9, 10⁹ → 10^9."""
    s = s.replace("¹", "^1").replace("²", "^2").replace("³", "^3")
    s = s.replace("⁴", "^4").replace("⁵", "^5").replace("⁶", "^6")
    s = s.replace("⁷", "^7").replace("⁸", "^8").replace("⁹", "^9").replace("⁰", "^0")
    # Только ~ и * (без -), чтобы не ловить референсные диапазоны типа "10 - 40"
    s = re.sub(r"10\s*[~*]\s*(\d+)", r"10^\1", s, flags=re.IGNORECASE)
    return s


def _parse_float(x: str) -> Optional[float]:
    x = (x or "").strip().replace(",", ".")
    x = re.sub(r"[^\d\.\-]", "", x)
    try:
        return float(x)
    except Exception:
        return None


def _extract_ref_text(s: str) -> str:
    """Извлекает референсный диапазон из строки."""
    t = (s or "").strip().replace("—", "-").replace("–", "-").replace(",", ".")
    t = re.sub(r"\s+", " ", t)

    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", t)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    m = re.search(r"(<=|>=|<|>|≤|≥)\s*(\d+(?:\.\d+)?)", t)
    if m:
        op = m.group(1).replace("≤", "<=").replace("≥", ">=")
        return f"{op}{m.group(2)}"

    # Формат «до число» → «<число»
    m = re.search(r"(?:^|\s)[Дд]о\s*(\d+(?:\.\d+)?)", t)
    if m:
        return f"<{m.group(1)}"

    return ""


# ──────────────────────────────────────────────
# Фильтр: шкальные аннотации
# ──────────────────────────────────────────────
_SCALE_ANNOTATION_STARTS = (
    "нормальный уровень",
    "умеренно-повышенный",
    "умеренно повышенный",
    "повышенный",
    "высокий уровень",
    "высокий риск",
    "умеренный риск",
    "риск отсутствует",
    "нормальное содержание",
    "диагностический критерий",
    "рекомендуется консультация",
    # P6: дополнительные шкальные/методологические фрагменты
    "в соответствии с",
    "включительно",
)

# P6: фразы описания рисков/уровней, которые могут встретиться В ЛЮБОМ месте строки
_RISK_PHRASES = (
    "риск отсутствует", "умеренный риск", "высокий риск",
    "низкий риск", "очень высокий риск",
    "нормальный уровень", "умеренно-повышенный", "умеренно повышенный",
    "повышенный уровень", "высокий уровень",
)

# P6: маркеры лабораторных методологий (не являются биомаркерами)
_METHODOLOGY_MARKERS = ("dcct", "ngsp", "ifcc", "в соответствии с")


def _is_scale_annotation(line: str) -> bool:
    """
    Проверяет, является ли строка шкальной аннотацией (пояснением к уровням),
    а не реальным биомаркером.

    Примеры True:
        "Нормальный уровень <1,70"
        "Умеренно-повышенный 1,70-2,25"
        ">1.45 ммоль/л - риск отсутствует"
        "0.9-1,45 ммоль/л - умеренный риск"

    Примеры False:
        "Холестерин общий 4.73 ммоль/л"
        "Глюкоза 5.27 ммоль/л 4.11 - 6.1"
    """
    s = (line or "").strip()
    if not s:
        return False
    low = s.lower()

    # Паттерн 1: строка начинается с описания уровня
    for prefix in _SCALE_ANNOTATION_STARTS:
        if low.startswith(prefix):
            return True

    # Паттерн 2: строка начинается с ">число" или "<число" и содержит текст-описание
    if re.match(r'^[><≤≥]\s*\d', s):
        if re.search(r'(риск|уровень|норм)', low):
            return True

    # Паттерн 3: "число-число ммоль/л - текст описания" (без имени биомаркера)
    if re.match(r'^\d+[.,]?\d*\s*[-–—]\s*\d+[.,]?\d*\s+\S+\s*[-–—]\s*\w', s):
        if re.search(r'(риск|уровень|норм)', low):
            return True

    # Паттерн 4: "до N% ..." или "N.N% и более ..." с описанием уровня/нормы
    if re.match(r'^до\s+\d', low) and re.search(r'(содержание|уровень|норм|риск|критерий)', low):
        return True
    if re.match(r'^\d+[.,]?\d*%\s+(и более|и выше|включительно)', low):
        if re.search(r'(содержание|уровень|норм|риск|критерий|диабет)', low):
            return True

    # Паттерн 5: "N.N-N.N% - описание" (напр. "6.0-6.4% - рекомендуется консультация")
    if re.match(r'^\d+[.,]?\d*\s*[-–—]\s*\d+[.,]?\d*%\s*[-–—]\s*\w', s):
        if re.search(r'(риск|уровень|норм|консультаци|критерий)', low):
            return True

    # P7: агрессивные паттерны для HbA1c шкалы (без требования ключевых слов)

    # "6.0-6.4% - рекомендуется консультация" — процентный диапазон в начале строки
    if re.match(r'^\d+[.,]?\d*\s*[-–—]\s*\d+[.,]?\d*\s*%', s):
        return True

    # "до N..." в начале строки — шкальная аннотация
    if re.match(r'^до\s+\d', low):
        return True

    # "N% и более" в любом месте строки
    if re.search(r'\d+[.,]?\d*\s*%\s+и\s+более', low):
        return True

    # Паттерн 6 (P6): строка СОДЕРЖИТ фразу описания риска/уровня в любом месте,
    # но НЕ содержит известного биомаркера → шкальная аннотация
    for phrase in _RISK_PHRASES:
        if phrase in low:
            if not has_known_biomarker(s):
                return True

    # Паттерн 7 (P6): строка содержит маркер лабораторной методологии (DCCT, NGSP, IFCC)
    # P8: НЕ фильтруем, если строка ТАКЖЕ содержит известный биомаркер —
    # это реальный показатель вида "Гликированный гемоглобин (DCCT) 5.0%"
    for marker in _METHODOLOGY_MARKERS:
        if marker in low:
            if not has_known_biomarker(s):
                return True
            break

    return False


def _starts_like_value_line(s: str) -> bool:
    t = (s or "").strip()
    return bool(re.match(r"^(?:[↑↓+]\s*)?\d", t))


def _looks_like_name_line(s: str) -> bool:
    t = (s or "").strip()
    if not t:
        return False
    low = t.lower()
    if is_noise(t):
        return False
    if _is_scale_annotation(t):
        return False
    if _starts_like_value_line(t):
        return False
    if not re.search(r"[A-Za-zА-Яа-я]{2,}", t):
        return False

    # P6/P7: отклонить строки, которые являются ТОЛЬКО указанием биоматериала.
    # Важно: "Калий (K+) (сыворотка крови)" должно ПРОХОДИТЬ (содержит индикатор),
    # а "(сыворотка крови)" одна — НЕТ.
    t_stripped = t.strip().lower().strip("() ")
    if t_stripped in ("венозная кровь", "сыворотка крови", "капиллярная кровь",
                      "кровь, фотометрия", "плазма крови", "моча разовая",
                      "цельная кровь"):
        return False

    return True


# ──────────────────────────────────────────────
# P9: Pre-clean — удаление регуляторных кодов перед парсингом
# ──────────────────────────────────────────────
def _preclean_line(s: str) -> str:
    """
    Удаляет регуляторные коды, коды услуг, указания биоматериала и методологии
    из строки ПЕРЕД извлечением значения/ref.
    Предотвращает путаницу чисел в кодах (A09.05.083, 804н) с реальными значениями.
    """
    if not s:
        return s
    out = re.sub(
        r'\bA\d{2}\.\d{2}\.\d{3}(?:\.\d+)?(?:\s*,\s*A\d{2}\.\d{2}\.\d{3}(?:\.\d+)?)*',
        '', s,
    )
    out = re.sub(r'\(Приказ[^)]*\)', '', out, flags=re.IGNORECASE)
    out = re.sub(r'\(Приказ[^)]*$', '', out, flags=re.IGNORECASE)
    out = re.sub(r'^МЗ\s+РФ[^)]*\)', '', out, flags=re.IGNORECASE)
    out = re.sub(
        r'\(\s*(?:венозная кровь|сыворотка крови|кровь[^)]*|капиллярная кровь|плазма крови?)\s*\)',
        '', out, flags=re.IGNORECASE,
    )
    out = re.sub(r'\(в соответствии[^)]*\)', '', out, flags=re.IGNORECASE)
    out = re.sub(r'Дата исследования[:\s]*[\d.]+[;\s]*', '', out, flags=re.IGNORECASE)
    out = re.sub(r'\s+', ' ', out).strip()
    return out


# ──────────────────────────────────────────────
# Pass 1: однострочный парсер
# ──────────────────────────────────────────────
def _try_parse_one_line(line: str) -> Optional[str]:
    """
    Пробует извлечь кандидата из одной строки.
    Формат: «Имя показателя  значение  единица  ref_low - ref_high»
    Возвращает TSV: name\\tvalue\\tref\\tunit или None.
    """
    s = re.sub(r"\s+", " ", (line or "").strip())
    if not s:
        return None
    if is_noise(s):
        return None
    if _is_scale_annotation(s):
        return None
    if _starts_like_value_line(s):
        return None

    # P9: Pre-clean regulatory codes before value/ref extraction
    s = _preclean_line(s)
    if not s or len(s) < 3:
        return None

    # Нормализуем научную нотацию
    s_norm = _normalize_scientific_notation(s)

    # --- "Смотри текст" / "см. интерпретацию" — показатель без числового ref ---
    see_text_match = _SEE_TEXT_BROAD.search(s_norm)
    if see_text_match:
        s_clean = s_norm[:see_text_match.start()].strip()
        if not s_clean:
            return None

        s_clean_norm = s_clean.replace(",", ".")
        s_clean_norm = _normalize_scientific_notation(s_clean_norm)

        nums = re.findall(r"[-+]?\d+(?:\.\d+)?", s_clean_norm)

        if nums:
            # Value BEFORE see-text marker (e.g. "Холестерин 4.73 см. текст")
            value_str = nums[-1]
            value = _parse_float(value_str)
            if value is None:
                return None
            name_part = s_clean_norm.rsplit(value_str, 1)[0].strip()
            after_value = s_clean_norm.split(value_str, 1)[1].strip() if value_str in s_clean_norm else ""
            unit = ""
            if after_value:
                unit_match = re.match(r"^([^/\s]+(?:[/%][^/\s]*)?)", after_value)
                if unit_match:
                    unit = unit_match.group(1).strip()
            if not name_part or not re.search(r"[A-Za-zА-Яа-я]", name_part):
                return None
            return f"{name_part}\t{value:g}\t\t{unit}"

        # Value AFTER see-text marker (e.g. "ЛПВП (HDL) см. интерпретацию 1.567")
        s_after = s_norm[see_text_match.end():].strip()
        if s_after:
            s_after_norm = s_after.replace(",", ".")
            nums_after = re.findall(r"[-+]?\d+(?:\.\d+)?", s_after_norm)
            if nums_after:
                value_str = nums_after[-1]
                # Strip trailing lab code from bare see-text value: "1.567" → "1.56"
                m_code = re.match(r'(\d+\.\d{2})\d+$', value_str)
                if m_code:
                    value_str = m_code.group(1)
                value = _parse_float(value_str)
                if value is not None:
                    name_part = s_clean
                    if name_part and re.search(r"[A-Za-zА-Яа-я]", name_part):
                        return f"{name_part}\t{value:g}\t\t"

        return None

    # Ищем референсный диапазон
    range_match = re.search(
        r"(-?\d+(?:[.,]\d+)?)\s*[–—-]\s*(-?\d+(?:[.,]\d+)?)", s_norm
    )
    comp_match = re.search(
        r"(<=|>=|<|>|≤|≥)\s*(-?\d+(?:[.,]\d+)?)", s_norm
    )
    do_match = re.search(
        r"[Дд]о\s*(\d+(?:[.,]\d+)?)", s_norm
    )

    ref_span = None
    ref_text = ""

    if range_match:
        a = range_match.group(1).replace(",", ".")
        b = range_match.group(2).replace(",", ".")
        ref_text = f"{a}-{b}"
        ref_span = range_match.span()
    elif comp_match:
        op = comp_match.group(1).replace("≤", "<=").replace("≥", ">=")
        x = comp_match.group(2).replace(",", ".")
        ref_text = f"{op}{x}"
        ref_span = comp_match.span()
    elif do_match:
        x = do_match.group(1).replace(",", ".")
        ref_text = f"<{x}"
        ref_span = do_match.span()
    else:
        return None

    left = s_norm[:ref_span[0]].strip()
    right = s_norm[ref_span[1]:].strip()

    # --- Dual-operator: "Name <op> value unit <op> ref" ---
    # When first comp_match is used as ref but left has no digits,
    # look for a second comp operator → first is value, second is ref.
    if not range_match and comp_match and ref_span == comp_match.span():
        if not re.search(r"\d", left):
            second_comp = re.search(
                r"(<=|>=|<|>|≤|≥)\s*(-?\d+(?:[.,]\d+)?)", right
            )
            if second_comp:
                value_num = _parse_float(comp_match.group(2).replace(",", "."))
                if value_num is not None:
                    op2 = second_comp.group(1).replace("≤", "<=").replace("≥", ">=")
                    x2 = second_comp.group(2).replace(",", ".")
                    new_ref = f"{op2}{x2}"
                    between = right[:second_comp.start()].strip()
                    unit = between if between else ""
                    name_part = left.strip()
                    if name_part and re.search(r"[A-Za-zА-Яа-я]", name_part):
                        return f"{name_part}\t{value_num:g}\t{new_ref}\t{unit}".strip()

    # Ищем значение в left
    left_norm = left.replace(",", ".")
    left_norm = _normalize_scientific_notation(left_norm)

    # Сначала: формат *10^N (включая x10^N из pypdf после P10-склейки)
    pow_patterns = [
        r"([-+]?\d+(?:[.,]\d+)?)\s*\*\s*10\s*\^\s*(\d+)",
        r"([-+]?\d+(?:[.,]\d+)?)[-+]?\s+[xхXХ]\*?10\s*\^\s*(\d+)",
        r"([-+]?\d+(?:[.,]\d+)?)\s+10\s*\^\s*(\d+)",
    ]
    pow_match = None
    for pattern in pow_patterns:
        pow_match = re.search(pattern, left_norm, re.IGNORECASE)
        if pow_match:
            break

    if pow_match:
        value_str = pow_match.group(1).replace(",", ".")
        value = _parse_float(value_str)
        if value is None:
            return None
        exp = pow_match.group(2)
        name_part = left_norm[:pow_match.start()].strip()
        after_exp = left_norm[pow_match.end():].strip()
        if after_exp:
            unit = f"*10^{exp}{after_exp}".strip()
        else:
            unit = f"*10^{exp}"
            if right:
                right_unit = right.split(" ")[0].strip()
                if right_unit and not re.match(r"^\d", right_unit):
                    unit = f"{unit}{right_unit}"
    else:
        # Обычный формат
        nums = re.findall(r"[-+]?\d+(?:\.\d+)?", left_norm)
        if not nums:
            return None
        value_str = nums[-1]
        value = _parse_float(value_str)
        if value is None:
            return None
        name_part = left_norm.rsplit(value_str, 1)[0].strip()
        # Strip trailing comparison operators (e.g., "Тестостерон >" → "Тестостерон")
        name_part = re.sub(r'\s*[<>≤≥]=?\s*$', '', name_part).strip()
        unit = ""
        after_value = left_norm.split(value_str, 1)[1] if value_str in left_norm else ""
        if after_value:
            after_value = after_value.strip()
            unit_match = re.match(r"^([^/\s]+(?:[/%][^/\s]*)?)", after_value)
            if unit_match:
                unit = unit_match.group(1).strip()
        if not unit and right:
            right_first = right.split(" ")[0].strip()
            if right_first and not re.match(r"^\d", right_first):
                unit = right_first

    if not name_part or not re.search(r"[A-Za-zА-Яа-я]", name_part):
        return None

    return f"{name_part}\t{value:g}\t{ref_text}\t{unit}".strip()


# ──────────────────────────────────────────────
# Вспомогательная функция: извлечение unit из строки-единицы
# ──────────────────────────────────────────────
def _extract_unit_from_line(s: str) -> str:
    """
    Извлекает единицу измерения из строки, которая содержит ТОЛЬКО unit.
    Примеры: "г/л", "*10^9/л", "ммоль/л", "%"
    Возвращает unit-строку или "".
    """
    t = (s or "").strip()
    if not t or len(t) > 20:  # unit не может быть длиннее 20 символов
        return ""
    # Содержит числа (кроме *10^N) — не чистый unit
    if has_numeric_value(t) and not re.match(r"^[xхXХ]?\*?10[\^*]\d+", t):
        return ""
    t_norm = _normalize_scientific_notation(t)
    # Проверяем через unit_dictionary
    if is_valid_unit(t_norm.strip(".,;:()")):
        return t_norm
    # Проверяем шаблоны: *10^N/л, г/л и т.д.
    if re.match(r"^[xхXХ]?\*?10\s*\^\s*\d+/[а-яa-z]+$", t_norm, re.IGNORECASE):
        return t_norm
    return ""


# ──────────────────────────────────────────────
# Pass 2: парсер значений (общая вспомогательная)
# ──────────────────────────────────────────────
def _parse_value_unit_from_line(s: str) -> Tuple[Optional[float], str]:
    """Парсит значение и единицу из строки-значения."""
    t = re.sub(r"\s+", " ", (s or "").strip())
    t = t.replace("↑", "").replace("↓", "").replace("+", "").strip()
    # Убираем trailing dash (Гемотест: "0.28-" означает ↓)
    t = re.sub(r"^(\d+(?:[.,]\d+)?)\s*-$", r"\1", t)
    # Strip leading comparison operators: "< 37 пмоль/л" → "37 пмоль/л"
    t = re.sub(r"^[<>≤≥]=?\s*", "", t).strip()
    t = _normalize_scientific_notation(t)

    # *10^N (включая x10^N из pypdf после P10-склейки)
    pow_patterns = [
        r"([-+]?\d+(?:[.,]\d+)?)\s*\*\s*10\s*\^\s*(\d+)(.*)$",
        r"([-+]?\d+(?:[.,]\d+)?)[-+]?\s+[xхXХ]\*?10\s*\^\s*(\d+)(.*)$",
        r"([-+]?\d+(?:[.,]\d+)?)\s+10\s*\^\s*(\d+)(.*)$",
    ]
    for pattern in pow_patterns:
        pow_match = re.search(pattern, t, re.IGNORECASE)
        if pow_match:
            base = _parse_float(pow_match.group(1))
            if base is not None:
                exp = pow_match.group(2)
                rest = pow_match.group(3).strip() if len(pow_match.groups()) > 2 else ""
                unit = f"*10^{exp}"
                if rest:
                    unit = f"{unit}{rest}".strip()
                return base, unit

    # Обычный формат
    m = re.match(r"^([-+]?\d+(?:[.,]\d+)?)\s*(.*)$", t)
    if not m:
        return None, ""
    val = _parse_float(m.group(1))
    rest = (m.group(2) or "").strip()
    if rest:
        unit_match = re.match(r"^([^/\s]+(?:[/%][^/\s]*)?)", rest)
        if unit_match:
            unit = unit_match.group(1).strip()
        else:
            unit = rest.split(" ")[0].strip()
    else:
        unit = ""
    return val, unit


def _multi_line_pass(lines: List[str]) -> List[str]:
    """
    Pass 2: многострочный парсер (скользящее окно до 4 строк).

    Для каждой строки-имени собирает окно из следующих 1–3 строк
    и ищет в нём компоненты: value, unit, ref (в произвольном порядке).

    Возвращает список TSV-кандидатов: name\\tvalue\\tref\\tunit.
    """
    out: List[str] = []
    i = 0

    while i < len(lines):
        ln = lines[i]

        # Ищем строку-имя
        if not _looks_like_name_line(ln):
            i += 1
            continue

        # Если строка содержит "Смотри текст" — это однострочный кейс с пустым ref,
        # не ищем ref в следующих строках (иначе зацепим мусорные пояснения).
        if _SEE_TEXT_PATTERN.search(ln):
            i += 1
            continue

        # P9: Очищаем имя от регуляторных кодов для формирования кандидата
        name_clean = _preclean_line(ln)
        if not name_clean:
            i += 1
            continue

        # Нашли имя — собираем окно из следующих 1–3 строк
        window = lines[i + 1: i + 4]  # максимум 3 строки после имени

        value_found: Optional[float] = None
        unit_found: str = ""
        ref_found: str = ""
        consumed: int = 0  # сколько строк из окна использовали

        for j, w in enumerate(window):
            w_stripped = (w or "").strip()
            if not w_stripped:
                continue  # пустая строка → пропуск

            # P9: Pre-clean regulatory codes in window lines
            w_stripped = _preclean_line(w_stripped)
            if not w_stripped:
                consumed = j + 1
                continue  # строка содержала только регуляторный код → пропуск

            # Если строка — noise, но НЕ числовая → пропускаем (не ломаем окно)
            if is_noise(w_stripped) and not re.match(r'^[↑↓+]?\s*\d', w_stripped):
                consumed = j + 1
                continue

            # Если встретили строку-имя, которая НЕ является единицей → СТОП
            if _looks_like_name_line(w_stripped) and not _extract_unit_from_line(w_stripped):
                break

            # --- Компонент: value (+ возможно unit и ref в той же строке) ---
            if value_found is None and _starts_like_value_line(w_stripped):
                val, unit_candidate = _parse_value_unit_from_line(w_stripped)
                if val is not None:
                    value_found = val
                    if unit_candidate:
                        unit_found = unit_candidate
                    # Ref тоже может быть на этой же строке (напр. "34.7 % 35.0 - 45.0")
                    if not ref_found:
                        ref_candidate = _extract_ref_text(w_stripped)
                        if ref_candidate:
                            ref_found = ref_candidate
                    consumed = j + 1
                    continue

            # --- Компонент: ref ---
            if not ref_found:
                ref_candidate = _extract_ref_text(w_stripped)
                if ref_candidate:
                    ref_found = ref_candidate
                    consumed = j + 1
                    continue

            # --- Компонент: unit (на отдельной строке) ---
            if not unit_found:
                unit_candidate = _extract_unit_from_line(w_stripped)
                if unit_candidate:
                    unit_found = unit_candidate
                    consumed = j + 1
                    continue

            # Строка не дала ни одного компонента → СТОП
            break

        # Формируем кандидата: обязательны value + ref
        if value_found is not None and ref_found:
            candidate = f"{name_clean}\t{value_found:g}\t{ref_found}\t{unit_found}".strip()
            out.append(candidate)
            i += 1 + consumed  # перепрыгиваем использованные строки
            continue

        # P6: если нашли value, но НЕТ ref — проверяем, не стоит ли дальше "Смотри текст"
        if value_found is not None and not ref_found:
            next_idx = i + 1 + consumed
            if next_idx < len(lines) and _SEE_TEXT_PATTERN.search(lines[next_idx]):
                candidate = f"{name_clean}\t{value_found:g}\t\t{unit_found}".strip()
                out.append(candidate)
                i = next_idx + 1  # перепрыгиваем строку "Смотри текст"
                continue

        # P6: если value НЕ найдено в окне, но в самой строке-имени есть число,
        # а следующая строка — "Смотри текст" → извлекаем value из строки-имени
        if value_found is None and not ref_found:
            next_check_idx = i + 1
            if next_check_idx < len(lines) and _SEE_TEXT_PATTERN.search(lines[next_check_idx]):
                ln_norm = name_clean.replace(",", ".")
                ln_norm = _normalize_scientific_notation(ln_norm)
                nums = re.findall(r"[-+]?\d+(?:\.\d+)?", ln_norm)
                if nums:
                    val = _parse_float(nums[-1])
                    if val is not None:
                        val_str = nums[-1]
                        after_val = ln_norm.split(val_str, 1)[-1].strip() if val_str in ln_norm else ""
                        embedded_unit = ""
                        if after_val:
                            u_match = re.match(r"^([A-Za-zА-Яа-яµ%/\.\-]+(?:[/%][^/\s]*)?)", after_val)
                            if u_match:
                                embedded_unit = u_match.group(1).strip()
                        candidate = f"{name_clean}\t{val:g}\t\t{embedded_unit}".strip()
                        out.append(candidate)
                        i = next_check_idx + 1
                        continue

        i += 1

    return out


def _two_line_pass_legacy(lines: List[str]) -> List[str]:
    """
    Pass 2 (LEGACY): двухстрочный парсер.
    Пары: строка-имя → строка-значение (возможно + следующая строка с ref).
    Оставлен для возможности отката. Не вызывается.
    """
    out: List[str] = []
    pending_name: Optional[str] = None
    i = 0

    while i < len(lines):
        ln = lines[i]
        if is_noise(ln):
            i += 1
            continue

        if _looks_like_name_line(ln):
            pending_name = ln
            i += 1
            continue

        if pending_name and _starts_like_value_line(ln):
            combined_line = ln
            if i + 1 < len(lines) and re.search(r"^\s*\d+\s", lines[i + 1]):
                combined_line = f"{ln} {lines[i + 1]}"

            val, unit = _parse_value_unit_from_line(combined_line)
            if val is None:
                pending_name = None
                i += 1
                continue

            ref = _extract_ref_text(combined_line)
            adv = 1
            if not ref and i + 1 < len(lines):
                ref2 = _extract_ref_text(lines[i + 1])
                if ref2:
                    ref = ref2
                    adv = 2

            if ref:
                candidate = f"{pending_name}\t{val:g}\t{ref}\t{unit}".strip()
                out.append(candidate)
                pending_name = None
                i += adv
                continue
            else:
                pending_name = None
                i += 1
                continue

        if pending_name:
            pending_name = None
        i += 1

    return out


# ──────────────────────────────────────────────
# Дедупликация
# ──────────────────────────────────────────────
def _dedup_candidates(candidates: List[str]) -> List[str]:
    """Дедупликация по ключу: (name_norm, value)."""
    seen: Set[str] = set()
    result: List[str] = []
    for c in candidates:
        parts = c.split("\t")
        if len(parts) < 2:
            continue
        key = re.sub(r"\s+", " ", parts[0].strip().lower()) + "|" + parts[1].strip()
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result


# ──────────────────────────────────────────────
# Pre-clean: Citilab-style format (prefix units, trailing lab codes, asterisks)
# ──────────────────────────────────────────────

def _strip_prefix_unit(line: str) -> str:
    """
    Strip unit prefix glued directly to biomarker name in Citilab PDFs.
    E.g. '10^9/лЛейкоциты (WBC) ...' → 'Лейкоциты (WBC) ...'
         'г/лГемоглобин ...' → 'Гемоглобин ...'
         '%Гематокрит ...' → 'Гематокрит ...'
    Only strips when next char after unit is uppercase (start of name).
    """
    m = re.match(
        r'^(10\s*\^?\s*\d{1,2}\s*/\s*[а-яa-z]+'
        r'|[а-яА-Яa-zA-Z]{1,6}/[а-яa-z]+'
        r'|МЕ/[а-яa-z]+'
        r'|мм/ч(?:ас)?'
        r'|%|фл|пг)',
        line
    )
    if m:
        rest = line[m.end():]
        if rest and rest[0].isupper():
            return rest
    return line


def _strip_trailing_lab_code(line: str) -> str:
    """
    Remove trailing lab service code appended to reference range (Citilab).
    Uses decimal precision of the low bound to determine where the high bound
    ends and the lab code begins.
    '... 3.89 - 9.231001' → '... 3.89 - 9.23'  (low 2dec → high 2dec)
    '... 62.0 - 106.04'   → '... 62.0 - 106.0'  (low 1dec → high 1dec)
    '... 0.010 - 0.0901001' → '... 0.010 - 0.090' (low 3dec → high 3dec)
    """
    # Range: "low.DDD - high.DDDCCC" at end of line
    m = re.search(
        r'(\d+)\.(\d+)\s*[-–—]\s*(\d+)\.(\d+)\s*$',
        line
    )
    if m:
        low_dec_len = len(m.group(2))
        high_dec_str = m.group(4)
        if len(high_dec_str) > low_dec_len:
            cut_pos = m.start(4) + low_dec_len
            return line[:cut_pos]
        return line

    # Comparison: "<|>|<=|>=|≤|≥ number.DDCCC" at end of line
    m = re.search(
        r'([<>≤≥]=?)\s*(\d+\.\d{2})(\d{1,5})\s*$',
        line
    )
    if m:
        return line[:m.start(3)]

    return line


def _strip_asterisk_marker(line: str) -> str:
    """Remove asterisk (*) after numeric values: '5.32*' → '5.32'"""
    return re.sub(r'(\d)\*(?=\s|$|[а-яА-Яa-zA-Z])', r'\1', line)


def _strip_direct_determination(line: str) -> str:
    """
    Remove '- прямое определение' from Citilab LDL-style names.
    Full pattern: '(ЛПНП, LDL) - прямое определение 1.83' → '(ЛПНП, LDL) 1.83'
    Split case: '(ЛПНП, LDL) - прямое' at end → '(ЛПНП, LDL)'
               'определение 1.83 ...' at start → '1.83 ...'
    """
    out = re.sub(r'\s*-\s*прямое\s+определение\b', '', line, flags=re.IGNORECASE)
    out = re.sub(r'\s*-\s*прямое\s*$', '', out, flags=re.IGNORECASE)
    out = re.sub(r'^определение\s+(?=\d)', '', out, flags=re.IGNORECASE)
    return out


def _preclean_citilab_format(lines: List[str]) -> List[str]:
    """
    Pre-clean lines from Citilab-style PDF format:
    1. Strip unit prefix glued to biomarker name
    2. Strip trailing lab service code from reference range
    3. Strip asterisk (*) after numeric values
    Safe to apply universally — patterns are specific enough.
    """
    out = []
    changed = 0
    for ln in lines:
        original = ln
        ln = _strip_prefix_unit(ln)
        ln = _strip_trailing_lab_code(ln)
        ln = _strip_asterisk_marker(ln)
        ln = _strip_direct_determination(ln)
        if ln != original:
            changed += 1
        out.append(ln)
    if changed > 0:
        print(f"[DEBUG] _preclean_citilab_format: modified {changed}/{len(lines)} lines",
              file=sys.stderr)
    return out


# ──────────────────────────────────────────────
# Предобработка: склейка разбитых pypdf-строк
# ──────────────────────────────────────────────
def _rejoin_broken_units(lines: List[str]) -> List[str]:
    """
    Склеивает единицы, разбитые pypdf на 2 строки:
      'x10*12/' + 'л' → 'x10*12/л'
      'x10*9/'  + 'л' → 'x10*9/л'
      
    Правило: если строка заканчивается на '/' и следующая строка —
    одиночная кириллическая буква (длина <= 2), склеиваем.
    """
    result = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if (ln.rstrip().endswith('/') and 
            i + 1 < len(lines) and 
            len(lines[i + 1].strip()) <= 2 and 
            re.match(r'^[а-яА-Яa-zA-Z]+$', lines[i + 1].strip())):
            result.append(ln.rstrip() + lines[i + 1].strip())
            i += 2
        else:
            result.append(ln)
            i += 1
    return result


def _rejoin_broken_names(lines: List[str]) -> List[str]:
    """
    Склеивает имя показателя с продолжением в скобках:
      'Средний объем эритроцитов' + '(MCV)' → 'Средний объем эритроцитов (MCV)'
      'Среднее содержание' + 'Hb' → 'Среднее содержание Hb'
      
    Правило: если текущая строка — имя (буквы, без цифр в начале, не noise),
    а следующая — короткая строка в скобках ИЛИ короткое латинское слово,
    склеиваем.
    """
    result = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if (i + 1 < len(lines) and 
            _looks_like_name_line(ln) and
            not _starts_like_value_line(ln)):
            next_ln = lines[i + 1].strip()
            # Случай 1: следующая строка — код в скобках: (MCV), (МСН), (МСНС)
            if re.match(r'^\([A-Za-zА-Яа-яёЁ0-9\-]+\)$', next_ln):
                result.append(ln.strip() + ' ' + next_ln)
                i += 2
                continue
            # Случай 2: следующая строка — короткое слово (Hb, IgG и т.п.)
            if (len(next_ln) <= 5 and 
                re.match(r'^[A-Za-z][A-Za-z0-9]*$', next_ln) and
                not _starts_like_value_line(next_ln)):
                result.append(ln.strip() + ' ' + next_ln)
                i += 2
                continue
        result.append(ln)
        i += 1
    return result


# ──────────────────────────────────────────────
# P13: Rejoin lines with unclosed parentheses
# ──────────────────────────────────────────────

def _rejoin_open_parens(lines: List[str]) -> List[str]:
    """
    Rejoin lines where a parenthesis was opened but not closed.

    pypdf sometimes splits: 'Гликозилированный гемоглобин (HBA1c,'
                            'DCCT/NGSP)'
    → 'Гликозилированный гемоглобин (HBA1c, DCCT/NGSP)'
    """
    result: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        open_count = line.count('(')
        close_count = line.count(')')
        joins = 0
        while open_count > close_count and i + 1 < len(lines) and joins < 5:
            i += 1
            line = line.rstrip() + ' ' + lines[i].strip()
            open_count = line.count('(')
            close_count = line.count(')')
            joins += 1
        result.append(line)
        i += 1
    return result


# ──────────────────────────────────────────────
# P10: Rejoin fragmented pypdf lines
# ──────────────────────────────────────────────

def _is_discardable_fragment(s: str) -> bool:
    """P10: Строки, которые полностью отбрасываются при склейке фрагментов."""
    low = (s or "").strip().lower()
    if not low:
        return True

    # Service codes: A09.05.XXX (одиночные и через запятую)
    if re.match(r'^a\d{2}\.\d{2}\.\d{3}', low):
        return True

    # Regulatory: ТОЛЬКО автономные фрагменты (не полные строки-показатели)
    if re.match(r'^\(?приказ', low):
        return True
    if low.startswith('мз рф') or low.startswith('мз  рф'):
        return True
    if low.strip() == '№' or re.match(r'^№\s*$', low):
        return True
    if re.match(r'^\d{3,4}(?:н\)?|\))\s*$', low):
        return True

    # Biomaterial in parentheses — standalone
    if low.strip('() ') in (
        'венозная кровь', 'сыворотка крови', 'капиллярная кровь',
        'кровь, фотометрия', 'плазма крови', 'цельная кровь',
        'моча разовая',
    ):
        return True

    if low.startswith('дата исследования'):
        return True
    if low.startswith('клинические рекомендации'):
        return True
    if low.startswith('в соответствии') or low in ('dcct', 'ngsp', 'ifcc'):
        return True

    # P13: standalone fragments from split "- прямое определение" / "см. интерпретацию результата"
    if low in ('определение', 'результата'):
        return True

    # Scale / risk descriptions
    if any(x in low for x in (
        'нормальный уровень', 'умеренно-повышенный', 'умеренно повышенный',
        'повышенный уровень', 'высокий уровень',
        'риск отсутствует', 'умеренный риск', 'высокий риск', 'низкий риск',
        'нормальное содержание', 'диагностический критерий',
        'рекомендуется консультация',
    )):
        return True

    # Boilerplate
    if any(x in low for x in (
        'результат лабораторных', 'получая данный результат',
        'заведующий лабораторией', 'печать:', 'страница',
        'лабораторный комплекс', 'гост', 'сертификат',
        'направляющий врач', 'дата регистрации',
        'адрес пациента', 'пол пациента',
        'номер истории', 'диагноз',
        'расчетный показатель', 'концентрация железа',
        'проведено методом',
    )):
        return True

    return False


def _is_unit_only(s: str) -> bool:
    """P10: Строка является ТОЛЬКО единицей измерения."""
    t = (s or "").strip()
    if not t or len(t) > 20:
        return False
    if re.match(
        r'^(?:ммоль/л|мкмоль/л|г/л|мг/л|мг/дл|Ед/л|МЕ/л|мл/мин|нг/мл|'
        r'пмоль/л|нмоль/л|%|фл|пг|г/дл|мм/ч(?:ас)?|тыс/мкл|млн/мкл|'
        r'10\^[39]/л|[xхXХ]?\*?10[\^*]?\d+/[а-яa-z]+)\s*$',
        t, re.IGNORECASE,
    ):
        return True
    # Broken unit fragments: "x10*12/", "x10*9/" (ending with /)
    if re.match(r'^[xхXХ]?\*?10[\^*]\d+/\s*$', t, re.IGNORECASE):
        return True
    return False


def _is_ref_range_line(s: str) -> bool:
    """P10: Строка является отдельным референсным диапазоном."""
    t = (s or "").strip()
    if not t:
        return False
    if re.match(r'^\d+(?:[.,]\d+)?\s*[-–—]\s*\d+(?:[.,]\d+)?$', t):
        return True
    if re.match(r'^(?:<=|>=|<|>|≤|≥)\s*\d+(?:[.,]\d+)?\s*$', t):
        return True
    return False


def _rejoin_fragmented_lines(lines: list[str]) -> list[str]:
    """
    P10: Склеивает строки, разбитые pypdf, в логические строки-показатели.

    Gemotest PDF text layer часто разбивает один показатель на 7-10 строк:
        Калий / (K+) / (сыворотка крови) / A09.05.034 / ... / 3.7 / ммоль/л / 3.5 - 5.1

    Здесь собираем фрагменты обратно: «Калий (K+) 3.7 ммоль/л 3.5 - 5.1».

    Буфер сбрасывается только при появлении нового имени показателя,
    строки «Смотри текст» или конца входа.
    """
    out: list[str] = []
    buf: list[str] = []

    for ln in lines:
        stripped = ln.strip()

        if not stripped:
            continue
        if _is_discardable_fragment(stripped):
            continue

        # 1. «Смотри текст» → add to buf + flush
        if _SEE_TEXT_PATTERN.search(stripped):
            buf.append(stripped)
            if buf:
                out.append(' '.join(buf))
            buf = []
            continue

        # 2. Unit-only → add to buf
        if _is_unit_only(stripped):
            buf.append(stripped)
            continue

        # 3. Value-like or comparison (цифра / < / > / ≤ / ≥) → add to buf
        if re.match(r'^[-+↑↓]?\s*\d', stripped) or re.match(r'^[<>≤≥]', stripped):
            buf.append(stripped)
            continue

        # 4. Name-like (начинается с буквы) → flush old buf, start new
        if re.match(r'^[A-ZА-ЯЁa-zа-яё]', stripped):
            if buf:
                out.append(' '.join(buf))
            cleaned = re.sub(
                r'\s*\(?Приказ[^)]*$', '', stripped, flags=re.IGNORECASE,
            ).strip()
            buf = [cleaned or stripped]
            continue

        # 5. Lab code in parentheses: (K+), (Na+), (АЛТ), (ЛДГ)
        if re.match(r'^\([A-ZА-Яа-яa-z+\d]{1,6}\)$', stripped):
            buf.append(stripped)
            continue

        # 6. Всё остальное — в буфер
        buf.append(stripped)

    if buf:
        out.append(' '.join(buf))

    return out


# ──────────────────────────────────────────────
# P11: Strip Gemotest +/- out-of-range markers
# ──────────────────────────────────────────────
def _strip_gemotest_markers(lines: list[str]) -> list[str]:
    """
    Gemotest помечает выход за референс знаками + / - после числа:
    «53+», «71.0-», «92.3+».  После склейки строк это даёт «53+ г/л»,
    и парсер захватывает «+» как единицу.

    Здесь аккуратно убираем маркеры, не трогая референсные диапазоны
    вроде «3.5-5.1» и операторы «< 41».
    """
    out = []
    for ln in lines:
        # "53+ г/л" → "53 г/л"  (+ перед пробелом)
        cleaned = re.sub(r'(\d+\.?\d*)\+(?=\s|$)', r'\1', ln)
        # "71.0- мкмоль/л" → "71.0 мкмоль/л"  (- перед пробелом+буквой)
        cleaned = re.sub(r'(\d+\.?\d*)-(?=\s+[А-Яа-яA-Za-z%])', r'\1', cleaned)
        # "71.0-" в конце строки
        cleaned = re.sub(r'(\d+\.?\d*)-$', r'\1', cleaned)
        out.append(cleaned)
    return out


# ──────────────────────────────────────────────
# ГЛАВНАЯ ФУНКЦИЯ
# ──────────────────────────────────────────────
def universal_extract(raw_text: str) -> str:
    """
    Universal Extractor v2 — главный парсер.

    Для МЕДСИ-формата: делегирует в medsi_inline_to_candidates.
    Для всех остальных: Pass 1 (однострочный) + Pass 2 (двухстрочный).

    Возвращает TSV-кандидаты (name\\tvalue\\tref\\tunit), один кандидат на строку.
    Пустая строка — если ничего не найдено.
    """
    if not raw_text or not raw_text.strip():
        return ""

    # Подготовка строк
    lines = [re.sub(r"\s+", " ", ln.strip()) for ln in raw_text.splitlines()]
    lines = [
        ln for ln in lines
        if ln and not re.match(r"^---\s*PAGE\s+\d+\s*---", ln, re.IGNORECASE)
    ]
    lines = [ln for ln in lines if ln]

    if not lines:
        return ""

    # ─── Предобработка: склейка разбитых единиц (x10*12/ + л) ───
    lines = _rejoin_broken_units(lines)

    # ─── Pre-clean Citilab-style format (prefix units, trailing codes, asterisks) ───
    # Must run BEFORE _rejoin_fragmented_lines: lines like "10^9/лЛейкоциты ..."
    # start with a digit and would be mis-classified as value-lines by P10.
    lines = _preclean_citilab_format(lines)

    # ─── P13: склейка строк с незакрытыми скобками (HBA1c, DCCT/NGSP) ───
    lines = _rejoin_open_parens(lines)

    # ─── P10: склейка фрагментированных pypdf-строк ───
    lines = _rejoin_fragmented_lines(lines)

    # ─── P11: убираем Gemotest +/- маркеры из значений ───
    lines = _strip_gemotest_markers(lines)

    # ─── Предобработка: склейка разбитых имён ───
    lines = _rejoin_broken_names(lines)

    # ─── Фильтр: шкальные аннотации ───
    lines = [ln for ln in lines if not _is_scale_annotation(ln)]

    # ─── Pass 1: однострочный ───
    one_line_cands: List[str] = []
    for ln in lines:
        # "Смотри текст" / "см. интерпретацию" и строки с известным биомаркером обходят score-фильтр
        has_see_text = bool(_SEE_TEXT_BROAD.search(ln))
        has_biomarker = has_known_biomarker(ln)
        if not has_see_text and not has_biomarker:
            sc = score_line(ln)
            if sc < 0.4:
                continue
        cand = _try_parse_one_line(ln)
        if cand:
            one_line_cands.append(cand)

    # ─── Pass 2: многострочный (окно 2–4 строки) ───
    multi_line_cands = _multi_line_pass(lines)

    # ─── Слияние + дедупликация ───
    # Многострочный приоритетнее (первым в списке)
    merged = _dedup_candidates(multi_line_cands + one_line_cands)

    return "\n".join(merged).strip('\n\r ')

