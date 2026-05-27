from sqlalchemy import text

from app.database.session import async_session


async def check_and_mark_seen(chat_id: int) -> bool:
    """Returns True if this is the first time we've seen this chat_id."""
    async with async_session() as session:
        result = await session.execute(
            text("INSERT INTO seen_users (chat_id) VALUES (:cid) ON CONFLICT DO NOTHING"),
            {"cid": chat_id},
        )
        await session.commit()
        return result.rowcount == 1
