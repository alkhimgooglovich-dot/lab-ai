"""
Тесты: фильтрация мусорных строк из бланков Гемотест и других лабораторий.

Запуск: pytest tests/test_gemotest_noise_filter.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.line_scorer import is_noise, is_header_service_line, score_line


class TestGostNoise:
    """Строки ГОСТ и сертификатов должны фильтроваться как шум."""

    def test_gost_iso_9001(self):
        assert is_noise("ГОСТ Р ИСО 9001-2015 с учетом требований ГОСТ Р ИСО 15189-2015")

    def test_gost_13485(self):
        assert is_noise("Сертификат соответствия ГОСТ ISO 13485-2017")

    def test_gost_33044(self):
        assert is_noise("Сертификат соответствия ГОСТ 33044-2014")

    def test_gost_simple(self):
        assert is_noise("ГОСТ 12345-2020")


class TestMedicalCodes:
    """Коды услуг по приказу МЗ должны фильтроваться."""

    def test_b03_code(self):
        assert is_noise("B03.016.003")

    def test_a09_code(self):
        assert is_noise("A09.05.009")

    def test_prikaz_bracket(self):
        assert is_noise("(Приказ МЗ РФ")

    def test_prikaz_number(self):
        """804н) — номер приказа в конце строки."""
        assert is_noise("804н)")


class TestLicenseNoise:
    """Лицензии лабораторий — мусор."""

    def test_license_l041(self):
        assert is_noise("Л041-01162-50/00369631 от 08.12.2020")

    def test_license_lo(self):
        assert is_noise("ЛО-50-01-009438 от 01.01.2020")


class TestGemotestHeaders:
    """Заголовки и служебные строки Гемотеста."""

    def test_obsheklinich(self):
        assert is_noise("ОБЩЕКЛИНИЧЕСКИЕ ИССЛЕДОВАНИЯ КРОВИ")

    def test_biokhim(self):
        assert is_noise("БИОХИМИЧЕСКИЕ ИССЛЕДОВАНИЯ КРОВИ")

    def test_lab_complex(self):
        assert is_noise("Лабораторный комплекс правообладателя")

    def test_result_disclaimer(self):
        assert is_noise("Результат лабораторных исследований не является единственным параметром для постановки диагноза.")

    def test_pol_pacienta(self):
        assert is_noise("Пол пациента")

    def test_familiya(self):
        assert is_noise("Фамилия пациента")

    def test_imya(self):
        assert is_noise("Имя пациента")

    def test_zavlab(self):
        assert is_noise("Заведующий лабораторией")

    def test_issledovanie_header(self):
        assert is_noise("Исследование")

    def test_znachenie_header(self):
        assert is_noise("Значение")

    def test_diagnoz(self):
        assert is_noise("Диагноз")

    def test_data_issledovaniya(self):
        assert is_noise("Дата исследования: 17.02.2026;")


class TestRealBiomarkersNotFiltered:
    """Реальные показатели НЕ должны фильтроваться."""

    def test_hemoglobin(self):
        assert not is_noise("Гемоглобин")

    def test_leukocytes(self):
        assert not is_noise("Лейкоциты")

    def test_soe(self):
        assert not is_noise("СОЭ (по Вестергрену)")

    def test_crb(self):
        assert not is_noise("С-реактивный белок (СРБ)")

    def test_neutrophils(self):
        assert not is_noise("Нейтрофилы сегментоядерные %")

    def test_erythrocytes(self):
        assert not is_noise("Эритроциты")

    def test_hematocrit(self):
        assert not is_noise("Гематокрит")

    def test_mcv(self):
        assert not is_noise("Средний объем эритроцитов")

    def test_value_144(self):
        """Числовые строки-значения — шум (OK, т.к. multi_line_pass обрабатывает их отдельно)."""
        # 144 это is_noise=True (чисто цифры), но multi_line_pass обрабатывает числа по-своему
        assert is_noise("144")

    def test_value_4_85(self):
        """Дробные числа — не шум."""
        assert not is_noise("4.85")

    def test_score_gost_is_zero(self):
        """ГОСТ-строки должны иметь score=0 (шум)."""
        assert score_line("ГОСТ Р ИСО 9001-2015") == 0.0

    def test_score_hemoglobin_gt_zero(self):
        """Реальный показатель должен иметь score > 0."""
        assert score_line("Гемоглобин") > 0.0





