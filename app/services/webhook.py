import logging

import httpx
from aiogram import types

from app.config.settings import settings

logger = logging.getLogger(__name__)

BOT_NAME = "Sales Agent"


async def notify_new_user(chat_id: int, user: types.User) -> None:
    """Fire-and-forget POST to the new-user webhook. Logs errors, never raises."""
    if not settings.bot_start_webhook_url:
        return

    payload = {
        "bot_name": BOT_NAME,
        "chat_id": chat_id,
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                settings.bot_start_webhook_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.bot_start_webhook_secret}",
                    "Content-Type": "application/json",
                },
            )
            logger.info(f"New-user webhook fired for chat_id={chat_id}, status={resp.status_code}")
    except Exception as e:
        logger.error(f"New-user webhook failed for chat_id={chat_id}: {e}")
