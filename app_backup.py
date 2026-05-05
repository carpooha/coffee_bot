# -*- coding: utf-8 -*-
import asyncio
import os
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties

# ============================================
# 1. ВСТАВЬТЕ СЮДА ИМПОРТЫ ДЛЯ БАЗЫ ДАННЫХ
# ============================================
from tinydb import TinyDB, Query

API_TOKEN = os.environ.get('TELEGRAM_TOKEN')

if not API_TOKEN:
    raise ValueError("❌ Токен не найден!")

# ============================================
# 2. ВСТАВЬТЕ СЮДА ID АДМИНИСТРАТОРА
# ============================================
ADMIN_ID = 152676166  # ЗАМЕНИТЕ НА ВАШ TELEGRAM ID

# ============================================
# 3. ВСТАВЬТЕ СЮДА КОД ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ
# ============================================
db = TinyDB('coffee_db.json')
finances = db.table('finances')

# Инициализируем базу данных, если она пустая
if not finances.all():
    finances.insert({'collected': 0.0, 'spent': 0.0})


def get_balance():
    """Получить текущий баланс"""
    data = finances.all()[0]
    return data['collected'] - data['spent']


def add_collected(amount):
    """Добавить собранные средства"""
    data = finances.all()[0]
    data['collected'] += amount
    finances.update(data, doc_ids=[1])


def add_spent(amount, description):
    """Списать потраченные средства"""
    data = finances.all()[0]
    data['spent'] += amount
    finances.update(data, doc_ids=[1])
    # Здесь можно добавить логирование операций в отдельную таблицу


# ============================================
# 4. FLASK ПРИЛОЖЕНИЕ (оставляем как есть)
# ============================================
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "☕️ Кофе-бот работает!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)


# ============================================
# 5. КЛАВИАТУРА (оставляем как есть)
# ============================================
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Где кофе и молоко?", callback_data="instruction")],
        [InlineKeyboardButton(text="💰 Финансы", callback_data="finance")],
        [InlineKeyboardButton(text="💸 Скинуться на кофе", callback_data="donate")]
    ])
    return keyboard


# ============================================
# 6. ОСНОВНАЯ ФУНКЦИЯ С ОБРАБОТЧИКАМИ (ЗДЕСЬ ДОБАВЛЯЕМ КОМАНДЫ АДМИНА)
# ============================================
async def run_bot():
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    
    # --- ОБЫЧНЫЕ КОМАНДЫ ---
    
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer("☕️ Добро пожаловать в Кофе-Бот!\n\nВыберите действие:", reply_markup=get_main_keyboard())
    
    @dp.callback_query()
    async def handle_callbacks(callback: types.CallbackQuery):
        if callback.data == "instruction":
            await callback.message.answer("📍 Кофе - жестяная банка в шкафу над кофемашиной, молоко в холодильнике в большом ящике")
        elif callback.data == "finance":
            data = finances.all()[0]
            collected = data['collected']
            spent = data['spent']
            balance = collected - spent
            text = f"""💰 ФИНАНСОВЫЙ ОТЧЕТ

Собрано: {collected:.2f} руб.
Потрачено: {spent:.2f} руб.
Баланс: {balance:.2f} руб."""
            await callback.message.answer(text)
        elif callback.data == "donate":
            await callback.message.answer("💸 Ссылка на сбор: https://vtb.paymo.ru/collect-money/?transaction=c208d1eb-2b1a-47f8-9d41-835e1a005ee8 Получатель: Наталья К.")
        await callback.answer()
    
    # ============================================
    # 7. КОМАНДЫ АДМИНИСТРАТОРА (ДОБАВЬТЕ ИХ СЮДА)
    # ============================================
    
    @dp.message(Command("add"))
    async def cmd_add_money(message: types.Message):
        """Добавить средства в фонд. Использование: /add 1000"""
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔️ У вас нет прав для этой команды")
            return
        
        try:
            amount = float(message.text.split()[1])
            add_collected(amount)
            await message.answer(f"✅ Добавлено {amount:.2f} руб. в кофейный фонд")
        except (IndexError, ValueError):
            await message.answer("❌ Использование: /add [сумма]\nПример: /add 500")
    
    @dp.message(Command("spend"))
    async def cmd_spend_money(message: types.Message):
        """Списать расходы. Использование: /spend 500 кофе"""
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔️ У вас нет прав для этой команды")
            return
        
        try:
            parts = message.text.split(maxsplit=2)
            amount = float(parts[1])
            description = parts[2] if len(parts) > 2 else "без описания"
            add_spent(amount, description)
            await message.answer(f"✅ Списано {amount:.2f} руб. Причина: {description}")
        except (IndexError, ValueError):
            await message.answer("❌ Использование: /spend [сумма] [описание]\nПример: /spend 500 купили кофе")
    
    @dp.message(Command("stats"))
    async def cmd_stats(message: types.Message):
        """Показать статистику (только для админа)"""
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔️ У вас нет прав для этой команды")
            return
        
        data = finances.all()[0]
        text = f"""📊 ПОДРОБНАЯ СТАТИСТИКА

💰 Всего собрано: {data['collected']:.2f} руб.
💸 Всего потрачено: {data['spent']:.2f} руб.
📈 Текущий баланс: {data['collected'] - data['spent']:.2f} руб."""
        await message.answer(text)
    
    # --- ЗАПУСК ---
    print("🤖 Кофе-бот запущен!")
    await dp.start_polling(bot)


# ============================================
# 8. ТОЧКА ВХОДА (оставляем как есть)
# ============================================
if __name__ == "__main__":
    thread = Thread(target=run_flask)
    thread.start()
    asyncio.run(run_bot())