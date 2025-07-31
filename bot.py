import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
API_TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")

import logging
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import aioschedule
import asyncio

# Проверка обязательных переменных
if not API_TOKEN:
    raise RuntimeError("Env var TOKEN is missing! Проверьте .env или Variables на хостинге.")

# Инициализация бота
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

# База данных
os.makedirs("db", exist_ok=True)
conn = sqlite3.connect("db/database.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    lang TEXT,
    registered INTEGER DEFAULT 0,
    deposited INTEGER DEFAULT 0
)
"""
)
conn.commit()

# Команда /start
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, lang) VALUES (?, ?, ?)",
        (user_id, username, "ru")
    )
    conn.commit()
    await message.answer("👋 Добро пожаловать! Проверяем подписку...")

# Админ-панель
@dp.message_handler(commands=["admin"])
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    # Корректная многострочная f-строка
    await message.answer(f"""👮 Админ-панель
Всего пользователей: {total}""")

# Ручная рассылка сигнала
@dp.message_handler(commands=["send"])
async def send_signal(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.get_args()
    if not text:
        await message.answer("Введите текст сигнала: /send Сигнал...")
        return
    cursor.execute("SELECT user_id FROM users WHERE deposited = 1")
    for (uid,) in cursor.fetchall():
        try:
            await bot.send_message(uid, f"📡 <b>Сигнал:</b>\n{text}")
        except Exception:
            continue
    await message.answer("✅ Сигнал отправлен.")

# Авто-рассылка каждые 10 минут
async def scheduled_job():
    cursor.execute("SELECT user_id FROM users WHERE deposited = 1")
    for (uid,) in cursor.fetchall():
        try:
            await bot.send_message(
                uid,
                "📡 <b>Авто-сигнал:</b>\nИгра: Aviator\nКоэффициент: 1.75"
            )
        except Exception:
            continue

async def scheduler():
    aioschedule.every(10).minutes.do(scheduled_job)
    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(30)

# Запуск бота и планировщика
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler())
    executor.start_polling(dp, skip_updates=True)