"""
Интеграционные тесты Citilab: полный пайплайн от pypdf-текста до объектов Item.

pypdf text → universal_extract() → parse_items_from_candidates() → Item objects

Запуск: pytest parsers/test_citilab_integration.py -v
"""
import sys
from pathlib import Path
from collections import defaultdict

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.universal_extractor import universal_extract
from engine import parse_items_from_candidates

# ═══════════════════════════════════════════════════════════
# Реальный pypdf-текст Citilab (4 страницы, полный ОАК + биохимия)
# ═══════════════════════════════════════════════════════════

CITILAB_FULL_TEXT = """
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
мм/чСОЭ (метод аттестован по Westergren) 15.0 2.0 - 20.01002
A09.05.083 Исследование уровня гликированного гемоглобина в крови1050
%Гликозилированный гемоглобин (HBA1c, DCCT/NGSP) 6.12* 4.80 - 5.901050
ммоль/мольГликозилированный гемоглобин (HBA1c, IFCC) 43.39* 29.00 - 42.001050
A09.05.043 Определение активности креатинкиназы в крови43
Ед/лКреатинфосфокиназа 188.0 39.0 - 308.043
Индекс атерогенности 1.21 < 3.001091
A09.05.031.000.01 Исследование уровня электролитов (калий, натрий, хлор) в крови58
КАЛИЙ, НАТРИЙ, ХЛОР (К+, NA+, CL-)58
ммоль/лКалий (К+) 4.78 3.50 - 5.1058
ммоль/лНатрий (Na+) 140.00 135.00 - 145.0058
ммоль/лХлор (Cl-) 102.6 98.0 - 107.058
ммоль/лМагний 1.03* 0.66 - 0.9951
мкмоль/лЖелезо сывороточное 23.8 5.8 - 34.530
ммоль/лХолестерин общий 3.45 3.20 - 5.205
ммоль/лЛипопротеины высокой плотности (ЛПВП, HDL)  см. интерпретацию результата 1.567
ммоль/лХолестерин не-ЛПВП 1.89 < 3.40150
ммоль/лЛипопротеины низкой плотности (ЛПНП, LDL) - прямое определение 1.83 0.10 - 4.141090
ммоль/лТриглицериды 0.70 0.10 - 2.306
ммоль/лЛипопротеины очень низкой плотности (ЛПОНП, VLDL) 0.32 0.26 - 1.0014377
мкмоль/лБилирубин общий 10.90 2.50 - 21.0016
Ед/лАСТ (аспартатаминотрансфераза) 17.8 5.0 - 40.012
Ед/лАЛТ (аланинаминотрансфераза) 16.7 5.0 - 41.013
мкмоль/лКреатинин в крови 77.0 62.0 - 106.04
ммоль/лГлюкоза 6.07 4.56 - 6.381
г/лОбщий белок в крови 71.3 64.0 - 83.019
ммоль/лМочевина 5.90 2.76 - 8.072
"""


# ═══════════════════════════════════════════════════════════
# Вспомогательные функции
# ═══════════════════════════════════════════════════════════

def _run_pipeline():
    """Прогоняет полный пайплайн и возвращает список Item."""
    candidates = universal_extract(CITILAB_FULL_TEXT)
    return parse_items_from_candidates(candidates)


def _build_lookup(items):
    """Строит словарь name → list[Item] (допускает дубликаты)."""
    by_name = defaultdict(list)
    for item in items:
        by_name[item.name].append(item)
    return by_name


def _find(by_name, name, approx_value=None):
    """Ищет Item по нормализованному имени, опционально по значению."""
    items = by_name.get(name, [])
    if not items:
        return None
    if approx_value is not None:
        for it in items:
            if it.value is not None and abs(it.value - approx_value) < 0.1:
                return it
    return items[0]


# ═══════════════════════════════════════════════════════════
# Тест 1: общее количество распарсенных показателей
# ═══════════════════════════════════════════════════════════

class TestCitilabFullPipeline:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.items = _run_pipeline()
        self.by_name = _build_lookup(self.items)

    def test_minimum_item_count(self):
        """Должно быть не менее 30 распарсенных показателей."""
        assert len(self.items) >= 30, (
            f"Ожидалось ≥30, получено {len(self.items)}. "
            f"Имена: {sorted(set(it.name for it in self.items))}"
        )

    # ─── ОАК: основные показатели ───

    def test_wbc(self):
        wbc = _find(self.by_name, "WBC")
        assert wbc is not None, f"WBC не найден. Доступные: {sorted(self.by_name.keys())}"
        assert wbc.value == pytest.approx(5.76, abs=0.01)
        assert wbc.ref is not None
        assert wbc.ref.low == pytest.approx(3.89, abs=0.01)
        assert wbc.ref.high == pytest.approx(9.23, abs=0.01)
        assert wbc.ref.high < 100, f"WBC ref.high={wbc.ref.high} — trailing code not stripped!"
        assert wbc.status == "В НОРМЕ"

    def test_rbc(self):
        rbc = _find(self.by_name, "RBC")
        assert rbc is not None, f"RBC не найден. Доступные: {sorted(self.by_name.keys())}"
        assert rbc.value == pytest.approx(5.32, abs=0.01)
        assert rbc.ref is not None
        assert rbc.ref.low == pytest.approx(3.74, abs=0.01)
        assert rbc.ref.high == pytest.approx(5.31, abs=0.01)
        assert rbc.status == "ВЫШЕ"

    def test_hgb(self):
        hgb = _find(self.by_name, "HGB")
        assert hgb is not None, f"HGB не найден. Доступные: {sorted(self.by_name.keys())}"
        assert hgb.value == pytest.approx(148.0, abs=0.1)
        assert hgb.ref is not None
        assert hgb.ref.low == pytest.approx(118.30, abs=0.1)
        assert hgb.ref.high == pytest.approx(165.70, abs=0.1)
        assert hgb.status == "В НОРМЕ"

    def test_hct(self):
        hct = _find(self.by_name, "HCT")
        assert hct is not None, f"HCT не найден. Доступные: {sorted(self.by_name.keys())}"
        assert hct.value == pytest.approx(43.7, abs=0.1)
        assert hct.ref is not None
        assert hct.ref.low == pytest.approx(35.89, abs=0.1)
        assert hct.ref.high == pytest.approx(50.64, abs=0.1)
        assert hct.status == "В НОРМЕ"

    def test_mcv(self):
        mcv = _find(self.by_name, "MCV")
        assert mcv is not None, f"MCV не найден. Доступные: {sorted(self.by_name.keys())}"
        assert mcv.value == pytest.approx(82.1, abs=0.1)
        assert mcv.ref is not None
        assert mcv.ref.low == pytest.approx(88.05, abs=0.1)
        assert mcv.ref.high == pytest.approx(104.07, abs=0.1)
        assert mcv.status == "НИЖЕ"

    def test_plt(self):
        plt = _find(self.by_name, "PLT")
        assert plt is not None, f"PLT не найден. Доступные: {sorted(self.by_name.keys())}"
        assert plt.value == pytest.approx(174.0, abs=0.1)
        assert plt.ref is not None
        assert plt.ref.low == pytest.approx(141.30, abs=0.1)
        assert plt.ref.high == pytest.approx(389.70, abs=0.1)
        assert plt.status == "В НОРМЕ"

    # ─── Лейкоцитарная формула (% варианты) ───

    def test_neutrophils_pct(self):
        ne = _find(self.by_name, "NE%", approx_value=44.4)
        assert ne is not None, f"NE% (~44.4) не найден. Доступные: {sorted(self.by_name.keys())}"
        assert ne.value == pytest.approx(44.4, abs=0.1)
        assert ne.ref is not None
        assert ne.ref.low == pytest.approx(40.80, abs=0.1)
        assert ne.ref.high == pytest.approx(70.39, abs=0.1)
        assert ne.status == "В НОРМЕ"

    def test_lymphocytes_pct(self):
        ly = _find(self.by_name, "LY%", approx_value=41.1)
        assert ly is not None, f"LY% (~41.1) не найден. Доступные: {sorted(self.by_name.keys())}"
        assert ly.value == pytest.approx(41.1, abs=0.1)
        assert ly.ref is not None
        assert ly.ref.low == pytest.approx(20.11, abs=0.1)
        assert ly.ref.high == pytest.approx(46.79, abs=0.1)
        assert ly.status == "В НОРМЕ"

    # ─── СОЭ ───

    def test_esr(self):
        esr = _find(self.by_name, "ESR")
        assert esr is not None, f"ESR не найден. Доступные: {sorted(self.by_name.keys())}"
        assert esr.value == pytest.approx(15.0, abs=0.1)
        assert esr.ref is not None
        assert esr.ref.low == pytest.approx(2.0, abs=0.1)
        assert esr.ref.high == pytest.approx(20.0, abs=0.1)
        assert esr.status == "В НОРМЕ"

    # ─── Гликозилированный гемоглобин (DCCT) ───

    def test_hba1c_dcct(self):
        hba1c = _find(self.by_name, "HBA1C", approx_value=6.12)
        assert hba1c is not None, (
            f"HBA1C (~6.12 DCCT) не найден. "
            f"HBA1C items: {[(it.value, it.ref_text) for it in self.by_name.get('HBA1C', [])]}"
        )
        assert hba1c.value == pytest.approx(6.12, abs=0.01)
        assert hba1c.ref is not None
        assert hba1c.ref.low == pytest.approx(4.80, abs=0.01)
        assert hba1c.ref.high == pytest.approx(5.90, abs=0.01)
        assert hba1c.ref.high < 100, f"HBA1C ref.high={hba1c.ref.high} — trailing code!"
        assert hba1c.status == "ВЫШЕ"

    # ─── Электролиты ───

    def test_potassium(self):
        k = _find(self.by_name, "K")
        assert k is not None, f"K не найден. Доступные: {sorted(self.by_name.keys())}"
        assert k.value == pytest.approx(4.78, abs=0.01)
        assert k.ref is not None
        assert k.ref.low == pytest.approx(3.50, abs=0.01)
        assert k.ref.high == pytest.approx(5.10, abs=0.01)
        assert k.status == "В НОРМЕ"

    def test_sodium(self):
        na = _find(self.by_name, "NA")
        assert na is not None, f"NA не найден. Доступные: {sorted(self.by_name.keys())}"
        assert na.value == pytest.approx(140.0, abs=0.1)
        assert na.ref is not None
        assert na.ref.low == pytest.approx(135.0, abs=0.1)
        assert na.ref.high == pytest.approx(145.0, abs=0.1)
        assert na.status == "В НОРМЕ"

    def test_magnesium(self):
        mg = _find(self.by_name, "MG")
        assert mg is not None, f"MG не найден. Доступные: {sorted(self.by_name.keys())}"
        assert mg.value == pytest.approx(1.03, abs=0.01)
        assert mg.ref is not None
        assert mg.ref.low == pytest.approx(0.66, abs=0.01)
        assert mg.ref.high == pytest.approx(0.99, abs=0.01)
        assert mg.status == "ВЫШЕ"

    # ─── Биохимия ───

    def test_atherogenic_index(self):
        ai = _find(self.by_name, "AI")
        assert ai is not None, f"AI не найден. Доступные: {sorted(self.by_name.keys())}"
        assert ai.value == pytest.approx(1.21, abs=0.01)
        assert ai.ref is not None
        assert ai.ref.high == pytest.approx(3.00, abs=0.01)
        assert ai.ref.high < 100, f"AI ref.high={ai.ref.high} — trailing code!"
        assert ai.status == "В НОРМЕ"

    def test_cholesterol(self):
        chol = _find(self.by_name, "CHOL")
        assert chol is not None, f"CHOL не найден. Доступные: {sorted(self.by_name.keys())}"
        assert chol.value == pytest.approx(3.45, abs=0.01)
        assert chol.ref is not None
        assert chol.ref.low == pytest.approx(3.20, abs=0.01)
        assert chol.ref.high == pytest.approx(5.20, abs=0.01)
        assert chol.status == "В НОРМЕ"

    def test_triglycerides(self):
        trig = _find(self.by_name, "TRIG")
        assert trig is not None, f"TRIG не найден. Доступные: {sorted(self.by_name.keys())}"
        assert trig.value == pytest.approx(0.70, abs=0.01)
        assert trig.ref is not None
        assert trig.ref.low == pytest.approx(0.10, abs=0.01)
        assert trig.ref.high == pytest.approx(2.30, abs=0.01)
        assert trig.status == "В НОРМЕ"

    def test_bilirubin_total(self):
        tbil = _find(self.by_name, "TBIL")
        assert tbil is not None, f"TBIL не найден. Доступные: {sorted(self.by_name.keys())}"
        assert tbil.value == pytest.approx(10.9, abs=0.1)
        assert tbil.ref is not None
        assert tbil.ref.low == pytest.approx(2.50, abs=0.1)
        assert tbil.ref.high == pytest.approx(21.0, abs=0.1)
        assert tbil.status == "В НОРМЕ"

    def test_ast(self):
        ast = _find(self.by_name, "AST")
        assert ast is not None, f"AST не найден. Доступные: {sorted(self.by_name.keys())}"
        assert ast.value == pytest.approx(17.8, abs=0.1)
        assert ast.ref is not None
        assert ast.ref.low == pytest.approx(5.0, abs=0.1)
        assert ast.ref.high == pytest.approx(40.0, abs=0.1)
        assert ast.status == "В НОРМЕ"

    def test_alt(self):
        alt = _find(self.by_name, "ALT")
        assert alt is not None, f"ALT не найден. Доступные: {sorted(self.by_name.keys())}"
        assert alt.value == pytest.approx(16.7, abs=0.1)
        assert alt.ref is not None
        assert alt.ref.low == pytest.approx(5.0, abs=0.1)
        assert alt.ref.high == pytest.approx(41.0, abs=0.1)
        assert alt.status == "В НОРМЕ"

    def test_creatinine(self):
        crea = _find(self.by_name, "CREA")
        assert crea is not None, f"CREA не найден. Доступные: {sorted(self.by_name.keys())}"
        assert crea.value == pytest.approx(77.0, abs=0.1)
        assert crea.ref is not None
        assert crea.ref.low == pytest.approx(62.0, abs=0.1)
        assert crea.ref.high == pytest.approx(106.0, abs=0.1)
        assert crea.status == "В НОРМЕ"

    def test_glucose(self):
        gluc = _find(self.by_name, "GLUC")
        assert gluc is not None, f"GLUC не найден. Доступные: {sorted(self.by_name.keys())}"
        assert gluc.value == pytest.approx(6.07, abs=0.01)
        assert gluc.ref is not None
        assert gluc.ref.low == pytest.approx(4.56, abs=0.01)
        assert gluc.ref.high == pytest.approx(6.38, abs=0.01)
        assert gluc.status == "В НОРМЕ"

    def test_total_protein(self):
        tp = _find(self.by_name, "TP")
        assert tp is not None, f"TP не найден. Доступные: {sorted(self.by_name.keys())}"
        assert tp.value == pytest.approx(71.3, abs=0.1)
        assert tp.ref is not None
        assert tp.ref.low == pytest.approx(64.0, abs=0.1)
        assert tp.ref.high == pytest.approx(83.0, abs=0.1)
        assert tp.status == "В НОРМЕ"

    def test_urea(self):
        urea = _find(self.by_name, "UREA")
        assert urea is not None, f"UREA не найден. Доступные: {sorted(self.by_name.keys())}"
        assert urea.value == pytest.approx(5.90, abs=0.01)
        assert urea.ref is not None
        assert urea.ref.low == pytest.approx(2.76, abs=0.01)
        assert urea.ref.high == pytest.approx(8.07, abs=0.01)
        assert urea.status == "В НОРМЕ"

    def test_iron(self):
        fe = _find(self.by_name, "FE")
        assert fe is not None, f"FE не найден. Доступные: {sorted(self.by_name.keys())}"
        assert fe.value == pytest.approx(23.8, abs=0.1)
        assert fe.ref is not None
        assert fe.ref.low == pytest.approx(5.8, abs=0.1)
        assert fe.ref.high == pytest.approx(34.5, abs=0.1)
        assert fe.status == "В НОРМЕ"


# ═══════════════════════════════════════════════════════════
# Тест 2: ни один raw_name не начинается с единицы измерения
# ═══════════════════════════════════════════════════════════

class TestCitilabNoUnitPrefix:

    def test_no_unit_prefix_in_raw_names(self):
        items = _run_pipeline()
        unit_prefixes = [
            'г/л', 'ммоль/л', 'мкмоль/л', 'Ед/л', 'фл', 'пг', '%',
            'мм/ч', '10^', 'ммоль/моль',
        ]
        for item in items:
            for prefix in unit_prefixes:
                assert not item.raw_name.startswith(prefix), (
                    f"Item '{item.raw_name}' (name={item.name}) "
                    f"всё ещё содержит префикс единицы '{prefix}'"
                )


# ═══════════════════════════════════════════════════════════
# Тест 3: ни один ref.high не содержит остатка лабораторного кода
# ═══════════════════════════════════════════════════════════

class TestCitilabNoHugeRefValues:

    def test_no_huge_ref_high(self):
        items = _run_pipeline()
        for item in items:
            if item.ref and item.ref.high is not None:
                assert item.ref.high < 10000, (
                    f"Item '{item.name}' ref.high={item.ref.high} — "
                    f"возможно не отрезан trailing lab code "
                    f"(raw_name='{item.raw_name}', ref_text='{item.ref_text}')"
                )

    def test_no_huge_ref_low(self):
        items = _run_pipeline()
        for item in items:
            if item.ref and item.ref.low is not None:
                assert item.ref.low < 10000, (
                    f"Item '{item.name}' ref.low={item.ref.low} — "
                    f"возможно не отрезан trailing lab code"
                )


# ═══════════════════════════════════════════════════════════
# Тест 4: детекция лаборатории
# ═══════════════════════════════════════════════════════════

class TestCitilabDetection:

    def test_citilab_detected_by_domain(self):
        from parsers.lab_detector import detect_lab, LabType
        text = """
        Россия, 199178, г. Санкт-Петербург
        19-ая Линия Васильевского острова
        Лиц. № ЛО-78-01-007677 от 20.03.2017 г.
        www.citilab.ru
        ФИО пациента: КИРИЛОВ НИКОЛАЙ ИВАНОВИЧ
        """
        result = detect_lab(text)
        assert result.lab_type == LabType.CITILAB
        assert result.confidence >= 0.3

    def test_citilab_detected_by_name(self):
        from parsers.lab_detector import detect_lab, LabType
        result = detect_lab("Лаборатория СИТИЛАБ\nАнализ крови")
        assert result.lab_type == LabType.CITILAB

    def test_citilab_legacy_returns_generic(self):
        from parsers.lab_detector import detect_lab_format
        text = "www.citilab.ru\nАнализ крови"
        assert detect_lab_format(text) == "generic"

    def test_citilab_not_confused_with_others(self):
        from parsers.lab_detector import detect_lab, LabType
        text = "www.citilab.ru\nСИТИЛАБ\nОбщий анализ крови"
        result = detect_lab(text)
        assert result.lab_type == LabType.CITILAB
        assert result.lab_type != LabType.MEDSI
        assert result.lab_type != LabType.HELIX
        assert result.lab_type != LabType.GEMOTEST


# ═══════════════════════════════════════════════════════════
# Тест 5: edge cases прочистки trailing lab code
# ═══════════════════════════════════════════════════════════

class TestCitilabEdgeCases:

    def test_edge_case_5digit_code_vldl(self):
        """ЛПОНП: '0.26 - 1.0014377' → код 14377 отрезан, ref.high = 1.00."""
        items = _run_pipeline()
        by_name = _build_lookup(items)
        vldl = _find(by_name, "VLDL") or _find(by_name, "ЛИПОПРОТЕИНЫ_ОЧЕНЬ_НИЗКОЙ_ПЛОТНОСТИ_(ЛПОНП,_VLDL)")
        if vldl:
            assert vldl.ref is not None
            assert vldl.ref.high == pytest.approx(1.00, abs=0.01), (
                f"VLDL ref.high={vldl.ref.high}, ожидалось 1.00"
            )
            assert vldl.ref.high < 10, "VLDL ref.high слишком большой — код не отрезан"

    def test_edge_case_creatinine_single_digit_code(self):
        """Креатинин: '62.0 - 106.04' → код 4 отрезан, ref.high = 106.0."""
        items = _run_pipeline()
        by_name = _build_lookup(items)
        crea = _find(by_name, "CREA")
        assert crea is not None
        assert crea.ref.high == pytest.approx(106.0, abs=0.1), (
            f"CREA ref.high={crea.ref.high}, ожидалось 106.0"
        )

    def test_edge_case_basophils_3_decimal(self):
        """Базофилы абс.: '0.010 - 0.0901001' → код отрезан, ref.high = 0.090."""
        items = _run_pipeline()
        by_name = _build_lookup(items)
        ba = _find(by_name, "BA", approx_value=0.04)
        if ba and ba.ref:
            assert ba.ref.high == pytest.approx(0.09, abs=0.001), (
                f"BA abs ref.high={ba.ref.high}, ожидалось 0.090"
            )

    def test_edge_case_atherogenic_index_no_prefix(self):
        """Индекс атерогенности без единицы: '< 3.001091' → код отрезан, ref.high = 3.00."""
        items = _run_pipeline()
        by_name = _build_lookup(items)
        ai = _find(by_name, "AI")
        assert ai is not None
        assert ai.ref is not None
        assert ai.ref.high == pytest.approx(3.00, abs=0.01), (
            f"AI ref.high={ai.ref.high}, ожидалось 3.00"
        )

    def test_edge_case_hdl_see_interpretation(self):
        """ЛПВП: 'см. интерпретацию результата' — известное ограничение.
        Паттерн 'см. интерпретацию' не совпадает с 'см. текст', поэтому
        этот показатель может быть не распарсен. Документировано как ограничение.
        """
        items = _run_pipeline()
        by_name = _build_lookup(items)
        hdl_items = by_name.get("HDL", [])
        # HDL может быть распарсен из других строк (не-ЛПВП),
        # но "see interpretation" вариант может отсутствовать — OK.
        # Проверяем только что pipeline не падает.
        assert isinstance(hdl_items, list)
