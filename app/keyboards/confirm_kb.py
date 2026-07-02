from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CONFIRM_SEND = "confirm:send"
CONFIRM_RESTART = "confirm:restart"
CONFIRM_RETRY = "confirm:retry"


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отправить заявку", callback_data=CONFIRM_SEND)],
            [InlineKeyboardButton(text="Заполнить заново", callback_data=CONFIRM_RESTART)],
        ]
    )


def retry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Попробовать снова", callback_data=CONFIRM_RETRY)],
            [InlineKeyboardButton(text="Заполнить заново", callback_data=CONFIRM_RESTART)],
        ]
    )
