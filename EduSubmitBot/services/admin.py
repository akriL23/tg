from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Group, Assignment, Submission

async def set_user_role(session: AsyncSession, telegram_id: int, role: str) -> None:
    await session.execute(
        update(User).where(User.telegram_id == telegram_id).values(role=role)
    )
    await session.commit()

async def remove_student_from_group(session: AsyncSession, group_id: int, student_id: int) -> None:
    from database.models import GroupMember
    await session.execute(
        delete(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == student_id
        )
    )
    await session.commit()

async def get_stats(session: AsyncSession):
    users_cnt = await session.scalar(select(func.count()).select_from(User))
    groups_cnt = await session.scalar(select(func.count()).select_from(Group))
    assignments_cnt = await session.scalar(select(func.count()).select_from(Assignment))
    submissions_cnt = await session.scalar(select(func.count()).select_from(Submission))
    return {
        "users": users_cnt,
        "groups": groups_cnt,
        "assignments": assignments_cnt,
        "submissions": submissions_cnt,
    }