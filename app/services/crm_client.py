import asyncio
import logging
from collections.abc import Awaitable, Callable

import httpx
from pydantic import ValidationError

from app.config import settings
from app.models.lead import CrmErrorResponse, CrmSuccessResponse, Lead

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503}

OnRetryCallback = Callable[[int], Awaitable[None]]


class CrmRetryableError(Exception):
    """Временная проблема CRM/сети — повтор имеет смысл."""


class CrmNonRetryableError(Exception):
    """CRM отклонила заявку по существу — повтор с теми же данными бессмыслен."""


class CrmDeliveryFailed(Exception):
    """Все retryable-попытки исчерпаны — финальный сбой отправки."""


def _describe_error(response: httpx.Response) -> str:
    try:
        parsed = CrmErrorResponse.model_validate(response.json())
    except (ValueError, ValidationError):
        logger.warning("CRM вернула неожиданный формат ответа: %r", response.text)
        return response.text or f"HTTP {response.status_code}"
    return f"{parsed.error.code}: {parsed.error.message}"


async def send_lead(
    lead: Lead,
    *,
    client: httpx.AsyncClient,
    on_retry: OnRetryCallback | None = None,
) -> CrmSuccessResponse:
    """Отправляет заявку в Mock-CRM с ретраями по правилам API_CONTRACT.md (раздел 5).

    Один и тот же `lead.request_id` используется во всех попытках (заголовок
    Idempotency-Key) — это ключ идемпотентности на случай, если "потерянный" запрос
    всё же будет обработан CRM после того, как бот уже посчитал его неудачным.
    """
    payload = lead.model_dump(mode="json")
    headers = {"Idempotency-Key": str(lead.request_id)}
    last_error: Exception | None = None

    for attempt in range(1, settings.retry_attempts + 1):
        try:
            response = await client.post(
                str(settings.crm_endpoint_url), json=payload, headers=headers
            )
        except httpx.HTTPError as exc:
            last_error = exc
            logger.warning("CRM сетевая ошибка (попытка %s): %s", attempt, exc)
        else:
            if response.status_code in (200, 201):
                try:
                    payload_json = response.json()
                except ValueError as exc:
                    last_error = exc
                    logger.warning(
                        "CRM вернула не-JSON тело на успешном статусе (попытка %s): %r",
                        attempt,
                        response.text,
                    )
                else:
                    try:
                        return CrmSuccessResponse.model_validate(payload_json)
                    except ValidationError as exc:
                        # Валидный JSON, но не по контракту (например, Beeceptor вернул
                        # шаблон {{...}} буквально) — это детерминированная проблема
                        # конфигурации CRM, не временный сбой. Повтор даст тот же
                        # результат, поэтому не ретраим (API_CONTRACT.md, раздел 5).
                        logger.error(
                            "CRM подтвердила приём (%s), но тело не соответствует "
                            "контракту: %r — %s",
                            response.status_code,
                            response.text,
                            exc,
                        )
                        raise CrmNonRetryableError(
                            "CRM ответила успехом, но тело не соответствует контракту"
                        ) from exc
            elif response.status_code in RETRYABLE_STATUS_CODES:
                last_error = CrmRetryableError(_describe_error(response))
                logger.warning(
                    "CRM временно недоступна (попытка %s/%s): %s",
                    attempt,
                    settings.retry_attempts,
                    last_error,
                )
            else:
                reason = _describe_error(response)
                logger.error(
                    "CRM отклонила заявку без возможности повтора (%s): %s",
                    response.status_code,
                    reason,
                )
                raise CrmNonRetryableError(reason)

        if attempt < settings.retry_attempts:
            if on_retry is not None:
                await on_retry(attempt)
            await asyncio.sleep(settings.retry_delay_seconds)

    raise CrmDeliveryFailed(
        f"Не удалось отправить заявку после {settings.retry_attempts} попыток"
    ) from last_error
