import pytest

from app.validators.name import NAME_MAX_LENGTH, NAME_MIN_LENGTH, NameValidationError, validate_name
from app.validators.phone import PhoneValidationError, validate_phone


class TestValidateName:
    def test_strips_surrounding_whitespace(self):
        assert validate_name("  Иван  ") == "Иван"

    def test_minimum_length_accepted(self):
        assert validate_name("Ян") == "Ян"

    def test_maximum_length_accepted(self):
        name = "И" * NAME_MAX_LENGTH
        assert validate_name(name) == name

    def test_below_minimum_length_rejected(self):
        with pytest.raises(NameValidationError):
            validate_name("И")

    def test_above_maximum_length_rejected(self):
        with pytest.raises(NameValidationError):
            validate_name("И" * (NAME_MAX_LENGTH + 1))

    def test_whitespace_only_rejected(self):
        with pytest.raises(NameValidationError):
            validate_name("   ")

    def test_empty_string_rejected(self):
        with pytest.raises(NameValidationError):
            validate_name("")

    def test_length_checked_after_stripping_whitespace(self):
        padded = " " * 10 + "Ян" + " " * 10
        assert validate_name(padded) == "Ян"

    def test_hyphenated_double_name_accepted(self):
        assert validate_name("Анна-Мария") == "Анна-Мария"

    def test_apostrophe_in_name_accepted(self):
        assert validate_name("O'Коннор") == "O'Коннор"

    def test_min_length_constant_matches_spec(self):
        assert NAME_MIN_LENGTH == 2

    def test_max_length_constant_matches_spec(self):
        assert NAME_MAX_LENGTH == 50


class TestValidatePhone:
    @pytest.mark.parametrize(
        "raw",
        [
            "+7 (912) 345-67-89",
            "+79123456789",
            "8 912 345-67-89",
            "89123456789",
            "8(912)345-67-89",
            "+7-912-345-67-89",
        ],
    )
    def test_valid_variations_normalize_to_e164_like_format(self, raw):
        assert validate_phone(raw) == "+79123456789"

    def test_strips_surrounding_whitespace(self):
        assert validate_phone("  +79123456789  ") == "+79123456789"

    def test_too_few_digits_rejected(self):
        with pytest.raises(PhoneValidationError):
            validate_phone("+7 912 345-67")

    def test_too_many_digits_rejected(self):
        with pytest.raises(PhoneValidationError):
            validate_phone("+7 912 345-67-890")

    def test_letters_rejected(self):
        with pytest.raises(PhoneValidationError):
            validate_phone("+7 9ab 345-67-89")

    def test_wrong_country_prefix_rejected(self):
        with pytest.raises(PhoneValidationError):
            validate_phone("+1 912 345-67-89")

    def test_empty_string_rejected(self):
        with pytest.raises(PhoneValidationError):
            validate_phone("")

    def test_random_text_rejected(self):
        with pytest.raises(PhoneValidationError):
            validate_phone("позвоните мне")
