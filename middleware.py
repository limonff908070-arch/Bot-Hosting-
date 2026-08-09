from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from config import ADMIN_ID
from user_db import register_user, is_blocked


class UserMiddleware(BaseMiddleware):
    """
    Global middleware that runs before every Message and CallbackQuery handler.

    Responsibilities
    ────────────────
    1. Register the user in users.json (first touch or username update).
    2. If the user is blocked, silently stop execution and notify them.
       The admin (ADMIN_ID) is always allowed through unconditionally.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[Any]],
        event: TelegramObject,
        data: dict,
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user:
            register_user(user.id, user.username or "")

            # Admin is unconditionally allowed; everyone else is checked.
            if user.id != ADMIN_ID and is_blocked(user.id):
                if isinstance(event, Message):
                    await event.answer("⛔ তুমি এই Bot থেকে Block হয়েছো।")
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        "⛔ তুমি এই Bot থেকে Block হয়েছো।", show_alert=True
                    )
                return  # Halt — do not call downstream handlers

        return await handler(event, data)
