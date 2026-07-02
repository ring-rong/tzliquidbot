import re

# Валидные примеры: "+7 (912) 345-67-89", "+79123456789", "8 912 345-67-89", "89123456789"
# Невалидные примеры: "123", "+7 912 345-67", "8-912-345-67-8Х", "abc"
PHONE_PATTERN = re.compile(r"^(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$")


class PhoneValidationError(Exception):
    """Телефон не прошёл валидацию. Текст сообщения уже подходит для показа пользователю."""


def validate_phone(raw: str) -> str:
    candidate = raw.strip()
    digits = re.sub(r"\D", "", candidate)

    if not PHONE_PATTERN.match(candidate):
        if len(digits) < 10:
            raise PhoneValidationError(
                "Похоже, в номере не хватает цифр. Пришлите, пожалуйста, номер "
                "в формате +7 (XXX) XXX-XX-XX или 8XXXXXXXXXX."
            )
        raise PhoneValidationError(
            "Не получается распознать номер. Пришлите, пожалуйста, в формате "
            "+7 (XXX) XXX-XX-XX, +7XXXXXXXXXX или 8 XXX XXX-XX-XX."
        )

    return f"+7{digits[-10:]}"
