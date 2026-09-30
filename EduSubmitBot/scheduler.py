from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.db import async_session
from database.models import Assignment, User, GroupMember, Reminder
from config import load_config
import logging
import pytz

logger = logging.getLogger(__name__)

config = load_config()
scheduler = AsyncIOScheduler(timezone=config.timezone)  # default tz for scheduler

def get_user_timezone(user_timezone_str: str):
    try:
        return pytz.timezone(user_timezone_str)
    except Exception:
        return pytz.UTC

async def schedule_reminders_for_assignment(assignment_id: int):
    async with async_session() as session:
        # get assignment
        result = await session.execute(select(Assignment).where(Assignment.id == assignment_id))
        assignment = result.scalar_one_or_none()
        if not assignment:
            return
        # get students in group
        result = await session.execute(
            select(User)
            .join(GroupMember, GroupMember.user_id == User.id)
            .where(GroupMember.group_id == assignment.group_id, GroupMember.role == "student")
        )
        students = result.scalars().all()
        now = datetime.now(pytz.UTC)
        for student in students:
            # Determine student timezone
            tz = get_user_timezone(student.timezone)
            # Convert assignment deadline to student tz for reminder times (but store UTC)
            deadline_utc = assignment.deadline.replace(tzinfo=pytz.UTC) if assignment.deadline.tzinfo is None else assignment.deadline
            deadline_local = deadline_utc.astimezone(tz)
            # 2 days before
            remind_2_local = deadline_local - timedelta(days=2)
            remind_2_utc = remind_2_local.astimezone(pytz.UTC)
            if remind_2_utc > now:
                exists = await session.execute(
                    select(Reminder).where(Reminder.assignment_id == assignment_id, Reminder.user_id == student.id, Reminder.remind_at == remind_2_utc)
                )
                if not exists.scalar_one_or_none():
                    reminder = Reminder(assignment_id=assignment_id, user_id=student.id, remind_at=remind_2_utc, sent=False)
                    session.add(reminder)
                    scheduler.add_job(
                        send_reminder,
                        trigger=DateTrigger(run_date=remind_2_utc),
                        args=[assignment_id, student.id, 2],
                        id=f"rem_{assignment_id}_{student.id}_2",
                        replace_existing=True
                    )
            # 1 day before
            remind_1_local = deadline_local - timedelta(days=1)
            remind_1_utc = remind_1_local.astimezone(pytz.UTC)
            if remind_1_utc > now:
                exists = await session.execute(
                    select(Reminder).where(Reminder.assignment_id == assignment_id, Reminder.user_id == student.id, Reminder.remind_at == remind_1_utc)
                )
                if not exists.scalar_one_or_none():
                    reminder = Reminder(assignment_id=assignment_id, user_id=student.id, remind_at=remind_1_utc, sent=False)
                    session.add(reminder)
                    scheduler.add_job(
                        send_reminder,
                        trigger=DateTrigger(run_date=remind_1_utc),
                        args=[assignment_id, student.id, 1],
                        id=f"rem_{assignment_id}_{student.id}_1",
                        replace_existing=True
                    )
        await session.commit()

async def send_reminder(assignment_id: int, student_id: int, days_left: int):
    async with async_session() as session:
        # get assignment and student
        result = await session.execute(select(Assignment).where(Assignment.id == assignment_id))
        assignment = result.scalar_one_or_none()
        result = await session.execute(select(User).where(User.id == student_id))
        student = result.scalar_one_or_none()
        if not assignment or not student:
            return
        # Determine student timezone for message
        tz = get_user_timezone(student.timezone)
        deadline_utc = assignment.deadline.replace(tzinfo=pytz.UTC) if assignment.deadline.tzinfo is None else assignment.deadline
        deadline_local = deadline_utc.astimezone(tz)
        try:
            await scheduler._bot.send_message(
                chat_id=student.telegram_id,
                text=f"Напоминание: до дедлайна задания «{assignment.title}» осталось {days_left} день(дня).\n"
                     f"Дедлайн: {deadline_local.strftime('%d.%m.%Y %H:%M')} {student.timezone}.\n"
                     "Для сдачи работы используйте бота.",
            )
            # mark reminder as sent
            await session.execute(
                update(Reminder)
                .where(Reminder.assignment_id == assignment_id, Reminder.user_id == student_id, Reminder.sent == False)
                .values(sent=True)
            )
            await session.commit()
        except Exception as e:
            logger.error(f"Failed to send reminder to student {student_id}: {e}")

def load_pending_reminders():
    """Load pending reminders from DB and schedule them."""
    # This should be called after scheduler is started and bot is available.
    # We'll call it from init_scheduler after setting scheduler._bot.
    import asyncio
    async def _load():
        async with async_session() as session:
            result = await session.execute(select(Reminder).where(Reminder.sent == False))
            reminders = result.scalars().all()
            for rem in reminders:
                # get assignment and student to compute days_left
                assign = await session.get(Assignment, rem.assignment_id)
                stud = await session.get(User, rem.user_id)
                if not assign or not stud:
                    continue
                # compute days_left based on reminder time
                now = datetime.now(pytz.UTC)
                delta = rem.remind_at - now
                days_left = max(0, int(delta.total_seconds() / 86400))
                if days_left < 0:
                    # already passed, mark sent?
                    continue
                # schedule job
                scheduler.add_job(
                    send_reminder,
                    trigger=DateTrigger(run_date=rem.remind_at),
                    args=[rem.assignment_id, rem.user_id, days_left],
                    id=f"rem_{rem.assignment_id}_{rem.user_id}_{int(rem.remind_at.timestamp())}",
                    replace_existing=True
                )
                logger.info(f"Rescheduled reminder ID {rem.id} for assignment {rem.assignment_id} user {rem.user_id}")
    # We need to run async function; but init_scheduler is sync. We'll store loop to run later.
    # For simplicity, we'll call asyncio.create_task if loop running.
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_load())
    except RuntimeError:
        # no running loop, we'll schedule later via init_scheduler after bot start? We'll just log.
        logger.warning("No running event loop to load pending reminders; will load on first update.")

def init_scheduler(bot):
    scheduler._bot = bot
    scheduler.start()
    # Load pending reminders
    load_pending_reminders()
    logger.info("Scheduler started")

def shutdown_scheduler():
    scheduler.shutdown()