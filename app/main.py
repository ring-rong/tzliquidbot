import asyncio
import logging

import httpx
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.handlers import router


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    async with httpx.AsyncClient(timeout=settings.crm_request_timeout_seconds) as http_client:
        await dp.start_polling(bot, http_client=http_client)


if __name__ == "__main__":
    asyncio.run(main())
