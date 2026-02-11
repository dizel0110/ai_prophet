from aiogram import types, Router
from aiogram.filters import Command
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from config import OWNER_USERNAME

router = Router()

@router.message(Command("dizel0110"))
async def admin_cmd(message: types.Message):
    if message.from_user.username != OWNER_USERNAME:
        await message.answer("🔮 Этот пророческий канал доступен только создателю.")
        return

    # VIP Mini App URL с параметром admin=true
    vip_web_app_url = "https://dizel0110.github.io/ai_prophet/?admin=true"
    kb = [[KeyboardButton(text="🛠 Админ Панель", web_app=WebAppInfo(url=vip_web_app_url))]]
    
    await message.answer(
        "👋 *Приветствую, Создатель!*\n\nТы активировал VIP-режим. Теперь тебе доступны дополнительные инструменты в Mini App.",
        reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True),
        parse_mode="Markdown"
    )
