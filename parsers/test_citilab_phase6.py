"""
Phase 6 tests: verify HbA1c and HDL parse through the FULL pipeline
(including _prestrip_interstitial_noise + _smart_to_candidates in engine.py).

Phases 1-5 fixed universal_extract for isolated blocks, but the REAL pypdf
text includes extra context (equipment info, interpretation sections, risk
scales) that may interfere.

Run: pytest parsers/test_citilab_phase6.py -v -s
"""
import re
import sys
from pathlib import Path
from collections import defaultdict

import pytest

_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from parsers.universal_extractor import universal_extract
from engine import (
    parse_items_from_candidates,
    _smart_to_candidates,
    _prestrip_interstitial_noise,
    _filter_noise_candidates,
    parse_with_fallback,
    assign_confidence,
    deduplicate_items,
    apply_sanity_filter,
    _is_garbage_name,
    _run_parse_pipeline,
)
from parsers.lab_detector import detect_lab


# =====================================================================
# REAL pypdf text with ALL context lines from the actual Citilab PDF.
# This includes equipment info, interpretation sections, risk scales,
# service codes, and date stamps that are NOT in the cleaned-up
# CITILAB_FULL_TEXT or CITILAB_FULL_TEXT_SPLIT constants.
# =====================================================================

CITILAB_REAL_PYPDF = """\
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
Аналитическая система: Автоматизированная модульная платформа Roche Cobas 6000 с биохимическим модулем c501, Roche Diagnostics,
Швейцария
A09.05.083 Исследование уровня гликированного гемоглобина в крови1050
%Гликозилированный гемоглобин (HBA1c,
DCCT/NGSP)
6.12* 4.80 - 5.901050
ммоль/мольГликозилированный гемоглобин (HBA1c, IFCC) 43.39* 29.00 - 42.001050
Дата поступления в лабораторию:
18/02/2026 11:23
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
A09.05.004 Исследование уровня холестерина липопротеинов высокой плотности в крови7
ммоль/лЛипопротеины высокой плотности (ЛПВП, HDL)  см. интерпретацию
результата
1.567
Интерпретация результата:
> 1.45 — риск развития коронарной болезни отсутствует
0.90 - 1.45 — умеренный риск
< 0.90 — высокий риск
A09.05.026.000.01 Холестерин не-ЛПВП150
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


def _prestrip(raw_text: str) -> str:
    """Simulate _prestrip_interstitial_noise from engine.py."""
    from parsers.line_scorer import is_header_service_line, is_noise
    lines = raw_text.splitlines()
    result = []
    for ln in lines:
        s = ln.strip()
        if not s:
            result.append(ln)
            continue
        if is_header_service_line(s):
            continue
        if is_noise(s):
            if re.match(r'^[^\S\n]*[^\S\n]*\d', s) or re.match(r'^[+\-]?\s*\d', s):
                result.append(ln)
                continue
            if re.match(r'^[а-яА-Яa-zA-Z/%*^]+[/а-яА-Яa-zA-Z0-9^]*$', s) and len(s) <= 15:
                result.append(ln)
                continue
            continue
        result.append(ln)
    return "\n".join(result)


def _build_lookup(items):
    by_name = defaultdict(list)
    for item in items:
        by_name[item.name].append(item)
    return by_name


# =====================================================================
# Test 1: universal_extract on REAL pypdf text (with prestrip)
# =====================================================================

class TestRealPypdfUniversalExtract:
    """Feed REAL pypdf text through _prestrip + universal_extract."""

    @pytest.fixture(autouse=True)
    def setup(self):
        prestripped = _prestrip(CITILAB_REAL_PYPDF)
        candidates = universal_extract(prestripped)
        self.items = parse_items_from_candidates(candidates)
        self.by_name = _build_lookup(self.items)
        self.all_names = sorted(set(it.name for it in self.items))

    def test_hba1c_dcct_present(self):
        """HBA1C DCCT/NGSP (~6.12) must be present."""
        hba1c = [i for i in self.by_name.get('HBA1C', [])
                 if i.value is not None and abs(i.value - 6.12) < 0.1]
        assert hba1c, (
            f"HBA1C ~6.12 not found. HBA1C items: "
            f"{[(it.value, it.ref_text) for it in self.by_name.get('HBA1C', [])]}. "
            f"All names: {self.all_names}"
        )
        assert hba1c[0].ref is not None
        assert hba1c[0].ref.low == pytest.approx(4.80, abs=0.01)
        assert hba1c[0].ref.high == pytest.approx(5.90, abs=0.01)

    def test_hba1c_ifcc_present(self):
        """HBA1C IFCC (~43.39) must be present."""
        hba1c = [i for i in self.by_name.get('HBA1C', [])
                 if i.value is not None and abs(i.value - 43.39) < 0.1]
        assert hba1c, (
            f"HBA1C ~43.39 not found. HBA1C items: "
            f"{[(it.value, it.ref_text) for it in self.by_name.get('HBA1C', [])]}. "
            f"All names: {self.all_names}"
        )
        assert hba1c[0].ref is not None
        assert hba1c[0].ref.high == pytest.approx(42.0, abs=0.01)

    def test_hdl_present(self):
        """HDL (~1.56) must be present from 'see interpretation' pattern."""
        hdl_items = self.by_name.get('HDL', [])
        assert hdl_items, (
            f"HDL not found. All names: {self.all_names}"
        )
        hdl = [i for i in hdl_items if i.value is not None and abs(i.value - 1.56) < 0.05]
        assert hdl, (
            f"HDL ~1.56 not found. HDL items: "
            f"{[(it.value, it.ref_text) for it in hdl_items]}"
        )

    def test_no_risk_scale_biomarkers(self):
        """Risk scale lines must NOT appear as biomarker names."""
        for item in self.items:
            low = item.name.lower()
            assert 'risk' not in low or item.name in ('RISK',), (
                f"Risk scale leaked as biomarker: {item.name} = {item.value}"
            )

    def test_no_interpretation_biomarker(self):
        """'Interpretation result' must NOT appear as biomarker."""
        for item in self.items:
            assert 'ИНТЕРПРЕТАЦИЯ' not in item.raw_name.upper(), (
                f"Interpretation leaked: {item.raw_name}"
            )

    def test_minimum_48_biomarkers(self):
        """Full text should yield >= 48 biomarkers."""
        assert len(self.items) >= 48, (
            f"Expected >= 48, got {len(self.items)}. Names: {self.all_names}"
        )

    def test_wbc_still_works(self):
        wbc = self.by_name.get('WBC', [])
        assert wbc, f"WBC regression! Names: {self.all_names}"
        assert wbc[0].value == pytest.approx(5.76, abs=0.01)

    def test_cholesterol_still_works(self):
        chol = self.by_name.get('CHOL', [])
        assert chol, f"CHOL regression! Names: {self.all_names}"
        assert chol[0].value == pytest.approx(3.45, abs=0.01)

    def test_glucose_still_works(self):
        gluc = self.by_name.get('GLUC', [])
        assert gluc, f"GLUC regression! Names: {self.all_names}"
        assert gluc[0].value == pytest.approx(6.07, abs=0.01)

    def test_ldl_still_works(self):
        ldl = self.by_name.get('LDL', [])
        assert ldl, f"LDL regression! Names: {self.all_names}"
        assert ldl[0].value == pytest.approx(1.83, abs=0.01)

    def test_no_huge_ref_values(self):
        """No trailing lab codes in ref ranges."""
        for item in self.items:
            if item.ref and item.ref.high is not None:
                assert item.ref.high < 10000, (
                    f"{item.name} ref.high={item.ref.high} - trailing code?"
                )


# =====================================================================
# Test 2: _prestrip_interstitial_noise preserves critical lines
# =====================================================================

class TestPrestripPreservesLines:
    """Verify _prestrip does not remove lines needed for HbA1c/HDL."""

    def test_hba1c_name_survives(self):
        result = _prestrip(CITILAB_REAL_PYPDF)
        assert '%' not in result or 'HBA1c' in result or 'гемоглобин' in result.lower()
        # After prestrip, the HBA1c name line should still be there
        assert 'HBA1c' in result, "HBA1c name line removed by prestrip!"

    def test_dcct_ngsp_survives(self):
        result = _prestrip(CITILAB_REAL_PYPDF)
        assert 'DCCT/NGSP)' in result, "DCCT/NGSP line removed by prestrip!"

    def test_hba1c_value_survives(self):
        result = _prestrip(CITILAB_REAL_PYPDF)
        assert '6.12' in result, "HBA1c value 6.12 removed by prestrip!"

    def test_hdl_name_survives(self):
        result = _prestrip(CITILAB_REAL_PYPDF)
        assert 'HDL' in result, "HDL name line removed by prestrip!"

    def test_hdl_value_survives(self):
        result = _prestrip(CITILAB_REAL_PYPDF)
        assert '1.567' in result, "HDL value 1.567 removed by prestrip!"

    def test_rezultata_survives(self):
        """'результата' standalone must survive prestrip (discarded later in P10)."""
        result = _prestrip(CITILAB_REAL_PYPDF)
        assert 'результата' in result.lower(), (
            "'результата' removed by prestrip - should survive until P10!"
        )

    def test_risk_lines_removed(self):
        """Risk scale lines starting with > or < should be removed."""
        result = _prestrip(CITILAB_REAL_PYPDF)
        for line in result.splitlines():
            s = line.strip()
            if s.startswith('>') and 'риск' in s.lower():
                pytest.fail(f"Risk line not removed: {s!r}")
            if s.startswith('<') and 'риск' in s.lower():
                pytest.fail(f"Risk line not removed: {s!r}")

    def test_moderate_risk_kept_for_p10(self):
        """'0.90 - 1.45 -- умеренный риск' starts with digit, stays in prestrip.
        P10 (_is_discardable_fragment) handles it later."""
        result = _prestrip(CITILAB_REAL_PYPDF)
        # This line starts with a digit so prestrip keeps it -- that's OK
        # P10 will discard it via 'умеренный риск' in _is_discardable_fragment
        lines = [ln.strip() for ln in result.splitlines()]
        moderate = [ln for ln in lines if 'умеренный риск' in ln.lower()]
        # It's OK if it's present (prestrip keeps digit-starting lines)
        # The important thing is it doesn't appear as a biomarker
        candidates = universal_extract(result)
        for c in candidates.splitlines():
            parts = c.split('\t')
            if parts:
                assert 'умеренный' not in parts[0].lower(), (
                    f"Risk scale leaked as candidate: {c!r}"
                )


# =====================================================================
# Test 3: _smart_to_candidates (REAL engine.py pipeline) on full text
# =====================================================================

class TestSmartToCandidates:
    """Call _smart_to_candidates from engine.py on CITILAB_REAL_PYPDF.

    This is the REAL pipeline entry point (not the _prestrip simulation).
    It calls detect_lab => lab-specific branch => _prestrip_interstitial_noise
    => universal_extract => _filter_noise_candidates.

    Run: pytest parsers/test_citilab_phase6.py -v -s -k smart
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.candidates_raw = _smart_to_candidates(CITILAB_REAL_PYPDF)
        self.cand_lines = [
            ln for ln in self.candidates_raw.splitlines() if ln.strip()
        ]
        self.items = parse_items_from_candidates(self.candidates_raw)
        self.by_name = _build_lookup(self.items)
        self.all_names = sorted(set(it.name for it in self.items))

    # -- Diagnostics (printed with -s) --

    def test_smart_detect_lab(self):
        """Print which lab type is detected."""
        det = detect_lab(CITILAB_REAL_PYPDF)
        print(f"\n=== detect_lab => {det.lab_type.value} "
              f"(conf={det.confidence:.2f}, sigs={det.matched_signatures})")
        # We expect CITILAB or UNKNOWN (both go through universal_extract)
        assert det.lab_type.value in ("citilab", "unknown"), (
            f"Unexpected lab type: {det.lab_type.value}"
        )

    def test_smart_print_all_candidates(self):
        """Print ALL candidates from _smart_to_candidates."""
        print(f"\n=== _smart_to_candidates => {len(self.cand_lines)} candidate lines:")
        for i, ln in enumerate(self.cand_lines, 1):
            print(f"  [{i:3d}] {ln}")
        assert len(self.cand_lines) >= 40, (
            f"Too few candidates: {len(self.cand_lines)}"
        )

    def test_smart_print_all_items(self):
        """Print ALL parsed items from _smart_to_candidates => parse_items."""
        print(f"\n=== parse_items => {len(self.items)} items:")
        for it in self.items:
            ref_str = f"{it.ref.low}-{it.ref.high}" if it.ref else "no ref"
            print(f"  {it.name:30s} = {it.value}  [{ref_str}]  unit={it.unit}  raw={it.raw_name!r}")
        print(f"\n=== Unique names ({len(self.all_names)}): {self.all_names}")

    # -- HBA1C assertions --

    def test_smart_hba1c_in_candidates(self):
        """HBA1c must appear in raw candidates from _smart_to_candidates."""
        hba1c_cands = [ln for ln in self.cand_lines
                       if 'hba1c' in ln.lower() or 'гликозилированный' in ln.lower()]
        print(f"\n=== HBA1c-related candidates: {hba1c_cands}")
        assert hba1c_cands, (
            "HBA1c NOT found in _smart_to_candidates output! "
            "Checking intermediate stages..."
        )

    def test_smart_hba1c_dcct_item(self):
        """HBA1C DCCT/NGSP (~6.12) must appear in parsed items."""
        hba1c = [i for i in self.by_name.get('HBA1C', [])
                 if i.value is not None and abs(i.value - 6.12) < 0.1]
        assert hba1c, (
            f"HBA1C ~6.12 not found via _smart_to_candidates! "
            f"HBA1C items: {[(it.value, it.ref_text) for it in self.by_name.get('HBA1C', [])]}. "
            f"All names: {self.all_names}"
        )

    def test_smart_hba1c_ifcc_item(self):
        """HBA1C IFCC (~43.39) must appear in parsed items."""
        hba1c = [i for i in self.by_name.get('HBA1C', [])
                 if i.value is not None and abs(i.value - 43.39) < 0.1]
        assert hba1c, (
            f"HBA1C ~43.39 not found via _smart_to_candidates! "
            f"HBA1C items: {[(it.value, it.ref_text) for it in self.by_name.get('HBA1C', [])]}. "
            f"All names: {self.all_names}"
        )

    # -- HDL assertions --

    def test_smart_hdl_in_candidates(self):
        """HDL must appear in raw candidates from _smart_to_candidates."""
        hdl_cands = [ln for ln in self.cand_lines
                     if 'hdl' in ln.lower() or 'лпвп' in ln.lower()]
        print(f"\n=== HDL-related candidates: {hdl_cands}")
        assert hdl_cands, (
            "HDL NOT found in _smart_to_candidates output! "
            "Checking intermediate stages..."
        )

    def test_smart_hdl_item(self):
        """HDL (~1.56) must appear in parsed items."""
        hdl_items = self.by_name.get('HDL', [])
        assert hdl_items, (
            f"HDL not found via _smart_to_candidates! All names: {self.all_names}"
        )
        hdl = [i for i in hdl_items if i.value is not None and abs(i.value - 1.56) < 0.05]
        assert hdl, (
            f"HDL ~1.56 not found. HDL items: "
            f"{[(it.value, it.ref_text) for it in hdl_items]}"
        )

    # -- No risk scale leakage --

    def test_smart_no_risk_scale_items(self):
        """Risk scale lines must NOT appear as biomarkers."""
        for item in self.items:
            low_raw = item.raw_name.lower()
            assert 'умеренный риск' not in low_raw, (
                f"Risk scale leaked as biomarker: {item.raw_name} = {item.value}"
            )
            assert 'высокий риск' not in low_raw, (
                f"Risk scale leaked as biomarker: {item.raw_name} = {item.value}"
            )

    # -- Regression checks --

    def test_smart_minimum_48_items(self):
        """Full pipeline should yield >= 48 items."""
        assert len(self.items) >= 48, (
            f"Expected >= 48, got {len(self.items)}. Names: {self.all_names}"
        )

    # -- Intermediate stage diagnostics (only if HBA1C/HDL missing) --

    def test_smart_prestrip_preserves_hba1c(self):
        """Verify _prestrip_interstitial_noise preserves HBA1c lines."""
        cleaned = _prestrip_interstitial_noise(CITILAB_REAL_PYPDF)
        assert 'HBA1c' in cleaned, (
            "HBA1c removed by _prestrip_interstitial_noise! "
            "Dumping removed lines..."
        )
        assert '6.12' in cleaned, (
            "HBA1c value 6.12 removed by _prestrip_interstitial_noise!"
        )

    def test_smart_prestrip_preserves_hdl(self):
        """Verify _prestrip_interstitial_noise preserves HDL lines."""
        cleaned = _prestrip_interstitial_noise(CITILAB_REAL_PYPDF)
        assert 'HDL' in cleaned, (
            "HDL removed by _prestrip_interstitial_noise! "
            "Dumping removed lines..."
        )
        assert '1.567' in cleaned or '1.56' in cleaned, (
            "HDL value removed by _prestrip_interstitial_noise!"
        )

    def test_smart_filter_noise_keeps_hba1c(self):
        """Verify _filter_noise_candidates does NOT remove HBA1c."""
        cleaned = _prestrip_interstitial_noise(CITILAB_REAL_PYPDF)
        raw_cands = universal_extract(cleaned)
        filtered = _filter_noise_candidates(raw_cands)
        hba1c_before = [ln for ln in raw_cands.splitlines()
                        if 'hba1c' in ln.lower() or 'гликозилированный' in ln.lower()]
        hba1c_after = [ln for ln in filtered.splitlines()
                       if 'hba1c' in ln.lower() or 'гликозилированный' in ln.lower()]
        print(f"\n=== HBA1c candidates BEFORE filter: {hba1c_before}")
        print(f"=== HBA1c candidates AFTER filter:  {hba1c_after}")
        assert len(hba1c_after) >= len(hba1c_before), (
            f"_filter_noise_candidates removed HBA1c! "
            f"Before: {hba1c_before}, After: {hba1c_after}"
        )

    def test_smart_filter_noise_keeps_hdl(self):
        """Verify _filter_noise_candidates does NOT remove HDL."""
        cleaned = _prestrip_interstitial_noise(CITILAB_REAL_PYPDF)
        raw_cands = universal_extract(cleaned)
        filtered = _filter_noise_candidates(raw_cands)
        hdl_before = [ln for ln in raw_cands.splitlines()
                      if 'hdl' in ln.lower() or 'лпвп' in ln.lower()]
        hdl_after = [ln for ln in filtered.splitlines()
                     if 'hdl' in ln.lower() or 'лпвп' in ln.lower()]
        print(f"\n=== HDL candidates BEFORE filter: {hdl_before}")
        print(f"=== HDL candidates AFTER filter:  {hdl_after}")
        assert len(hdl_after) >= len(hdl_before), (
            f"_filter_noise_candidates removed HDL! "
            f"Before: {hdl_before}, After: {hdl_after}"
        )


# =====================================================================
# Test 4: Full pipeline trace — candidates to final items
# Traces: _smart_to_candidates => parse_items_from_candidates =>
#          _is_garbage_name => assign_confidence => deduplicate_items =>
#          apply_sanity_filter (same as _run_parse_pipeline / app.py)
# =====================================================================

def _find_items(items, name, value=None, tol=0.1):
    """Helper: find items by name and optional value."""
    found = [i for i in items if i.name == name]
    if value is not None:
        found = [i for i in found if i.value is not None and abs(i.value - value) < tol]
    return found


class TestFullPipelineTrace:
    """Trace HBA1C and HDL through every post-candidate pipeline stage.

    This matches what _run_parse_pipeline / app.py does:
      1. _smart_to_candidates
      2. parse_with_fallback (which internally does parse_items + dedup)
      3. assign_confidence (again)
      4. deduplicate_items (again)
      5. apply_sanity_filter

    Run: pytest parsers/test_citilab_phase6.py -v -s -k trace
    """

    # -- Step 1: candidates --

    def test_trace_step1_candidates(self):
        """Step 1: _smart_to_candidates produces HBA1C and HDL candidates."""
        candidates = _smart_to_candidates(CITILAB_REAL_PYPDF)
        cand_lines = [ln for ln in candidates.splitlines() if ln.strip()]
        hba1c = [ln for ln in cand_lines if 'hba1c' in ln.lower()]
        hdl = [ln for ln in cand_lines if 'hdl' in ln.lower() or 'лпвп' in ln.lower()]
        print(f"\n=== STEP 1: _smart_to_candidates => {len(cand_lines)} lines")
        print(f"  HBA1c candidates: {hba1c}")
        print(f"  HDL candidates:   {hdl}")
        assert hba1c, "HBA1c missing from candidates"
        assert hdl, "HDL missing from candidates"

    # -- Step 2: parse_items_from_candidates --

    def test_trace_step2_parse_items(self):
        """Step 2: parse_items_from_candidates. Check _is_garbage_name."""
        candidates = _smart_to_candidates(CITILAB_REAL_PYPDF)
        items = parse_items_from_candidates(candidates)
        names = sorted(set(it.name for it in items))
        hba1c = _find_items(items, 'HBA1C')
        hdl = _find_items(items, 'HDL')
        print(f"\n=== STEP 2: parse_items_from_candidates => {len(items)} items")
        print(f"  HBA1C items: {[(it.value, it.raw_name) for it in hba1c]}")
        print(f"  HDL items:   {[(it.value, it.raw_name) for it in hdl]}")

        # Also check _is_garbage_name directly on the raw names
        for it in hba1c:
            is_garb = _is_garbage_name(it.raw_name)
            print(f"  _is_garbage_name('{it.raw_name}') => {is_garb}")
            assert not is_garb, f"HBA1C raw_name is garbage: {it.raw_name!r}"
        for it in hdl:
            is_garb = _is_garbage_name(it.raw_name)
            print(f"  _is_garbage_name('{it.raw_name}') => {is_garb}")
            assert not is_garb, f"HDL raw_name is garbage: {it.raw_name!r}"

        assert hba1c, f"HBA1C missing after parse_items! Names: {names}"
        assert hdl, f"HDL missing after parse_items! Names: {names}"

    # -- Step 3: parse_with_fallback (does its own dedup internally) --

    def test_trace_step3_parse_with_fallback(self):
        """Step 3: parse_with_fallback (includes internal dedup)."""
        candidates = _smart_to_candidates(CITILAB_REAL_PYPDF)
        items = parse_with_fallback(candidates)
        names = sorted(set(it.name for it in items))
        hba1c = _find_items(items, 'HBA1C')
        hdl = _find_items(items, 'HDL')
        print(f"\n=== STEP 3: parse_with_fallback => {len(items)} items")
        print(f"  HBA1C items: {[(it.value, it.raw_name) for it in hba1c]}")
        print(f"  HDL items:   {[(it.value, it.raw_name) for it in hdl]}")
        print(f"  All names ({len(names)}): {names}")
        assert hba1c, f"HBA1C missing after parse_with_fallback! Names: {names}"
        assert hdl, f"HDL missing after parse_with_fallback! Names: {names}"

    # -- Step 4: assign_confidence + deduplicate_items (second time) --

    def test_trace_step4_dedup(self):
        """Step 4: assign_confidence + deduplicate_items (as in _run_parse_pipeline)."""
        candidates = _smart_to_candidates(CITILAB_REAL_PYPDF)
        items = parse_with_fallback(candidates)
        assign_confidence(items)
        items_before = list(items)
        items, dropped = deduplicate_items(items)
        hba1c_before = _find_items(items_before, 'HBA1C')
        hba1c_after = _find_items(items, 'HBA1C')
        hdl_before = _find_items(items_before, 'HDL')
        hdl_after = _find_items(items, 'HDL')
        print(f"\n=== STEP 4: deduplicate_items => {len(items)} items (dropped {dropped})")
        print(f"  HBA1C before dedup: {[(it.value, it.confidence) for it in hba1c_before]}")
        print(f"  HBA1C after dedup:  {[(it.value, it.confidence) for it in hba1c_after]}")
        print(f"  HDL before dedup:   {[(it.value, it.confidence) for it in hdl_before]}")
        print(f"  HDL after dedup:    {[(it.value, it.confidence) for it in hdl_after]}")
        assert hba1c_after, (
            f"HBA1C dropped by deduplicate_items! "
            f"Before: {[(it.value, it.raw_name, it.confidence) for it in hba1c_before]}"
        )
        assert hdl_after, (
            f"HDL dropped by deduplicate_items! "
            f"Before: {[(it.value, it.raw_name, it.confidence) for it in hdl_before]}"
        )

    # -- Step 5: apply_sanity_filter --

    def test_trace_step5_sanity_filter(self):
        """Step 5: apply_sanity_filter."""
        candidates = _smart_to_candidates(CITILAB_REAL_PYPDF)
        items = parse_with_fallback(candidates)
        assign_confidence(items)
        items, _ = deduplicate_items(items)
        items_before = list(items)
        items, outlier_count = apply_sanity_filter(items)
        hba1c_before = _find_items(items_before, 'HBA1C')
        hba1c_after = _find_items(items, 'HBA1C')
        hdl_before = _find_items(items_before, 'HDL')
        hdl_after = _find_items(items, 'HDL')
        print(f"\n=== STEP 5: apply_sanity_filter => {len(items)} items (outliers: {outlier_count})")
        print(f"  HBA1C before sanity: {[(it.value, it.name) for it in hba1c_before]}")
        print(f"  HBA1C after sanity:  {[(it.value, it.name) for it in hba1c_after]}")
        print(f"  HDL before sanity:   {[(it.value, it.name) for it in hdl_before]}")
        print(f"  HDL after sanity:    {[(it.value, it.name) for it in hdl_after]}")

        # Check sanity ranges for HBA1C values
        from parsers.sanity_ranges import is_sanity_outlier, SANITY_RANGES
        print(f"  SANITY_RANGES['HBA1C'] = {SANITY_RANGES.get('HBA1C')}")
        print(f"  SANITY_RANGES['HDL'] = {SANITY_RANGES.get('HDL')}")
        for it in hba1c_before:
            is_out = is_sanity_outlier('HBA1C', it.value) if it.value else False
            print(f"  is_sanity_outlier('HBA1C', {it.value}) => {is_out}")
        for it in hdl_before:
            is_out = is_sanity_outlier('HDL', it.value) if it.value else False
            print(f"  is_sanity_outlier('HDL', {it.value}) => {is_out}")

        assert hba1c_after, (
            f"HBA1C dropped by sanity filter! "
            f"Before: {[(it.value, it.name) for it in hba1c_before]}, "
            f"Range: {SANITY_RANGES.get('HBA1C')}"
        )
        assert hdl_after, (
            f"HDL dropped by sanity filter! "
            f"Before: {[(it.value, it.name) for it in hdl_before]}, "
            f"Range: {SANITY_RANGES.get('HDL')}"
        )

    # -- Step 6: Full _run_parse_pipeline --

    def test_trace_step6_run_parse_pipeline(self):
        """Step 6: _run_parse_pipeline (the REAL engine entry point)."""
        result = _run_parse_pipeline(CITILAB_REAL_PYPDF)
        items, quality, dedup_dropped, outlier_count = result
        assert items is not None, "Pipeline returned None items!"
        names = sorted(set(it.name for it in items))
        hba1c = _find_items(items, 'HBA1C')
        hdl = _find_items(items, 'HDL')
        print(f"\n=== STEP 6: _run_parse_pipeline => {len(items)} items "
              f"(dedup_dropped={dedup_dropped}, outliers={outlier_count})")
        print(f"  HBA1C items: {[(it.value, it.raw_name, it.ref_text) for it in hba1c]}")
        print(f"  HDL items:   {[(it.value, it.raw_name, it.ref_text) for it in hdl]}")
        print(f"  All names ({len(names)}): {names}")
        assert hba1c, f"HBA1C missing from _run_parse_pipeline! Names: {names}"
        assert hdl, f"HDL missing from _run_parse_pipeline! Names: {names}"

    # -- Summary: which step loses HBA1C/HDL --

    def test_trace_summary(self):
        """Summary: trace through all steps, report where items are lost."""
        candidates = _smart_to_candidates(CITILAB_REAL_PYPDF)

        # Step 2
        items_raw = parse_items_from_candidates(candidates)
        hba1c_raw = _find_items(items_raw, 'HBA1C')
        hdl_raw = _find_items(items_raw, 'HDL')

        # Step 3
        items_fallback = parse_with_fallback(candidates)
        hba1c_fb = _find_items(items_fallback, 'HBA1C')
        hdl_fb = _find_items(items_fallback, 'HDL')

        # Step 4
        assign_confidence(items_fallback)
        items_dedup, _ = deduplicate_items(items_fallback)
        hba1c_dedup = _find_items(items_dedup, 'HBA1C')
        hdl_dedup = _find_items(items_dedup, 'HDL')

        # Step 5
        items_sane, _ = apply_sanity_filter(items_dedup)
        hba1c_sane = _find_items(items_sane, 'HBA1C')
        hdl_sane = _find_items(items_sane, 'HDL')

        print("\n=== PIPELINE TRACE SUMMARY ===")
        print(f"  Step 2 (parse_items):      HBA1C={len(hba1c_raw)} vals={[i.value for i in hba1c_raw]:},  HDL={len(hdl_raw)} vals={[i.value for i in hdl_raw]}")
        print(f"  Step 3 (parse_w_fallback): HBA1C={len(hba1c_fb)} vals={[i.value for i in hba1c_fb]},  HDL={len(hdl_fb)} vals={[i.value for i in hdl_fb]}")
        print(f"  Step 4 (dedup):            HBA1C={len(hba1c_dedup)} vals={[i.value for i in hba1c_dedup]},  HDL={len(hdl_dedup)} vals={[i.value for i in hdl_dedup]}")
        print(f"  Step 5 (sanity):           HBA1C={len(hba1c_sane)} vals={[i.value for i in hba1c_sane]},  HDL={len(hdl_sane)} vals={[i.value for i in hdl_sane]}")

        # Find where they disappear
        lost_at = []
        if hba1c_raw and not hba1c_fb:
            lost_at.append("HBA1C lost at Step 3 (parse_with_fallback)")
        if hba1c_fb and not hba1c_dedup:
            lost_at.append("HBA1C lost at Step 4 (deduplicate_items)")
        if hba1c_dedup and not hba1c_sane:
            lost_at.append("HBA1C lost at Step 5 (apply_sanity_filter)")
        if hdl_raw and not hdl_fb:
            lost_at.append("HDL lost at Step 3 (parse_with_fallback)")
        if hdl_fb and not hdl_dedup:
            lost_at.append("HDL lost at Step 4 (deduplicate_items)")
        if hdl_dedup and not hdl_sane:
            lost_at.append("HDL lost at Step 5 (apply_sanity_filter)")

        if lost_at:
            print(f"\n  !!! LOSSES DETECTED: {lost_at}")
        else:
            print(f"\n  OK: HBA1C and HDL survive all pipeline stages")


# =====================================================================
# Test 5: Targeted fix tests
# =====================================================================

class TestHba1cDedupPrefersDCCT:
    """Fix 1: deduplicate_items should prefer DCCT/NGSP (%) over IFCC."""

    def test_dedup_keeps_dcct_over_ifcc(self):
        """When both DCCT and IFCC exist, dedup keeps DCCT (6.12%)."""
        result = _run_parse_pipeline(CITILAB_REAL_PYPDF)
        items = result[0]
        hba1c = _find_items(items, 'HBA1C')
        assert len(hba1c) == 1, f"Expected exactly 1 HBA1C, got {len(hba1c)}"
        assert hba1c[0].value == pytest.approx(6.12, abs=0.01), (
            f"Expected DCCT 6.12%, got {hba1c[0].value}"
        )
        assert 'DCCT' in hba1c[0].raw_name or 'NGSP' in hba1c[0].raw_name, (
            f"Expected DCCT/NGSP variant, got raw_name={hba1c[0].raw_name!r}"
        )

    def test_dedup_dcct_has_ref(self):
        """DCCT variant should have ref 4.80-5.90."""
        result = _run_parse_pipeline(CITILAB_REAL_PYPDF)
        items = result[0]
        hba1c = _find_items(items, 'HBA1C')[0]
        assert hba1c.ref is not None
        assert hba1c.ref.low == pytest.approx(4.80, abs=0.01)
        assert hba1c.ref.high == pytest.approx(5.90, abs=0.01)

    def test_dedup_hba1c_status_high(self):
        """HBA1C 6.12% with ref 4.80-5.90 => status VYSSE."""
        result = _run_parse_pipeline(CITILAB_REAL_PYPDF)
        items = result[0]
        hba1c = _find_items(items, 'HBA1C')[0]
        assert hba1c.status == "ВЫШЕ", (
            f"Expected status 'ВЫШЕ' for HBA1C 6.12 > 5.90, got '{hba1c.status}'"
        )

    def test_dedup_unit_test_dcct_vs_ifcc(self):
        """Unit test: deduplicate_items with two HBA1C items directly."""
        from engine import Item, Range
        dcct = Item(
            raw_name="Гликозилированный гемоглобин (HBA1c, DCCT/NGSP)",
            name="HBA1C", value=6.12, unit="%",
            ref_text="4.80-5.90", ref=Range(4.80, 5.90),
            ref_source="lab", status="ВЫШЕ", confidence=0.8,
        )
        ifcc = Item(
            raw_name="Гликозилированный гемоглобин (HBA1c, IFCC)",
            name="HBA1C", value=43.39, unit="ммоль/моль",
            ref_text="29.00-42.00", ref=Range(29.0, 42.0),
            ref_source="lab", status="ВЫШЕ", confidence=0.8,
        )
        result, dropped = deduplicate_items([dcct, ifcc])
        assert len(result) == 1
        assert dropped == 1
        assert result[0].value == pytest.approx(6.12, abs=0.01)
        assert 'DCCT' in result[0].raw_name


class TestHdlFallbackRef:
    """Fix 2: HDL with 'см. интерпретацию' gets fallback ref low=1.45."""

    def test_hdl_has_ref_after_pipeline(self):
        """HDL should have a ref after _run_parse_pipeline."""
        result = _run_parse_pipeline(CITILAB_REAL_PYPDF)
        items = result[0]
        hdl = _find_items(items, 'HDL')
        assert hdl, "HDL missing from pipeline!"
        assert hdl[0].ref is not None, (
            f"HDL ref is None! ref_text={hdl[0].ref_text!r}"
        )
        assert hdl[0].ref.low == pytest.approx(1.45, abs=0.01)

    def test_hdl_value_156(self):
        """HDL value should be ~1.56."""
        result = _run_parse_pipeline(CITILAB_REAL_PYPDF)
        items = result[0]
        hdl = _find_items(items, 'HDL', value=1.56, tol=0.05)
        assert hdl, "HDL ~1.56 not found!"

    def test_hdl_status_normal(self):
        """HDL 1.56 > 1.45 => status 'В НОРМЕ'."""
        result = _run_parse_pipeline(CITILAB_REAL_PYPDF)
        items = result[0]
        hdl = _find_items(items, 'HDL')[0]
        assert hdl.status == "В НОРМЕ", (
            f"Expected 'В НОРМЕ' for HDL 1.56 > 1.45, got '{hdl.status}'"
        )

    def test_hdl_ref_source_fallback(self):
        """HDL ref_source should be 'интерпретация лаборатории'."""
        result = _run_parse_pipeline(CITILAB_REAL_PYPDF)
        items = result[0]
        hdl = _find_items(items, 'HDL')[0]
        assert hdl.ref_source == "интерпретация лаборатории"

    def test_fallback_ref_does_not_override_existing(self):
        """_apply_fallback_refs must NOT override existing lab refs."""
        from engine import _apply_fallback_refs, Item, Range
        item = Item(
            raw_name="HDL test", name="HDL", value=0.8, unit="ммоль/л",
            ref_text="0.90-1.50", ref=Range(0.90, 1.50),
            ref_source="lab", status="НИЖЕ", confidence=0.8,
        )
        _apply_fallback_refs([item])
        # Should not change
        assert item.ref.low == pytest.approx(0.90, abs=0.01)
        assert item.ref.high == pytest.approx(1.50, abs=0.01)
        assert item.status == "НИЖЕ"
        assert item.ref_source == "lab"


class TestNonHdlCholNotHDL:
    """Non-HDL cholesterol must not normalize to HDL."""

    def test_non_hdl_chol_canonical_name(self):
        """'Холестерин не-ЛПВП' should normalize to NON_HDL_CHOL."""
        from engine import normalize_name
        assert normalize_name("Холестерин не-ЛПВП") == "NON_HDL_CHOL"

    def test_non_hdl_chol_in_pipeline(self):
        """NON_HDL_CHOL should be a separate item in the pipeline."""
        result = _run_parse_pipeline(CITILAB_REAL_PYPDF)
        items = result[0]
        non_hdl = [i for i in items if i.name == 'NON_HDL_CHOL']
        assert non_hdl, "NON_HDL_CHOL not found in pipeline!"
        assert non_hdl[0].value == pytest.approx(1.89, abs=0.01)


class TestSuspiciousSlashInParens:
    """Slashes inside parenthesized codes must not trigger suspicious."""

    def test_dcct_ngsp_not_suspicious(self):
        """'(HBA1c, DCCT/NGSP)' should NOT be suspicious."""
        from parsers.quality import _is_suspicious_item
        from engine import Item, Range
        item = Item(
            raw_name="Гликозилированный гемоглобин (HBA1c, DCCT/NGSP)",
            name="HBA1C", value=6.12, unit="%",
            ref_text="4.80-5.90", ref=Range(4.80, 5.90),
            ref_source="lab", status="ВЫШЕ", confidence=0.8,
        )
        assert not _is_suspicious_item(item), (
            "DCCT/NGSP in parens should NOT be suspicious!"
        )

    def test_bare_slash_is_suspicious(self):
        """Bare slash outside parens should still be suspicious."""
        from parsers.quality import _is_suspicious_item
        from engine import Item
        item = Item(
            raw_name="мл/л Глюкоза", name="GLUC", value=5.0,
            unit="", ref_text="3.3-5.5", ref=None,
            ref_source="", status="", confidence=0.5,
        )
        assert _is_suspicious_item(item), (
            "Bare slash outside parens should be suspicious!"
        )
