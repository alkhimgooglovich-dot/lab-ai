# CLAUDE.md — Описание проекта LAB-AI

## Что это за проект

LAB-AI — сервис парсинга и интерпретации медицинских лабораторных анализов (PDF).
Пользователь загружает PDF с анализами из российских лабораторий, система извлекает биомаркеры и генерирует понятное объяснение на русском языке.

**Это информационный сервис, НЕ медицинский.** Все генерируемые тексты должны содержать дисклеймер.

## Структура проекта

```
├── engine.py                  # ГЛАВНЫЙ файл — весь pipeline парсинга
├── app.py                     # Flask web-приложение
├── main.py                    # Точка входа
├── parsers/
│   ├── universal_extractor.py # Универсальный парсер текста → TSV-кандидаты
│   ├── medsi_extractor.py     # Специализированный парсер для МЕДСИ
│   ├── lab_detector.py        # Data-driven детектор формата лаборатории
│   ├── lab_signatures.py      # Конфиг сигнатур лабораторий (веса, паттерны)
│   ├── line_scorer.py         # Скоринг строк (шум vs данные)
│   ├── metrics.py             # Метрики качества парсинга (B1)
│   ├── quality.py             # Оценка качества: coverage, suspicious, duplicates
│   ├── sanity_ranges.py       # Допустимые диапазоны значений биомаркеров
│   ├── fallback_generic.py    # Fallback-парсер (split_value_unit_ref)
│   └── ocr_preflight.py       # Adaptive threshold preflight (B5-A)
├── ocr_preprocess.py          # Preprocessing изображений перед OCR
├── unit_dictionary.py         # Словарь единиц измерения
├── report_helpers.py          # Генерация HTML-отчёта
├── templates/
│   ├── index.html             # Главная страница
│   └── report.html            # Шаблон отчёта
└── tests/                     # Тесты (1069+)
    ├── test_engine.py
    ├── test_universal_extractor.py
    ├── test_medsi_extractor.py
    ├── test_lab_detector.py
    ├── test_lab_detector_datadriven.py
    ├── test_gemotest_*.py
    ├── test_citilab_*.py       # Тесты Citilab (P9 preclean, P10 rejoin, P11 polish)
    ├── test_invitro_detection.py
    ├── test_metrics_b1.py
    ├── test_ocr_rerun_b2.py
    ├── test_llm_gate_b3.py
    ├── test_reasons_b4.py
    ├── test_ocr_preflight_b5a.py
    ├── test_report_quality_section_b5b.py
    └── ... (50+ файлов тестов)
```

## Pipeline обработки

```
PDF/Фото
  → pypdf (текстовый слой) ИЛИ Yandex Vision OCR (если текста нет/мало)
  → _prestrip_interstitial_noise() — удаление шумовых строк
  → _smart_to_candidates() — детекция лаборатории + конвертация в TSV
      ├── МЕДСИ → medsi_inline_to_candidates()
      ├── HELIX → helix_table_to_candidates()
      ├── INVITRO/GEMOTEST/UNKNOWN → universal_extract()
      └── fallback: если спец-парсер вернул <5 кандидатов → universal_extract()
  → parse_items_from_candidates() — TSV → структурированные Item
  → assign_confidence() + deduplicate_items() + apply_sanity_filter()
  → evaluate_parse_quality() — метрики качества
  → compute_parse_score() — итоговый score 0..100
  → LLM gate: вызов YandexGPT ТОЛЬКО если valid_value_count >= 5 AND parse_score >= 55
  → Генерация HTML-отчёта
```

## Поддерживаемые лаборатории

| Лаборатория | LabType    | Парсер                    | Статус       |
|-------------|------------|---------------------------|--------------|
| Helix       | HELIX      | helix_table_to_candidates | Зрелый       |
| МЕДСИ       | MEDSI      | medsi_inline_to_candidates| Зрелый       |
| Гемотест    | GEMOTEST   | universal_extract         | Работает     |
| Инвитро     | INVITRO    | universal_extract         | Работает     |
| Citilab     | UNKNOWN*   | universal_extract         | 48/50 тестов |
| Другие      | UNKNOWN    | universal_extract         | Базовый      |

*Citilab пока не имеет отдельных сигнатур в lab_signatures.py

## Ключевые правила (ОБЯЗАТЕЛЬНЫ)

### Нулевая регрессия
- **ВСЕ существующие тесты ДОЛЖНЫ оставаться зелёными** после любых изменений
- Перед коммитом запускай: `pytest -x --tb=short`
- Текущий счётчик тестов: 1069+, только растёт

### Фиксированные пороги (НЕ менять!)
- `valid_value_count >= 5` — минимум для вызова LLM
- `parse_score >= 55` (LLM_MIN_PARSE_SCORE) — минимум parse_score для вызова LLM
- `confidence >= 0.7` — минимум для присвоения статуса high/low
- `OCR_RERUN_MIN_SCORE = 45` — порог для повторного OCR

### Маршрутизация лабораторий
- UNKNOWN → только universal_extract (НИКОГДА helix или medsi)
- Если спец-парсер вернул 0 items → fallback на universal_extract
- Детекция через weighted scoring в lab_signatures.py, не через if-else

### Тестирование
- Юнит-тесты на изолированных данных могут давать ложные green
- **Всегда используй полные реальные блоки pypdf текста** для интеграционных тестов
- Окружающие строки (заголовки, описания оборудования, шкалы риска) влияют на pipeline

## Как запускать тесты

```bash
# Все тесты
pytest -x --tb=short

# Конкретный файл
pytest tests/test_engine.py -v

# Конкретный тест
pytest tests/test_engine.py::TestClassName::test_method -v

# С подробным выводом
pytest -x --tb=long -v
```

## Внешние зависимости

- **Python 3.10+**
- **pypdf** — извлечение текстового слоя из PDF
- **OpenCV** — preprocessing изображений (deskew, adaptive threshold)
- **Yandex Vision OCR** — распознавание текста с изображений
- **YandexGPT** — генерация объяснений биомаркеров
- **Flask** — веб-сервер

## Стиль кода

- Язык кода и комментариев: **английский**
- Документация и пользовательские тексты: **русский**
- Имена переменных: snake_case
- Константы: UPPER_SNAKE_CASE
- Dataclass Item — основная структура данных биомаркера
- Логирование через _dbg() в engine.py

## Текущая задача (на горизонте)

- Phase 6: исправить парсинг HbA1c и HDL для Citilab (2 из 50 биомаркеров)
- Добавить сигнатуры Citilab в lab_signatures.py
- Fallback reference database для объяснений биомаркеров
