import os
import time
from aiogram import Bot, Dispatcher, types
from aiogram.types import ChatPermissions
from aiogram.utils import executor

# Токен берём из переменной окружения
API_TOKEN = os.environ.get("API_TOKEN")
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Настройки бота
MAX_WARNINGS = 3
MUTE_TIME = 600
FLOOD_TIME = 3
SPAM_LIMIT = 3

# Хранение данных пользователей
user_warnings = {}
last_message_time = {}
last_messages = {}

# Проверка на ссылки
def has_link(text):
    import re
    pattern = r"(https?://\S+|t\.me/\S+|www\.\S+|\S+\.\w+)"
    return re.search(pattern, text)

# Основная функция модерации
@dp.message_handler()
async def auto_moderate(message: types.Message):
    if not message.text:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.lower()

    now = time.time()

    # антифлуд
    if user_id in last_message_time:
        if now - last_message_time[user_id] < FLOOD_TIME:
            await message.delete()
            register_violation(user_id, chat_id)
            return
    last_message_time[user_id] = now

    # антиспам
    last_text, count = last_messages.get(user_id, ("", 0))
    if text == last_text:
        count += 1
        last_messages[user_id] = (text, count)
        if count >= SPAM_LIMIT:
            await message.delete()
            register_violation(user_id, chat_id)
            last_messages[user_id] = ("", 0)
            return
    else:
        last_messages[user_id] = (text, 1)

    # ссылки
    if has_link(text):
        await message.delete()
        register_violation(user_id, chat_id)
        return

# Учёт нарушений и мут
def register_violation(user_id, chat_id):
    user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
    if user_warnings[user_id] >= MAX_WARNINGS:
        from asyncio import create_task
        until = int(time.time()) + MUTE_TIME
        create_task(
            bot.restrict_chat_member(
                chat_id,
                user_id,
                ChatPermissions(can_send_messages=False),
                until_date=until
            )
        )
        user_warnings[user_id] = 0

# Запуск бота
if __name__ == "__main__":
    print("🤖 Бот запущен в тихом режиме")
    executor.start_polling(dp, skip_updates=True)
