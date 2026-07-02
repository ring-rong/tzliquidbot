from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.models.lead import PreferredTime

TIME_CALLBACK_PREFIX = "time:"

_TIME_LABELS: dict[PreferredTime, str] = {
    PreferredTime.MORNING: "Утро",
    PreferredTime.AFTERNOON: "День",
    PreferredTime.EVENING: "Вечер",
}


def time_label(value: PreferredTime) -> str:
    return _TIME_LABELS[value]


def time_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=label, callback_data=f"{TIME_CALLBACK_PREFIX}{value.value}"
                )
                for value, label in _TIME_LABELS.items()
            ]
        ]
    )
