import asyncio
import logging

import httpx
from aiogram import types

from app.config.settings import settings

logger = logging.getLogger(__name__)

WEBHOOK_URL = "https://app-notification.x8x.pro/functions/v1/bot-start-event"
BOT_NAME = "Sales Agent"

_background_tasks: set[asyncio.Task] = set()


async def notify_bot_start(user: types.User) -> None:
    secret = settings.bot_start_webhook_secret
    if not secret:
        logger.info("BOT_START_WEBHOOK_SECRET not set — skipping new-user notification")
        return

    payload = {
        "bot_name": BOT_NAME,
        "telegram_user_id": user.id,
        "telegram_username": user.username,
        "telegram_first_name": user.first_name,
        "telegram_last_name": user.last_name,
    }

    logger.info(f"BOT_START payload: {payload}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                WEBHOOK_URL,
                json=payload,
                headers={"Authorization": f"Bearer {secret}"},
            )
        if response.status_code == 200:
            logger.info(f"New-user notification sent for {user.id}")
        else:
            logger.error(
                f"New-user notification failed ({response.status_code}): {response.text[:200]}"
            )
    except Exception as e:
        logger.error(f"New-user notification error for {user.id}: {e}")


def schedule_bot_start_notification(user: types.User) -> None:
    task = asyncio.create_task(notify_bot_start(user))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)