import secrets
import string
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Group, User

def generate_invite_code(length=8):
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

async def create_group(session: AsyncSession, title: str, teacher_id: int):
    invite_code = generate_invite_code()
    # ensure uniqueness (simple retry)
    while True:
        result = await session.execute(select(Group).where(Group.invite_code == invite_code))
        if not result.scalar_one_or_none():
            break
        invite_code = generate_invite_code()
    group = Group(title=title, invite_code=invite_code, teacher_id=teacher_id)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group

async def get_groups_by_teacher(session: AsyncSession, teacher_id: int):
    result = await session.execute(select(Group).where(Group.teacher_id == teacher_id))
    return result.scalars().all()

async def get_group_by_code(session: AsyncSession, invite_code: str):
    result = await session.execute(select(Group).where(Group.invite_code == invite_code))
    return result.scalar_one_or_none()

async def get_group_by_id(session: AsyncSession, group_id: int):
    result = await session.execute(select(Group).where(Group.id == group_id))
    return result.scalar_one_or_none()