# API-контракт: Bot → Mock-CRM (Beeceptor)

`POST /v1/leads` — единственный эндпоинт, который использует бот. Ниже — request/response
схема и готовые конфиги правил для Beeceptor, которые дают именно то поведение, что
требует ТЗ: латентность 1.5–2 сек и часть запросов, падающих с 500/429.

---

## 1. Request payload (бот → Mock-API)

```http
POST /v1/leads HTTP/1.1
Host: <name>.free.beeceptor.com
Content-Type: application/json
Idempotency-Key: b7e6a1b0-6f2e-4a3f-9c1e-8e6a2d9f2a41
```

```json
{
  "request_id": "b7e6a1b0-6f2e-4a3f-9c1e-8e6a2d9f2a41",
  "name": "Иван Петров",
  "phone": "+79123456789",
  "preferred_time": "morning",
  "source": "telegram_bot",
  "submitted_at": "2026-07-02T18:45:03+03:00"
}
```

| Поле              | Тип    | Обязательное | Описание |
|-------------------|--------|:---:|----------|
| `request_id`      | string (UUID4) | да | Генерируется ботом **один раз на карточку заявки**, не на попытку. Один и тот же `request_id` во всех 3 ретраях одной отправки — это ключ идемпотентности: если реальная CRM всё же обработает "потерянный" запрос после таймаута, она увидит дубль и не создаст вторую заявку. Mock-сервис его просто эхом вернёт, но паттерн правильный. |
| `name`             | string | да | 2–50 символов, как в ТЗ, уже провалидировано ботом до отправки. |
| `phone`            | string | да | Нормализованный вид `+7XXXXXXXXXX` (E.164-подобный) — нормализация происходит на стороне бота в `validators/phone.py`, в CRM уходит уже чистое значение, а не то, что ввёл пользователь дословно. |
| `preferred_time`   | enum   | да | `"morning" \| "afternoon" \| "evening"` — внутренний код, не текст кнопки. Маппинг Утро→morning/День→afternoon/Вечер→evening делается в `keyboards/time_kb.py` или `models/lead.py`, а не хардкодится в хендлере. |
| `source`           | string | да | Константа `"telegram_bot"` — задел на случай, если у CRM когда-то появятся другие источники лидов. |
| `submitted_at`     | string (ISO 8601, с таймзоной) | да | Время фактической отправки (клик "Отправить заявку"), не время `/start`. |

Заголовок `Idempotency-Key` дублирует `request_id` — часть реальных CRM/платёжных API
ожидают идемпотентность именно через заголовок, а не тело. Дублирование ничего не стоит
и приучает к правильному паттерну.

---

## 2. Response payload — успех (`200 OK`)

```json
{
  "status": "ok",
  "lead_id": "lead_3f9a7c21",
  "request_id": "b7e6a1b0-6f2e-4a3f-9c1e-8e6a2d9f2a41",
  "received_at": "2026-07-02T18:45:05+03:00"
}
```

Бот показывает пользователю сообщение об успехе (раздел 6 CLAUDE.md), `lead_id` можно
залогировать (не PII), но не показывать пользователю — ему не нужен внутренний ID CRM.

## 3. Response payload — временная ошибка (`500 Internal Server Error`)

```json
{
  "status": "error",
  "error": {
    "code": "internal_error",
    "message": "CRM service temporarily unavailable"
  }
}
```

## 4. Response payload — превышен лимит (`429 Too Many Requests`)

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 3
Content-Type: application/json
```
```json
{
  "status": "error",
  "error": {
    "code": "rate_limited",
    "message": "Too many requests, please retry later",
    "retry_after_seconds": 3
  }
}
```

По ТЗ фиксированный интервал ретрая — **3 секунды**, это и есть основной источник
паузы в `crm_client.py`. Заголовок `Retry-After` добавлен для реалистичности (так
себя ведут настоящие API) и как необязательное улучшение: если он присутствует и
отличается от дефолта, можно ориентироваться на него — но это опция, а не замена
фиксированного `RETRY_DELAY_SECONDS=3` из `config.py`.

## 5. Что бот делает с кодами ответа — правило retryable/non-retryable

Чтобы не ретраить то, что ретраить бессмысленно (это тоже часть "чистого кода", не
только соответствие ТЗ):

| Код ответа | Поведение бота |
|---|---|
| `200 / 201` | Успех, парсим `LeadResponse`, показываем подтверждение. |
| `500`, `502`, `503` | **Retryable.** Показать «Сервер CRM временно занят...», ждать 3 сек, повторить. |
| `429` | **Retryable.** То же сообщение. Если есть `Retry-After` — можно им дополнить лог, но ждём всё равно 3 сек (фиксировано по ТЗ). |
| Сетевая ошибка (timeout, connection error) | **Retryable**, как 500 — CRM недоступна, а не отклонила запрос. |
| `400`, `422` (если вдруг настроите такое правило) | **Не retryable.** Это ошибка данных, а не временная проблема сервера — повтор с теми же данными даст тот же результат. Логируем как критическую ошибку сразу, без 3 попыток. Для этого ТЗ не обязательно, но `crm_client.py` стоит спроектировать с этим различием — иначе retry-цикл будет "мусорным" по смыслу (раздел 8 CLAUDE.md). |
| `200`/`201`, но тело не парсится в `CrmSuccessResponse` | **Не retryable.** ⚠️ Реальный кейс, пойманный на практике: если CRM ответила успехом, но JSON не соответствует контракту (например, Mock-сервис вернул шаблон `{{...}}` буквально из-за не включённой опции "Enable dynamic mock responses" в Beeceptor) — это проблема конфигурации/контракта, а не временная недоступность сервера. Повторный идентичный запрос детерминированно даст тот же битый ответ. Ретраить его 3 раза — 9+ секунд впустую и ложное ощущение "сервер нестабилен", хотя на самом деле сервер стабильно отвечает неправильно. Логировать как критическую ошибку сразу (`ValidationError` от pydantic — явный сигнал именно этого случая), не гонять по общему retry-циклу вместе с 500/429. |

После **3 неудачных retryable-попыток** — критический сбой, финальное сообщение
пользователю (раздел 6 CLAUDE.md), данные не теряются (кнопка повторной отправки на
карточке).

---

## 6. Pydantic-модели (`app/models/lead.py`, `app/services/crm_client.py`)

```python
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PreferredTime(StrEnum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


class Lead(BaseModel):
    """Заявка лида — отправляется в тело POST /v1/leads."""

    request_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=2, max_length=50)
    phone: str  # уже нормализован validators/phone.py до создания Lead
    preferred_time: PreferredTime
    source: str = "telegram_bot"
    submitted_at: datetime


class CrmError(BaseModel):
    code: str
    message: str
    retry_after_seconds: int | None = None


class CrmErrorResponse(BaseModel):
    status: str
    error: CrmError


class CrmSuccessResponse(BaseModel):
    status: str
    lead_id: str
    request_id: UUID
    received_at: datetime
```

`crm_client.py` парсит успех в `CrmSuccessResponse`, ошибку — в `CrmErrorResponse`;
если тело ответа вообще не парсится как JSON (Mock-сервис может вернуть текст на
неожиданном правиле) — это тоже relayable как временная ошибка, но с явным логом
"CRM вернула неожиданный формат ответа", чтобы не потерять диагностику при отладке.

---

## 7. Конфигурация правил на стороне Beeceptor

Свободный тариф Beeceptor поддерживает **взвешенные случайные ответы** (`sendRandom`)
на один и тот же путь — это подтверждённый способ получить "часть запросов падает"
без стейтфул-логики. Точного "ровно каждый 5-й" random-режим не гарантирует (веса
соблюдаются статистически, не детерминированно) — для демонстрации ретрая в README
это даже нагляднее: видно, что бот реагирует на *непредсказуемый* сбой, а не на
захардкоженный сценарий.

Создайте одно правило на `POST /v1/leads` с тремя взвешенными вариантами ответа —
проще всего собрать через UI (Rules → Create Rule → Weighted Response), но вот тот
же конфиг в JSON (пригодится, если будете накатывать через Beeceptor Rules API):

```json
{
  "match": { "method": "POST", "operator": "EM", "value": "/v1/leads" },
  "mock": true,
  "sendType": "sendRandom",
  "sendRandom": [
    {
      "weight": 70,
      "name": "Success",
      "delay": 1800,
      "send": {
        "status": 200,
        "body": "{ \"status\": \"ok\", \"lead_id\": \"lead_{{random.uuid}}\", \"request_id\": \"{{request.body.request_id}}\", \"received_at\": \"{{now}}\" }",
        "headers": { "Content-Type": "application/json" },
        "templated": true
      }
    },
    {
      "weight": 20,
      "name": "Internal error",
      "delay": 800,
      "send": {
        "status": 500,
        "body": "{ \"status\": \"error\", \"error\": { \"code\": \"internal_error\", \"message\": \"CRM service temporarily unavailable\" } }",
        "headers": { "Content-Type": "application/json" },
        "templated": false
      }
    },
    {
      "weight": 10,
      "name": "Rate limited",
      "delay": 300,
      "send": {
        "status": 429,
        "body": "{ \"status\": \"error\", \"error\": { \"code\": \"rate_limited\", \"message\": \"Too many requests, please retry later\", \"retry_after_seconds\": 3 } }",
        "headers": { "Content-Type": "application/json", "Retry-After": "3" },
        "templated": false
      }
    }
  ],
  "enabled": true
}
```

Пояснения к конфигу:
- `delay` — в миллисекундах, задаётся отдельно на каждый вариант ответа. Успех —
  1800 мс (внутри требуемого диапазона 1.5–2 сек из ТЗ). Ошибки специально с меньшей
  задержкой — реалистичнее (сервер быстро отвечает "занят", а не думает 2 секунды
  над отказом), но не критично, можно унифицировать под 1800–2000 везде.
- `templated: true` в успешном варианте — Beeceptor умеет подставлять значения из
  тела запроса (`{{request.body.request_id}}`) и служебные хелперы (`{{now}}`,
  `{{random.uuid}}`) в ответ; это опционально — можно оставить статичный
  `request_id`-заглушку, если шаблонизация не нужна для теста.
- Веса 70/20/10 — подобраны так, чтобы ошибка триггерилась достаточно часто для
  ручной проверки за разумное число сообщений в Telegram, не превращая обычный
  прогон в сплошные фейлы. Значение можно менять прямо в UI без переразвёртывания
  бота — URL остаётся тот же.
- Если хочется **детерминированного** "ровно каждый 5-й запрос" вместо вероятностного
  — в Beeceptor это делается через stateful-счётчики в шаблонах ответа (Step Counters);
  доступность этой возможности зависит от вашего тарифа — проверьте в интерфейсе
  раздел "State" при создании правила. Для целей этого тестового задания взвешенный
  режим полнее покрывает ТЗ (там написано "или каждый 5-й") и не требует шаблонов со
  счётчиками.

---

## 8. Проверка вручную (curl)

```bash
curl -i -X POST "https://<name>.free.beeceptor.com/v1/leads" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: b7e6a1b0-6f2e-4a3f-9c1e-8e6a2d9f2a41" \
  -d '{
    "request_id": "b7e6a1b0-6f2e-4a3f-9c1e-8e6a2d9f2a41",
    "name": "Иван Петров",
    "phone": "+79123456789",
    "preferred_time": "morning",
    "source": "telegram_bot",
    "submitted_at": "2026-07-02T18:45:03+03:00"
  }'
```

Прогоните 8–10 раз подряд — при весах 70/20/10 почти наверняка увидите и `500`, и
`429` вперемешку с `200`, что и нужно для скриншота/лога в README (раздел 7 —
"как проверялась отказоустойчивость").
