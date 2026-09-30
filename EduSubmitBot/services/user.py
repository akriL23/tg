from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Assignment, Submission, SubmissionFile, GroupMember
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

async def get_active_assignments_for_student(session: AsyncSession, student_id: int):
    """Return assignments where student is a member of the group and deadline not passed."""
    from datetime import datetime
    now = datetime.utcnow()
    # Get groups where student is member
    result = await session.execute(
        select(Assignment)
        .join(GroupMember, Assignment.group_id == GroupMember.group_id)
        .where(GroupMember.user_id == student_id, Assignment.deadline >= now)
        .order_by(Assignment.deadline)
    )
    return result.scalars().all()

async def create_submission(session: AsyncSession, assignment_id: int, user_id: int, file_id: str, file_name: str, file_size: int):
    # Determine if late
    from datetime import datetime
    assignment = await session.get(Assignment, assignment_id)
    is_late = datetime.utcnow() > assignment.deadline if assignment else False
    submission = Submission(
        assignment_id=assignment_id,
        user_id=user_id,
        submitted_at=datetime.utcnow(),
        is_late=is_late,
        status='submitted'
    )
    session.add(submission)
    await session.flush()  # to get submission.id
    # File
    submission_file = SubmissionFile(
        submission_id=submission.id,
        file_id=file_id,
        file_name=file_name,
        file_size=file_size,
        version=1
    )
    session.add(submission_file)
    await session.commit()
    await session.refresh(submission)
    return submission

async def get_submission_by_id(session: AsyncSession, submission_id: int):
    result = await session.execute(select(Submission).where(Submission.id == submission_id))
    return result.scalar_one_or_none()

async def get_latest_submission_file(session: AsyncSession, submission_id: int):
    result = await session.execute(
        select(SubmissionFile)
        .where(SubmissionFile.submission_id == submission_id)
        .order_by(SubmissionFile.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()

async def add_submission_file_version(session: AsyncSession, submission_id: int, file_id: str, file_name: str, file_size: int):
    # Get latest version
    latest = await get_latest_submission_file(session, submission_id)
    new_version = (latest.version + 1) if latest else 1
    submission_file = SubmissionFile(
        submission_id=submission_id,
        file_id=file_id,
        file_name=file_name,
        file_size=file_size,
        version=new_version
    )
    session.add(submission_file)
    await session.commit()
    await session.refresh(submission_file)
    return submission_file