from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from services.group import create_group
from services.user import get_user
from database.db import async_session

router = Router()

class CreateGroup(StatesGroup):
    waiting_for_title = State()

@router.message(Command("create_group"))
async def cmd_create_group(message: Message, state: FSMContext):
    # check if user is teacher or admin
    async with async_session() as session:
        user = await get_user(session, message.from_user.id)
        if not user or user.role not in ("teacher", "admin"):
            await message.answer("Только преподаватели и администраторы могут создавать группы.")
            return
    await message.answer("Введите название группы:")
    await state.set_state(CreateGroup.waiting_for_title)

@router.message(CreateGroup.waiting_for_title)
async def process_title(message: Message, state: FSMContext):
    title = message.text.strip()
    async with async_session() as session:
        user = await get_user(session, message.from_user.id)
        group = await create_group(session, title, user.id)
    await message.answer(
        f"Группа «{group.title}» успешно создана!\n"
        f"Инвайт-код: <code>{group.invite_code}</code>\n"
        f"Распространите этот код среди студентов, чтобы они могли присоединиться.",
        parse_mode="HTML"
    )
    await state.clear()

def register_handlers(dp):
    dp.include_router(router)