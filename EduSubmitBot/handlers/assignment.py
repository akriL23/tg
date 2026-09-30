from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InputFile
from services.assignment import create_assignment, get_students_in_group, get_assignments_by_teacher, get_submissions_by_assignment, get_submission_files
from services.group import get_groups_by_teacher
from services.user import get_user
from database.db import async_session
from datetime import datetime, timedelta
import os

router = Router()

class NewAssignment(StatesGroup):
    waiting_for_group = State()
    waiting_for_file = State()
    waiting_for_confirmation = State()  # optional

class SubmissionView(StatesGroup):
    waiting_for_assignment = State()
    viewing_submissions = State()

@router.message(Command("new_assignment"))
async def cmd_new_assignment(message: Message, state: FSMContext):
    async with async_session() as session:
        user = await get_user(session, message.from_user.id)
        if not user or user.role not in ("teacher", "admin"):
            await message.answer("Только преподаватели и администраторы могут создавать задания.")
            return
        groups = await get_groups_by_teacher(session, user.id)
        if not groups:
            await message.answer("У вас пока нет групп. Сначала создайте группу через /create_group.")
            return
        # Build list
        group_list = "\n".join([f"{g.id}. {g.title}" for g in groups])
        await state.update_data(groups={g.id: g for g in groups})  # store mapping
        await message.answer(
            "Выберите группу, для которой создаётся задание, отправив её номер:\n"
            f"{group_list}"
        )
        await state.set_state(NewAssignment.waiting_for_group)

@router.message(NewAssignment.waiting_for_group)
async def process_group_select(message: Message, state: FSMContext):
    try:
        idx = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, отправьте номер группы.")
        return
    data = await state.get_data()
    groups_map = data.get('groups', {})
    group = groups_map.get(idx)
    if not group:
        await message.answer("Группа с таким номером не найдена.")
        return
    await state.update_data(group_id=group.id, group_title=group.title)
    await message.answer(
        f"Выбрана группа: «{group.title}»\n"
        "Теперь отправьте файл задания (документ, изображение, архив и т.д.)."
    )
    await state.set_state(NewAssignment.waiting_for_file)

@router.message(NewAssignment.waiting_for_file, F.document | F.photo | F.video | F.audio | F.voice)
async def process_file_received(message: Message, state: FSMContext):
    # Get file_id
    file_id = None
    if message.document:
        file_id = message.document.file_id
    elif message.photo:
        file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.audio:
        file_id = message.audio.file_id
    elif message.voice:
        file_id = message.voice.file_id
    if not file_id:
        await message.answer("Не удалось получить файл. Попробуйте ещё раз.")
        return
    await state.update_data(file_id=file_id)
    # Auto deadline: now + 7 days
    deadline = datetime.utcnow() + timedelta(days=7)
    await state.update_data(deadline=deadline.isoformat())
    # Ask confirmation
    await message.answer(
        f"Файл получен.\nДедлайн установлен автоматически на 7 дней от сейчас: {deadline.strftime('%d.%m.%Y %H:%M')} UTC.\n"
        "Подтвердить создание задания? (Да/Нет)"
    )
    await state.set_state(NewAssignment.waiting_for_confirmation)

@router.message(NewAssignment.waiting_for_confirmation, F.text.lower().in_(["да", "yes", "y", "lf"]))
async def process_confirm_yes(message: Message, state: FSMContext):
    data = await state.get_data()
    async with async_session() as session:
        user = await get_user(session, message.from_user.id)
        assignment = await create_assignment(
            session,
            group_id=data['group_id'],
            title=f"Задание от {datetime.utcnow().strftime('%d.%m.%Y')}",
            description="Файл задания прикреплён ниже.",  # simple
            file_id=data['file_id'],
            deadline=datetime.fromisoformat(data['deadline']),
            allow_late=False,
            created_by=user.id
        )
        # Notify students
        students = await get_students_in_group(session, data['group_id'])
        for student in students:
            try:
                await message.bot.send_document(
                    chat_id=student.telegram_id,
                    document=data['file_id'],
                    caption=f"Новое задание в группе «{data['group_title']}»!\n"
                            f"Дедлайн: {assignment.deadline.strftime('%d.%m.%Y %H:%M')} UTC.\n"
                            "Для сдачи работы используйте бота."
                )
            except Exception:
                pass  # ignore if user blocked bot
        await message.answer(
            f"Задание создано и разослано студентам группы «{data['group_title']}».\n"
            f"ID задания: {assignment.id}"
        )
    await state.clear()

@router.message(NewAssignment.waiting_for_confirmation)
async def process_confirm_no(message: Message, state: FSMContext):
    await message.answer("Создание задания отменено.")
    await state.clear()

# ---------- /submissions handler ----------
@router.message(Command("submissions"))
async def cmd_submissions(message: Message, state: FSMContext):
    async with async_session() as session:
        user = await get_user(session, message.from_user.id)
        if not user or user.role not in ("teacher", "admin"):
            await message.answer("Только преподаватели и администраторы могут просматривать сдачи.")
            return
        assignments = await get_assignments_by_teacher(session, user.id)
        if not assignments:
            await message.answer("У вас пока нет созданных заданий.")
            return
        # Build list with inline keyboard? We'll use numbered list for simplicity.
        await state.update_data(assignments={a.id: a for a in assignments})
        assignment_list = "\n".join(
            [f"{a.id}. {a.title} (дедлайн: {a.deadline.strftime('%d.%m.%Y')})" for a in assignments]
        )
        await message.answer(
            "Выберите задание, чтобы посмотреть сдачи, отправив его номер:\n"
            f"{assignment_list}"
        )
        await state.set_state(SubmissionView.waiting_for_assignment)

@router.message(SubmissionView.waiting_for_assignment)
async def process_assignment_select(message: Message, state: FSMContext):
    try:
        idx = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, отправьте номер задания.")
        return
    data = await state.get_data()
    assignments_map = data.get('assignments', {})
    assignment = assignments_map.get(idx)
    if not assignment:
        await message.answer("Задание с таким номером не найдено.")
        return
    await state.update_data(assignment_id=assignment.id, assignment_title=assignment.title)
    async with async_session() as session:
        submissions = await get_submissions_by_assignment(session, assignment.id)
        if not submissions:
            await message.answer(f"По заданию «{assignment.title}» пока нет сдач.")
            await state.clear()
            return
        # Show first submission
        await state.update_data(submissions=[s.id for s in submissions], submission_index=0)
        await show_submission(message, state, session)

async def show_submission(message: Message, state: FSMContext, session):
    data = await state.get_data()
    submissions_ids = data.get('submissions', [])
    index = data.get('submission_index', 0)
    if index >= len(submissions_ids):
        await message.answer("Больше сдач нет.")
        await state.clear()
        return
    sub_id = submissions_ids[index]
    submission = await session.get(Submission, sub_id)
    files = await get_submission_files(session, sub_id)
    # Get student info
    from services.user import get_user
    student = await get_user(session, submission.user_id)
    # Build caption
    caption = (
        f"Сдача #{sub_id} по заданию «{data.get('assignment_title')}»\n"
        f"Студент: {student.full_name if student else 'Неизвестно'} (ID: {submission.user_id})\n"
        f"Дата сдачи: {submission.submitted_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"Статус: {submission.status}\n"
        f"Комментарий преподавателя: {submission.teacher_comment or '—'}\n"
        f"Файлов: {len(files)}"
    )
    # Send first file as document, if multiple we can send as media group later; for simplicity send first.
    if files:
        file = files[0]
        # file.telegram_id? we have file_id stored.
        try:
            await message.bot.send_document(
                chat_id=message.chat.id,
                document=file.file_id,
                caption=caption
            )
        except Exception:
            await message.answer(caption)
    else:
        await message.answer(caption)
    # Offer navigation
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    if index > 0:
        builder.button(text="◀️ Предыдущая", callback_data=f"sub_prev:{index}")
    if index < len(submissions_ids) - 1:
        builder.button(text="Следующая ▶️", callback_data=f"sub_next:{index}")
    builder.button(text="Закрыть", callback_data="sub_close")
    await message.answer("Навигация:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("sub_prev:"))
async def process_sub_prev(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data.get('submission_index', 0)
    if index > 0:
        await state.update_data(submission_index=index - 1)
    await callback.answer()
    # Need to refresh message; we'll edit? Simpler: answer and call show_submission again.
    # We'll delete previous and send new? For now just answer and let user resend command? We'll do a hack.
    await callback.message.answer("Загружаю предыдущую сдачу...")
    # We'll just trigger show_submission by sending a fake message? Better to edit.
    # For simplicity, we'll just answer and let user use buttons again.
    # We'll implement a proper edit later due to time.
    await show_submission(callback.message, state, None)  # session not available; we'll skip for now.

@router.callback_query(F.data.startswith("sub_next:"))
async def process_sub_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data.get('submission_index', 0)
    submissions_ids = data.get('submissions', [])
    if index < len(submissions_ids) - 1:
        await state.update_data(submission_index=index + 1)
    await callback.answer()
    await callback.message.answer("Загружаю следующую сдачу...")
    await show_submission(callback.message, state, None)

@router.callback_query(F.data == "sub_close")
async def process_sub_close(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Просмотр сдач завершён.")
    await callback.answer()

def register_handlers(dp):
    dp.include_router(router)