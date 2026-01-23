import os
import time
import re
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ChatPermissions, ChatMemberUpdated
from aiohttp import web

# ================================
# Настройки бота
# ================================
API_TOKEN = os.environ.get("API_TOKEN")  # Токен из переменной окружения
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # Например: https://your-app.onrender.com/webhook/<token>
PORT = int(os.environ.get("PORT", 5000))

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

MAX_WARNINGS = 3
MUTE_TIME = 600
FLOOD_TIME = 3
SPAM_LIMIT = 3

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
# Модерация сообщений
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

# ================================
# Учет нарушений и мут
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
# Webhook для Render
# ================================
async def handle(request):
    update = types.Update(**await request.json())
    await dp.process_update(update)
    return web.Response()

app = web.Application()
app.router.add_post(WEBHOOK_PATH, handle)

# ================================
# Запуск веб-сервера и установка webhook
# ================================
async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_cleanup(app):
    await bot.delete_webhook()

app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)

if __name__ == "__main__":
    web.run_app(app, port=PORT)