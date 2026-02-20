"""
Конфигурация сигнатур лабораторий для data-driven детектора.

Чтобы добавить новую лабораторию:
1. Добавь LabType в parsers/lab_detector.py (одна строка в Enum)
2. Добавь запись в LAB_SIGNATURES ниже
3. Готово — detect_lab() подхватит автоматически
"""

from parsers.lab_detector import LabType


# ─── Структура сигнатуры ───
# Каждая запись — dict:
#   "lab_type": LabType.XXX
#   "threshold": float (0.0–1.0) — минимальный confidence для детекции
#   "signatures": list[dict] — список сигнатур с весами
#
# Каждая сигнатура:
#   "kind": "domain" | "name" | "structural" | "header" | "code_pattern"
#   "pattern": str — текст для поиска (регистронезависимо) ИЛИ regex
#   "regex": bool — если True, pattern интерпретируется как regex
#   "weight": float — вес совпадения (суммируется в raw_score)
#   "callable": bool — если True, pattern — ключ в _CALLABLE_CHECKS

LAB_SIGNATURES = [
    # ═══ MEDSI ═══
    {
        "lab_type": LabType.MEDSI,
        "threshold": 0.3,
        "signatures": [
            {"kind": "name",        "pattern": "медси",                 "weight": 0.4},
            {"kind": "name",        "pattern": "medsi",                 "weight": 0.4},
            {"kind": "domain",      "pattern": "medsi.ru",              "weight": 0.5},
            {"kind": "code_pattern","pattern": r"^\(\w+\)\s",           "weight": 0.4, "regex": True,
             "min_count": 3,  # сработать, если >= 3 строк совпали
            },
            {"kind": "structural",  "pattern": "is_medsi_format",       "weight": 0.6,
             "callable": True,  # вызвать функцию is_medsi_format(text)
            },
        ],
    },

    # ═══ HELIX ═══
    {
        "lab_type": LabType.HELIX,
        "threshold": 0.3,
        "signatures": [
            {"kind": "name",       "pattern": "хеликс",               "weight": 0.4},
            {"kind": "name",       "pattern": "helix",                "weight": 0.4},
            {"kind": "domain",     "pattern": "helix.ru",             "weight": 0.5},
            {"kind": "domain",     "pattern": "helix-lab",            "weight": 0.4},
            {"kind": "header",     "pattern": r"(Исследование|Тест)\s*\t\s*Результат",
             "weight": 0.5, "regex": True},
            {"kind": "structural", "pattern": "helix_pairs",          "weight": 0.5,
             "callable": True,  # вызвать _count_helix_pairs(text) >= 5
            },
        ],
    },

    # ═══ INVITRO ═══
    {
        "lab_type": LabType.INVITRO,
        "threshold": 0.3,
        "signatures": [
            {"kind": "name",       "pattern": "инвитро",              "weight": 0.4},
            {"kind": "name",       "pattern": "invitro",              "weight": 0.4},
            {"kind": "name",       "pattern": "ООО «ИНВИТРО»",       "weight": 0.5},
            {"kind": "name",       "pattern": "Независимая лаборатория ИНВИТРО", "weight": 0.5},
            {"kind": "domain",     "pattern": "invitro.ru",           "weight": 0.5},
            {"kind": "domain",     "pattern": "www.invitro.ru",       "weight": 0.5},
        ],
    },
]


