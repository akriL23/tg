import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from services.user import get_or_create_user, set_user_role, get_user, get_active_assignments_for_student, create_submission, get_submission_by_id, add_submission_file_version
from services.assignment import get_submission_files
from services.assignment import get_assignment_by_id
from services.group import get_groups_by_teacher, get_group_by_id
from database.db import async_session
from keyboards.main_menu import get_main_keyboard
from database.models import UserRole, MemberRole

logger = logging.getLogger(__name__)

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
        # Debug: print role
        print(f"DEBUG: user {user.telegram_id} role from DB: {user.role}")
    if user.role == UserRole.TEACHER:
        await message.answer(
            "Вы вошли как преподаватель.\n"
            "Доступные команды: /my_groups, /create_group, /delete_group, /new_assignment, /delete_assignment, /submissions, /help",
            reply_markup=get_main_keyboard(user.role.value)
        )
    elif user.role == UserRole.ADMIN:
        await message.answer(
            "Вы вошли как администратор.\n"
            "Доступные команды: /list_all, /stats, /admin, /create_group, /delete_group, /help",
            reply_markup=get_main_keyboard(user.role.value)
        )
    else:
        await message.answer("Вы вошли как студент.\nДля присоединения к группе используйте инвайт-код: /join <code>\nИли перейдите по ссылке-приглашению.\n/help для списка команд.", reply_markup=get_main_keyboard(user.role.value))

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """
Доступные команды:
/start - начать работу с ботом
/help - показать эту справку
/menu - показать главное меню (кнопки)

Для администратора:
/create_group - создать новую группу (интерактивно)
/delete_group - удалить группу (интерактивно)
/list_all - показать все группы и задания
/stats - статистика бота

Для преподавателя:
/my_groups - список моих групп
/new_assignment - создать новое задание (интерактивно)
/delete_assignment - удалить задание (интерактивно)
/submissions - просмотр и оценка сдач

Для студента:
/join <код> - присоединиться к группе по инвайт-коду
/register_student - регистрация через FSM (фамилия, имя, группа)
/my_assignments - мои активные задания
/my_submissions - мои сдачи
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
            await message.answer("Главное меню:", reply_markup=get_main_keyboard(user.role.value))
        else:
            await message.answer("Сначала выполните /start для регистрации.")

# Reply keyboard button handlers
@router.message(F.text == "Создать группу")
async def btn_create_group(message: Message, state: FSMContext):
    from handlers.group import cmd_create_group
    await cmd_create_group(message, state)

@router.message(F.text == "Мои группы")
async def btn_my_groups(message: Message):
    from handlers.group import cmd_my_groups
    await cmd_my_groups(message)

@router.message(F.text == "Удалить группу")
async def btn_delete_group(message: Message, state: FSMContext):
    from handlers.group import cmd_delete_group
    await cmd_delete_group(message, state)

@router.message(F.text == "Создать задание")
async def btn_new_assignment(message: Message, state: FSMContext):
    from handlers.assignment import cmd_new_assignment
    await cmd_new_assignment(message, state)

@router.message(F.text == "Удалить задание")
async def btn_delete_assignment(message: Message, state: FSMContext):
    from handlers.assignment import cmd_delete_assignment
    await cmd_delete_assignment(message, state)

@router.message(F.text == "Посмотреть сдачи")
async def btn_submissions(message: Message, state: FSMContext):
    from handlers.assignment import cmd_submissions
    await cmd_submissions(message, state)

@router.message(F.text == "Панель админа")
async def btn_admin_panel(message: Message):
    from handlers.admin import cmd_admin_menu
    await cmd_admin_menu(message)

@router.message(F.text == "Список всего")
async def btn_list_all(message: Message):
    from handlers.admin import cmd_list_all
    await cmd_list_all(message)

@router.message(F.text == "Статистика")
async def btn_stats(message: Message):
    from handlers.admin import cmd_stats
    await cmd_stats(message)

@router.message(F.text == "Помощь")
async def btn_help(message: Message):
    await cmd_help(message)

@router.message(F.text == "Мои задания")
async def btn_my_assignments(message: Message, state: FSMContext):
    await cmd_my_assignments(message, state)

@router.message(F.text == "Мои сдачи")
async def btn_my_submissions(message: Message, state: FSMContext):
    await cmd_my_submissions(message, state)

@router.message(F.text == "Присоединиться к группе")
async def btn_join(message: Message):
    await message.answer("Отправьте инвайт-код в формате: /join <код>")

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
        if not user or user.role != UserRole.STUDENT:
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
    # Check file size
    from config import load_config
    config = load_config()
    if file_size and file_size > config.max_file_size:
        await message.answer(
            f"Файл слишком большой ({file_size // (1024*1024)} МБ). "
            f"Максимальный размер: {config.max_file_size // (1024*1024)} МБ."
        )
        return
    data = await state.get_data()
    assignment_id = data.get('assignment_id')
    async with async_session() as session:
        # Check if student already has a submission for this assignment
        from sqlalchemy import select
        from database.models import Submission
        result = await session.execute(
            select(Submission).where(Submission.assignment_id == assignment_id, Submission.user_id == message.from_user.id)
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
        # Notify teacher if enabled
        config = load_config()
        if config.notify_teacher_on_submit:
            assignment = await get_assignment_by_id(session, assignment_id)
            if assignment:
                # Get teacher from group
                from services.group import get_group_by_id
                group = await get_group_by_id(session, assignment.group_id)
                if group:
                    teacher = await get_user(session, group.teacher_id)
                    if teacher:
                        try:
                            student = await get_user(session, message.from_user.id)
                            student_name = student.full_name if student else f"ID:{message.from_user.id}"
                            await message.bot.send_message(
                                chat_id=teacher.telegram_id,
                                text=f"📥 Новая сдача задания «{assignment.title}»\n"
                                     f"Студент: {student_name}\n"
                                     f"Группа: {group.title}\n"
                                     f"Время: {submission.submitted_at.strftime('%d.%m.%Y %H:%M')}"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to notify teacher {teacher.telegram_id}: {e}")
    await state.clear()

@router.message(Command("my_submissions"))
async def cmd_my_submissions(message: Message, state: FSMContext):
    async with async_session() as session:
        user = await get_user(session, message.from_user.id)
        if not user or user.role != UserRole.STUDENT:
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