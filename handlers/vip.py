from aiogram import types, Router, F
from aiogram.filters import Command
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from config import OWNER_USERNAME, VIP_PASSWORD, VIP_RESET_PASSWORD, get_base_url
import json
import os
import time
from config import TEMP_DIR

router = Router()

SETTINGS_FILE = os.path.join(TEMP_DIR, "user_settings.json")

# Лимиты безопасности
MAX_FAILED_ATTEMPTS = 3  # Максимум неудачных попыток
LOCKOUT_DURATION = 3600  # Блокировка на 1 час (3600 сек)

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

def check_lockout(chat_id: str) -> tuple[bool, int]:
    """
    Проверка блокировки
    Returns: (is_locked, remaining_seconds)
    """
    user_data = user_settings.get(chat_id, {})
    locked_until = user_data.get('vip_locked_until', 0)
    
    if locked_until > time.time():
        remaining = int(locked_until - time.time())
        return True, remaining
    
    # Сбрасываем истёкшую блокировку
    if locked_until > 0:
        user_data['vip_locked_until'] = 0
        user_data['vip_failed_attempts'] = 0
        user_settings[chat_id] = user_data
        save_settings(user_settings)
    
    return False, 0

def record_failed_attempt(chat_id: str):
    """Запись неудачной попытки"""
    user_data = user_settings.get(chat_id, {})
    attempts = user_data.get('vip_failed_attempts', 0) + 1
    user_data['vip_failed_attempts'] = attempts
    
    if attempts >= MAX_FAILED_ATTEMPTS:
        user_data['vip_locked_until'] = int(time.time()) + LOCKOUT_DURATION
        user_data['vip_failed_attempts'] = 0
    
    user_settings[chat_id] = user_data
    save_settings(user_settings)

def reset_failed_attempts(chat_id: str):
    """Сброс попыток после успешного входа"""
    user_data = user_settings.get(chat_id, {})
    user_data['vip_failed_attempts'] = 0
    user_data['vip_locked_until'] = 0
    user_settings[chat_id] = user_data
    save_settings(user_settings)

@router.message(Command("dizel0110"))
async def admin_cmd(message: types.Message):
    """Вход в VIP режим по паролю"""
    chat_id = str(message.chat.id)
    username = message.from_user.username or ""
    
    # Проверяем, не заблокирован ли пользователь
    is_locked, remaining = check_lockout(chat_id)
    
    # Владелец не блокируется
    if is_locked and username != OWNER_USERNAME:
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await message.answer(
            f"🔒 *Доступ заблокирован*\n\n"
            f"Превышено количество неудачных попыток.\n"
            f"Ожидайте: {hours}ч {minutes}мин\n\n"
            f"Для сброса используйте `/resetvip <пароль_сброса>`",
            parse_mode="Markdown"
        )
        return
    
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
    
    # Проверка пароля сброса (для владельца)
    if password == VIP_RESET_PASSWORD and username == OWNER_USERNAME:
        reset_failed_attempts(chat_id)
        await message.answer("✅ *Блокировка снята*\n\nТеперь вы можете войти в VIP режим.")
        return
    
    # Проверяем основной пароль
    if password != VIP_PASSWORD:
        record_failed_attempt(chat_id)
        attempts_left = MAX_FAILED_ATTEMPTS - user_settings.get(chat_id, {}).get('vip_failed_attempts', 0)
        
        if attempts_left > 0:
            await message.answer(
                f"❌ *Неверный пароль*\n\n"
                f"Осталось попыток: {attempts_left}\n"
                f"После {MAX_FAILED_ATTEMPTS} ошибок доступ будет заблокирован на 1 час.",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"🔒 *ДОСТУП ЗАБЛОКИРОВАН*\n\n"
                f"Превышено количество неудачных попыток.\n"
                f"Блокировка на 1 час.\n\n"
                f"Владелец может сбросить командой `/resetvip {VIP_RESET_PASSWORD}`",
                parse_mode="Markdown"
            )
        
        user_settings.get(chat_id, {}).pop('waiting_vip_password', None)
        save_settings(user_settings)
        return

    # Успешный вход - сбрасываем попытки
    reset_failed_attempts(chat_id)
    
    # VIP Mini App URL с параметром admin=true
    vip_web_app_url = f"{get_base_url()}/static/prophet/index.html?admin=true"
    kb = get_vip_menu()

    # Устанавливаем VIP режим
    user_settings.setdefault(chat_id, {})['vip_mode'] = True
    user_settings.get(chat_id, {}).pop('waiting_vip_password', None)
    save_settings(user_settings)

    await message.answer(
        "✅ *VIP режим активирован!*\n\n"
        "🌟 *Доступны расширенные функции:*\n"
        "• 💎 Gemini 3.5 Flash — флагман мая 2026\n"
        "• 🎵 Приоритетная обработка\n"
        "• 🧠 Расширенные возможности\n\n"
        "Используй меню ниже или команду /exitvip для выхода.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@router.message(Command("resetvip"))
async def reset_vip_lock(message: types.Message):
    """Сброс блокировки VIP (только для владельца)"""
    chat_id = str(message.chat.id)
    username = message.from_user.username or ""
    
    if username != OWNER_USERNAME:
        await message.answer("🔐 Эта команда доступна только создателю.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "🔓 *Сброс блокировки VIP*\n\n"
            f"Использование: `/resetvip {VIP_RESET_PASSWORD}`\n\n"
            "_Только для владельца._",
            parse_mode="Markdown"
        )
        return
    
    password = args[1]
    if password == VIP_RESET_PASSWORD:
        reset_failed_attempts(chat_id)
        await message.answer("✅ *Блокировка снята*\n\nТеперь вы можете войти в VIP режим.")
    else:
        await message.answer("❌ Неверный пароль сброса.")

@router.message(Command("exitvip"))
async def exit_vip(message: types.Message):
    """Выход из VIP режима"""
    chat_id = str(message.chat.id)
    
    if user_settings.get(chat_id, {}).get('vip_mode'):
        user_settings[chat_id]['vip_mode'] = False
        save_settings(user_settings)
        
        from handlers.messages import get_main_menu
        
        await message.answer(
            "🔓 *Выход из VIP режима*\n\n"
            "Теперь вы используете обычный режим (Hugging Face).\n\n"
            "Для возврата используйте `/dizel0110 <пароль>`",
            parse_mode="Markdown",
            reply_markup=get_main_menu(vip_mode=False)
        )
    else:
        await message.answer("ℹ️ Вы не в VIP режиме.")
