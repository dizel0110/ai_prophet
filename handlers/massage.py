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
        "AI Prophet поможет расслабить тело.\n"
        "Мы — супружеская команда профессиональных мастеров массажа.\n"
        "Классика, антицеллюлитный, спортивный, стоун-терапия и другие техники.\n\n"
        "👇 Открой салон и выбери услугу"
    )
    inline_kb = [
        [InlineKeyboardButton(text="🖐 Открыть салон", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton(text="🎵 Музыка для массажа", callback_data="massage_music")],
    ]
    if GEM_BOT_URL:
        inline_kb.append([InlineKeyboardButton(text="🤖 GEM-бот помощник", url=GEM_BOT_URL)])
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb),
    )
    await message.answer("Кнопка быстрого доступа:", reply_markup=get_massage_menu())


@router.callback_query(lambda c: c.data == "massage_music")
async def on_massage_music(callback: types.CallbackQuery):
    await callback.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌿 Ambient", callback_data="pl_ambient"),
         InlineKeyboardButton(text="🎹 Классика", callback_data="pl_classic")],
        [InlineKeyboardButton(text="🌊 Природа", callback_data="pl_nature"),
         InlineKeyboardButton(text="🎷 Jazz", callback_data="pl_jazz")],
        [InlineKeyboardButton(text="💆 Спа", callback_data="pl_spa"),
         InlineKeyboardButton(text="🧘 Тайский", callback_data="pl_thai")],
    ])
    await callback.message.answer(
        "🎵 *Выбери жанр для массажного плейлиста:*\n\n"
        "Я подберу 5 треков в выбранном стиле.",
        parse_mode="Markdown",
        reply_markup=kb,
    )


@router.callback_query(lambda c: c.data and c.data.startswith("pl_"))
async def on_playlist_genre(callback: types.CallbackQuery):
    genre_map = {
        "pl_ambient": "ambient spa relaxing music",
        "pl_classic": "classical piano relaxing massage",
        "pl_nature": "nature sounds water birds meditation",
        "pl_jazz": "jazz lounge chill relaxation",
        "pl_spa": "spa relaxation massage music",
        "pl_thai": "thai massage traditional music",
    }
    query = genre_map.get(callback.data, "relaxing massage music")
    await callback.answer(f"🔮 Ищу: {query}")
    from core.tools import search_media_content, send_playlist
    result = search_media_content(query=query, media_type="audio", count=5, chat_id=str(callback.message.chat.id))
    if result.get("text"):
        await callback.message.answer(f"🔮 *Атмосфера:*\n_{result['text']}_", parse_mode="Markdown")
    await send_playlist(callback.bot, callback.message.chat.id, result.get("tracks", []), chat_id_str=str(callback.message.chat.id))
