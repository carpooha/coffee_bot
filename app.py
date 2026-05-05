# -*- coding: utf-8 -*-
import asyncio
import os
import json
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from tinydb import TinyDB, Query

API_TOKEN = os.environ.get('TELEGRAM_TOKEN')

if not API_TOKEN:
    raise ValueError("❌ Токен не найден!")

ADMIN_ID = 123456789  # 👈 ВСТАВЬТЕ СВОЙ ID

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

# --- Flask для Render ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "☕️ Кофе-бот работает!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)

# --- Клавиатура ---
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Где кофе и молоко?", callback_data="instruction")],
        [InlineKeyboardButton(text="💰 Финансы", callback_data="finance")],
        [InlineKeyboardButton(text="💸 Скинуться на кофе", callback_data="donate")]
    ])
    return keyboard

# --- Основная функция ---
async def run_bot():
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    
    # Сбрасываем webhook (важно для работы polling на Render)
    await bot.delete_webhook(drop_pending_updates=True)
    
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
    
    # ... остальные обработчики ...
    
    print("🤖 Кофе-бот запущен!")
    await dp.start_polling(bot)

---
Выберите действие:"""
        else:
            welcome_text = "☕️ Добро пожаловать в Кофе-Бот!\n\nВыберите действие:"
        await message.answer(welcome_text, reply_markup=get_main_keyboard())
    
    @dp.callback_query(lambda c: c.data == "instruction")
    async def show_instruction(callback: types.CallbackQuery):
        text = """📍 ГДЕ НАЙТИ КОФЕ И МОЛОКО:

☕️ Кофе: В верхнем ящике кухонного шкафа
🥛 Молоко: В холодильнике (вторая полка)
👤 Ответственный: Анна (каб. 405)"""
        await callback.message.answer(text)
        await callback.answer()
    
    @dp.callback_query(lambda c: c.data == "finance")
    async def show_finance(callback: types.CallbackQuery):
        data = finances.all()[0]
        collected = data['collected']
        spent = data['spent']
        balance = collected - spent
        text = f"""💰 ФИНАНСОВЫЙ ОТЧЕТ

Собрано: {collected:.2f} руб.
Потрачено: {spent:.2f} руб.
Баланс: {balance:.2f} руб."""
        await callback.message.answer(text)
        await callback.answer()
    
    @dp.callback_query(lambda c: c.data == "donate")
    async def show_donate(callback: types.CallbackQuery):
        text = "💸 Ссылка для оплаты: https://ваша-ссылка-на-оплату.com"
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
            await message.answer("⛔️ У вас нет прав")
            return
        data = finances.all()[0]
        text = f"""📊 СТАТИСТИКА

💰 Собрано: {data['collected']:.2f} руб.
💸 Потрачено: {data['spent']:.2f} руб.
📈 Баланс: {data['collected'] - data['spent']:.2f} руб."""
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
    
    print("🤖 Кофе-бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    thread = Thread(target=run_flask)
    thread.start()
    asyncio.run(run_bot())