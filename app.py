# -*- coding: utf-8 -*-
import asyncio
import os
import json
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command, Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from tinydb import TinyDB, Query

API_TOKEN = os.environ.get('TELEGRAM_TOKEN')

if not API_TOKEN:
    raise ValueError("❌ Токен не найден!")

# ID администратора (замените на свой Telegram ID)
ADMIN_ID = 123456789  # 👈 ВСТАВЬТЕ СВОЙ ID

# --- База данных ---
db = TinyDB('coffee_db.json')
finances = db.table('finances')
users = db.table('users')

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

def save_user(user_id, username, first_name, last_name):
    User = Query()
    if not users.search(User.user_id == user_id):
        users.insert({
            'user_id': user_id,
            'username': username or "",
            'first_name': first_name or "",
            'last_name': last_name or "",
        })

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

# --- Машина состояний для обратной связи ---
class FeedbackStates(StatesGroup):
    waiting_for_feedback = State()

# --- Flask для Render ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "☕️ Кофе-бот работает!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)

# --- Клавиатуры ---
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(text="📖 Где кофе и молоко?", callback_data="instruction"),
        InlineKeyboardButton(text="💰 Финансы", callback_data="finance"),
        InlineKeyboardButton(text="💸 Скинуться на кофе", callback_data="donate"),
        InlineKeyboardButton(text="📢 Объявления", callback_data="show_announcement"),
        InlineKeyboardButton(text="📝 Обратная связь", callback_data="feedback")
    )
    return keyboard

def get_admin_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(text="✅ Отвечено", callback_data="feedback_answered"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data="feedback_rejected")
    )
    return keyboard

# --- Основная функция ---
async def run_bot():
    bot = Bot(token=API_TOKEN, parse_mode="HTML")
    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)
    
    # ---------- КОМАНДА START ----------
    @dp.message_handler(Command("start"))
    async def cmd_start(message: types.Message):
        save_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
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
    
    # ---------- КНОПКИ МЕНЮ ----------
    @dp.callback_query_handler(lambda c: c.data == "instruction")
    async def show_instruction(callback: types.CallbackQuery):
        text = """📍 ГДЕ НАЙТИ КОФЕ И МОЛОКО:

☕️ Кофе: В верхнем ящике кухонного шкафа
🥛 Молоко: В холодильнике (вторая полка)
👤 Ответственный: Анна (каб. 405)"""
        await callback.message.answer(text)
        await callback.answer()
    
    @dp.callback_query_handler(lambda c: c.data == "finance")
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
    
    @dp.callback_query_handler(lambda c: c.data == "donate")
    async def show_donate(callback: types.CallbackQuery):
        text = "💸 Ссылка для оплаты: https://ваша-ссылка-на-оплату.com"
        await callback.message.answer(text)
        await callback.answer()
    
    @dp.callback_query_handler(lambda c: c.data == "show_announcement")
    async def show_announcement_button(callback: types.CallbackQuery):
        announcement = get_announcement()
        if announcement:
            text = f"📢 <b>ТЕКУЩЕЕ ОБЪЯВЛЕНИЕ:</b>\n\n{announcement}"
        else:
            text = "📢 <b>Нет активных объявлений</b>\n\nАдминистратор пока ничего не объявлял."
        await callback.message.answer(text)
        await callback.answer()
    
    # ---------- ОБРАТНАЯ СВЯЗЬ ----------
    @dp.callback_query_handler(lambda c: c.data == "feedback")
    async def start_feedback(callback: types.CallbackQuery):
        await callback.message.answer(
            "📝 <b>Напишите ваш отзыв, пожелание или сообщите о проблеме.</b>\n\n"
            "Просто отправьте текстовое сообщение. Если передумали — отправьте /cancel"
        )
        await FeedbackStates.waiting_for_feedback.set()
        await callback.answer()
    
    @dp.message_handler(Command("cancel"), state="*")
    async def cancel_feedback(message: types.Message, state: FSMContext):
        await state.finish()
        await message.answer("✅ Действие отменено.", reply_markup=get_main_keyboard())
    
    @dp.message_handler(state=FeedbackStates.waiting_for_feedback, content_types=types.ContentTypes.TEXT)
    async def process_feedback(message: types.Message, state: FSMContext):
        save_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        feedback_text = message.text
        user_id = message.from_user.id
        username = message.from_user.username or "без username"
        full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
        
        admin_message = f"""📝 <b>НОВЫЙ ОТЗЫВ</b>

👤 <b>Отправитель:</b> {full_name}
🆔 <b>User ID:</b> <code>{user_id}</code>
📱 <b>Username:</b> @{username}

💬 <b>Сообщение:</b>
{feedback_text}"""
        
        try:
            await bot.send_message(ADMIN_ID, admin_message, reply_markup=get_admin_keyboard())
            await message.answer(
                "✅ Спасибо за ваш отзыв! Он отправлен администратору.\n"
                "Возвращаемся в главное меню:",
                reply_markup=get_main_keyboard()
            )
            await state.finish()
        except Exception as e:
            await message.answer("❌ Ошибка при отправке отзыва. Попробуйте позже.")
            await state.finish()
    
    @dp.callback_query_handler(lambda c: c.data == "feedback_answered")
    async def feedback_answered(callback: types.CallbackQuery):
        await callback.message.edit_text(callback.message.text + "\n\n✅ <b>Статус:</b> Обработано")
        await callback.answer()
    
    @dp.callback_query_handler(lambda c: c.data == "feedback_rejected")
    async def feedback_rejected(callback: types.CallbackQuery):
        await callback.message.edit_text(callback.message.text + "\n\n❌ <b>Статус:</b> Отклонено")
        await callback.answer()
    
    # ---------- КОМАНДЫ АДМИНИСТРАТОРА ----------
    @dp.message_handler(Command("add"))
    async def cmd_add_money(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔️ У вас нет прав")
            return
        try:
            amount = float(message.text.split()[1])
            add_collected(amount)
            await message.answer(f"✅ Добавлено {amount:.2f} руб. в кофейный фонд")
        except (IndexError, ValueError):
            await message.answer("❌ Использование: /add [сумма]\nПример: /add 500")
    
    @dp.message_handler(Command("spend"))
    async def cmd_spend_money(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔️ У вас нет прав")
            return
        try:
            parts = message.text.split(maxsplit=2)
            amount = float(parts[1])
            description = parts[2] if len(parts) > 2 else "без описания"
            add_spent(amount, description)
            await message.answer(f"✅ Списано {amount:.2f} руб. Причина: {description}")
        except (IndexError, ValueError):
            await message.answer("❌ Использование: /spend [сумма] [описание]\nПример: /spend 500 купили кофе")
    
    @dp.message_handler(Command("stats"))
    async def cmd_stats(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔️ У вас нет прав")
            return
        data = finances.all()[0]
        text = f"""📊 ПОДРОБНАЯ СТАТИСТИКА

💰 Всего собрано: {data['collected']:.2f} руб.
💸 Всего потрачено: {data['spent']:.2f} руб.
📈 Текущий баланс: {data['collected'] - data['spent']:.2f} руб."""
        await message.answer(text)
    
    @dp.message_handler(Command("users"))
    async def cmd_users_stats(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔️ У вас нет прав")
            return
        all_users = users.all()
        if not all_users:
            await message.answer("📊 Нет пользователей в базе")
            return
        text = f"👥 <b>СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ</b>\n\n📊 Всего: {len(all_users)}\n"
        await message.answer(text)
    
    @dp.message_handler(Command("announce"))
    async def cmd_announce(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔️ У вас нет прав")
            return
        try:
            text = message.text.split(maxsplit=1)[1]
            save_announcement(text)
            await message.answer(f"✅ Объявление сохранено!\n\n{text}")
        except IndexError:
            await message.answer("❌ Использование: /announce [текст]")
    
    @dp.message_handler(Command("clear_announce"))
    async def cmd_clear_announce(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔️ У вас нет прав")
            return
        save_announcement("")
        await message.answer("✅ Объявление удалено")
    
    @dp.message_handler(Command("broadcast"))
    async def cmd_broadcast(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔️ У вас нет прав")
            return
        try:
            broadcast_text = message.text.split(maxsplit=1)[1]
        except IndexError:
            await message.answer("❌ Использование: /broadcast [текст]")
            return
        
        all_users = users.all()
        if not all_users:
            await message.answer("❌ Нет пользователей для рассылки")
            return
        
        status_msg = await message.answer(f"📢 Начинаю рассылку для {len(all_users)} пользователей...")
        
        success_count = 0
        fail_count = 0
        
        for user in all_users:
            try:
                await bot.send_message(
                    user['user_id'],
                    f"📢 <b>Сообщение от администратора:</b>\n\n{broadcast_text}"
                )
                success_count += 1
            except:
                fail_count += 1
            await asyncio.sleep(0.05)
        
        await status_msg.edit_text(
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"📨 Отправлено: {success_count}\n"
            f"❌ Не доставлено: {fail_count}"
        )
    
    # --- ЗАПУСК ---
    print("🤖 Кофе-бот запущен!")
    await dp.start_polling()

if __name__ == "__main__":
    thread = Thread(target=run_flask)
    thread.start()
    asyncio.run(run_bot())