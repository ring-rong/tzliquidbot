from uuid import uuid4

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.keyboards.confirm_kb import confirm_keyboard
from app.keyboards.time_kb import TIME_CALLBACK_PREFIX, time_keyboard
from app.models.lead import PreferredTime
from app.states.lead_form import LeadForm
from app.texts import messages
from app.validators.name import NameValidationError, validate_name
from app.validators.phone import PhoneValidationError, validate_phone

router = Router(name="survey")


@router.message(LeadForm.name)
async def process_name(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer(messages.NAME_NOT_TEXT)
        return

    try:
        name = validate_name(message.text)
    except NameValidationError as exc:
        await message.answer(str(exc))
        return

    await state.update_data(name=name)
    await state.set_state(LeadForm.phone)
    await message.answer(messages.ASK_PHONE)


@router.message(LeadForm.phone)
async def process_phone(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer(messages.PHONE_NOT_TEXT)
        return

    try:
        phone = validate_phone(message.text)
    except PhoneValidationError as exc:
        await message.answer(str(exc))
        return

    await state.update_data(phone=phone)
    await state.set_state(LeadForm.time)
    await message.answer(messages.ASK_TIME, reply_markup=time_keyboard())


@router.message(LeadForm.time)
async def process_time_text_input(message: Message) -> None:
    await message.answer(messages.TIME_USE_BUTTONS)


@router.callback_query(LeadForm.time, F.data.startswith(TIME_CALLBACK_PREFIX))
async def process_time_choice(callback: CallbackQuery, state: FSMContext) -> None:
    raw_value = callback.data.removeprefix(TIME_CALLBACK_PREFIX)
    preferred_time = PreferredTime(raw_value)

    await state.update_data(preferred_time=preferred_time.value, request_id=str(uuid4()))
    await state.set_state(LeadForm.confirm)

    data = await state.get_data()
    await callback.message.edit_text(
        messages.summary_card(data["name"], data["phone"], preferred_time),
        reply_markup=confirm_keyboard(),
    )
    await callback.answer()
