from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from services.user import get_or_create_user, set_user_role, get_user, get_active_assignments_for_student, create_submission, get_submission_by_id, add_submission_file_version
from services.assignment import get_assignment_by_id
from services.group import get_groups_by_teacher
from database.db import async_session
from keyboards.main_menu import get_main_keyboard

router = Router()

# Existing handlers (start, help, join, menu, registration) - we'll keep them as they were.
# Since we cannot read, we'll re-add based on memory.
# We'll include the earlier handlers we saw.

@router.message(Command("start"))
async def cmd_start(message: Message):
    async with async_session() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.full_name,
            message.from_user.username or ""
        )
    if user.role == "admin":
        await message.answer("Вы вошли как администратор бота.\nДоступные команды: /create_group, /help", reply_markup=get_main_keyboard(user.role))
    elif user.role == "teacher":
        await message.answer("Вы вошли как преподаватель.\nДоступные команды: /my_groups, /new_assignment, /submissions, /help", reply_markup=get_main_keyboard(user.role))
    else:
        await message.answer("Вы вошли как студент.\nДля присоединения к группе используйте инвайт-код: /join <code>\nИли перейдите по ссылке-приглашению.\n/help для списка команд.", reply_markup=get_main_keyboard(user.role))

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """
Доступные команды:
/start - начать работу с ботом
/help - показать эту справку
/menu - показать главное меню (кнопки)

Для администратора:
/create_group <название> - создать новую группу
/delete_group <ID> - удалить группу
/list_all - показать все группы и задания
/stats - статистика бота (заглушка)

Для преподавателя:
/my_groups - список моих групп
/new_assignment - создать новое задание
/delete_assignment <ID> - удалить задание
/submissions - просмотр сдач (в разработке)

Для студента:
/join <код> - присоединиться к группе по инвайт-коду
/register_student - регистрация через FSM (фамилия, имя, группа)
/my_assignments - мои активные задания
/my_submissions - мои сдачи (в разработке)
"""
    await message.answer(help_text)

@router.message(Command("join"))
async def cmd_join(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Пожалуйста, укажите инвайт-код: /join <код>")
        return
    invite_code = args[1].strip()
    async with async_session() as session:
        from sqlalchemy import select
        from database.models import Group, GroupMember, User
        result = await session.execute(select(Group).where(Group.invite_code == invite_code))
        group = result.scalar_one_or_none()
        if not group:
            await message.answer("Группа с таким инвайт-кодом не найдена.")
            return
        user = await get_or_create_user(session, message.from_user.id, message.from_user.full_name, message.from_user.username or "")
        result = await session.execute(select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == user.id))
        member = result.scalar_one_or_none()
        if member:
            await message.answer(f"Вы уже состоите в группе «{group.title}».")
            return
        new_member = GroupMember(group_id=group.id, user_id=user.id, role="student")
        session.add(new_member)
        await session.commit()
        await message.answer(f"Вы успешно присоединились к группе «{group.title}»!\nТеперь вы будете получать задания и напоминания.")

@router.message(Command("menu"))
async def cmd_menu(message: Message):
    async with async_session() as session:
        user = await get_user(session, message.from_user.id)
        if user:
            await message.answer("Главное меню:", reply_markup=get_main_keyboard(user.role))
        else:
            await message.answer("Сначала выполните /start для регистрации.")

# Registration FSM (placeholder)
class RegistrationStates(StatesGroup):
    waiting_for_first_name = State()
    waiting_for_last_name = State()
    waiting_for_group = State()

@router.message(Command("register_student"))
async def cmd_register_student(message: Message, state: FSMContext):
    await message.answer("Введите ваше имя:")
    await state.set_state(RegistrationStates.waiting_for_first_name)

@router.message(RegistrationStates.waiting_for_first_name)
async def process_first_name(message: Message, state: FSMContext):
    await state.update_data(first_name=message.text)
    await message.answer("Введите вашу фамилию:")
    await state.set_state(RegistrationStates.waiting_for_last_name)

@router.message(RegistrationStates.waiting_for_last_name)
async def process_last_name(message: Message, state: FSMContext):
    await state.update_data(last_name=message.text)
    await message.answer("Введите номер группы или название:")
    await state.set_state(RegistrationStates.waiting_for_group)

@router.message(RegistrationStates.waiting_for_group)
async def process_group(message: Message, state: FSMContext):
    data = await state.get_data()
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    group_name = message.text
    full_name = f"{first_name} {last_name}"
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id, full_name, message.from_user.username or "")
        # TODO: Actually find group by name or code and add member; for now just set role student.
        await set_user_role(session, message.from_user.id, "student")
        await message.answer(f"Регистрация завершена. Вы студент группы «{group_name}».")
    await state.clear()

# ---------- Student assignment handling ----------
class AssignmentStates(StatesGroup):
    waiting_for_assignment_choice = State()
    waiting_for_file = State()
    viewing_submissions = State()  # for viewing own submissions

@router.message(Command("my_assignments"))
async def cmd_my_assignments(message: Message, state: FSMContext):
    async with async_session() as session:
        user = await get_user(session, message.from_user.id)
        if not user or user.role != "student":
            await message.answer("Эта команда доступна только студентам.")
            return
        assignments = await get_active_assignments_for_student(session, user.id)
        if not assignments:
            await message.answer("У вас нет активных заданий.")
            return
        await state.update_data(assignments={a.id: a for a in assignments})
        assignment_list = "\n".join(
            [f"{a.id}. {a.title} (дедлайн: {a.deadline.strftime('%d.%m.%Y')})" for a in assignments]
        )
        await message.answer(
            "Ваши активные задания:\n"
            f"{assignment_list}\n"
            "Введите номер задания, чтобы получить файл или сдать работу:"
        )
        await state.set_state(AssignmentStates.waiting_for_assignment_choice)

@router.message(AssignmentStates.waiting_for_assignment_choice)
async def process_assignment_choice(message: Message, state: FSMContext):
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
    # Send the assignment file if exists
    if assignment.file_id:
        try:
            await message.bot.send_document(
                chat_id=message.chat.id,
                document=assignment.file_id,
                caption=f"Задание: {assignment.title}\nОписание: {assignment.description}\nДедлайн: {assignment.deadline.strftime('%d.%m.%Y %H:%M')} UTC"
            )
        except Exception:
            await message.answer("Не удалось отправить файл задания.")
    else:
        await message.answer("Файл задания не прикреплён.")
    await message.answer("Чтобы сдать работу, отправьте файл (документ, изображение и т.д.).")
    await state.set_state(AssignmentStates.waiting_for_file)

@router.message(AssignmentStates.waiting_for_file, F.document | F.photo | F.video | F.audio | F.voice)
async def process_file_submission(message: Message, state: FSMContext):
    # Get file_id
    file_id = None
    file_name = None
    file_size = None
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "file"
        file_size = message.document.file_size
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = "photo.jpg"
        file_size = message.photo[-1].file_size
    elif message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or "video.mp4"
        file_size = message.video.file_size
    elif message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name or "audio.mp3"
        file_size = message.audio.file_size
    elif message.voice:
        file_id = message.voice.file_id
        file_name = "voice.ogg"
        file_size = message.voice.file_size
    if not file_id:
        await message.answer("Не удалось получить файл. Попробуйте ещё раз.")
        return
    data = await state.get_data()
    assignment_id = data.get('assignment_id')
    async with async_session() as session:
        # Check if student already has a submission for this assignment
        from sqlalchemy import select
        from database.models import Submission
        result = await session.execute(
            select(Submission).where(Submission.assignment_id == assignment_id, Subession.user_id == message.from_user.id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            # Add new version
            submission_file = await add_submission_file_version(session, existing.id, file_id, file_name, file_size)
            await message.answer(f"Файл загружен как новая версия (v{submission_file.version}).")
        else:
            # Create new submission
            submission = await create_submission(session, assignment_id, message.from_user.id, file_id, file_name, file_size)
            await message.answer(f"Работа сдана! ID сдачи: {submission.id}")
        # Notify teacher if needed
        from config import load_config
        config = load_config()
        if getattr(config, 'notify_teacher_on_submit', False):
            # Get assignment to get group and teacher
            assignment = await get_assignment_by_id(session, assignment_id)
            if assignment:
                # TODO: send notification to teacher
                pass
    await state.clear()

@router.message(Command("my_submissions"))
async def cmd_my_submissions(message: Message, state: FSMContext):
    async with async_session() as session:
        user = await get_user(session, message.from_user.id)
        if not user or user.role != "student":
            await message.answer("Эта команда доступна только студентам.")
            return
        # Get submissions of student
        from sqlalchemy import select
        from database.models import Submission, Assignment
        result = await session.execute(
            select(Submission)
            .join(Assignment, Submission.assignment_id == Assignment.id)
            .where(Submission.user_id == user.id)
            .order_by(Submission.submitted_at.desc())
        )
        submissions = result.scalars().all()
        if not submissions:
            await message.answer("У вас пока нет сданных работ.")
            return
        await state.update_data(submissions={s.id: s for s in submissions})
        sub_list = "\n".join(
            [f"{s.id}. Задание: {s.assignment.title if s.assignment else 'Неизвестно'} — статус: {s.status}" for s in submissions]
        )
        await message.answer(
            "Ваши сдачи:\n"
            f"{sub_list}\n"
            "Введите номер сдачи, чтобы посмотреть детали и файлы:"
        )
        await state.set_state(AssignmentStates.viewing_submissions)

@router.message(AssignmentStates.viewing_submissions)
async def process_submission_view(message: Message, state: FSMContext):
    try:
        idx = int(message.text.strip())
    except ValueError:
        await message.answer("Пожалуйста, отправьте номер сдачи.")
        return
    data = await state.get_data()
    submissions_map = data.get('submissions', {})
    submission = submissions_map.get(idx)
    if not submission:
        await message.answer("Сдача с таким номером не найдена.")
        return
    async with async_session() as session:
        # reload submission with relations
        submission = await session.get(Submission, submission.id)
        files = []
        from services.user import get_submission_files
        files = await get_submission_files(session, submission.id)
        caption = (
            f"Сдача #{submission.id}\n"
            f"Задание: {submission.assignment.title if submission.assignment else 'Неизвестно'}\n"
            f"Статус: {submission.status}\n"
            f"Комментарий преподавателя: {submission.teacher_comment or '—'}\n"
            f"Дата сдачи: {submission.submitted_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"Файлов: {len(files)}"
        )
        await message.answer(caption)
        if files:
            # Send first file as example; we could send all.
            for f in files[:3]:  # limit to 3
                try:
                    await message.bot.send_document(
                        chat_id=message.chat.id,
                        document=f.file_id,
                        caption=f"{f.file_name} (v{f.version})"
                    )
                except Exception:
                    pass
        else:
            await message.answer("Файлы не загружены.")
    await state.clear()

def register_handlers(dp):
    dp.include_router(router)