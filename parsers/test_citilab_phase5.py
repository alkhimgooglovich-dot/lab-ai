"""
Phase 5 tests: 4 missing Citilab biomarkers (HBA1c DCCT, HBA1c IFCC, LDL, HDL).

Fixes:
  - _rejoin_open_parens: join lines with unclosed '('
  - _is_discardable_fragment: discard standalone 'определение' / 'результата'
  - _SEE_TEXT_BROAD: recognise 'см. интерпретацию' as see-text pattern
  - trailing lab code strip for bare see-text values

Run: pytest parsers/test_citilab_phase5.py -v
"""
import sys
from pathlib import Path
from collections import defaultdict

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.universal_extractor import (
    universal_extract,
    _rejoin_open_parens,
    _is_discardable_fragment,
)
from engine import parse_items_from_candidates


# ═══════════════════════════════════════════════════════════
# Unit tests: _rejoin_open_parens
# ═══════════════════════════════════════════════════════════

class TestRejoinOpenParens:

    def test_hba1c_dcct_split(self):
        """HBA1c DCCT/NGSP: parenthesis split across 2 lines."""
        lines = [
            'Гликозилированный гемоглобин (HBA1c,',
            'DCCT/NGSP)',
            '6.12 4.80 - 5.90',
        ]
        result = _rejoin_open_parens(lines)
        assert len(result) == 2
        assert 'HBA1c, DCCT/NGSP)' in result[0]
        assert '6.12' in result[1]

    def test_balanced_parens_no_change(self):
        """Balanced parentheses — no joining."""
        lines = [
            'Лейкоциты (WBC) 5.76 3.89 - 9.23',
            'Эритроциты (RBC) 5.32 3.74 - 5.31',
        ]
        result = _rejoin_open_parens(lines)
        assert len(result) == 2
        assert result == lines

    def test_no_parens(self):
        """Lines without parentheses pass through."""
        lines = ['Глюкоза 6.07 4.56 - 6.38']
        result = _rejoin_open_parens(lines)
        assert result == lines

    def test_three_line_split(self):
        """Parenthesis split across 3 lines (rare but possible)."""
        lines = [
            'Показатель (A,',
            'B,',
            'C)',
            '1.23 0.50 - 2.00',
        ]
        result = _rejoin_open_parens(lines)
        assert len(result) == 2
        assert 'A, B, C)' in result[0]


# ═══════════════════════════════════════════════════════════
# Unit tests: _is_discardable_fragment
# ═══════════════════════════════════════════════════════════

class TestDiscardableFragment:

    def test_opredelenie_standalone(self):
        assert _is_discardable_fragment('определение') is True

    def test_rezultata_standalone(self):
        assert _is_discardable_fragment('результата') is True

    def test_not_discard_full_name(self):
        """Full biomarker-like name must NOT be discarded."""
        assert _is_discardable_fragment('Определение активности') is False

    def test_not_discard_opredelenie_with_value(self):
        assert _is_discardable_fragment('определение 1.83 0.10 - 4.14') is False


# ═══════════════════════════════════════════════════════════
# Pipeline tests: HBA1c DCCT/NGSP (split lines)
# ═══════════════════════════════════════════════════════════

class TestHBA1cDCCT:

    def test_hba1c_dcct_split_pipeline(self):
        """HBA1c DCCT/NGSP: 3 pypdf lines → single biomarker."""
        text = """%Гликозилированный гемоглобин (HBA1c,
DCCT/NGSP)
6.12* 4.80 - 5.901050"""
        candidates = universal_extract(text)
        items = parse_items_from_candidates(candidates)
        names = {item.name for item in items}
        assert 'HBA1C' in names, f"HBA1C not found. Names: {names}"
        hba1c = [i for i in items if i.name == 'HBA1C'][0]
        assert hba1c.value == pytest.approx(6.12, abs=0.01)
        assert hba1c.ref is not None
        assert hba1c.ref.low == pytest.approx(4.80, abs=0.01)
        assert hba1c.ref.high == pytest.approx(5.90, abs=0.01)

    def test_hba1c_dcct_single_line(self):
        """HBA1c DCCT/NGSP: single line (integration test format)."""
        text = "%Гликозилированный гемоглобин (HBA1c, DCCT/NGSP) 6.12* 4.80 - 5.901050"
        candidates = universal_extract(text)
        items = parse_items_from_candidates(candidates)
        names = {item.name for item in items}
        assert 'HBA1C' in names, f"HBA1C not found. Names: {names}"


# ═══════════════════════════════════════════════════════════
# Pipeline tests: HBA1c IFCC
# ═══════════════════════════════════════════════════════════

class TestHBA1cIFCC:

    def test_hba1c_ifcc_single_line(self):
        """HBA1c IFCC: single line with ммоль/моль prefix."""
        text = "ммоль/мольГликозилированный гемоглобин (HBA1c, IFCC) 43.39* 29.00 - 42.001050"
        candidates = universal_extract(text)
        items = parse_items_from_candidates(candidates)
        names = {item.name for item in items}
        assert 'HBA1C' in names, f"HBA1C not found. Names: {names}"
        hba1c = [i for i in items if i.name == 'HBA1C'][0]
        assert hba1c.value == pytest.approx(43.39, abs=0.01)
        assert hba1c.ref is not None
        assert hba1c.ref.low == pytest.approx(29.0, abs=0.01)
        assert hba1c.ref.high == pytest.approx(42.0, abs=0.01)


# ═══════════════════════════════════════════════════════════
# Pipeline tests: LDL (split lines)
# ═══════════════════════════════════════════════════════════

class TestLDL:

    def test_ldl_split_pipeline(self):
        """LDL with 'прямое определение' split across lines."""
        text = """ммоль/лЛипопротеины низкой плотности (ЛПНП, LDL) - прямое
определение
1.83 0.10 - 4.141090"""
        candidates = universal_extract(text)
        items = parse_items_from_candidates(candidates)
        names = {item.name for item in items}
        assert 'LDL' in names, f"LDL not found. Names: {names}"
        ldl = [i for i in items if i.name == 'LDL'][0]
        assert ldl.value == pytest.approx(1.83, abs=0.01)
        assert ldl.ref is not None
        assert ldl.ref.high == pytest.approx(4.14, abs=0.01)

    def test_ldl_single_line(self):
        """LDL: single line (integration test format)."""
        text = "ммоль/лЛипопротеины низкой плотности (ЛПНП, LDL) - прямое определение 1.83 0.10 - 4.141090"
        candidates = universal_extract(text)
        items = parse_items_from_candidates(candidates)
        names = {item.name for item in items}
        assert 'LDL' in names, f"LDL not found. Names: {names}"


# ═══════════════════════════════════════════════════════════
# Pipeline tests: HDL (see interpretation)
# ═══════════════════════════════════════════════════════════

class TestHDL:

    def test_hdl_see_text_split(self):
        """HDL with 'см. интерпретацию' pattern — split pypdf lines."""
        text = """ммоль/лЛипопротеины высокой плотности (ЛПВП, HDL)  см. интерпретацию
результата
1.567"""
        candidates = universal_extract(text)
        items = parse_items_from_candidates(candidates)
        names = {item.name for item in items}
        assert 'HDL' in names, f"HDL not found. Names: {names}"
        hdl = [i for i in items if i.name == 'HDL'][0]
        assert hdl.value == pytest.approx(1.56, abs=0.02)

    def test_hdl_see_text_single_line(self):
        """HDL: single line (integration test format)."""
        text = "ммоль/лЛипопротеины высокой плотности (ЛПВП, HDL)  см. интерпретацию результата 1.567"
        candidates = universal_extract(text)
        items = parse_items_from_candidates(candidates)
        names = {item.name for item in items}
        assert 'HDL' in names, f"HDL not found. Names: {names}"
        hdl = [i for i in items if i.name == 'HDL'][0]
        assert hdl.value == pytest.approx(1.56, abs=0.02)


# ═══════════════════════════════════════════════════════════
# Full pipeline: Citilab 50 biomarkers
# ═══════════════════════════════════════════════════════════

CITILAB_FULL_TEXT_SPLIT = """
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
%Гликозилированный гемоглобин (HBA1c,
DCCT/NGSP)
6.12* 4.80 - 5.901050
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
ммоль/лЛипопротеины высокой плотности (ЛПВП, HDL)  см. интерпретацию
результата
1.567
ммоль/лХолестерин не-ЛПВП 1.89 < 3.40150
ммоль/лЛипопротеины низкой плотности (ЛПНП, LDL) - прямое
определение
1.83 0.10 - 4.141090
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


def _build_lookup(items):
    by_name = defaultdict(list)
    for item in items:
        by_name[item.name].append(item)
    return by_name


class TestCitilabFullSplit:
    """Full Citilab text with pypdf split lines — all 4 missing biomarkers."""

    @pytest.fixture(autouse=True)
    def setup(self):
        candidates = universal_extract(CITILAB_FULL_TEXT_SPLIT)
        self.items = parse_items_from_candidates(candidates)
        self.by_name = _build_lookup(self.items)
        self.all_names = sorted(set(it.name for it in self.items))

    def test_minimum_48_biomarkers(self):
        assert len(self.items) >= 48, (
            f"Expected ≥48, got {len(self.items)}. Names: {self.all_names}"
        )

    def test_hba1c_dcct_present(self):
        hba1c = [i for i in self.by_name.get('HBA1C', [])
                 if i.value is not None and abs(i.value - 6.12) < 0.1]
        assert hba1c, f"HBA1C ~6.12 not found. HBA1C items: {self.by_name.get('HBA1C', [])}"
        assert hba1c[0].ref is not None
        assert hba1c[0].ref.low == pytest.approx(4.80, abs=0.01)
        assert hba1c[0].ref.high == pytest.approx(5.90, abs=0.01)

    def test_hba1c_ifcc_present(self):
        hba1c = [i for i in self.by_name.get('HBA1C', [])
                 if i.value is not None and abs(i.value - 43.39) < 0.1]
        assert hba1c, f"HBA1C ~43.39 not found. HBA1C items: {self.by_name.get('HBA1C', [])}"
        assert hba1c[0].ref is not None
        assert hba1c[0].ref.high == pytest.approx(42.0, abs=0.01)

    def test_ldl_present(self):
        ldl_items = self.by_name.get('LDL', [])
        assert ldl_items, f"LDL not found. Names: {self.all_names}"
        ldl = ldl_items[0]
        assert ldl.value == pytest.approx(1.83, abs=0.01)
        assert ldl.ref is not None
        assert ldl.ref.high == pytest.approx(4.14, abs=0.01)

    def test_hdl_present(self):
        hdl_items = self.by_name.get('HDL', [])
        assert hdl_items, f"HDL not found. Names: {self.all_names}"
        hdl = hdl_items[0]
        assert hdl.value == pytest.approx(1.56, abs=0.02)

    def test_opredelenie_not_a_biomarker(self):
        """'определение' must NOT appear as a standalone biomarker name."""
        for item in self.items:
            low = item.name.lower()
            assert low != 'определение', (
                f"'определение' appeared as biomarker: {item}"
            )

    def test_no_huge_ref_high(self):
        for item in self.items:
            if item.ref and item.ref.high is not None:
                assert item.ref.high < 10000, (
                    f"Item '{item.name}' ref.high={item.ref.high} — trailing code?"
                )

    def test_wbc_still_works(self):
        wbc = self.by_name.get('WBC', [])
        assert wbc, f"WBC not found — regression! Names: {self.all_names}"
        assert wbc[0].value == pytest.approx(5.76, abs=0.01)

    def test_glucose_still_works(self):
        gluc = self.by_name.get('GLUC', [])
        assert gluc, f"GLUC not found — regression! Names: {self.all_names}"
        assert gluc[0].value == pytest.approx(6.07, abs=0.01)
