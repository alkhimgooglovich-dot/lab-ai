"""
Тесты Этапа 5.3: data-driven Lab Detector.

Покрывает:
- Детекция HELIX/MEDSI/INVITRO через конфигурацию
- UNKNOWN при недостаточном score
- Конфликт сигнатур (приоритет через score)
- Регрессия существующих кейсов

Запуск: pytest tests/test_lab_detector_datadriven.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.lab_detector import detect_lab, detect_lab_format, LabType, LabDetectionResult


# ══════════════════════════════════════
# 1. Детекция каждой лаборатории
# ══════════════════════════════════════

class TestMedsiDetection:
    def test_medsi_by_name(self):
        text = "Клиника МЕДСИ\nWBC 5.0 10^9/л 4.0-9.0"
        result = detect_lab(text)
        assert result.lab_type == LabType.MEDSI

    def test_medsi_by_domain(self):
        text = "medsi.ru\nГемоглобин 140 г/л 120-160"
        result = detect_lab(text)
        assert result.lab_type == LabType.MEDSI

    def test_medsi_confidence_above_threshold(self):
        text = "МЕДСИ анализы\nWBC 5.0"
        result = detect_lab(text)
        assert result.confidence >= 0.3


class TestHelixDetection:
    def test_helix_by_domain(self):
        text = "helix.ru\nWBC 5.0 10^9/л 4.0-9.0"
        result = detect_lab(text)
        assert result.lab_type == LabType.HELIX

    def test_helix_by_name(self):
        text = "Лаборатория Хеликс\nWBC 5.0"
        result = detect_lab(text)
        assert result.lab_type == LabType.HELIX

    def test_helix_by_header(self):
        text = "Исследование\tРезультат\nWBC\t5.0\n"
        result = detect_lab(text)
        assert result.lab_type == LabType.HELIX


class TestInvitroDetection:
    def test_invitro_by_domain(self):
        text = "Результаты анализов\ninvitro.ru\nWBC 5.0 10^9/л 4.0-9.0"
        result = detect_lab(text)
        assert result.lab_type == LabType.INVITRO

    def test_invitro_by_www_domain(self):
        text = "www.invitro.ru\nГемоглобин 140 г/л 120-160"
        result = detect_lab(text)
        assert result.lab_type == LabType.INVITRO

    def test_invitro_by_russian_name(self):
        text = 'ООО «ИНВИТРО»\nАнализ крови\nWBC 6.1'
        result = detect_lab(text)
        assert result.lab_type == LabType.INVITRO

    def test_invitro_by_full_name(self):
        text = "Независимая лаборатория ИНВИТРО\nRBC 4.5"
        result = detect_lab(text)
        assert result.lab_type == LabType.INVITRO

    def test_invitro_case_insensitive(self):
        text = "InViTrO результаты\nHGB 130 г/л"
        result = detect_lab(text)
        assert result.lab_type == LabType.INVITRO

    def test_invitro_confidence_above_threshold(self):
        text = "invitro.ru\nWBC 5.0"
        result = detect_lab(text)
        assert result.confidence >= 0.3


# ══════════════════════════════════════
# 2. UNKNOWN при недостаточном score
# ══════════════════════════════════════

class TestUnknownDetection:
    def test_generic_text_unknown(self):
        text = "Гемоглобин 145 г/л 120-160\nЛейкоциты 5.2 10^9/л 4.0-9.0"
        result = detect_lab(text)
        assert result.lab_type == LabType.UNKNOWN

    def test_empty_text_unknown(self):
        result = detect_lab("")
        assert result.lab_type == LabType.UNKNOWN

    def test_whitespace_only_unknown(self):
        result = detect_lab("   \n  \t  ")
        assert result.lab_type == LabType.UNKNOWN

    def test_random_text_unknown(self):
        text = "Привет, это просто текст без лабораторных данных."
        result = detect_lab(text)
        assert result.lab_type == LabType.UNKNOWN


# ══════════════════════════════════════
# 3. Конфликт сигнатур — приоритет через score
# ══════════════════════════════════════

class TestConflictResolution:
    def test_helix_wins_over_invitro(self):
        """Если есть helix.ru + invitro.ru → побеждает тот, у кого больше score."""
        text = "helix.ru\nЛаборатория Хеликс\ninvitro.ru\nWBC 5.0"
        result = detect_lab(text)
        # Helix имеет 2 сигнатуры (domain + name), Invitro — 1 (domain)
        assert result.lab_type == LabType.HELIX

    def test_invitro_wins_when_more_signals(self):
        """Invitro побеждает, если у него больше совпавших сигнатур."""
        text = "invitro.ru\nООО «ИНВИТРО»\nНезависимая лаборатория ИНВИТРО\nhelix\nWBC 5.0"
        result = detect_lab(text)
        # Invitro: 3+ сигнатуры (domain + name + full_name), Helix: 1 (name)
        assert result.lab_type == LabType.INVITRO

    def test_medsi_wins_over_helix_when_stronger(self):
        """МЕДСИ побеждает Helix при более сильных сигнатурах."""
        text = "medsi.ru\nКлиника МЕДСИ\nhelix\nWBC 5.0"
        result = detect_lab(text)
        assert result.lab_type == LabType.MEDSI

    def test_mixed_weak_signals_unknown(self):
        """Слабые сигналы разных лабораторий → UNKNOWN, если ни один не прошёл threshold."""
        # Этот текст НЕ содержит прямых сигнатур
        text = "Лаборатория №42\nWBC 5.0 10^9/л 4.0-9.0"
        result = detect_lab(text)
        assert result.lab_type == LabType.UNKNOWN


# ══════════════════════════════════════
# 4. Регрессия: обратная совместимость
# ══════════════════════════════════════

class TestLegacyCompatibility:
    def test_detect_lab_format_medsi(self):
        text = "МЕДСИ анализы\nmedsi.ru\nWBC 5.0"
        assert detect_lab_format(text) == "medsi"

    def test_detect_lab_format_helix(self):
        text = "helix.ru\nЛаборатория Хеликс\nWBC 5.0"
        assert detect_lab_format(text) == "helix"

    def test_detect_lab_format_invitro_returns_generic(self):
        """INVITRO → 'generic' (нет отдельного парсера)."""
        text = "invitro.ru\nWBC 5.0"
        assert detect_lab_format(text) == "generic"

    def test_detect_lab_format_unknown_returns_generic(self):
        text = "Обычный текст анализа"
        assert detect_lab_format(text) == "generic"

    def test_detect_lab_format_empty(self):
        assert detect_lab_format("") == "generic"


# ══════════════════════════════════════
# 5. LabType enum и dataclass
# ══════════════════════════════════════

class TestLabTypeEnum:
    def test_invitro_in_enum(self):
        assert hasattr(LabType, "INVITRO")
        assert LabType.INVITRO.value == "invitro"

    def test_all_lab_types(self):
        expected = {"medsi", "helix", "invitro", "unknown"}
        actual = {lt.value for lt in LabType}
        assert expected == actual

    def test_detect_result_dataclass(self):
        from parsers.lab_detector import DetectResult
        r = DetectResult(LabType.INVITRO, confidence=0.9, matched_signatures=["invitro.ru"])
        assert r.lab_type == LabType.INVITRO
        assert r.confidence == 0.9


# ══════════════════════════════════════
# 6. Data-driven расширяемость
# ══════════════════════════════════════

class TestDataDrivenExtensibility:
    def test_signatures_config_is_list(self):
        from parsers.lab_signatures import LAB_SIGNATURES
        assert isinstance(LAB_SIGNATURES, list)
        assert len(LAB_SIGNATURES) >= 3  # MEDSI, HELIX, INVITRO

    def test_each_config_has_required_fields(self):
        from parsers.lab_signatures import LAB_SIGNATURES
        for config in LAB_SIGNATURES:
            assert "lab_type" in config
            assert "threshold" in config
            assert "signatures" in config
            assert isinstance(config["signatures"], list)

    def test_each_signature_has_weight(self):
        from parsers.lab_signatures import LAB_SIGNATURES
        for config in LAB_SIGNATURES:
            for sig in config["signatures"]:
                assert "weight" in sig
                assert "pattern" in sig
                assert "kind" in sig


