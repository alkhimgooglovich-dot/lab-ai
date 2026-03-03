"""
Phase 3 — End-to-end tests for Citilab PDF pipeline.

Verifies:
1. _strip_prefix_unit / _strip_trailing_lab_code work on individual lines
2. _preclean_citilab_format transforms a block of lines
3. universal_extract produces clean output from Citilab text
4. _smart_to_candidates correctly detects CITILAB and applies pre-clean
5. Full pipeline: _smart_to_candidates → parse_items_from_candidates
"""
import sys, os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ────────────────────────────────────────────────
# 1. Unit-level: strip functions
# ────────────────────────────────────────────────

def test_strip_prefix_unit_works():
    from parsers.universal_extractor import _strip_prefix_unit
    cases = [
        ("10^9/лЛейкоциты (WBC) 5.76 3.89 - 9.231001", "Лейкоциты"),
        ("г/лГемоглобин (HGB, Hb) 148.00 118.30 - 165.701001", "Гемоглобин"),
        ("%Гематокрит (HCT) 43.70 35.89 - 50.641001", "Гематокрит"),
        ("флСредний объем эритроцита (MCV) 82.10* 88.05 - 104.071001", "Средний"),
        ("пгСреднее содержание Hb в эритроците (MCH) 27.80 27.75 - 34.521001", "Среднее"),
        ("Ед/лКреатинфосфокиназа 188.0 39.0 - 308.043", "Креатинфосфокиназа"),
        ("ммоль/лКалий (К+) 4.78 3.50 - 5.1058", "Калий"),
        ("мкмоль/лЖелезо сывороточное 23.8 5.8 - 34.530", "Железо"),
        ("мм/чСОЭ (метод аттестован по Westergren) 15.0 2.0 - 20.01002", "СОЭ"),
    ]
    for raw, expected_start in cases:
        result = _strip_prefix_unit(raw)
        assert result.startswith(expected_start), \
            f"_strip_prefix_unit('{raw[:40]}...') = '{result[:40]}...', expected start '{expected_start}'"


def test_strip_trailing_lab_code_works():
    from parsers.universal_extractor import _strip_trailing_lab_code
    cases = [
        ("Лейкоциты (WBC) 5.76 3.89 - 9.231001", "9.23"),
        ("Гемоглобин (HGB, Hb) 148.00 118.30 - 165.701001", "165.70"),
        ("Креатинфосфокиназа 188.0 39.0 - 308.043", "308.0"),
        ("Калий (К+) 4.78 3.50 - 5.1058", "5.10"),
        ("Индекс атерогенности 1.21 < 3.001091", "3.00"),
    ]
    for raw, expected_end in cases:
        result = _strip_trailing_lab_code(raw)
        assert result.endswith(expected_end), \
            f"_strip_trailing_lab_code('{raw}') = '{result}', expected end '{expected_end}'"


# ────────────────────────────────────────────────
# 2. _preclean_citilab_format on a block
# ────────────────────────────────────────────────

def test_preclean_citilab_full():
    from parsers.universal_extractor import _preclean_citilab_format
    lines = [
        "10^9/лЛейкоциты (WBC) 5.76 3.89 - 9.231001",
        "г/лГемоглобин (HGB, Hb) 148.00 118.30 - 165.701001",
        "%Гематокрит (HCT) 43.70 35.89 - 50.641001",
        "10^9/лТромбоциты (PLT) 174.00 141.30 - 389.701001",
        "Ед/лКреатинфосфокиназа 188.0 39.0 - 308.043",
        "ммоль/лКалий (К+) 4.78 3.50 - 5.1058",
        "Индекс атерогенности 1.21 < 3.001091",
    ]
    result = _preclean_citilab_format(lines)
    assert result[0].startswith("Лейкоциты (WBC)")
    assert result[3].startswith("Тромбоциты (PLT)")
    for r in result:
        assert "1001" not in r, f"Trailing code not stripped: {r}"


# ────────────────────────────────────────────────
# 3. universal_extract cleans Citilab text
# ────────────────────────────────────────────────

def test_universal_extract_cleans_citilab():
    from parsers.universal_extractor import universal_extract
    line = "10^9/лЛейкоциты (WBC) 5.76 3.89 - 9.231001"
    result = universal_extract(line)
    assert "10^9/лЛейкоциты" not in result, f"Prefix NOT stripped: {result}"
    assert "9.231001" not in result, f"Trailing code NOT stripped: {result}"


def test_universal_extract_citilab_block():
    from parsers.universal_extractor import universal_extract
    text = "\n".join([
        "10^9/лЛейкоциты (WBC) 5.76 3.89 - 9.231001",
        "10^12/лЭритроциты (RBC) 5.32* 3.74 - 5.311001",
        "г/лГемоглобин (HGB, Hb) 148.00 118.30 - 165.701001",
        "%Гематокрит (HCT) 43.70 35.89 - 50.641001",
        "10^9/лТромбоциты (PLT) 174.00 141.30 - 389.701001",
        "Ед/лКреатинфосфокиназа 188.0 39.0 - 308.043",
        "ммоль/лКалий (К+) 4.78 3.50 - 5.1058",
    ])
    result = universal_extract(text)
    unit_prefixes = ['г/л', 'ммоль/л', 'мкмоль/л', 'Ед/л', 'фл', 'пг', '10^']
    for line in result.splitlines():
        parts = line.split("\t")
        name = parts[0]
        ref = parts[2] if len(parts) > 2 else ""
        for pfx in unit_prefixes:
            assert not name.startswith(pfx), f"name '{name}' still has prefix '{pfx}'"
        assert "1001" not in ref, f"ref '{ref}' has trailing code"


# ────────────────────────────────────────────────
# 4. Lab detection: Citilab must NOT be detected as Helix
# ────────────────────────────────────────────────

CITILAB_PYPDF_TEXT = """Полных лет: 64
ФИO пациента: КИРИЛОВ НИКОЛАЙ ИВАНОВИЧ
490886217
Пол:
Дата рождения: 05/09/1961
№ заказа:
МУЖСКОЙ
Референсная группа: Муж
Заказчик: 17211.ООО "ИММУНИТЕТ"
Исследование Результат Единицы Референсный интервал
nr490886217
ПРОФИЛЬ «Клинический анализ крови»
Дата поступления в лабораторию:
18/02/2026 11:21
Биоматериал: Венозная кровь Дата взятия биоматериала:
17/02/2026 08:36
Аналитическая система: Автоматический гематологический анализатор Sysmex XN-2000, Sysmex, Япония
B03.016.002 Общий (клинический) анализ крови1001
ОБЩИЙ АНАЛИЗ КРОВИ (CBC)1001
10^9/лЛейкоциты (WBC) 5.76 3.89 - 9.231001
10^12/лЭритроциты (RBC) 5.32* 3.74 - 5.311001
г/лГемоглобин (HGB, Hb) 148.00 118.30 - 165.701001
%Гематокрит (HCT) 43.70 35.89 - 50.641001
флСредний объем эритроцита (MCV) 82.10* 88.05 - 104.071001
пгСреднее содержание Hb в эритроците (MCH) 27.80 27.75 - 34.521001
г/лСредняя концентрация Hb в эритроцитах (MCHC) 339.00 314.50 - 347.401001
флИндекс распределения эритроцитов (RDW-SD) 37.90* 38.56 - 50.281001
%Индекс распределения эритроцитов (RDW-CV) 12.50 11.43 - 13.901001
10^9/лТромбоциты (PLT) 174.00 141.30 - 389.701001
флСредний объем тромбоцита (MPV) 9.10 9.10 - 12.601001
%Тромбокрит (PCT) 0.16 0.14 - 0.341001
флИндекс распред. тромбоцитов (PDW) 9.60 9.30 - 16.701001
ЛЕЙКОЦИТАРНАЯ ФОРМУЛА1001
10^9/лНейтрофилы (Ne), абсолютное количество 2.55 0.78 - 6.041001
%Нейтрофилы (Ne), % 44.40 40.80 - 70.391001
10^9/лЛимфоциты (LYMF), абсолютное количество 2.37 1.01 - 2.751001
%Лимфоциты (LYMF), % 41.10 20.11 - 46.791001
10^9/лМоноциты (MON), абсолютное количество 0.59 0.29 - 0.721001
%Моноциты (MON), % 10.20 4.26 - 11.081001
10^9/лЭозинофилы (Eo), абсолютное количество 0.21 0.04 - 0.581001
%Эозинофилы (Eo), % 3.60 0.73 - 8.861001
10^9/лБазофилы (Ba), абсолютное количество 0.040 0.010 - 0.0901001
%Базофилы (Ba), % 0.70 0.20 - 1.501001
10^9/лНезрелые гранулоциты, абсолютное количество 0.01 0.00 - 0.041001
%Незрелые гранулоциты % 0.20 0.00 - 0.501001
10^9/лНормобласты, абсолютное количество 0.00 0.00 - 0.031001
%Нормобласты % 0.00 0.00 - 0.201001
Аналитическая система: Автоматический анализатор СОЭ Test 1, Alifax, Италия
мм/чСОЭ (метод аттестован по Westergren) 15.0 2.0 - 20.01002
Ед/лКреатинфосфокиназа 188.0 39.0 - 308.043
Индекс атерогенности 1.21 < 3.001091
ммоль/лКалий (К+) 4.78 3.50 - 5.1058
ммоль/лНатрий (Na+) 140.00 135.00 - 145.0058
ммоль/лХлор (Cl-) 102.6 98.0 - 107.058
ммоль/лМагний 1.03* 0.66 - 0.9951
мкмоль/лЖелезо сывороточное 23.8 5.8 - 34.530
ммоль/лХолестерин общий 3.45 3.20 - 5.205
ммоль/лТриглицериды 0.70 0.10 - 2.306
ммоль/лЛипопротеины очень низкой плотности (ЛПОНП, VLDL) 0.32 0.26 - 1.0014377
мкмоль/лБилирубин общий 10.90 2.50 - 21.0016
Ед/лАСТ (аспартатаминотрансфераза) 17.8 5.0 - 40.012
Ед/лАЛТ (аланинаминотрансфераза) 16.7 5.0 - 41.013
мкмоль/лКреатинин в крови 77.0 62.0 - 106.04
ммоль/лГлюкоза 6.07 4.56 - 6.381
г/лОбщий белок в крови 71.3 64.0 - 83.019
ммоль/лМочевина 5.90 2.76 - 8.072"""


def test_citilab_detection():
    from parsers.lab_detector import detect_lab, LabType
    det = detect_lab(CITILAB_PYPDF_TEXT)
    assert det.lab_type == LabType.CITILAB, \
        f"Expected CITILAB, got {det.lab_type.value} (conf={det.confidence:.2f}, sigs={det.matched_signatures})"
    assert det.confidence >= 0.3


# ────────────────────────────────────────────────
# 5. _smart_to_candidates: no unit prefixes, no trailing codes
# ────────────────────────────────────────────────

def test_smart_to_candidates_citilab():
    from engine import _smart_to_candidates

    candidates = _smart_to_candidates(CITILAB_PYPDF_TEXT)
    assert candidates, "No candidates produced!"

    unit_prefixes = ['г/л', 'ммоль/л', 'мкмоль/л', 'Ед/л', '10^', 'фл', 'пг', 'мм/ч']
    for line in candidates.splitlines():
        parts = line.split("\t")
        name = parts[0] if parts else ""
        ref = parts[2] if len(parts) > 2 else ""
        for pfx in unit_prefixes:
            assert not name.startswith(pfx), \
                f"name '{name}' still starts with unit prefix '{pfx}'"
        assert "1001" not in ref, \
            f"ref '{ref}' still has trailing code 1001 in candidate: {line}"


# ────────────────────────────────────────────────
# 6. Full pipeline: _smart_to_candidates → parse_items_from_candidates
# ────────────────────────────────────────────────

def test_actual_citilab_pdf_pipeline():
    from engine import _smart_to_candidates, parse_items_from_candidates

    candidates = _smart_to_candidates(CITILAB_PYPDF_TEXT)
    assert candidates, "No candidates produced!"

    items = parse_items_from_candidates(candidates)
    assert len(items) >= 25, f"Expected ≥25 items, got {len(items)}"

    by_name = {item.name: item for item in items}

    # WBC
    assert "WBC" in by_name, f"WBC missing! Names: {sorted(by_name.keys())}"
    assert by_name["WBC"].value == pytest.approx(5.76, abs=0.01)
    if by_name["WBC"].ref and by_name["WBC"].ref.high is not None:
        assert by_name["WBC"].ref.high < 100, \
            f"WBC ref.high={by_name['WBC'].ref.high} — trailing code!"

    # PLT
    assert "PLT" in by_name, f"PLT missing! Names: {sorted(by_name.keys())}"
    assert by_name["PLT"].value == pytest.approx(174.0, abs=0.1)

    # HGB
    assert "HGB" in by_name, f"HGB missing! Names: {sorted(by_name.keys())}"
    assert by_name["HGB"].value == pytest.approx(148.0, abs=0.1)

    # Leukocyte formula markers (absolute or %)
    leuko_markers = ["NE", "NE%", "LYMF", "LY%", "MON", "MO%", "EO", "EO%", "BA", "BA%"]
    found_leuko = [m for m in leuko_markers if m in by_name]
    assert len(found_leuko) >= 3, \
        f"Expected ≥3 of {leuko_markers}, found {found_leuko}. Names: {sorted(by_name.keys())}"

    # No item should have unit prefix in raw_name
    unit_prefixes = ['г/л', 'ммоль/л', 'мкмоль/л', 'Ед/л', 'фл', 'пг', '%', 'мм/ч', '10^']
    for item in items:
        for pfx in unit_prefixes:
            assert not item.raw_name.startswith(pfx), \
                f"raw_name '{item.raw_name}' still has unit prefix '{pfx}'"

    # No ref should have implausibly high values (trailing lab code)
    for item in items:
        if item.ref and item.ref.high is not None:
            assert item.ref.high < 10000, \
                f"'{item.name}' ref.high={item.ref.high} — likely trailing code!"
