from datetime import datetime, timedelta
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Assignment, User, GroupMember, Submission, SubmissionFile

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

async def get_assignments_by_teacher(session: AsyncSession, teacher_id: int):
    """Return assignments created by teacher in groups they teach."""
    # Get groups where teacher is teacher_id (via Group.teacher_id) or via GroupMember?
    # We'll use Group.teacher_id for simplicity.
    result = await session.execute(
        select(Assignment)
        .join(Group, Assignment.group_id == Group.id)
        .where(Group.teacher_id == teacher_id)
        .order_by(desc(Assignment.created_at))
    )
    return result.scalars().all()

async def get_submissions_by_assignment(session: AsyncSession, assignment_id: int):
    result = await session.execute(
        select(Submission)
        .where(Submission.assignment_id == assignment_id)
        .order_by(Submission.submitted_at)
    )
    return result.scalars().all()

async def get_submission_files(session: AsyncSession, submission_id: int):
    result = await session.execute(
        select(SubmissionFile)
        .where(SubmissionFile.submission_id == submission_id)
        .order_by(SubmissionFile.version)
    )
    return result.scalars().all()