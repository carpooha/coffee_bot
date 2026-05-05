# -*- coding: utf-8 -*-
import asyncio
import os
import json
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from tinydb import TinyDB, Query
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from aiogram.fsm import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# --- Состояния для обратной связи ---
class FeedbackStates(StatesGroup):
    waiting_for_feedback = State()

API_TOKEN = os.environ.get('TELEGRAM_TOKEN')

if not API_TOKEN:
    raise ValueError("❌ Токен не найден!")

ADMIN_ID = 152676166  # 👈 ВСТАВЬТЕ СВОЙ ID

# --- База данных ---
db = TinyDB('coffee_db.json')
finances = db.table('finances')

if not finances.all():
    finances.insert({'collected': 0.0, 'spent': 0.0})

def add_collected(amount):
    data = finances.all()[0]
    data['collected'] += amount
    finances.update(data, doc_ids=[1])

def add_spent(amount, description):
    data = finances.all()[0]
    data['spent'] += amount
    finances.update(data, doc_ids=[1])

# --- Хранение объявления ---
ANNOUNCEMENT_FILE = 'announcement.json'

def save_announcement(text):
    with open(ANNOUNCEMENT_FILE, 'w', encoding='utf-8') as f:
        json.dump({'text': text}, f, ensure_ascii=False)

def get_announcement():
    try:
        with open(ANNOUNCEMENT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('text', '')
    except:
        return ''

# --- Flask для health check ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "☕️ Кофе-бот работает!"

# --- Клавиатура ---
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Где кофе и молоко?", callback_data="instruction")],
        [InlineKeyboardButton(text="💰 Финансы", callback_data="finance")],
        [InlineKeyboardButton(text="💸 Скинуться на кофе", callback_data="donate")],
        [InlineKeyboardButton(text="📝 Обратная связь", callback_data="feedback")]  # НОВАЯ КНОПКА
    ])
    return keyboard

def get_admin_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отвечено", callback_data="feedback_answered")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data="feedback_rejected")]
    ])
    return keyboard

# --- Бот ---
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    announcement = get_announcement()
    if announcement:
        welcome_text = f"""☕️ Добро пожаловать в Кофе-Бот!

📢 <b>ОБЪЯВЛЕНИЕ:</b>
{announcement}

---
Выберите действие:"""
    else:
        welcome_text = "☕️ Добро пожаловать в Кофе-Бот!\n\nВыберите действие:"
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

@dp.callback_query(lambda c: c.data == "instruction")
async def show_instruction(callback: types.CallbackQuery):
    text = """📍 ГДЕ НАЙТИ КОФЕ И МОЛОКО:

☕️ Кофе: В шкафу над кофемашиной в жестяной коричневой банке. Пакет с кофе еще выше если в банке кончилось
🥛 Молоко: В холодильнике в верхнем выдвижном ящике, или в дверке открытое"""
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "finance")
async def show_finance(callback: types.CallbackQuery):
    data = finances.all()[0]
    collected = data['collected']
    spent = data['spent']
    balance = collected - spent
    text = f"💰 ФИНАНСОВЫЙ ОТЧЕТ\n\nСобрано: {collected:.2f} руб.\nПотрачено: {spent:.2f} руб.\nБаланс: {balance:.2f} руб."
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "donate")
async def show_donate(callback: types.CallbackQuery):
    text = "💸 Ссылка на сбор: https://vtb.paymo.ru/collect-money/?transaction=c208d1eb-2b1a-47f8-9d41-835e1a005ee8"
    await callback.message.answer(text)
    await callback.answer()

# ---------- КОМАНДЫ АДМИНИСТРАТОРА ----------
@dp.message(Command("add"))
async def cmd_add_money(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔️ У вас нет прав")
        return
    try:
        amount = float(message.text.split()[1])
        add_collected(amount)
        await message.answer(f"✅ Добавлено {amount:.2f} руб.")
    except (IndexError, ValueError):
        await message.answer("❌ Использование: /add [сумма]")

@dp.message(Command("spend"))
async def cmd_spend_money(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔️ У вас нет прав")
        return
    try:
        parts = message.text.split(maxsplit=2)
        amount = float(parts[1])
        description = parts[2] if len(parts) > 2 else "без описания"
        add_spent(amount, description)
        await message.answer(f"✅ Списано {amount:.2f} руб. ({description})")
    except (IndexError, ValueError):
        await message.answer("❌ Использование: /spend [сумма] [описание]")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("No permission")
        return
    data = finances.all()[0]
    text = f"STATISTICS\n\nCollected: {data['collected']} rub.\nSpent: {data['spent']} rub.\nBalance: {data['collected'] - data['spent']} rub."
    await message.answer(text)

@dp.message(Command("announce"))
async def cmd_announce(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔️ У вас нет прав")
        return
    try:
        text = message.text.split(maxsplit=1)[1]
        save_announcement(text)
        await message.answer(f"✅ Объявление сохранено!")
    except IndexError:
        await message.answer("❌ Использование: /announce [текст]")

@dp.message(Command("clear_announce"))
async def cmd_clear_announce(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔️ У вас нет прав")
        return
    save_announcement("")
    await message.answer("✅ Объявление удалено")

# --- ОБРАТНАЯ СВЯЗЬ ---

@dp.callback_query(lambda c: c.data == "feedback")
async def start_feedback(callback: types.CallbackQuery, state: FSMContext):
    """Начинаем процесс обратной связи"""
    await callback.message.answer(
        "📝 Напишите ваш отзыв, пожелание или сообщите о проблеме.\n\n"
        "Просто отправьте текстовое сообщение. Если передумали — отправьте /cancel"
    )
    await state.set_state(FeedbackStates.waiting_for_feedback)
    await callback.answer()

@dp.message(Command("cancel"))
async def cancel_feedback(message: types.Message, state: FSMContext):
    """Отмена обратной связи"""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активного действия для отмены")
        return
    
    await state.clear()
    await message.answer("✅ Действие отменено.", reply_markup=get_main_keyboard())

@dp.message(FeedbackStates.waiting_for_feedback)
async def process_feedback(message: types.Message, state: FSMContext):
    """Обрабатываем полученный отзыв"""
    feedback_text = message.text
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()
    
    # Формируем сообщение для администратора
    admin_message = f"""📝 НОВЫЙ ОТЗЫВ

Отправитель: {full_name}
User ID: {user_id}
Username: @{username}

Сообщение:
{feedback_text}"""
    
    try:
        # Отправляем администратору
        await bot.send_message(ADMIN_ID, admin_message, reply_markup=get_admin_keyboard())
        
        # Подтверждаем пользователю
        await message.answer(
            "✅ Спасибо за ваш отзыв! Он отправлен администратору.\n\n"
            "Возвращаемся в главное меню:",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        
    except Exception as e:
        await message.answer(
            "❌ Произошла ошибка при отправке отзыва. Пожалуйста, попробуйте позже."
        )
        print(f"Ошибка отправки отзыва: {e}")
        await state.clear()

@dp.callback_query(lambda c: c.data == "feedback_answered")
async def feedback_answered(callback: types.CallbackQuery):
    """Администратор отметил, что ответил на отзыв"""
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ Статус: Обработано"
    )
    await callback.answer("Отмечено как отвеченное")

@dp.callback_query(lambda c: c.data == "feedback_rejected")
async def feedback_rejected(callback: types.CallbackQuery):
    """Администратор отклонил отзыв"""
    await callback.message.edit_text(
        callback.message.text + "\n\n❌ Статус: Отклонено"
    )
    await callback.answer("Отзыв отклонен")

# --- Запуск бота через polling (не webhook) ---
async def start_bot():  # <-- ЭТО ВМЕСТО run_bot()
    await bot.delete_webhook(drop_pending_updates=True)
    print("🤖 Кофе-бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    thread = Thread(target=run_flask)
    thread.start()
    asyncio.run(start_bot())  # <-- ЗДЕСЬ ВЫЗЫВАЕТСЯ start_bot()

# --- Точка входа для Render ---
# Запускаем Flask в отдельном потоке, а бота в основном
def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    from threading import Thread
    thread = Thread(target=run_flask)
    thread.start()
    asyncio.run(start_bot())