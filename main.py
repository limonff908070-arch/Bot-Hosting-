import asyncio
import logging
import sys

# ── Windows cp1252 fix ────────────────────────────────────────────────────────
# On Windows RDP, sys.stdout and sys.stderr default to the system code page
# (usually cp1252). Any emoji or non-ASCII character in a log message will
# raise UnicodeEncodeError and crash the bot immediately.
# Reconfigure both streams to UTF-8 before anything else runs.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
# ─────────────────────────────────────────────────────────────────────────────

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import MASTER_BOT_TOKEN
from handlers import router
from admin_handlers import admin_router
from middleware import UserMiddleware


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        # Explicitly pass UTF-8 so logging never falls back to cp1252 on Windows
        logging.StreamHandler(stream=sys.stderr),
    ],
)
# Patch the handler's stream encoding just in case reconfigure() was not enough
for _h in logging.root.handlers:
    if hasattr(_h, "stream") and hasattr(_h.stream, "reconfigure"):
        try:
            _h.stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

logger = logging.getLogger(__name__)


async def main():
    bot     = Bot(token=MASTER_BOT_TOKEN)
    storage = MemoryStorage()
    dp      = Dispatcher(storage=storage)

    # Global middleware — registers every user and enforces block list.
    # Must be registered on the dispatcher so it runs for ALL updates.
    dp.message.outer_middleware(UserMiddleware())
    dp.callback_query.outer_middleware(UserMiddleware())

    # admin_router first so its StateFilter("*") handlers for BTN_ADMIN_PANEL
    # are matched before the user router's StateFilter("*") handlers.
    dp.include_router(admin_router)
    dp.include_router(router)

    logger.info("Master Bot Manager V2 starting...")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
