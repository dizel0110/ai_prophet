from aiogram import types, Router
from aiogram.filters import Command
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
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
    text = (
        "🖐 *Мастерская Массажа*\n\n"
        "Мы — супружеская команда профессиональных мастеров массажа.\n"
        "Классика, антицеллюлитный, спортивный, стоун-терапия и другие техники.\n\n"
        "👇 Открой Mini App, чтобы увидеть все услуги и записаться"
    )
    if GEM_BOT_URL:
        text += (
            f"\n\n🤖 *GEM-бот помощник:*\n"
            f"Если бот не отвечает, воспользуйтесь внешним: "
            f"[Открыть GEM-бота]({GEM_BOT_URL})"
        )

    await message.answer(text, parse_mode="Markdown", reply_markup=get_massage_menu())
