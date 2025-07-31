import os
from dotenv import load_dotenv
load_dotenv()

import asyncio
import requests
import hashlib
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
import aioschedule

# --------------- ПЛАТФОРМА 1WIN ------------------
PLATFORM_NAME = "1win"
PLATFORM_REF_URL = "https://lkis.cc/0105"
PLATFORM_API_KEY = os.getenv("PLATFORM_API_KEY")
PLATFORM_API_URL = "https://partner.1win.xyz/api/v1/stats"

TOKEN = os.getenv("TOKEN")
CHANNEL_USERNAME = "@trghfssh"
ADMIN_IDS = [8298051618]  # замените на реальные ID

# ----------- ИГРЫ -------------------
crash_games = ["Aviator", "Lucky Jet", "Avia Masters", "Astronaut"]
mines_games = ["Mines", "Mi Mines", "New Mines", "Royal Mines"]
other_games = [
    "Dice", "Balloon", "Color Prediction", "Tropicana",
    "King Thimbles", "Penalty Shoot", "Goal", "Bombucks",
    "Chicken Road", "Football X"
]
games = crash_games + mines_games + other_games

# ----------- БАЗА ДАННЫХ ------------
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    lang TEXT,
    registered INTEGER DEFAULT 0,
    deposited INTEGER DEFAULT 0
)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS subscriptions (
    user_id INTEGER,
    game TEXT
)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT,
    signal TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)""")
conn.commit()

# ----------- ЯЗЫКИ ------------
LANGUAGES = {
    'ru': {
        'welcome': "Добро пожаловать! Пожалуйста, подпишитесь на наш канал и зарегистрируйтесь:",
        'check': "Проверить регистрацию и депозит",
        'access_granted': "✅ Доступ открыт. Получайте сигналы!",
        'access_denied': "❌ Регистрация или депозит не обнаружен.",
        'sub_required': "❗ Подпишитесь на канал и попробуйте снова.",
        'choose_lang': "Выберите язык:"
    },
    'en': {
        'welcome': "Welcome! Please subscribe to our channel and register:",
        'check': "Check registration and deposit",
        'access_granted': "✅ Access granted. Receive your signals!",
        'access_denied': "❌ Registration or deposit not found.",
        'sub_required': "❗ Please subscribe to the channel and try again.",
        'choose_lang': "Choose your language:"
    }
}

# ----------- СОСТОЯНИЯ FSM ------------
class UserState(StatesGroup):
    choosing_language = State()

# ----------- ИНИЦИАЛИЗАЦИЯ ------------
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())

# ----------- /start ------------
@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="English", callback_data="lang_en")]
    ])
    await message.answer("Choose your language / Выберите язык:", reply_markup=keyboard)
    await state.set_state(UserState.choosing_language)

@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def language_chosen(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    user = callback.from_user
    utm_label = hashlib.sha256(str(user.id).encode()).hexdigest()[:10]
    reg_link = f"{PLATFORM_REF_URL}?utm={utm_label}"
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, lang) VALUES (?, ?, ?)",
                   (user.id, user.username, lang))
    cursor.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user.id))
    for g in games:
        cursor.execute("INSERT OR IGNORE INTO subscriptions (user_id, game) VALUES (?, ?)", (user.id, g))
    conn.commit()
    await state.update_data(lang=lang, utm=utm_label)
    text = LANGUAGES[lang]['welcome']
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LANGUAGES[lang]['check'], callback_data="check_access")]
    ])
    await callback.message.answer(f"{text}\n➡️ {reg_link}", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "check_access")
async def check_access(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = data.get('lang', 'ru')
    utm = data.get('utm')
    user_id = callback.from_user.id
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status not in ["member", "administrator", "creator"]:
            await callback.message.answer(LANGUAGES[lang]['sub_required'])
            return
    except:
        await callback.message.answer("Subscription check error.")
        return
    reg, dep = await is_registered_and_deposited(utm)
    cursor.execute("UPDATE users SET registered=?, deposited=? WHERE user_id=?",
                   (int(reg), int(dep), user_id))
    conn.commit()
    if reg and dep:
        await callback.message.answer(LANGUAGES[lang]['access_granted'])
        await callback.message.answer("📡 <b>Сигналы:</b>\\n🎯 Aviator: 1.75 через 2 мин\\n💥 Dice: Red через 3 хода")
    else:
        await callback.message.answer(LANGUAGES[lang]['access_denied'])

async def is_registered_and_deposited(utm_label):
    try:
        response = requests.get(PLATFORM_API_URL, headers={"Authorization": f"Bearer {PLATFORM_API_KEY}"})
        if response.status_code == 200:
            data = response.json()
            for user in data.get("users", []):
                if user.get("utm") == utm_label:
                    is_reg = True
                    is_dep = float(user.get("deposits", 0)) > 0
                    return (is_reg, is_dep)
    except Exception as e:
        logging.error(f"API error: {e}")
    return (False, False)

# Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
