"""
Тесты: финальные проверки Гемотест — мусор, рекомендация, имена, CRP.

Запуск: pytest tests/test_gemotest_final.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestNoiseSubstringFilter:
    """Мусорные кандидаты отсеиваются по содержимому."""

    def test_gemotest_lab_name(self):
        from engine import _filter_noise_candidates
        candidates = 'Гемоглобин\t144\t132-172\tг/л\nООО "ЛАБОРАТОРИЯ ГЕМОТЕСТ"\t9001\t9001-2015\t-2015'
        result = _filter_noise_candidates(candidates)
        assert "ГЕМОТЕСТ" not in result
        assert "Гемоглобин" in result

    def test_gemotest_standalone_name(self):
        """Имя 'ГЕМОТЕСТ"' (без 'ЛАБОРАТОРИЯ') тоже фильтруется."""
        from engine import _filter_noise_candidates
        candidates = 'ГЕМОТЕСТ"\t9001\t9001-2015\t-2015'
        result = _filter_noise_candidates(candidates)
        assert result.strip() == ""

    def test_gost_with_prefix(self):
        from engine import _filter_noise_candidates
        candidates = 'ГОСТ Р ИСО\t9001\t9001-2015\t-2015'
        result = _filter_noise_candidates(candidates)
        assert result.strip() == ""

    def test_gost_inside_name(self):
        from engine import _filter_noise_candidates
        candidates = 'с учетом требований ГОСТ Р ИСО\t15189\t15189-2015\t-2015'
        result = _filter_noise_candidates(candidates)
        assert result.strip() == ""

    def test_real_biomarker_not_filtered(self):
        from engine import _filter_noise_candidates
        candidates = 'Гемоглобин\t144\t132-172\tг/л\nЭритроциты\t4.85\t4.28-5.78\tx10^12/л'
        result = _filter_noise_candidates(candidates)
        lines = [l for l in result.splitlines() if l.strip()]
        assert len(lines) == 2

    def test_sertifikat_filtered(self):
        from engine import _filter_noise_candidates
        candidates = 'Сертификат соответствия ГОСТ\t33044\t33044-2014\t-2014'
        result = _filter_noise_candidates(candidates)
        assert result.strip() == ""


class TestQualityNoteForPdf:
    """Рекомендация 'загрузить PDF' не показывается для PDF."""

    def test_no_recommendation_for_pdf(self):
        from parsers.report_helpers import build_user_quality_note
        quality = {
            "metrics": {
                "reasons": ["LOW_BIOMARKER_RATIO"],
            }
        }
        note = build_user_quality_note(quality, source_type="pdf")
        assert "PDF" not in note
        assert "фото" not in note

    def test_recommendation_for_image(self):
        from parsers.report_helpers import build_user_quality_note
        quality = {
            "metrics": {
                "reasons": ["LOW_BIOMARKER_RATIO"],
            }
        }
        note = build_user_quality_note(quality, source_type="image")
        assert "PDF" in note or "фото" in note

    def test_no_recommendation_when_no_reasons(self):
        from parsers.report_helpers import build_user_quality_note
        quality = {"metrics": {"reasons": []}}
        note = build_user_quality_note(quality, source_type="image")
        assert note == ""


class TestMchDisplayName:
    """MCH и MCHC имеют понятные отображаемые имена."""

    def test_mch_normalize(self):
        from engine import normalize_name, clean_raw_name
        assert normalize_name(clean_raw_name("в эритроците (МСН)")) == "MCH"

    def test_mchc_normalize(self):
        from engine import normalize_name, clean_raw_name
        assert normalize_name(clean_raw_name("в эритроцитах (МСНС)")) == "MCHC"

    def test_mch_not_rbc(self):
        from engine import normalize_name, clean_raw_name
        result = normalize_name(clean_raw_name("в эритроците (МСН)"))
        assert result != "RBC"


class TestPrestripInterstitialNoise:
    """_prestrip_interstitial_noise убирает мусор между именем и значением."""

    def test_medical_codes_removed(self):
        from engine import _prestrip_interstitial_noise
        text = "С-реактивный белок (СРБ)\nA09.05.009\n(Приказ МЗ РФ\n№\n804н)\n1.05\nмг/л\n< 5"
        result = _prestrip_interstitial_noise(text)
        lines = [l for l in result.splitlines() if l.strip()]
        # A09.05.009, (Приказ МЗ РФ, 804н) должны быть убраны
        assert not any("A09" in l for l in lines)
        assert not any("Приказ" in l for l in lines)
        assert not any("804н)" in l for l in lines)
        # Имя, значение, единица, реф — сохранены
        assert any("С-реактивный" in l for l in lines)
        assert any("1.05" in l for l in lines)
        assert any("мг/л" in l for l in lines)
        assert any("< 5" in l for l in lines)

    def test_values_preserved(self):
        """Строки-значения (начинаются с цифры) не удаляются."""
        from engine import _prestrip_interstitial_noise
        text = "Гемоглобин\n144\nг/л\n132 - 172"
        result = _prestrip_interstitial_noise(text)
        assert "144" in result
        assert "132 - 172" in result

    def test_units_preserved(self):
        """Единицы (л, %, мм/час и т.п.) не удаляются."""
        from engine import _prestrip_interstitial_noise
        text = "x10*9/\nл\n3.9 - 10.9"
        result = _prestrip_interstitial_noise(text)
        assert "л" in result

    def test_section_headers_removed(self):
        """Заголовки секций (БИОХИМИЧЕСКИЕ ИССЛЕДОВАНИЯ и т.п.) удаляются."""
        from engine import _prestrip_interstitial_noise
        text = "БИОХИМИЧЕСКИЕ ИССЛЕДОВАНИЯ КРОВИ\nС-реактивный белок (СРБ)"
        result = _prestrip_interstitial_noise(text)
        assert "БИОХИМИЧЕСКИЕ" not in result
        assert "С-реактивный" in result


class TestCrpExtraction:
    """CRP извлекается из Гемотест-текста после предочистки."""

    def test_crp_found_in_gemotest(self):
        from tests.test_gemotest_detection import GEMOTEST_PYPDF_TEXT
        from parsers.universal_extractor import universal_extract
        from engine import _prestrip_interstitial_noise, parse_items_from_candidates, _filter_noise_candidates

        cleaned = _prestrip_interstitial_noise(GEMOTEST_PYPDF_TEXT)
        candidates = universal_extract(cleaned)
        candidates = _filter_noise_candidates(candidates)
        items = parse_items_from_candidates(candidates)

        names = {it.name for it in items}
        assert "CRP" in names, f"CRP not found, got: {names}"

    def test_crp_value_correct(self):
        from tests.test_gemotest_detection import GEMOTEST_PYPDF_TEXT
        from parsers.universal_extractor import universal_extract
        from engine import _prestrip_interstitial_noise, parse_items_from_candidates, _filter_noise_candidates

        cleaned = _prestrip_interstitial_noise(GEMOTEST_PYPDF_TEXT)
        candidates = universal_extract(cleaned)
        candidates = _filter_noise_candidates(candidates)
        items = parse_items_from_candidates(candidates)

        crp = next((it for it in items if it.name == "CRP"), None)
        assert crp is not None
        assert crp.value == 1.05
        assert crp.status == "В НОРМЕ"

    def test_all_22_items(self):
        """Из Гемотест-текста извлекается >= 22 показателей."""
        from tests.test_gemotest_detection import GEMOTEST_PYPDF_TEXT
        from parsers.universal_extractor import universal_extract
        from engine import _prestrip_interstitial_noise, parse_items_from_candidates, _filter_noise_candidates

        cleaned = _prestrip_interstitial_noise(GEMOTEST_PYPDF_TEXT)
        candidates = universal_extract(cleaned)
        candidates = _filter_noise_candidates(candidates)
        items = parse_items_from_candidates(candidates)

        assert len(items) >= 22, f"Expected >= 22, got {len(items)}"

    def test_monocytes_below_normal(self):
        """Моноциты: 0.28 < 0.3 → статус НИЖЕ."""
        from tests.test_gemotest_detection import GEMOTEST_PYPDF_TEXT
        from parsers.universal_extractor import universal_extract
        from engine import _prestrip_interstitial_noise, parse_items_from_candidates, _filter_noise_candidates

        cleaned = _prestrip_interstitial_noise(GEMOTEST_PYPDF_TEXT)
        candidates = universal_extract(cleaned)
        candidates = _filter_noise_candidates(candidates)
        items = parse_items_from_candidates(candidates)

        mo = next((it for it in items if it.name == "MO"), None)
        assert mo is not None, "Моноциты не найдены"
        assert mo.value == 0.28
        assert mo.status == "НИЖЕ", f"Expected НИЖЕ, got {mo.status}"
