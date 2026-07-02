NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 50


class NameValidationError(Exception):
    """Имя не прошло валидацию. Текст сообщения уже подходит для показа пользователю."""


def validate_name(raw: str) -> str:
    name = raw.strip()

    if len(name) < NAME_MIN_LENGTH:
        raise NameValidationError(
            f"Имя слишком короткое — введите, пожалуйста, не менее {NAME_MIN_LENGTH} символов."
        )
    if len(name) > NAME_MAX_LENGTH:
        raise NameValidationError(
            f"Имя слишком длинное — уложитесь, пожалуйста, в {NAME_MAX_LENGTH} символов."
        )

    return name
