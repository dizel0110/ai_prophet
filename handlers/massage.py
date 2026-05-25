from aiogram import types, Router
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import get_base_url, GEM_BOT_URL

router = Router()

def _massage_url() -> str:
    return f"{get_base_url()}/static/massage/index.html"

def get_massage_menu():
    url = _massage_url()
    kb = [
        [KeyboardButton(text="🖐 Открыть салон", web_app=WebAppInfo(url=url))],
        [KeyboardButton(text="⬅️ Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@router.message(Command("massage"))
async def cmd_massage(message: types.Message):
    url = _massage_url()
    text = (
        "🖐 *Мастерская Массажа*\n\n"
        "Мы — супружеская команда профессиональных мастеров массажа.\n"
        "Классика, антицеллюлитный, спортивный, стоун-терапия и другие техники.\n\n"
        "👇 Нажми на кнопку ниже, чтобы открыть салон"
    )
    inline_kb = [[InlineKeyboardButton(text="🖐 Открыть салон", web_app=WebAppInfo(url=url))]]
    if GEM_BOT_URL:
        inline_kb.append([InlineKeyboardButton(text="🤖 GEM-бот помощник", url=GEM_BOT_URL)])
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb),
    )
    await message.answer("Кнопка быстрого доступа:", reply_markup=get_massage_menu())
