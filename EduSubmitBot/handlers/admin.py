from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.admin import (
    get_all_groups,
    get_all_assignments,
    delete_group,
    delete_assignment,
    is_admin,
    set_user_role,
    remove_student_from_group,
    get_stats,
)
from services.user import get_user
from services.group import get_group_by_id, get_students_in_group
from services.assignment import get_assignment_by_id
from database.db import async_session
from sqlalchemy import select
from database.models import User, GroupMember

router = Router()

class AdminActions(StatesGroup):
    waiting_for_set_admin_target = State()
    waiting_for_remove_group = State()
    waiting_for_remove_student = State()
    waiting_for_remove_assignment = State()

def groups_keyboard(groups):
    builder = InlineKeyboardBuilder()
    for g in groups:
        builder.button(text=f"{g.title} (ID:{g.id})", callback_data=f"remgroup_{g.id}")
    builder.adjust(2)
    return builder.as_markup()

def assignments_keyboard(assignments):
    builder = InlineKeyboardBuilder()
    for a in assignments:
        builder.button(
            text=f"{a.title} (ID:{a.id})",
            callback_data=f"remassign_{a.id}"
        )
    builder.adjust(1)
    return builder.as_markup()

def students_in_group_keyboard(students):
    builder = InlineKeyboardBuilder()
    for s in students:
        label = f"{s.full_name or s.username or s.telegram_id}"
        builder.button(text=label, callback_data=f"remstu_{s.telegram_id}")
    builder.adjust(1)
    return builder.as_markup()

def admin_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Удалить группу", callback_data="adm_del_group")
    builder.button(text="🗑 Удалить задание", callback_data="adm_del_assignment")
    builder.button(text="👑 Назначить администратора", callback_data="adm_set_admin")
    builder.button(text="🚫 Удалить студента из группы", callback_data="adm_rem_student")
    builder.button(text="📋 Список всех групп и заданий", callback_data="adm_list_all")
    builder.button(text="📊 Статистика", callback_data="adm_stats")
    builder.adjust(2)
    return builder.as_markup()

async def check_admin(message: Message) -> bool:
    async with async_session() as session:
        return await is_admin(session, message.from_user.id)

@router.message(Command("admin"))
async def cmd_admin_menu(message: Message):
    if not await check_admin(message):
        await message.answer("Доступ запрещён.")
        return
    await message.answer("Панель администратора:", reply_markup=admin_main_keyboard())

@router.message(Command("list_all"))
async def cmd_list_all(message: Message):
    if not await check_admin(message):
        await message.answer("Доступ запрещён.")
        return
    async with async_session() as session:
        groups = await get_all_groups(session)
        assignments = await get_all_assignments(session)
    text = "📚 Все группы:\n"
    if groups:
        for g in groups:
            text += f"• {g.title} (ID:{g.id})\n"
    else:
        text += "Нет групп.\n"
    text += "\n📝 Все задания:\n"
    if assignments:
        for a in assignments:
            text += f"• {a.title} (ID:{a.id}) в группе ID:{a.group_id}\n"
    else:
        text += "Нет заданий.\n"
    await message.answer(text)

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not await check_admin(message):
        await message.answer("Доступ запрещён.")
        return
    async with async_session() as session:
        stats = await get_stats(session)
    text = (
        "📊 Статистика бота:\n"
        f"👥 Пользователей: {stats['users']}\n"
        f"👥 Групп: {stats['groups']}\n"
        f"📝 Заданий: {stats['assignments']}\n"
        f"✅ Сдач: {stats['submissions']}\n"
    )
    await message.answer(text)

@router.callback_query(F.data == "adm_del_group")
async def adm_del_group_cb(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.message):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    groups = await get_all_groups(async_session())
    if not groups:
        await callback.message.edit_text("Групп нет.")
        await callback.answer()
        return
    await callback.message.edit_text(
        "Выберите группу для удаления:",
        reply_markup=groups_keyboard(groups)
    )
    await state.set_state(AdminActions.waiting_for_remove_group)
    await callback.answer()

@router.callback_query(F.data == "adm_del_assignment")
async def adm_del_assignment_cb(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.message):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    async with async_session() as session:
        assignments = await get_all_assignments(session)
    if not assignments:
        await callback.message.edit_text("Заданий нет.")
        await callback.answer()
        return
    await callback.message.edit_text(
        "Выберите задание для удаления:",
        reply_markup=assignments_keyboard(assignments)
    )
    await state.set_state(AdminActions.waiting_for_remove_assignment)
    await callback.answer()

@router.callback_query(F.data == "adm_set_admin")
async def adm_set_admin_cb(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.message):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    await callback.message.edit_text(
        "Введите Telegram‑ID или @username пользователя, которого нужно сделать администратором:\n"
        "Пример: 123456789  или  @newadmin"
    )
    await state.set_state(AdminActions.waiting_for_set_admin_target)
    await callback.answer()

@router.callback_query(F.data == "adm_rem_student")
async def adm_rem_student_cb(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.message):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    groups = await get_all_groups(async_session())
    if not groups:
        await callback.message.edit_text("Групп нет.")
        await callback.answer()
        return
    await callback.message.edit_text(
        "Выберите группу, из которой нужно удалить студента:",
        reply_markup=groups_keyboard(groups)
    )
    await state.set_state(AdminActions.waiting_for_remove_group)
    await callback.answer()

@router.callback_query(F.data == "adm_list_all")
async def adm_list_all_cb(callback: CallbackQuery):
    if not await check_admin(callback.message):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    async with async_session() as session:
        groups = await get_all_groups(session)
        assignments = await get_all_assignments(session)
    text = "📚 Все группы:\n"
    if groups:
        for g in groups:
            text += f"• {g.title} (ID:{g.id})\n"
    else:
        text += "Нет групп.\n"
    text += "\n📝 Все задания:\n"
    if assignments:
        for a in assignments:
            text += f"• {a.title} (ID:{a.id}) в группе ID:{a.group_id}\n"
    else:
        text += "Нет заданий.\n"
    await callback.message.edit_text(text)
    await callback.answer()

@router.callback_query(F.data == "adm_stats")
async def adm_stats_cb(callback: CallbackQuery):
    if not await check_admin(callback.message):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    async with async_session() as session:
        stats = await get_stats(session)
    text = (
        "📊 Статистика бота:\n"
        f"👥 Пользователей: {stats['users']}\n"
        f"👥 Групп: {stats['groups']}\n"
        f"📝 Заданий: {stats['assignments']}\n"
        f"✅ Сдач: {stats['submissions']}\n"
    )
    await callback.message.edit_text(text)
    await callback.answer()

@router.callback_query(F.data.startswith("remgroup_"), AdminActions.waiting_for_remove_group)
async def adm_remove_group_cb(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.message):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    group_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        await delete_group(session, group_id)
    await callback.message.edit_text(f"Группа с ID {group_id} удалена.")
    await state.clear()
    await callback.answer()

@router.callback_query(F.data.startswith("remassign_"), AdminActions.waiting_for_remove_assignment)
async def adm_remove_assignment_cb(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.message):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    assignment_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        await delete_assignment(session, assignment_id)
    await callback.message.edit_text(f"Задание с ID {assignment_id} удалено.")
    await state.clear()
    await callback.answer()

@router.message(AdminActions.waiting_for_set_admin_target)
async def adm_set_admin_input(message: Message, state: FSMContext):
    if not await check_admin(message):
        await message.answer("Доступ запрещён.")
        await state.clear()
        return
    target = message.text.strip()
    async with async_session() as session:
        if target.isdigit():
            tg_id = int(target)
        else:
            username = target.lstrip('@')
            result = await session.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()
            if not user:
                await message.answer("Пользователь с таким username не найден.")
                await state.clear()
                return
            tg_id = user.telegram_id
        await set_user_role(session, tg_id, "admin")
        await message.answer(f"Пользователь {tg_id} теперь администратор.")
    await state.clear()

@router.callback_query(F.data.startswith("remgroup_"), AdminActions.waiting_for_remove_group)
async def adm_choose_group_for_removal(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.message):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    group_id = int(callback.data.split("_")[1])
    await state.update_data(removal_group_id=group_id)
    async with async_session() as session:
        students = await get_students_in_group(session, group_id)
    if not students:
        await callback.message.edit_text("В этой группе нет студентов.")
        await state.clear()
        return
    await callback.message.edit_text(
        "Выберите студента, которого нужно удалить из группы:",
        reply_markup=students_in_group_keyboard(students)
    )
    await state.set_state(AdminActions.waiting_for_remove_student)
    await callback.answer()

@router.callback_query(F.data.startswith("remstu_"), AdminActions.waiting_for_remove_student)
async def adm_remove_student_cb(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback.message):
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    data = await state.get_data()
    group_id = data.get("removal_group_id")
    student_tg_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        await remove_student_from_group(session, group_id, student_tg_id)
        result = await session.execute(select(User).where(User.telegram_id == student_tg_id))
        student = result.scalar_one_or_none()
        name = student.full_name if student else str(student_tg_id)
    await callback.message.edit_text(
        f"Студент {name} (ID:{student_tg_id}) удалён из группы ID {group_id}."
    )
    await state.clear()
    await callback.answer()

def register_handlers(dp):
    dp.include_router(router)