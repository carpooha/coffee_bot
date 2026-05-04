# -*- coding: utf-8 -*-
import asyncio
import os
import aiohttp  # <-- ЭТО ДОБАВИТЬ!
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties

API_TOKEN = os.environ.get('TELEGRAM_TOKEN')

if not API_TOKEN:
    raise ValueError("❌ Токен не найден! Проверьте переменную окружения TELEGRAM_TOKEN")

def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Где кофе и молоко?", callback_data="instruction")],
        [InlineKeyboardButton(text="💰 Финансы", callback_data="finance")],
        [InlineKeyboardButton(text="💸 Скинуться на кофе", callback_data="donate")]
    ])
    return keyboard

async def main():
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher()
    
    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        await message.answer("☕️ Добро пожаловать в Кофе-Бот!\n\nВыберите действие:", reply_markup=get_main_keyboard())
    
    @dp.callback_query()
    async def handle_callbacks(callback: types.CallbackQuery):
        if callback.data == "instruction":
            await callback.message.answer("📍 Кофе в верхнем ящике, молоко в холодильнике")
        elif callback.data == "finance":
            await callback.message.answer("💰 Собрано: 0 руб.\nПотрачено: 0 руб.\nБаланс: 0 руб.")
        elif callback.data == "donate":
            await callback.message.answer("💸 Ссылка для оплаты: https://ваша-ссылка-на-оплату.com")
        await callback.answer()
    
    print("🤖 Кофе-бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())