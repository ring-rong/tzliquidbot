import logging
from datetime import UTC, datetime

import httpx
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from app.keyboards.confirm_kb import CONFIRM_RESTART, CONFIRM_RETRY, CONFIRM_SEND, retry_keyboard
from app.models.lead import Lead, PreferredTime
from app.services.crm_client import CrmDeliveryFailed, CrmNonRetryableError, send_lead
from app.states.lead_form import LeadForm
from app.texts import messages

router = Router(name="confirm")
logger = logging.getLogger(__name__)


async def _submit_lead(
    callback: CallbackQuery, state: FSMContext, http_client: httpx.AsyncClient
) -> None:
    data = await state.get_data()
    lead = Lead(
        request_id=data["request_id"],
        name=data["name"],
        phone=data["phone"],
        preferred_time=PreferredTime(data["preferred_time"]),
        submitted_at=datetime.now(UTC),
    )

    await callback.message.edit_text(messages.SENDING, reply_markup=None)

    async def on_retry(attempt: int) -> None:
        await callback.message.answer(messages.retry_message(attempt))

    try:
        await send_lead(lead, client=http_client, on_retry=on_retry)
    except (CrmDeliveryFailed, CrmNonRetryableError) as exc:
        logger.error("Отправка заявки %s не удалась: %s", lead.request_id, exc)
        await callback.message.answer(messages.CRITICAL_FAILURE, reply_markup=retry_keyboard())
        return

    await state.clear()
    await callback.message.answer(messages.success_text(data["name"]))


@router.callback_query(LeadForm.confirm, F.data.in_({CONFIRM_SEND, CONFIRM_RETRY}))
async def handle_send(
    callback: CallbackQuery, state: FSMContext, http_client: httpx.AsyncClient
) -> None:
    await callback.answer()
    await _submit_lead(callback, state, http_client)


@router.callback_query(LeadForm.confirm, F.data == CONFIRM_RESTART)
async def handle_restart(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(LeadForm.name)
    await callback.message.edit_text(messages.RESTART, reply_markup=None)
