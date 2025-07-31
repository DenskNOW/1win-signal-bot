import datetime
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
PLATFORM_REF_URL = "https://1winclick.link/YOUR_REF"
PLATFORM_API_KEY = os.getenv("PLATFORM_API_KEY")
PLATFORM_API_URL = "https://partner.1win.xyz/api/v1/stats"

TOKEN = os.getenv("TOKEN")
CHANNEL_USERNAME = "@your_channel"
ADMIN_IDS = [123456789]  # замените на реальные ID

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

cursor.execute("""CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT,
    signal TEXT,
    time TEXT
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
    
cursor.execute("""CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT,
    signal TEXT,
    time TEXT
)""")

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
    
cursor.execute("""CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT,
    signal TEXT,
    time TEXT
)""")

conn.commit()
    if reg and dep:
        await callback.message.answer(LANGUAGES[lang]['access_granted'])
        await callback.message.answer("📡 <b>Сигналы:</b>
🎯 Aviator: 1.75 через 2 мин
💥 Dice: Red через 3 хода")
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



# ВСТАВЬ СЮДА: все импорты и настройки .env как раньше

# ЛОГИРОВАНИЕ В ФАЙЛ
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

# Функция рассылки сигналов
async def send_scheduled_signals():
    cursor.execute("SELECT game, signal FROM signals ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if not row:
        return
    game, signal = row
    msg = f"📡 <b>Сигнал:</b>\n🎮 {game}: {signal}"

    cursor.execute("SELECT user_id FROM subscriptions WHERE game=?", (game,))
    users = cursor.fetchall()

    for (uid,) in users:
        cursor.execute("SELECT deposited FROM users WHERE user_id=?", (uid,))
        dep = cursor.fetchone()
        if dep and dep[0]:
            try:
                await bot.send_message(uid, msg)
                logging.info(f"✅ Сигнал отправлен {uid}")
            except Exception as e:
                logging.warning(f"⚠️ Не удалось отправить пользователю {uid}: {e}")

# Планировщик
import aioschedule

async def scheduler():
    aioschedule.every(1).minutes.do(run_template_dispatch)
    aioschedule.every(10).minutes.do(send_scheduled_signals)
    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(1)

# Команда админа
@dp.message(lambda msg: msg.text == "/admin" and msg.from_user.id in ADMIN_IDS)
async def admin_panel(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить сигнал", callback_data="admin_add_signal")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="🧾 Шаблоны", callback_data="admin_templates")]
    ])
    await message.answer("🛠 Админ-панель", reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "admin_add_signal")
async def admin_add_signal_start(callback: types.CallbackQuery):
    await callback.message.answer("📥 Введите сигнал в формате:
<игра> | <сигнал>")
    await bot.session.storage.set_data(callback.from_user.id, {"awaiting_signal": True})

@dp.message(lambda msg: msg.from_user.id in ADMIN_IDS)
async def admin_add_signal_input(message: types.Message):
    state = await bot.session.storage.get_data(message.from_user.id)
    if not state or not state.get("awaiting_signal"):
        return
    try:
        game, signal = map(str.strip, message.text.split("|", 1))
        cursor.execute("INSERT INTO signals (game, signal) VALUES (?, ?)", (game, signal))
        
cursor.execute("""CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT,
    signal TEXT,
    time TEXT
)""")

conn.commit()
        await message.answer(f"✅ Сигнал добавлен: {game} — {signal}")
        await bot.session.storage.set_data(message.from_user.id, {})
    except:
        await message.answer("❌ Неверный формат. Используй: <игра> | <сигнал>")

# ЗАМЕНА main():
async def main():
    logging.info("🚀 Бот запускается...")
    await asyncio.gather(
        dp.start_polling(bot),
        scheduler()
    )

if __name__ == "__main__":
    asyncio.run(main())

# --------- ШАБЛОННЫЕ СИГНАЛЫ ---------
signal_templates_data = [
    {"game": "Aviator", "signal": "1.90 через 3 мин", "time": "10:00"},
    {"game": "Dice", "signal": "Red через 5 ходов", "time": "14:30"},
    {"game": "Football X", "signal": "x2.0 через 1 матч", "time": "18:45"},
]

async def run_template_dispatch():
    now = datetime.datetime.now().strftime("%H:%M")
    for tpl in signal_templates:
        if tpl["time"] == now:
            cursor.execute("INSERT INTO signals (game, signal) VALUES (?, ?)", (tpl["game"], tpl["signal"]))
            
cursor.execute("""CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT,
    signal TEXT,
    time TEXT
)""")

conn.commit()
            logging.info(f"📌 Шаблонный сигнал добавлен: {tpl['game']} — {tpl['signal']}")

# --------- УПРАВЛЕНИЕ ШАБЛОНАМИ ---------
@dp.callback_query(lambda c: c.data == "admin_templates")
async def old_show_templates(callback: types.CallbackQuery):
    text = "🧾 Текущие шаблоны сигналов:\n"
    for tpl in signal_templates:
        text += f"🎮 {tpl['game']} — {tpl['signal']} в {tpl['time']}\n"
    await callback.message.answer(text)
    await callback.message.answer("➕ Чтобы добавить шаблон, пришли:
<игра> | <сигнал> | <время (HH:MM)>")
    await bot.session.storage.set_data(callback.from_user.id, {"awaiting_template": True})

@dp.message(lambda msg: msg.from_user.id in ADMIN_IDS)
async def handle_template_add(message: types.Message):
    state = await bot.session.storage.get_data(message.from_user.id)
    if not state or not state.get("awaiting_template"):
        return
    try:
        game, signal, time = map(str.strip, message.text.split("|", 2))
        cursor.execute("INSERT INTO templates (game, signal, time) VALUES (?, ?, ?)", (game, signal, time))
        conn.commit()
        signal_templates.append({"game": game, "signal": signal, "time": time})
        await message.answer(f"✅ Шаблон добавлен: {game} — {signal} в {time}")
        await bot.session.storage.set_data(message.from_user.id, {})
    except:
        await message.answer("❌ Неверный формат. Используй: <игра> | <сигнал> | <время>")

@dp.callback_query(lambda c: c.data.startswith("delete_template_"))
async def delete_template(callback: types.CallbackQuery):
    try:
        index = int(callback.data.split("_")[-1])
        tpl = signal_templates.pop(index)
    cursor.execute("DELETE FROM templates WHERE game=? AND signal=? AND time=?", (tpl['game'], tpl['signal'], tpl['time']))
    conn.commit()
        await callback.message.answer(f"🗑 Удалён шаблон: {tpl['game']} — {tpl['signal']} в {tpl['time']}")
    except Exception as e:
        await callback.message.answer("❌ Ошибка при удалении шаблона.")

@dp.callback_query(lambda c: c.data == "admin_templates")
async def show_templates(callback: types.CallbackQuery):
    text = "🧾 Текущие шаблоны сигналов:\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for i, tpl in enumerate(signal_templates):
        text += f"{i}. 🎮 {tpl['game']} — {tpl['signal']} в {tpl['time']}\n"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"❌ Удалить {i}", callback_data=f"delete_template_{i}")
        ])
    await callback.message.answer(text, reply_markup=keyboard)
    await callback.message.answer("➕ Чтобы добавить шаблон, пришли:
<игра> | <сигнал> | <время (HH:MM)>")
    await bot.session.storage.set_data(callback.from_user.id, {"awaiting_template": True})

def load_templates():
    cursor.execute("SELECT game, signal, time FROM templates")
    rows = cursor.fetchall()
    return [{"game": r[0], "signal": r[1], "time": r[2]} for r in rows]

signal_templates = load_templates()
