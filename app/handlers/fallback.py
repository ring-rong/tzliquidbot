from aiogram import Router
from aiogram.types import CallbackQuery, Message

from app.texts import messages

router = Router(name="fallback")


@router.message()
async def handle_unexpected_message(message: Message) -> None:
    """Ловит сообщения вне активного шага анкеты — до этого хендлера они молча
    отбрасывались диспетчером (ни одного роутера/фильтра не подходило), из-за чего
    чат выглядел зависшим и требовал повторного /start."""
    await message.answer(messages.UNKNOWN_INPUT)


@router.callback_query()
async def handle_stale_callback(callback: CallbackQuery) -> None:
    """Клик по кнопке из карточки, чьё FSM-состояние уже не активно (например,
    состояние потерялось при перезапуске контейнера до перехода на Redis)."""
    await callback.answer()
    if callback.message is not None:
        await callback.message.answer(messages.STALE_BUTTON)
