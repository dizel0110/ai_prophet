from aiogram import types, Router, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from config import OWNER_USERNAME, VIP_PASSWORD
import json
import os
from config import TEMP_DIR

router = Router()

SETTINGS_FILE = os.path.join(TEMP_DIR, "user_settings.json")

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass

user_settings = load_settings()

def get_vip_menu():
    """Меню VIP режима"""
    kb = [
        [KeyboardButton(text="🔮 VIP Предсказание"), KeyboardButton(text="🎙 VIP Голос")],
        [KeyboardButton(text="🖼 VIP Видение"), KeyboardButton(text="🌐 VIP Поиск")],
        [KeyboardButton(text="🎵 VIP Музыка")],
        [KeyboardButton(text="🔓 Выйти из VIP")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@router.message(Command("dizel0110"))
async def admin_cmd(message: types.Message):
    """Вход в VIP режим по паролю"""
    chat_id = str(message.chat.id)
    
    # Проверяем пароль (первое сообщение после команды)
    args = message.text.split()
    
    # Если пароль не передан, просим ввести
    if len(args) < 2:
        await message.answer(
            "🔐 *Вход в VIP режим*\n\n"
            "Введите пароль для доступа к расширенным функциям.\n\n"
            "_Пароль известен только создателю._",
            parse_mode="Markdown"
        )
        # Устанавливаем флаг ожидания пароля
        user_settings.setdefault(chat_id, {})['waiting_vip_password'] = True
        save_settings(user_settings)
        return
    
    password = args[1]
    
    # Проверяем пароль
    if password != VIP_PASSWORD:
        await message.answer("❌ Неверный пароль. Доступ запрещён.")
        user_settings.get(chat_id, {}).pop('waiting_vip_password', None)
        save_settings(user_settings)
        return
    
    # VIP Mini App URL с параметром admin=true
    vip_web_app_url = "https://dizel0110.github.io/ai_prophet/?admin=true"
    kb = get_vip_menu()

    # Устанавливаем VIP режим
    user_settings.setdefault(chat_id, {})['vip_mode'] = True
    user_settings.get(chat_id, {}).pop('waiting_vip_password', None)
    save_settings(user_settings)

    await message.answer(
        "✅ *VIP режим активирован!*\n\n"
        "🌟 *Доступны расширенные функции:*\n"
        "• 💎 Gemini 2.5 Flash — передовая модель\n"
        "• 🎵 Приоритетная обработка\n"
        "• 🧠 Расширенные возможности\n\n"
        "Используй меню ниже или команду /exitvip для выхода.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@router.message(Command("exitvip"))
async def exit_vip(message: types.Message):
    """Выход из VIP режима"""
    chat_id = str(message.chat.id)
    
    if user_settings.get(chat_id, {}).get('vip_mode'):
        user_settings[chat_id]['vip_mode'] = False
        save_settings(user_settings)
        
        await message.answer(
            "🔓 *Выход из VIP режима*\n\n"
            "Теперь вы используете обычный режим (Hugging Face).\n\n"
            "Для возврата используйте `/dizel0110 <пароль>`",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text="📱 Открыть Mini App")],
                [KeyboardButton(text="🔮 Предсказание"), KeyboardButton(text="🎙 Голос Судьбы")],
                [KeyboardButton(text="🖼 Видение"), KeyboardButton(text="⚙️ Настройки")]
            ], resize_keyboard=True)
        )
    else:
        await message.answer("ℹ️ Вы не в VIP режиме.")
