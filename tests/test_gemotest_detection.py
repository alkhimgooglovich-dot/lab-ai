"""
Тесты: детекция Гемотест + защита от ложного определения как МЕДСИ.

Запуск: pytest tests/test_gemotest_detection.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.lab_detector import detect_lab, LabType
from parsers.medsi_extractor import is_medsi_format


# ═══════════════════════════════════════════════
# Golden text: pypdf-извлечение из реального PDF Гемотест
# ═══════════════════════════════════════════════
GEMOTEST_PYPDF_TEXT = """\
ОБЩЕКЛИНИЧЕСКИЕ ИССЛЕДОВАНИЯ КРОВИ
Общий анализ крови с лейкоцитарной формулой и СОЭ, микроскопия мазка при патологических изменениях в
лейкоцитарной формуле (венозная кровь)
B03.016.003
(Приказ МЗ РФ
№
804н)
Дата исследования: 17.02.2026;
Гемоглобин
144
г/л
132 - 172
Эритроциты
4.85
x10*12/
л
4.28 - 5.78
Гематокрит
42.30
%
39.51 - 50.95
Средний объем эритроцитов
(MCV)
87.3
фл
82 - 98
Среднее содержание
Hb
в эритроците (МСН)
29.70
пг
27.93 - 33.24
Средняя концентрация
Hb
в эритроцитах (МСНС)
340
г/л
319 - 356
Цветовой показатель
0.89
-
0.85 - 1.00
Тромбоциты
191
x10*9/
л
148 - 339
Лейкоциты
4.07
x10*9/
л
3.9 - 10.9
Незрелые гранулоциты
0.02
10*9/л
0 - 0.09
Незрелые гранулоциты %
0.5
%
Нейтрофилы сегментоядерные
1.99
x10*9/
л
1.5 - 6.8
Нейтрофилы сегментоядерные %
48.80
%
37.95 - 71.44
Эозинофилы
0.18
x10*9/
л
0 - 0.4
Эозинофилы %
4.3
%
0.3 - 5.4
Базофилы
0.01
x10*9/
л
0.01 - 0.05
Базофилы %
0.3
%
0 - 1
Моноциты
0.28-
x10*9/
л
0.3 - 1.1
Моноциты %
6.8
%
4.8 - 13.8
Лимфоциты
1.59
x10*9/
л
1.1 - 3.4
Лимфоциты %
39.3
%
24 - 48.4
СОЭ (по Вестергрену)
5
мм/час
0 - 20
БИОХИМИЧЕСКИЕ ИССЛЕДОВАНИЯ КРОВИ
С-реактивный белок (СРБ)
A09.05.009
(Приказ МЗ РФ
№
804н)
1.05
мг/л
< 5
Дата исследования: 18.02.2026;
Результат лабораторных исследований не является единственным параметром для постановки диагноза.
Лабораторный комплекс правообладателя
ООО "ЛАБОРАТОРИЯ ГЕМОТЕСТ"
Л041-01162-50/00369631 от 08.12.2020
ГОСТ Р ИСО 9001-2015 с учетом требований ГОСТ Р ИСО 15189-2015
Сертификат соответствия ГОСТ ISO 13485-2017
Сертификат соответствия ГОСТ 33044-2014
8 800 550 13 13, https://gemotest.ru
"""

# Текст без Гемотест-маркеров, но с 10*9 и 10*12 (generic OAK)
GENERIC_OAK_TEXT = """\
Лаборатория "Здоровье"
Общий анализ крови
Лейкоциты 5.2 10*9/л 4.0-9.0
Эритроциты 4.8 10*12/л 4.0-5.5
Гемоглобин 145 г/л 120-160
"""


# ═══════════════════════════════════════════════
# Тест 1: Гемотест определяется как GEMOTEST
# ═══════════════════════════════════════════════
class TestGemotestDetection:

    def test_gemotest_detected(self):
        """Текст Гемотеста определяется как GEMOTEST."""
        result = detect_lab(GEMOTEST_PYPDF_TEXT)
        assert result.lab_type == LabType.GEMOTEST, (
            f"Expected GEMOTEST, got {result.lab_type.value} "
            f"(conf={result.confidence:.2f}, sigs={result.matched_signatures})"
        )

    def test_gemotest_confidence(self):
        """Confidence для Гемотеста >= 0.5."""
        result = detect_lab(GEMOTEST_PYPDF_TEXT)
        assert result.confidence >= 0.5

    def test_gemotest_not_medsi(self):
        """Гемотест НЕ определяется как МЕДСИ."""
        result = detect_lab(GEMOTEST_PYPDF_TEXT)
        assert result.lab_type != LabType.MEDSI

    def test_gemotest_matched_sigs(self):
        """Найдены сигнатуры Гемотеста."""
        result = detect_lab(GEMOTEST_PYPDF_TEXT)
        assert len(result.matched_signatures) > 0


# ═══════════════════════════════════════════════
# Тест 2: is_medsi_format не срабатывает ложно
# ═══════════════════════════════════════════════
class TestMedsiFormatFalsePositive:

    def test_gemotest_not_medsi_format(self):
        """is_medsi_format НЕ срабатывает на тексте Гемотеста."""
        assert is_medsi_format(GEMOTEST_PYPDF_TEXT) is False

    def test_generic_oak_not_medsi(self):
        """Обычный ОАК без МЕДСИ-маркеров не определяется как МЕДСИ."""
        assert is_medsi_format(GENERIC_OAK_TEXT) is False

    def test_real_medsi_still_works(self):
        """Реальный текст МЕДСИ по-прежнему определяется."""
        medsi_text = (
            "(WBC) Лейкоциты 10*9/л 4.50-11.004.78\n"
            "(RBC) Эритроциты 10*12/л 4.30-5.705.33\n"
            "(HGB) Гемоглобин г/л 130-170155\n"
            "(HCT) Гематокрит % 39-49↑42\n"
            "(PLT) Тромбоциты 10*9/л 150-400213\n"
        )
        assert is_medsi_format(medsi_text) is True

    def test_medsi_with_units_and_codes(self):
        """МЕДСИ с 10*9, 10*12 И >= 2 строк (CODE) — ещё определяется."""
        text = "Анализ крови\n10*9/л\n10*12/л\n(WBC) тест\n(RBC) тест"
        assert is_medsi_format(text) is True


# ═══════════════════════════════════════════════
# Тест 3: Регрессия — существующие тесты не ломаются
# ═══════════════════════════════════════════════
class TestRegression:

    def test_helix_still_helix(self):
        text = "helix.ru\nИсследование\tРезультат\nWBC\t5.0"
        result = detect_lab(text)
        assert result.lab_type == LabType.HELIX

    def test_medsi_by_domain_still_works(self):
        text = "Результаты анализов\nmedsi.ru\n(WBC) Лейкоциты 10*9/л 4.50-11.004.78"
        result = detect_lab(text)
        assert result.lab_type == LabType.MEDSI

    def test_unknown_stays_unknown(self):
        text = "Привет, мир! Это обычный текст без анализов."
        result = detect_lab(text)
        assert result.lab_type == LabType.UNKNOWN

    def test_invitro_still_invitro(self):
        text = "ООО «ИНВИТРО»\ninvitro.ru\nГемоглобин 145 г/л 120-160"
        result = detect_lab(text)
        assert result.lab_type == LabType.INVITRO

