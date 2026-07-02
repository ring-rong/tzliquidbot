import asyncio
import logging

import httpx
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from app.config import settings
from app.handlers import router


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=settings.bot_token)
    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)
    dp.include_router(router)

    try:
        async with httpx.AsyncClient(timeout=settings.crm_request_timeout_seconds) as http_client:
            await dp.start_polling(bot, http_client=http_client)
    finally:
        await storage.close()


if __name__ == "__main__":
    asyncio.run(main())
