from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from services.assignment import create_assignment, get_students_in_group
from services.group import get_groups_by_teacher
from services.user import get_user
from database.db import async_session
from datetime import datetime, timedelta

router = Router()

class NewAssignment(StatesGroup):
    waiting_for_group = State()
    waiting_for_file = State()
    waiting_for_confirmation = State()  # optional

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

def register_handlers(dp):
    dp.include_router(router)