from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User
from config import load_config

config = load_config()

async def get_or_create_user(session: AsyncSession, telegram_id: int, full_name: str, username: str) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        # update name/username if changed
        if user.full_name != full_name or user.username != username:
            user.full_name = full_name
            user.username = username
            await session.commit()
        return user
    # new user
    role = 'student'  # default, will be updated via invite or admin
    if telegram_id in config.admin_ids:
        role = 'admin'
    user = User(telegram_id=telegram_id, full_name=full_name, username=username, role=role)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

async def set_user_role(session: AsyncSession, telegram_id: int, role: str):
    await session.execute(update(User).where(User.telegram_id == telegram_id).values(role=role))
    await session.commit()

async def get_user(session: AsyncSession, telegram_id: int):
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()