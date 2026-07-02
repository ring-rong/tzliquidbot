# PROGRESS

Статус на: 2026-07-02, старт работы.

## Сделано
- Прочитаны `CLAUDE.md` и `API_CONTRACT.md` целиком.
- Проверен Mock-API вручную (`curl`): `200` от `POST /v1/leads`, эндпоинт живой.
- Создана структура каталогов `lead-bot/app/...` с пустыми `__init__.py` (раздел 4 CLAUDE.md).
- `git init`, `.gitignore`.
- Фаза 1: `models/lead.py` (Lead/PreferredTime/CrmSuccessResponse/CrmErrorResponse),
  `validators/name.py`, `validators/phone.py`. 25 юнит-тестов, все зелёные. Закоммичено.

- Фаза 2: `config.py` (Settings), `crm_client.py` (async POST + retry на 3
  попытки/3 сек по `API_CONTRACT.md` разделу 5), 5 respx-тестов, все зелёные.
  `ruff`/`black` без замечаний по всему проекту на этот момент.

- Фаза 3: `states/lead_form.py`, `keyboards/`, `texts/messages.py`,
  `handlers/{start,survey,confirm}.py`. Роутеры собраны в `app/handlers/__init__.py`.
  Ручная проверка сборки роутера прошла (`from app.handlers import router`).
  `ruff`/`black`/тесты (30/30) по-прежнему чистые.

- Фаза 4: `main.py` (Bot/Dispatcher/httpx.AsyncClient DI), `.env.example`. Импорт и
  конструирование объектов проверены без сети в Telegram; сеть до api.telegram.org
  из окружения разработки достижима, но реального `BOT_TOKEN` нет — живой прогон
  не выполнен, см. открытые вопросы ниже.

- Фаза 5: `docker/Dockerfile` + `docker-compose.yml` (в корне репозитория — см.
  DEVLOG про эту развилку) + `.dockerignore`. YAML провалидирован парсером, сам билд
  не выполнен — нет Docker-демона в окружении разработки. Это ключевой пункт,
  который должен выполнить владелец: `docker compose up --build` с нуля.

## В процессе
- Фаза 6/7: README, финальная самопроверка, сбор доказательств для DoD.

## Дальше
- Фаза 4: `main.py`/`config.py`, первый ручной прогон.
- Фаза 5: Docker.
- Фаза 6: доказательства для DoD.
- Фаза 7: README + DEVLOG + самопроверка.

## Открытые вопросы к владельцу
- **Docker и живой Telegram-прогон нельзя выполнить из текущего окружения
  разработки** (нет демона Docker, нет `BOT_TOKEN`, нет доступа к живому Telegram-клиенту
  с двух аккаунтов). Весь код/тесты/Docker-конфиг будут готовы и провалидированы
  локально (pytest, ruff/black), но пункты DoD, требующие реального `docker compose up
  --build` и ручного прохода `/start` → отправка в Telegram (включая проверку ретрая и
  параллельности двух чатов), должен выполнить владелец на своей машине по инструкции
  в README. Это зафиксировано и в DEVLOG.md.
