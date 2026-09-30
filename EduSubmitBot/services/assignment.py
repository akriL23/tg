from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Assignment, User, GroupMember

async def create_assignment(session: AsyncSession, group_id: int, title: str, description: str, file_id: str | None, deadline: datetime, allow_late: bool, created_by: int):
    assignment = Assignment(
        group_id=group_id,
        title=title,
        description=description,
        file_id=file_id,
        deadline=deadline,
        allow_late=allow_late,
        created_by=created_by
    )
    session.add(assignment)
    await session.commit()
    await session.refresh(assignment)
    return assignment

async def get_assignment_by_id(session: AsyncSession, assignment_id: int):
    result = await session.execute(select(Assignment).where(Assignment.id == assignment_id))
    return result.scalar_one_or_none()

async def get_students_in_group(session: AsyncSession, group_id: int):
    result = await session.execute(
        select(User)
        .join(GroupMember, GroupMember.user_id == User.id)
        .where(GroupMember.group_id == group_id, GroupMember.role == "student")
    )
    return result.scalars().all()