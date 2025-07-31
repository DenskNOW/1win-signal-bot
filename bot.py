import os
import sqlite3
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from dotenv import load_dotenv
import aioschedule

# Загрузка переменных окружения
load_dotenv()

API_TOKEN = os.getenv("TOKEN")
if not API_TOKEN:
    logging.warning("Env var TOKEN is missing! Using fallback hardcoded TOKEN.")
    API_TOKEN = "8480410720:AAHfJ9hd-_aCetvn987BaMmBje2IoGrAhAw"

raw_admin = os.getenv("ADMIN_ID")
if not raw_admin:
    logging.warning("Env var ADMIN_ID is missing! Using fallback 8298051618.")
    ADMIN_ID = 8298051618
else:
    ADMIN_ID = int(raw_admin)

CHANNEL_ID = os.getenv("CHANNEL_ID") or "@your_channel"

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
""")
conn.commit()

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

@dp.message_handler(commands=["admin"])
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    await message.answer(f"👮 Админ-панель
Всего пользователей: {total}")

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
            await bot.send_message(uid, f"📡 <b>Сигнал:</b>
{text}")
        except Exception:
            continue
    await message.answer("✅ Сигнал отправлен.")

async def scheduled_job():
    cursor.execute("SELECT user_id FROM users WHERE deposited = 1")
    for (uid,) in cursor.fetchall():
        try:
            await bot.send_message(uid, "📡 <b>Авто-сигнал:</b>
Игра: Aviator
Коэффициент: 1.75")
        except Exception:
            continue

async def scheduler():
    aioschedule.every(10).minutes.do(scheduled_job)
    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(30)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler())
    executor.start_polling(dp, skip_updates=True)
