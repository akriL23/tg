from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Group, Assignment, Submission
from services.user import set_user_role

async def get_all_groups(session: AsyncSession):
    result = await session.execute(select(Group).order_by(Group.id))
    return result.scalars().all()

async def get_all_assignments(session: AsyncSession):
    result = await session.execute(select(Assignment).order_by(Assignment.id))
    return result.scalars().all()

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