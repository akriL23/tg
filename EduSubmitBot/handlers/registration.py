from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from services.user import get_or_create_user
from database.db import async_session
from sqlalchemy import select
from database.models import Group, GroupMember, User

router = Router()

class RegisterStudent(StatesGroup):
    waiting_for_surname = State()
    waiting_for_name = State()
    waiting_for_group = State()

@router.message(Command("register_student"))
async def cmd_register_student(message: Message, state: FSMContext):
    await message.answer("Введите вашу фамилию:")
    await state.set_state(RegisterStudent.waiting_for_surname)

@router.message(RegisterStudent.waiting_for_surname)
async def process_surname(message: Message, state: FSMContext):
    await state.update_data(surname=message.text.strip())
    await message.answer("Введите ваше имя:")
    await state.set_state(RegisterStudent.waiting_for_name)

@router.message(RegisterStudent.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введите название группы, к которой хотите присоединиться (или инвайт-код):")
    await state.set_state(RegisterStudent.waiting_for_group)

@router.message(RegisterStudent.waiting_for_group)
async def process_group(message: Message, state: FSMContext):
    data = await state.get_data()
    surname = data.get('surname')
    name = data.get('name')
    group_input = message.text.strip()
    full_name = f"{surname} {name}"
    async with async_session() as session:
        # get or create user
        user = await get_or_create_user(session, message.from_user.id, full_name, message.from_user.username or "")
        # try to find group by title or invite code
        result = await session.execute(select(Group).where((Group.title == group_input) | (Group.invite_code == group_input)))
        group = result.scalar_one_or_none()
        if not group:
            await message.answer(f"Группа «{group_input}» не найдена. Попросите преподавателя создать группу или пригласить вас по инвайт-коду.")
            await state.clear()
            return
        # check if already member
        result = await session.execute(select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == user.id))
        member = result.scalar_one_or_none()
        if member:
            await message.answer(f"Вы уже состоите в группе «{group.title}».")
            await state.clear()
            return
        # add as student
        new_member = GroupMember(group_id=group.id, user_id=user.id, role="student")
        session.add(new_member)
        await session.commit()
        await message.answer(f"Вы успешно зарегистрированы и добавлены в группу «{group.title}»!\nФИО: {full_name}")
    await state.clear()

def register_handlers(dp):
    dp.include_router(router)