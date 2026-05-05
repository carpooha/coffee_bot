# -*- coding: utf-8 -*-
import asyncio
import os
import json
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from tinydb import TinyDB, Query

API_TOKEN = os.environ.get('TELEGRAM_TOKEN')

if not API_TOKEN:
    raise ValueError("❌ Токен не найден!")

# ID администратора (замените на свой Telegram ID)
ADMIN_ID = 152676166  # 👈 ВСТАВЬТЕ СВОЙ ID

# --- База данных ---
db = TinyDB('coffee_db.json')
finances = db.table('finances')
users = db.table('users')  # Храним всех, кто написал /start

if not finances.all():
    finances.insert({'collected': 0.0, 'spent': 0.0})

# Функции для финансов
def get_balance():
    data = finances.all()[0]
    return data['collected'] - data['spent']

def add_collected(amount):
    data = finances.all()[0]
    data['collected'] += amount
    finances.update(data, doc_ids=[1])

def add_spent(amount, description):
    data = finances.all()[0]
    data['spent'] += amount
    finances.update(data, doc_ids=[1])

# Функция для сохранения пользователя
def save_user(user_id, username, first_name, last_name):
    User = Query()
    if not users.search(User.user_id == user_id):
        users.insert({
            'user_id': user_id,
            'username': username or "",
            'first_name': first_name or "",
            'last_name': last_name or "",
        })
        print(f"➕ Новый пользователь: {user_id} (@{username})")

# --- Хранение пассивного объявления (видят при /start) ---
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

# --- Flask для Render (чтобы сервис не засыпал) ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "☕️ Кофе-бот работает!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)

# --- Клавиатуры ---
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Где кофе и молоко?", callback_data="instruction")],
        [InlineKeyboardButton(text="💰 Финансы", callback_data="finance")],
        [InlineKeyboardButton(text="💸 Скинуться на кофе", callback_data="donate")],
        [InlineKeyboardButton(text="📢 Объявления", callback_data="show_announcement")],
        [InlineKeyboardButton(text="📝 Обратная связь", callback_data="feedback")]
    ])
    return keyboard

def get_admin_keyboard():
    """Клавиатура для администратора при получении отзыва"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отвечено", callback_data="feedback_answered")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data="feedback_rejected")]
    ])
    return keyboard

# --- Основная функция с обработчиками ---
async def run_bot():
    storage = MemoryStorage()
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=storage)
    
    # ---------- ОБЫЧНЫЕ КОМАНДЫ ----------
    
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        # Сохраняем пользователя
        save_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        
        # Показываем пассивное объявление (если есть)
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
    
    @dp.callback_query(F.data == "instruction")
    async def show_instruction(callback: types.CallbackQuery):
        text = """📍 ГДЕ НАЙТИ КОФЕ И МОЛОКО:

☕️ Кофе: Коричневая жестяная банка в шкафу над кофеваркой, а еще выше пакеты с кофе, если в банке оно закончилось
🥛 Молоко: Обычно в холодильнике в верхнем выдвижном ящике
👤 Если кончилось то скоро купим :)"""
        await callback.message.answer(text)
        await callback.answer()
    
    @dp.callback_query(F.data == "finance")
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
    
    @dp.callback_query(F.data == "donate")
    async def show_donate(callback: types.CallbackQuery):
        text = "💸 Ссылка на сбор: https://vtb.paymo.ru/collect-money/?transaction=c208d1eb-2b1a-47f8-9d41-835e1a005ee8"
        await callback.message.answer(text)
        await callback.answer()
    
    @dp.callback_query(F.data == "show_announcement")
    async def show_announcement_button(callback: types.CallbackQuery):
        """Показать текущее пассивное объявление"""
        announcement = get_announcement()
        if announcement:
            text = f"📢 <b>ТЕКУЩЕЕ ОБЪЯВЛЕНИЕ:</b>\n\n{announcement}"
        else:
            text = "📢 <b>Нет активных объявлений</b>\n\nАдминистратор пока ничего не объявлял."
        await callback.message.answer(text)
        await callback.answer()
    
    # ---------- ОБРАТНАЯ СВЯЗЬ ----------
    
    @dp.callback_query(F.data == "feedback")
    async def start_feedback(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.answer(
            "📝 <b>Напишите ваш отзыв, пожелание или сообщите о проблеме.</b>\n\n"
            "Просто отправьте текстовое сообщение. Если передумали — отправьте /cancel",
        )
        await state.set_state(FeedbackStates.waiting_for_feedback)
        await callback.answer()
    
    @dp.message(Command("cancel"))
    async def cancel_feedback(message: types.Message, state: FSMContext):
        current_state = await state.get_state()
        if current_state is None:
            await message.answer("❌ Нет активного действия для отмены")
            return
        await state.clear()
        await message.answer("✅ Действие отменено.", reply_markup=get_main_keyboard())
    
    @dp.message(StateFilter(FeedbackStates.waiting_for_feedback), F.text)
    async def process_feedback(message: types.Message, state: FSMContext):
        # Сохраняем пользователя (на случай, если его ещё нет)
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
            await state.clear()
        except Exception as e:
            await message.answer("❌ Ошибка при отправке отзыва. Попробуйте позже.")
            print(f"Ошибка: {e}")
            await state.clear()
    
    @dp.message(StateFilter(FeedbackStates.waiting_for_feedback))
    async def feedback_invalid_input(message: types.Message, state: FSMContext):
        await message.answer(
            "📝 Пожалуйста, отправьте <b>текстовое сообщение</b>.\n"
            "Если хотите отменить — отправьте /cancel"
        )
    
    @dp.callback_query(F.data == "feedback_answered")
    async def feedback_answered(callback: types.CallbackQuery):
        await callback.message.edit_text(callback.message.text + "\n\n✅ <b>Статус:</b> Обработано")
        await callback.answer("Отмечено как отвеченное")
    
    @dp.callback_query(F.data == "feedback_rejected")
    async def feedback_rejected(callback: types.CallbackQuery):
        await callback.message.edit_text(callback.message.text + "\n\n❌ <b>Статус:</b> Отклонено")
        await callback.answer("Отзыв отклонен")
    
    # ---------- КОМАНДЫ АДМИНИСТРАТОРА ----------
    
    @dp.message(Command("add"))
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
            await message.answer(f"✅ Списано {amount:.2f} руб. Причина: {description}")
        except (IndexError, ValueError):
            await message.answer("❌ Использование: /spend [сумма] [описание]\nПример: /spend 500 купили кофе")
    
    @dp.message(Command("stats"))
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
    
    @dp.message(Command("users"))
    async def cmd_users_stats(message: types.Message):
        """Показать статистику пользователей"""
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔️ У вас нет прав")
            return
        all_users = users.all()
        if not all_users:
            await message.answer("📊 Нет пользователей в базе")
            return
        text = f"👥 <b>СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ</b>\n\n📊 Всего: {len(all_users)}\n\n📋 <b>Список (последние 10):</b>\n"
        for i, user in enumerate(all_users[-10:], 1):
            name = user.get('first_name', 'Без имени')
            username = f"@{user['username']}" if user.get('username') else "нет username"
            text += f"{i}. {name} {username} (ID: {user['user_id']})\n"
        await message.answer(text)
    
    # --- ПАССИВНОЕ ОБЪЯВЛЕНИЕ (видят при /start) ---
    @dp.message(Command("announce"))
    async def cmd_announce(message: types.Message):
        """Установить объявление (видно при /start)"""
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔️ У вас нет прав")
            return
        try:
            text = message.text.split(maxsplit=1)[1]
            save_announcement(text)
            await message.answer(f"✅ Пассивное объявление сохранено!\n\nТеперь все увидят его при команде /start:\n\n{text}")
        except IndexError:
            await message.answer("❌ Использование: /announce [текст]\n\nПример: /announce Завтра кофе не завезут")
    
    @dp.message(Command("clear_announce"))
    async def cmd_clear_announce(message: types.Message):
        """Очистить пассивное объявление"""
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔️ У вас нет прав")
            return
        save_announcement("")
        await message.answer("✅ Пассивное объявление удалено")
    
    # --- АКТИВНАЯ РАССЫЛКА (отправляет сообщение всем пользователям) ---
    @dp.message(Command("broadcast"))
    async def cmd_broadcast(message: types.Message):
        """Отправить сообщение ВСЕМ пользователям (активная рассылка)"""
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔️ У вас нет прав")
            return
        
        try:
            broadcast_text = message.text.split(maxsplit=1)[1]
        except IndexError:
            await message.answer(
                "❌ Использование: /broadcast [текст]\n\n"
                "Пример: /broadcast Всем сотрудникам! Завтра кофе не завезут."
            )
            return
        
        all_users = users.all()
        if not all_users:
            await message.answer("❌ Нет пользователей для рассылки")
            return
        
        status_msg = await message.answer(f"📢 Начинаю рассылку для {len(all_users)} пользователей...")
        
        success_count = 0
        fail_count = 0
        
        for user in all_users:
            user_id = user['user_id']
            try:
                await bot.send_message(
                    user_id,
                    f"📢 <b>Сообщение от администратора:</b>\n\n{broadcast_text}",
                    parse_mode="HTML"
                )
                success_count += 1
            except Exception:
                fail_count += 1
            await asyncio.sleep(0.05)
        
        await status_msg.edit_text(
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"📨 Отправлено: {success_count}\n"
            f"❌ Не доставлено: {fail_count}\n"
            f"👥 Всего в базе: {len(all_users)}",
            parse_mode="HTML"
        )
    
    # --- ЗАПУСК ---
    print("🤖 Кофе-бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    thread = Thread(target=run_flask)
    thread.start()
    asyncio.run(run_bot())