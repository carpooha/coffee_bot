# -*- coding: utf-8 -*-
import asyncio
import os
import ssl
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

# --- Flask сервер для поддержания активности ---
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "?? Кофе-бот работает!"

def run_flask():
    # Render требует, чтобы приложение слушало порт, который он назначает
    port = int(os.environ.get('PORT', 8080))
    app_flask.run(host='0.0.0.0', port=port)

# --- Код Вашего кофе-бота (перенесенный из bot_moloko.py) ---
API_TOKEN = os.environ.get('TELEGRAM_TOKEN') # Берем токен из переменных окружения!

if not API_TOKEN:
    raise ValueError("Токен не найден! Установите переменную окружения TELEGRAM_TOKEN")

def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="?? Где кофе и молоко?", callback_data="instruction")],
        [InlineKeyboardButton(text="?? Финансы", callback_data="finance")],
        [InlineKeyboardButton(text="?? Скинуться на кофе", callback_data="donate")]
    ])
    return keyboard

async def run_bot():
    # Настройка SSL для обхода проблем с сертификатами в облаке
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    session = AiohttpSession(connector=connector)

    bot = Bot(token=API_TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer("?? Добро пожаловать в Кофе-Бот!\n\nВыберите действие:", reply_markup=get_main_keyboard())

    @dp.callback_query()
    async def handle_callbacks(callback: types.CallbackQuery):
        if callback.data == "instruction":
            await callback.message.answer("?? Кофе в верхнем ящике, молоко в холодильнике")
        elif callback.data == "finance":
            await callback.message.answer("?? Собрано: 0 руб.\nПотрачено: 0 руб.")
        elif callback.data == "donate":
            await callback.message.answer("?? Ссылка для оплаты: https://ваша-ссылка-на-оплату.com")
        await callback.answer()

    print("?? Кофе-бот запущен!")
    await dp.start_polling(bot)

# --- Главная точка входа ---
if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке
    thread = Thread(target=run_flask)
    thread.start()
    # Запускаем бота
    asyncio.run(run_bot())