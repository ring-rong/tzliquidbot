# Lead-bot — Telegram-бот для сбора заявок

## 1. Что это

Telegram-бот на aiogram 3.x, который проводит короткий опрос (имя → телефон → удобное
время связи), показывает сводную карточку для подтверждения и отправляет заявку
асинхронным POST-запросом во внешний Mock-CRM (Beeceptor). Бот переживает временные
сбои CRM (500/429/сетевые ошибки) через ретраи с фиксированной паузой и не блокирует
обслуживание других пользователей, пока ждёт ответа CRM.

## 2. Стек и почему

- **Python 3.12 + aiogram 3.x** — нативно асинхронный фреймворк с встроенным FSM и
  роутерами, что даёт модульность (`handlers/`, `states/`) без самодельной обвязки.
- **httpx.AsyncClient** для запроса к CRM — асинхронный, современный API, один клиент
  живёт всё время работы процесса и переиспользуется между заявками (пул соединений),
  а не создаётся заново на каждый запрос.
- **Pydantic v2** — `Lead`/`CrmSuccessResponse`/`CrmErrorResponse` дословно повторяют
  `API_CONTRACT.md`, поэтому несоответствие контракту падает валидацией, а не молча
  проглатывается.
- **pydantic-settings** — типизированный `Settings` из `.env`, ни один секрет/URL/число
  ретраев не захардкожен в коде (`app/config.py`).
- **MemoryStorage для FSM** — заявка тестового задания не многоинстансная, состояние
  теряется только при рестарте процесса контейнера, что для этого объёма приемлемо
  (см. раздел 8 "Известные ограничения" про переход на `RedisStorage`).
- **pytest + pytest-asyncio + respx** — retry-логика проверяется детерминированно
  (respx подставляет фиксированную последовательность ответов), не завязываясь на то,
  выпадет ли реальному Beeceptor `500`/`429` именно в момент прогона тестов.
- **Docker + docker compose** — единственный поддерживаемый способ финального запуска.

## 3. Структура проекта

```
lead-bot/
├── app/
│   ├── main.py                # точка входа: Bot/Dispatcher, один httpx.AsyncClient на всё время жизни
│   ├── config.py               # Settings (pydantic-settings): BOT_TOKEN, CRM_ENDPOINT_URL, retry-параметры
│   ├── handlers/
│   │   ├── __init__.py         # сборка всех роутеров в один
│   │   ├── start.py            # /start → приветствие, вход в FSM
│   │   ├── survey.py           # шаги опроса: имя → телефон → время (кнопки)
│   │   └── confirm.py          # сводная карточка, отправка в CRM, ретрай/рестарт
│   ├── states/lead_form.py     # LeadForm(StatesGroup): name, phone, time, confirm
│   ├── keyboards/
│   │   ├── time_kb.py          # инлайн-клавиатура Утро/День/Вечер + маппинг в PreferredTime
│   │   └── confirm_kb.py       # клавиатуры "Отправить/Заполнить заново" и "Попробовать снова"
│   ├── validators/
│   │   ├── name.py             # validate_name(): 2–50 символов
│   │   └── phone.py            # validate_phone(): нормализация к +7XXXXXXXXXX
│   ├── services/crm_client.py  # send_lead(): async POST + retry-цикл (3 попытки/3 сек)
│   ├── models/lead.py          # Lead, PreferredTime, CrmSuccessResponse, CrmErrorResponse
│   └── texts/messages.py       # все пользовательские тексты одним модулем
├── tests/
│   ├── conftest.py             # тестовые заглушки BOT_TOKEN/CRM_ENDPOINT_URL
│   ├── test_validators.py      # 25 тестов на граничные случаи имени/телефона
│   └── test_crm_client.py      # 5 respx-тестов: успех, 500→500→200, 429×3→сбой, сеть, non-retryable
├── docker/Dockerfile           # python:3.12-slim, непривилегированный пользователь
├── docker-compose.yml          # в корне репозитория — см. DEVLOG.md, почему не в docker/
├── .env.example                # пустые BOT_TOKEN/CRM_ENDPOINT_URL, заполненные retry-дефолты
├── .dockerignore / .gitignore
├── requirements.txt / requirements-dev.txt
├── pyproject.toml              # конфиг pytest-asyncio, ruff, black
├── DEVLOG.md                   # реальные развилки и решения по ходу работы
└── PROGRESS.md                 # снимок прогресса на момент последней правки
```

## 4. Как запустить локально (без Docker)

```bash
cd lead-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # включает requirements.txt + pytest/ruff/black

cp .env.example .env
# впишите в .env:
#   BOT_TOKEN=<токен от @BotFather>
#   CRM_ENDPOINT_URL=https://mpfbba1a2c2708d21084.free.beeceptor.com/v1/leads

python -m app.main
```

Если `python3 -m venv` ругается на отсутствие `ensurepip` (бывает на некоторых Debian/
Ubuntu без пакета `python3-venv`) — либо `sudo apt install python3-venv`, либо:
`python3 -m venv --without-pip .venv && curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python`.

Тесты и линтеры:

```bash
pytest tests/ -v
ruff check .
black --check .
```

## 5. Как запустить в Docker

```bash
cd lead-bot
cp .env.example .env   # заполнить BOT_TOKEN и CRM_ENDPOINT_URL, как в пункте 4
docker compose up --build
```

Обязательные переменные окружения (см. `.env.example`): `BOT_TOKEN`,
`CRM_ENDPOINT_URL`. `RETRY_ATTEMPTS`/`RETRY_DELAY_SECONDS`/
`CRM_REQUEST_TIMEOUT_SECONDS` необязательны — в `app/config.py` уже стоят дефолты,
совпадающие с ТЗ (3 попытки, 3 секунды).

Контейнер запускает `python -m app.main` от непривилегированного пользователя
(`botuser`, не root). Остановить: `docker compose down`.

## 6. Настройка Mock-API

Mock-CRM уже настроен и подтверждён рабочим владельцем задачи (Beeceptor, `POST
/v1/leads`, взвешенное правило 70% `200` / 20% `500` / 10% `429`, задержка ~1.5–2 сек
на успехе) — регистрировать и настраивать его заново не нужно, URL уже готов:

```
CRM_ENDPOINT_URL=https://mpfbba1a2c2708d21084.free.beeceptor.com/v1/leads
```

Полная схема запроса/ответа и точный конфиг Beeceptor-правила — в `API_CONTRACT.md`.
Проверка вручную (тот же curl, что и в `API_CONTRACT.md`, раздел 8):

```bash
curl -i -X POST "https://mpfbba1a2c2708d21084.free.beeceptor.com/v1/leads" \
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

Прогнав это 8–10 раз подряд, при весах 70/20/10 почти наверняка увидите вперемешку
`200`, `500` и `429`. В этой разработке эндпоинт проверялся так несколько раз — живой
на момент последнего коммита.

Свободный тариф Beeceptor удаляет неактивные эндпоинты через 90 дней, логи чистит
через 15 — если бот долго не обращался к нему, проверьте доступность заново перед
использованием.

## 7. Как проверялась отказоустойчивость

**Юнит-тесты (`tests/test_crm_client.py`, respx-моки, детерминированно):**
- успех с первой попытки (`200` сразу);
- `500 → 500 → 200` — две ретрая, третья попытка успешна;
- `429 × 3` — все три попытки исчерпаны, поднимается `CrmDeliveryFailed`;
- сетевой таймаут (`httpx.ConnectTimeout`) на первой попытке ведёт себя как `500` —
  ретраится и добивается успеха на второй;
- `422` (non-retryable) — падает сразу, без единой повторной попытки.

Запуск: `pytest tests/test_crm_client.py -v` — все 5 зелёные.

**Ручная/e2e проверка на реальном Beeceptor-эндпоинте:** должна быть выполнена и
задокументирована владельцем репозитория со скриншотами/логами — см. раздел 8 ниже,
почему это не сделано в рамках данной сессии разработки.

## 8. Известные ограничения

- **`MemoryStorage` вместо `RedisStorage`.** Состояние FSM живёт в памяти процесса —
  при рестарте контейнера все незавершённые анкеты теряются. Для тестового задания
  этого достаточно. Для мульти-инстанс продакшена: заменить `MemoryStorage()` на
  `RedisStorage.from_url(...)` в `app/main.py` (aiogram поддерживает это из коробки,
  интерфейс `BaseStorage` не меняется) и поднять Redis рядом в `docker-compose.yml`.
- **Двойная отправка одной карточки не дебаунсится.** Если пользователь очень быстро
  дважды нажмёт "Отправить заявку", уйдут два независимых запроса (с одним и тем же
  `request_id`, так что CRM с настоящей идемпотентностью не создаст дубль — но
  Mock-CRM это не гарантирует). Не реализовано намеренно — это отдельная защита сверх
  объёма ТЗ, добавлять её "на всякий случай" — то самое переусложнение, которое
  прямо запрещено разделом 8 CLAUDE.md.
- **Регэксп телефона принимает только явно перечисленные в ТЗ форматы** (`+7`/`8` +
  10 цифр в допустимой группировке). Голый 10-значный номер без префикса
  (`9123456789`) сознательно не принимается — в ТЗ такой вариант не упомянут.
- **Docker-сборка и живой ручной прогон в Telegram не выполнены мной в рамках этой
  сессии разработки** — в окружении, где писался код, нет Docker-демона и нет
  `BOT_TOKEN`/доступа к живому Telegram-клиенту (детали и что именно проверено вместо
  этого — в `DEVLOG.md`, фазы 4–6). Код и тесты полностью готовы; `docker compose up
  --build` с нуля и полный ручной прогон (включая проверку асинхронности на двух
  чатах и живого ретрая `500`/`429`) — необходимый последний шаг, который должен
  выполнить владелец репозитория по инструкциям разделов 4/5/6 этого README.

## 9. DEVLOG

Процесс работы с ИИ, реальные развилки и решения (в том числе почему
`docker-compose.yml` лежит в корне, а не в `docker/`, и что именно не удалось
проверить руками в среде разработки) — задокументированы в [`DEVLOG.md`](./DEVLOG.md).
