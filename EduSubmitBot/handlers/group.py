from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.group import create_group, get_groups_by_teacher, delete_group
from services.user import get_user
from database.db import async_session
from sqlalchemy import select
from database.models import Group

router = Router()

class CreateGroup(StatesGroup):
    waiting_for_title = State()

class DeleteGroup(StatesGroup):
    waiting_for_confirmation = State()

@router.message(Command("create_group"))
async def cmd_create_group(message: Message, state: FSMContext):
    # check if user is teacher or admin
    async with async_session() as session:
        user = await get_user(session, message.from_user.id)
        if not user or user.role.value not in ("teacher", "admin"):
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

@router.message(Command("my_groups"))
async def cmd_my_groups(message: Message):
    async with async_session() as session:
        user = await get_user(session, message.from_user.id)
        if not user or user.role.value not in ("teacher", "admin"):
            await message.answer("Эта команда доступна только преподавателям и администраторам.")
            return
        groups = await get_groups_by_teacher(session, user.id)
        if not groups:
            await message.answer("У вас пока нет групп. Создайте группу через /create_group.")
            return
        group_list = "\n".join([
            f"{g.id}. {g.title} (код: {g.invite_code})"
            for g in groups
        ])
        await message.answer(f"Ваши группы:\n{group_list}")

@router.message(Command("delete_group"))
async def cmd_delete_group(message: Message, state: FSMContext):
    async with async_session() as session:
        user = await get_user(session, message.from_user.id)
        if not user or user.role.value not in ("teacher", "admin"):
            await message.answer("Только преподаватели и администраторы могут удалять группы.")
            return
        groups = await get_groups_by_teacher(session, user.id)
        if not groups:
            await message.answer("У вас нет групп для удаления.")
            return
        # Build inline keyboard
        builder = InlineKeyboardBuilder()
        for g in groups:
            builder.button(text=f"{g.title} (ID:{g.id})", callback_data=f"delgroup_{g.id}")
        builder.adjust(1)
        await message.answer(
            "Выберите группу для удаления:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(DeleteGroup.waiting_for_confirmation)

@router.callback_query(F.data.startswith("delgroup_"), DeleteGroup.waiting_for_confirmation)
async def process_delete_group(callback: CallbackQuery, state: FSMContext):
    group_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        user = await get_user(session, callback.from_user.id)
        if not user or user.role.value not in ("teacher", "admin"):
            await callback.answer("Доступ запрещён.", show_alert=True)
            return
        # Verify ownership
        group = await session.get(Group, group_id)
        if not group or group.teacher_id != user.id:
            await callback.answer("Группа не найдена или у вас нет прав на её удаление.", show_alert=True)
            return
        await delete_group(session, group_id)
    await callback.message.edit_text(f"Группа с ID {group_id} удалена.")
    await state.clear()
    await callback.answer()

def register_handlers(dp):
    dp.include_router(router)