"""
Tests for P7 bugfix — HbA phantom, missing K/Na/LDH.
"""

import sys, re
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from parsers.universal_extractor import universal_extract, _is_scale_annotation, _looks_like_name_line
from engine import _is_garbage_name


class TestHbaPhantomFiltered:
    """HbA phantom (value=1, ref=6.0-6.4) must not appear."""

    def test_hba_alone_is_garbage(self):
        assert _is_garbage_name("HbA")

    def test_hba_with_space_is_garbage(self):
        assert _is_garbage_name("HbA ")

    def test_hba1c_is_NOT_garbage(self):
        """Full HbA1c name must NOT be filtered."""
        assert not _is_garbage_name("Гликированный гемоглобин")

    def test_hba1c_code_is_NOT_garbage(self):
        assert not _is_garbage_name("HbA1c")

    def test_percentage_range_is_scale(self):
        assert _is_scale_annotation("6.0-6.4% - рекомендуется консультация эндокринолога")

    def test_percentage_and_more_is_scale(self):
        assert _is_scale_annotation("6.5% и более - диагностический критерий")

    def test_do_percent_is_scale(self):
        assert _is_scale_annotation("до 6.0% включительно (в соответствии с DCCT)")


class TestPotassiumSodiumPreserved:
    """K+, Na+ must not be filtered as garbage."""

    def test_k_plus_not_garbage(self):
        assert not _is_garbage_name("Калий (K+)")

    def test_na_plus_not_garbage(self):
        assert not _is_garbage_name("Натрий (Na+)")

    def test_parenthesis_k_not_garbage(self):
        assert not _is_garbage_name("(K+)")

    def test_parenthesis_na_not_garbage(self):
        assert not _is_garbage_name("(Na+)")

    def test_serum_alone_IS_garbage(self):
        """Pure biomaterial must still be garbage."""
        assert _is_garbage_name("(сыворотка крови)")

    def test_venous_blood_alone_IS_garbage(self):
        assert _is_garbage_name("(венозная кровь)")

    def test_kaliy_with_serum_is_valid_name(self):
        assert _looks_like_name_line("Калий (K+) (сыворотка крови)")

    def test_natriy_is_valid_name(self):
        assert _looks_like_name_line("Натрий (Na+) (сыворотка крови)")

    def test_serum_alone_not_name(self):
        assert not _looks_like_name_line("(сыворотка крови)")


class TestLdhPreserved:
    """LDH must not be filtered — sanitized name is valid."""

    def test_ldh_sanitized_not_garbage(self):
        assert not _is_garbage_name("Лактатдегидрогеназа (ЛДГ)")

    def test_ldh_full_original_not_garbage_after_sanitize(self):
        """Even if original has МЗ РФ, after sanitize it should be clean."""
        from engine import sanitize_raw_name
        original = "Лактатдегидрогеназа (ЛДГ) (венозная кровь) A09.05.039 (Приказ МЗ РФ № 804н)"
        sanitized = sanitize_raw_name(original)
        assert not _is_garbage_name(sanitized), f"Sanitized name incorrectly flagged as garbage: '{sanitized}'"
        assert "Лактатдегидрогеназа" in sanitized

    def test_mz_rf_alone_IS_garbage(self):
        """Pure 'МЗ РФ' must still be garbage."""
        assert _is_garbage_name("МЗ РФ")


class TestIntegrationP7:
    """Integration: full Gemotest sample after P7."""

    SAMPLE = """\
Общий белок (венозная кровь) 70 г/л 64-83
Калий (K+) (сыворотка крови) 3.7 ммоль/л 3.5-5.1
Натрий (Na+) (сыворотка крови) 140 ммоль/л 136-145
Лактатдегидрогеназа (ЛДГ) (венозная кровь) A09.05.039 (Приказ МЗ РФ № 804н) 164 Ед/л 135-225
Глюкоза 5.27 ммоль/л 4.11 - 6.1
до 6.0% включительно (в соответствии с DCCT) - нормальное содержание HbA1c
6.0-6.4% - рекомендуется консультация эндокринолога
6.5% и более - диагностический критерий сахарного диабета
"""

    def test_potassium_in_candidates(self):
        candidates = universal_extract(self.SAMPLE)
        lower = (candidates or "").lower()
        assert "калий" in lower or "3.7" in (candidates or ""), \
            f"Potassium missing from candidates: {candidates}"

    def test_sodium_in_candidates(self):
        candidates = universal_extract(self.SAMPLE)
        lower = (candidates or "").lower()
        assert "натрий" in lower or "140" in (candidates or ""), \
            f"Sodium missing from candidates: {candidates}"

    def test_glucose_in_candidates(self):
        candidates = universal_extract(self.SAMPLE)
        lower = (candidates or "").lower()
        assert "глюкоз" in lower or "5.27" in (candidates or "")

    def test_no_hba_phantom(self):
        candidates = universal_extract(self.SAMPLE)
        for line in (candidates or "").splitlines():
            parts = line.split("\t")
            name = parts[0].lower() if parts else ""
            # "hba" alone (without "1c") should not be a candidate
            if re.match(r'^hba?\s*$', name):
                assert False, f"HbA phantom found in candidates: {line}"

    def test_no_scale_lines(self):
        candidates = universal_extract(self.SAMPLE)
        for line in (candidates or "").splitlines():
            name = line.split("\t")[0].lower() if "\t" in line else line.lower()
            assert "диагностический критерий" not in name
            assert "рекомендуется консультация" not in name
            assert "нормальное содержание" not in name


