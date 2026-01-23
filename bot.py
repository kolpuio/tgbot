import os
import time
import re
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ChatPermissions, ChatMemberUpdated
from aiogram.utils import executor
from aiohttp import web

# ================================
# Настройки Telegram-бота
# ================================
API_TOKEN = os.environ.get("API_TOKEN")
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

MAX_WARNINGS = 3      # сколько нарушений до мута
MUTE_TIME = 600       # длительность мута в секундах (10 минут)
FLOOD_TIME = 3        # минимальный интервал между сообщениями одного пользователя
SPAM_LIMIT = 3        # сколько одинаковых сообщений подряд до удаления

user_warnings = {}
last_message_time = {}
last_messages = {}

# ================================
# Проверка на ссылки
# ================================
def has_link(text):
    pattern = r"(https?://\S+|t\.me/\S+|www\.\S+|\S+\.\w+)"
    return re.search(pattern, text)

# ================================
# Основная функция модерации
# ================================
@dp.message_handler()
async def auto_moderate(message: types.Message):
    if not message.text:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.lower()
    now = time.time()

    # антифлуд
    if user_id in last_message_time and now - last_message_time[user_id] < FLOOD_TIME:
        await message.delete()
        register_violation(user_id, chat_id)
        return
    last_message_time[user_id] = now

    # антиспам (повтор сообщений)
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

# ================================
# Учёт нарушений и мут
# ================================
def register_violation(user_id, chat_id):
    user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
    if user_warnings[user_id] >= MAX_WARNINGS:
        until = int(time.time()) + MUTE_TIME
        asyncio.create_task(
            bot.restrict_chat_member(
                chat_id,
                user_id,
                ChatPermissions(can_send_messages=False),
                until_date=until
            )
        )
        user_warnings[user_id] = 0

# ================================
# Приветствие новых участников
# ================================
@dp.chat_member_handler()
async def welcome_new_member(chat_member: ChatMemberUpdated):
    if chat_member.new_chat_member.status == "member":
        chat_id = chat_member.chat.id
        user_name = chat_member.from_user.full_name
        await bot.send_message(
            chat_id,
            f"Привет, {user_name}! Пожалуйста, ознакомьтесь с правилами группы 📜"
        )

# ================================
# Пустой HTTP-сервер для Render
# ================================
async def handle(request):
    return web.Response(text="Bot is running ✅")

def start_web_server():
    port = int(os.environ.get("PORT", 5000))
    app = web.Application()
    app.router.add_get("/", handle)
    web.run_app(app, port=port)

# ================================
# Запуск
# ================================
if __name__ == "__main__":
    # Запуск веб-сервера в отдельном потоке
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, start_web_server)

    print("🤖 Telegram Bot запущен!")
    executor.start_polling(dp, skip_updates=True)