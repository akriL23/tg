import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import load_config
from handlers.setup import setup_handlers
from database.db import init_db
from scheduler import init_scheduler, shutdown_scheduler
from middlewares.error_handler import ErrorHandlerMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    config = load_config()
    bot = Bot(token=config.bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Add error handler middleware
    dp.message.middleware(ErrorHandlerMiddleware())
    dp.callback_query.middleware(ErrorHandlerMiddleware())

    # Initialize database
    await init_db()

    # Setup handlers
    setup_handlers(dp)

    # Initialize scheduler
    init_scheduler(bot)

    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        shutdown_scheduler()

if __name__ == '__main__':
    asyncio.run(main())