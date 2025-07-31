import os
import logging
import sqlite3
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import aioschedule
from dotenv import load_dotenv

# Загрузка .env
load_dotenv()

# Получение переменных окружения
API_TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8298051618"))
CHANNEL_ID = os.getenv("CHANNEL_ID", "@your_channel")

if not API_TOKEN:
    raise RuntimeError("Env var TOKEN is missing!")

# Инициализация бота
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

# Подключение к БД
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

# /start
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

# /admin
@dp.message_handler(commands=["admin"])
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    await message.answer(f"👮 Админ-панель\nВсего пользователей: {total}")

# /send
@dp.message_handler(commands=["send"])
async def send
