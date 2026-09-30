from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from services.user import get_or_create_user, set_user_role, get_user
from database.db import async_session
from config import load_config
from keyboards.main_menu import get_main_keyboard

router = Router()
config = load_config()

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

Для администратора:
/create_group <название> - создать новую группу
/stats - статистика бота

Для преподавателя:
/my_groups - список моих групп
/new_assignment - создать новое задание
/submissions - просмотр сдач по заданию

Для студента:
/join <код> - присоединиться к группе по инвайт-коду
/my_assignments - мои активные задания
/my_submissions - мои сданные работы
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

def register_handlers(dp):
    dp.include_router(router)