import logging
from aiogram import BaseMiddleware
from aiogram.types import Update, ErrorEvent
from typing import Callable, Dict, Any, Awaitable

logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as exc:
            # Log the exception with details
            logger.exception("Exception in update processing: %s", exc)
            # Optionally notify admin or user
            # For now, we just let the exception propagate?
            # We'll swallow and send a generic message to user if possible.
            # Since we have access to event, we can try to answer if it's a message.
            if hasattr(event, 'message') and event.message:
                try:
                    await event.message.answer(
                        "Произошла внутренняя ошибка бота. Пожалуйста, попробуйте позже."
                    )
                except Exception:
                    pass  # If we can't answer, just ignore
            elif hasattr(event, 'callback_query') and event.callback_query:
                try:
                    await event.callback_query.answer(
                        "Произошла внутренняя ошибка бота.", show_alert=True
                    )
                except Exception:
                    pass
            # Re-raise if you want the error to be logged elsewhere; but we already logged.
            # Returning None means we handled it.
            return None