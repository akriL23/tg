from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard(role: str) -> ReplyKeyboardMarkup:
    if role == "admin":
        keyboard = [
            [KeyboardButton(text="Создать группу"), KeyboardButton(text="Мои группы")],
            [KeyboardButton(text="Удалить группу"), KeyboardButton(text="Статистика")],
            [KeyboardButton(text="Панель админа"), KeyboardButton(text="Список всего")],
            [KeyboardButton(text="Помощь")]
        ]
    elif role == "teacher":
        keyboard = [
            [KeyboardButton(text="Мои группы"), KeyboardButton(text="Создать задание")],
            [KeyboardButton(text="Удалить группу"), KeyboardButton(text="Удалить задание")],
            [KeyboardButton(text="Посмотреть сдачи"), KeyboardButton(text="Помощь")]
        ]
    else:  # student
        keyboard = [
            [KeyboardButton(text="Мои задания"), KeyboardButton(text="Присоединиться к группе")],
            [KeyboardButton(text="Мои сдачи"), KeyboardButton(text="Помощь")]
        ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)