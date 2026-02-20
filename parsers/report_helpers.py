"""
B5-B: helper-функции для отображения метрик качества в отчёте.
Только отображение — никакой логики принятия решений.
"""


# ── Словарь «код причины → человекочитаемый текст» ──────────────────────
_REASON_LABELS: dict[str, str] = {
    "HIGH_NOISE":          "Много шума / нераспознанных строк в тексте",
    "LOW_DIGIT_RATIO":     "Мало строк с числами — возможно, документ не содержит таблицы",
    "LOW_BIOMARKER_RATIO": "Мало строк с известными показателями",
    "TOO_FEW_LINES":       "Слишком мало строк OCR — документ может быть обрезан",
    "LOW_COVERAGE":        "Низкий процент успешно распознанных строк",
    "MANY_OUTLIERS":       "Много аномальных значений — возможны ошибки OCR",
    "MANY_SUSPICIOUS":     "Много подозрительных показателей (без единиц/референсов)",
}


def _human_reason(code: str) -> str:
    """Переводит код причины в понятный текст."""
    return _REASON_LABELS.get(code, code)


def _llm_gate_text(gate: dict) -> str:
    """
    Формирует текст о статусе ИИ-расшифровки.
    gate — это quality["metrics"]["llm_gate"] (если есть).
    """
    decision = gate.get("decision", "")
    if decision == "CALL":
        return "ИИ-расшифровка (LLM): выполнена"
    elif decision == "SKIP_LOW_VALUES":
        return "ИИ-расшифровка (LLM): пропущена — недостаточно валидных показателей (нужно ≥ 5)"
    elif decision == "SKIP_LOW_SCORE":
        score = gate.get("parse_score", "?")
        threshold = gate.get("min_parse_score", "?")
        return (
            f"ИИ-расшифровка (LLM): пропущена — низкое качество распознавания "
            f"(score {score}, порог {threshold})"
        )
    else:
        return f"ИИ-расшифровка (LLM): статус неизвестен ({decision})"


def _rerun_text(rerun: dict) -> str:
    """
    Формирует текст о повторном OCR.
    rerun — это quality["metrics"]["rerun"] (если есть).
    """
    if not rerun.get("performed", False):
        return "Повтор OCR: не потребовался"
    before = rerun.get("score_before", "?")
    after = rerun.get("score_after", "?")
    chosen = rerun.get("chosen", "?")
    return (
        f"Повтор OCR: выполнен (score до: {before}, после: {after}, "
        f"выбран прогон: {chosen})"
    )


def build_quality_section_text(quality: dict) -> str:
    """
    Строит многострочный текст секции «Диагностика качества» для PDF.

    Принимает полный словарь quality (из пайплайна).
    Если quality["metrics"] отсутствует — возвращает "Нет данных о качестве".

    Ничего не решает — только отображает уже вычисленные данные.
    """
    metrics = quality.get("metrics")
    if not metrics:
        return "Нет данных о качестве распознавания."

    lines: list[str] = []

    # 1. Parse score
    parse_score = metrics.get("parse_score")
    if parse_score is not None:
        lines.append(f"Качество распознавания: {parse_score}/100")
    else:
        lines.append("Качество распознавания: нет данных")

    # 2. Замечания (reasons)
    reasons = metrics.get("reasons", [])
    reason_summary = metrics.get("reason_summary", "")
    if reasons:
        human_reasons = [_human_reason(r) for r in reasons]
        lines.append("Замечания: " + "; ".join(human_reasons))
    else:
        lines.append("Замечания: нет критичных замечаний")

    # 3. Повтор OCR
    rerun = metrics.get("rerun")
    if rerun is not None:
        lines.append(_rerun_text(rerun))

    # 4. LLM gate
    llm_gate = metrics.get("llm_gate")
    if llm_gate is not None:
        lines.append(_llm_gate_text(llm_gate))

    return "\n".join(lines)


def build_quality_section_html(quality: dict) -> str:
    """
    HTML-версия секции качества — для вставки в Jinja-шаблон через {{ ... | safe }}.
    """
    text = build_quality_section_text(quality)
    # Каждую строку оборачиваем в <p>
    paragraphs = [f"<p>{line}</p>" for line in text.split("\n") if line.strip()]
    return "\n".join(paragraphs)


def build_user_quality_note(quality: dict) -> str:
    """
    Короткая текстовая заметка для добавления в текстовый ответ пользователю.
    Возвращает пустую строку, если добавлять нечего.
    """
    metrics = quality.get("metrics")
    if not metrics:
        return ""

    parts: list[str] = []

    # Если LLM пропущен — объяснить
    llm_gate = metrics.get("llm_gate")
    if llm_gate:
        decision = llm_gate.get("decision", "")
        if decision == "SKIP_LOW_VALUES":
            parts.append(
                "ИИ-расшифровка не выполнена: недостаточно надёжно распознанных показателей."
            )
        elif decision == "SKIP_LOW_SCORE":
            parts.append(
                "ИИ-расшифровка не выполнена: низкое качество распознавания документа."
            )

    # Если есть замечания — рекомендация
    reasons = metrics.get("reasons", [])
    if reasons:
        parts.append(
            "Рекомендация: попробуйте загрузить PDF-файл вместо фото, "
            "либо сделайте снимок без бликов и крупнее."
        )

    return "\n".join(parts)

