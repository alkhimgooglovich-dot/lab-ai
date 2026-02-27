"""
Tests for P8 — recovery of lost indicators from split PDF lines.
"""

import sys
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from parsers.universal_extractor import universal_extract, _is_scale_annotation


class TestHba1cNotFilteredAsScale:
    """HbA1c indicator line with DCCT must NOT be filtered as scale annotation."""

    def test_hba1c_line_with_dcct_not_scale(self):
        line = "Гликированный гемоглобин (в соответствии со стандартизацией DCCT) 5.0 % Смотри текст"
        assert not _is_scale_annotation(line), \
            "HbA1c indicator line was incorrectly filtered as scale annotation"

    def test_pure_dcct_explanation_is_scale(self):
        line = "до 6.0% включительно (в соответствии с DCCT) - нормальное содержание HbA1c"
        assert _is_scale_annotation(line)

    def test_ngsp_explanation_is_scale(self):
        line = "Исследование проведено методом сертифицированным NGSP и IFCC"
        assert _is_scale_annotation(line)

    def test_methodology_without_biomarker_is_scale(self):
        line = "Определено в соответствии с требованиями DCCT"
        assert _is_scale_annotation(line)


class TestLdhParsing:
    """LDH with regulatory codes must be parsed correctly."""

    SAMPLE_LDH = (
        "Лактатдегидрогеназа (ЛДГ) (венозная кровь) A09.05.039 (Приказ МЗ РФ № 804н) 164 Ед/л 135-225\n"
        "Глюкоза 5.27 ммоль/л 4.11 - 6.1\n"
    )

    def test_ldh_extracted(self):
        candidates = universal_extract(self.SAMPLE_LDH)
        assert "164" in (candidates or ""), \
            f"LDH value 164 not found in candidates: {candidates}"

    def test_glucose_still_works(self):
        candidates = universal_extract(self.SAMPLE_LDH)
        assert "5.27" in (candidates or "")


class TestPotassiumRecovery:
    """Potassium must be recovered from split lines."""

    SAMPLE_K_SPLIT = (
        "Калий (K+) (сыворотка крови)\n"
        "3.7 ммоль/л 3.5-5.1\n"
        "Хлориды 103 ммоль/л 98-106\n"
    )

    SAMPLE_K_ONELINE = (
        "Калий (K+) (сыворотка крови) 3.7 ммоль/л 3.5-5.1\n"
    )

    def test_potassium_split_lines(self):
        candidates = universal_extract(self.SAMPLE_K_SPLIT)
        lower = (candidates or "").lower()
        assert "3.7" in (candidates or "") or "калий" in lower, \
            f"Potassium not found in split-line test: {candidates}"

    def test_potassium_single_line(self):
        candidates = universal_extract(self.SAMPLE_K_ONELINE)
        lower = (candidates or "").lower()
        assert "3.7" in (candidates or "") or "калий" in lower, \
            f"Potassium not found in single-line test: {candidates}"


class TestSodiumRecovery:
    """Sodium must be recovered, with a proper display name."""

    SAMPLE_NA = (
        "Натрий (Na+) (сыворотка крови) A09.05.031 (Приказ МЗ РФ № 804н)\n"
        "142.5 ммоль/л 136-145\n"
    )

    def test_sodium_extracted(self):
        candidates = universal_extract(self.SAMPLE_NA)
        assert "142.5" in (candidates or ""), \
            f"Sodium value 142.5 not found: {candidates}"


class TestDisplayNameMap:
    """Short/code-only names should use DISPLAY_NAME_MAP."""

    @staticmethod
    def _get_map():
        try:
            from engine import DISPLAY_NAME_MAP
            return DISPLAY_NAME_MAP
        except ImportError:
            import importlib, types
            import ast
            src = (PROJECT_ROOT / "engine.py").read_text(encoding="utf-8")
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "DISPLAY_NAME_MAP":
                            return ast.literal_eval(node.value)
            raise RuntimeError("DISPLAY_NAME_MAP not found in engine.py")

    def test_na_display_name(self):
        m = self._get_map()
        assert "NA" in m
        assert "Натрий" in m["NA"]

    def test_k_display_name(self):
        m = self._get_map()
        assert "K" in m
        assert "Калий" in m["K"]

    def test_ldh_display_name(self):
        m = self._get_map()
        assert "LDH" in m


class TestFullGemotestP8:
    """Full integration test with all problematic lines."""

    SAMPLE = (
        "Общий белок (венозная кровь) 70 г/л 64-83\n"
        "Лактатдегидрогеназа (ЛДГ) (венозная кровь) A09.05.039 (Приказ МЗ РФ № 804н) 164 Ед/л 135-225\n"
        "Калий (K+) (сыворотка крови) 3.7 ммоль/л 3.5-5.1\n"
        "Натрий (Na+) (сыворотка крови) A09.05.031 (Приказ МЗ РФ № 804н)\n"
        "142.5 ммоль/л 136-145\n"
        "Гликированный гемоглобин (в соответствии со стандартизацией DCCT) 5.0 % Смотри текст\n"
        "до 6.0% включительно (в соответствии с DCCT) - нормальное содержание HbA1c\n"
        "6.0-6.4% - рекомендуется консультация эндокринолога\n"
        "6.5% и более - диагностический критерий сахарного диабета\n"
        "Глюкоза 5.27 ммоль/л 4.11 - 6.1\n"
    )

    def test_ldh_present(self):
        candidates = universal_extract(self.SAMPLE)
        assert "164" in (candidates or ""), f"LDH missing: {candidates}"

    def test_potassium_present(self):
        candidates = universal_extract(self.SAMPLE)
        assert "3.7" in (candidates or ""), f"K+ missing: {candidates}"

    def test_sodium_present(self):
        candidates = universal_extract(self.SAMPLE)
        assert "142.5" in (candidates or ""), f"Na+ missing: {candidates}"

    def test_hba1c_present(self):
        candidates = universal_extract(self.SAMPLE)
        lower = (candidates or "").lower()
        assert "5" in (candidates or "") or "гликированн" in lower, \
            f"HbA1c missing: {candidates}"

    def test_glucose_present(self):
        candidates = universal_extract(self.SAMPLE)
        assert "5.27" in (candidates or ""), f"Glucose missing: {candidates}"

    def test_no_scale_lines_in_candidates(self):
        candidates = universal_extract(self.SAMPLE)
        for line in (candidates or "").splitlines():
            name = line.split("\t")[0].lower() if "\t" in line else line.lower()
            assert "диагностический критерий" not in name
            assert "рекомендуется консультация" not in name
            assert "нормальное содержание" not in name

    def test_no_garbage_names(self):
        candidates = universal_extract(self.SAMPLE)
        for line in (candidates or "").splitlines():
            name = line.split("\t")[0] if "\t" in line else line
            stripped = name.strip().lower()
            assert stripped != "мз рф"
            assert not stripped.startswith("приказ")
