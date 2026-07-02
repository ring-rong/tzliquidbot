from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.config import settings
from app.models.lead import CrmSuccessResponse, Lead, PreferredTime
from app.services.crm_client import (
    CrmDeliveryFailed,
    CrmNonRetryableError,
    send_lead,
)

CRM_URL = str(settings.crm_endpoint_url)


def make_lead() -> Lead:
    return Lead(
        name="Иван Петров",
        phone="+79123456789",
        preferred_time=PreferredTime.MORNING,
        submitted_at=datetime.now(UTC),
    )


def success_response(request_id: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "status": "ok",
            "lead_id": "lead_3f9a7c21",
            "request_id": request_id,
            "received_at": "2026-07-02T18:45:05+03:00",
        },
    )


def error_response(status_code: int, code: str, message: str) -> httpx.Response:
    return httpx.Response(
        status_code,
        json={"status": "error", "error": {"code": code, "message": message}},
    )


def unsubstituted_template_response() -> httpx.Response:
    """200 с валидным JSON, но не по контракту — как реальный ответ Beeceptor,
    когда шаблонизация выключена в правиле: request_id/received_at приходят
    буквальной строкой `{{...}}` вместо UUID/datetime."""
    return httpx.Response(
        200,
        json={
            "status": "ok",
            "lead_id": "lead_demo",
            "request_id": "{{request.body.request_id}}",
            "received_at": "{{now}}",
        },
    )


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    monkeypatch.setattr(settings, "retry_delay_seconds", 0.0)


@respx.mock
async def test_success_on_first_attempt():
    lead = make_lead()
    route = respx.post(CRM_URL).mock(side_effect=[success_response(str(lead.request_id))])

    async with httpx.AsyncClient() as client:
        result = await send_lead(lead, client=client)

    assert isinstance(result, CrmSuccessResponse)
    assert result.status == "ok"
    assert route.call_count == 1


@respx.mock
async def test_retries_on_500_then_succeeds():
    lead = make_lead()
    retry_calls: list[int] = []

    async def on_retry(attempt: int) -> None:
        retry_calls.append(attempt)

    route = respx.post(CRM_URL).mock(
        side_effect=[
            error_response(500, "internal_error", "CRM service temporarily unavailable"),
            error_response(500, "internal_error", "CRM service temporarily unavailable"),
            success_response(str(lead.request_id)),
        ]
    )

    async with httpx.AsyncClient() as client:
        result = await send_lead(lead, client=client, on_retry=on_retry)

    assert isinstance(result, CrmSuccessResponse)
    assert route.call_count == 3
    assert retry_calls == [1, 2]


@respx.mock
async def test_429_three_times_raises_critical_failure():
    lead = make_lead()
    retry_calls: list[int] = []

    async def on_retry(attempt: int) -> None:
        retry_calls.append(attempt)

    route = respx.post(CRM_URL).mock(
        side_effect=[
            error_response(429, "rate_limited", "Too many requests, please retry later"),
            error_response(429, "rate_limited", "Too many requests, please retry later"),
            error_response(429, "rate_limited", "Too many requests, please retry later"),
        ]
    )

    async with httpx.AsyncClient() as client:
        with pytest.raises(CrmDeliveryFailed):
            await send_lead(lead, client=client, on_retry=on_retry)

    assert route.call_count == 3
    assert retry_calls == [1, 2]


@respx.mock
async def test_network_error_is_retried_like_500():
    lead = make_lead()

    route = respx.post(CRM_URL).mock(
        side_effect=[
            httpx.ConnectTimeout("connection timed out"),
            success_response(str(lead.request_id)),
        ]
    )

    async with httpx.AsyncClient() as client:
        result = await send_lead(lead, client=client)

    assert isinstance(result, CrmSuccessResponse)
    assert route.call_count == 2


@respx.mock
async def test_non_retryable_status_fails_immediately_without_retry():
    lead = make_lead()

    route = respx.post(CRM_URL).mock(
        side_effect=[error_response(422, "validation_error", "Invalid payload")]
    )

    async with httpx.AsyncClient() as client:
        with pytest.raises(CrmNonRetryableError):
            await send_lead(lead, client=client)

    assert route.call_count == 1


@respx.mock
async def test_200_with_contract_violating_body_fails_immediately_without_retry():
    lead = make_lead()
    retry_calls: list[int] = []

    async def on_retry(attempt: int) -> None:
        retry_calls.append(attempt)

    route = respx.post(CRM_URL).mock(side_effect=[unsubstituted_template_response()])

    async with httpx.AsyncClient() as client:
        with pytest.raises(CrmNonRetryableError):
            await send_lead(lead, client=client, on_retry=on_retry)

    assert route.call_count == 1
    assert retry_calls == []
