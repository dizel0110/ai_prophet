"""
Настройки лимитов скачивания аудио
Интерактивный выбор с визуализацией и кастомными значениями
"""

import os
import json
import logging
from aiogram import Router, types, F
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton,
    Modal, TextInput
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)
router = Router()

# Путь к файлу настроек пользователя
LIMITS_FILE = "temp/user_limits.json"

# Дефолтные значения
DEFAULT_LIMITS = {
    "duration": 1800,  # 30 мин
    "size": 50,  # 50 MB
}

# Мин/Макс значения
MIN_DURATION = 60  # 1 мин
MAX_DURATION = 3600  # 60 мин
MIN_SIZE = 5  # 5 MB
MAX_SIZE = 200  # 200 MB


class LimitStates(StatesGroup):
    waiting_for_duration = State()
    waiting_for_size = State()


def load_user_limits(chat_id):
    """Загрузка настроек пользователя"""
    if os.path.exists(LIMITS_FILE):
        try:
            with open(LIMITS_FILE, 'r', encoding='utf-8') as f:
                all_limits = json.load(f)
                user_limits = all_limits.get(str(chat_id), DEFAULT_LIMITS.copy())
                #Merge с дефолтами
                return {**DEFAULT_LIMITS, **user_limits}
        except Exception as e:
            logger.warning(f"Failed to load limits: {e}")
    return DEFAULT_LIMITS.copy()


def save_user_limits(chat_id, limits):
    """Сохранение настроек пользователя"""
    all_limits = {}
    if os.path.exists(LIMITS_FILE):
        try:
            with open(LIMITS_FILE, 'r', encoding='utf-8') as f:
                all_limits = json.load(f)
        except Exception:
            pass
    
    all_limits[str(chat_id)] = limits
    
    os.makedirs("temp", exist_ok=True)
    try:
        with open(LIMITS_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_limits, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save limits: {e}")


def format_duration(seconds):
    """Форматирование длительности"""
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        if secs == 0:
            return f"{mins} мин"
        return f"{mins} мин {secs} сек"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours} ч {mins} мин"


def get_limit_status(duration, size):
    """Определение статуса лимитов"""
    # Длительность
    if duration <= 300:
        dur_status = "🟢", "быстро"
    elif duration <= 1800:
        dur_status = "🟡", "нормально"
    else:
        dur_status = "🔴", "долго"
    
    # Размер
    if size <= 10:
        size_status = "🟢", "мгновенно"
    elif size <= 50:
        size_status = "🟡", "нормально"
    else:
        size_status = "🔴", "долго"
    
    return dur_status, size_status


def create_progress_bar(value, min_val, max_val, width=20):
    """Создание плавного прогресс-бара"""
    percent = (value - min_val) / (max_val - min_val) * 100
    percent = max(0, min(100, percent))
    filled = int(percent / (100 / width))
    filled = max(0, min(width, filled))
    
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}]"


def create_limits_keyboard(chat_id):
    """Создание клавиатуры настроек лимитов"""
    limits = load_user_limits(chat_id)
    duration = limits.get("duration", 1800)
    size = limits.get("size", 50)
    
    dur_color, dur_speed = get_limit_status(duration, size)[0], get_limit_status(duration, size)[1]
    size_color, size_speed = get_limit_status(duration, size)[0], get_limit_status(duration, size)[1]
    
    # Прогресс-бары
    dur_bar = create_progress_bar(duration, MIN_DURATION, MAX_DURATION)
    size_bar = create_progress_bar(size, MIN_SIZE, MAX_SIZE)
    
    kb = [
        # Быстрые пресеты
        [
            InlineKeyboardButton(text="⚡ Быстро", callback_data="limit_preset:fast"),
            InlineKeyboardButton(text="⚖️ Баланс", callback_data="limit_preset:balanced"),
            InlineKeyboardButton(text="🐢 Макс", callback_data="limit_preset:max"),
        ],
        # Длительность
        [
            InlineKeyboardButton(text="⏱️ -1 мин", callback_data="limit_duration:-60"),
            InlineKeyboardButton(text=f"⏱ {format_duration(duration)}", callback_data="limit_set:duration"),
            InlineKeyboardButton(text="⏱️ +1 мин", callback_data="limit_duration:60"),
        ],
        # Длительность - шаги
        [
            InlineKeyboardButton(text="⏱️ -5 мин", callback_data="limit_duration:-300"),
            InlineKeyboardButton(text=dur_bar, callback_data="limit_info:duration"),
            InlineKeyboardButton(text="⏱️ +5 мин", callback_data="limit_duration:300"),
        ],
        # Размер
        [
            InlineKeyboardButton(text="📦 -5 MB", callback_data="limit_size:-5"),
            InlineKeyboardButton(text=f"📦 {size} MB", callback_data="limit_set:size"),
            InlineKeyboardButton(text="📦 +5 MB", callback_data="limit_size:5"),
        ],
        # Размер - шаги
        [
            InlineKeyboardButton(text="📦 -20 MB", callback_data="limit_size:-20"),
            InlineKeyboardButton(text=size_bar, callback_data="limit_info:size"),
            InlineKeyboardButton(text="📦 +20 MB", callback_data="limit_size:20"),
        ],
        # Сохранение
        [
            InlineKeyboardButton(text="💾 Сохранить", callback_data="limit_save"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="limit_cancel"),
        ],
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data.startswith("limit_"))
async def handle_limit_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка кнопок настроек лимитов"""
    chat_id = callback.message.chat.id
    data = callback.data.split(":")
    action = data[0]
    
    limits = load_user_limits(chat_id)
    duration = limits.get("duration", 1800)
    size = limits.get("size", 50)
    
    if action == "limit_preset":
        preset = data[1]
        if preset == "fast":
            limits["duration"] = 300
            limits["size"] = 10
        elif preset == "balanced":
            limits["duration"] = 1800
            limits["size"] = 50
        elif preset == "max":
            limits["duration"] = 3600
            limits["size"] = 200
        duration = limits["duration"]
        size = limits["size"]
    
    elif action == "limit_duration":
        change = int(data[1])
        duration = max(MIN_DURATION, min(MAX_DURATION, duration + change))
        limits["duration"] = duration
    
    elif action == "limit_size":
        change = int(data[1])
        size = max(MIN_SIZE, min(MAX_SIZE, size + change))
        limits["size"] = size
    
    elif action == "limit_save":
        save_user_limits(chat_id, limits)
        await callback.answer(f"✅ Сохранено!", show_alert=True)
        await update_limits_message(callback.message, chat_id, limits)
        return
    
    elif action == "limit_cancel":
        await callback.message.delete()
        await state.clear()
        return
    
    elif action == "limit_info":
        param = data[1]
        if param == "duration":
            info = (
                "⏱ *Длительность аудио*\n\n"
                f"Мин: {format_duration(MIN_DURATION)}\n"
                f"Макс: {format_duration(MAX_DURATION)}\n\n"
                "🟢 До 5 мин — быстро\n"
                "🟡 5-30 мин — нормально\n"
                "🔴 30+ мин — долго"
            )
        else:
            info = (
                "📦 *Размер файла*\n\n"
                f"Мин: {MIN_SIZE} MB\n"
                f"Макс: {MAX_SIZE} MB\n\n"
                "🟢 До 10 MB — быстро\n"
                "🟡 10-50 MB — нормально\n"
                "🔴 50+ MB — долго"
            )
        await callback.answer(info, show_alert=True)
        return
    
    elif action == "limit_set":
        param = data[1]
        if param == "duration":
            await callback.answer("Введите длительность (сек или мин):\nПример: 300 или 5 мин", show_alert=True)
            await state.set_state(LimitStates.waiting_for_duration)
        elif param == "size":
            await callback.answer("Введите размер в MB:\nПример: 50", show_alert=True)
            await state.set_state(LimitStates.waiting_for_size)
        return
    
    await update_limits_message(callback.message, chat_id, limits)


async def update_limits_message(message, chat_id, limits):
    """Обновление сообщения с настройками"""
    duration = limits.get("duration", 1800)
    size = limits.get("size", 50)
    
    dur_color, dur_speed = get_limit_status(duration, size)
    size_color, size_speed = get_limit_status(duration, size)[0], get_limit_status(duration, size)[1]
    
    dur_bar = create_progress_bar(duration, MIN_DURATION, MAX_DURATION)
    size_bar = create_progress_bar(size, MIN_SIZE, MAX_SIZE)
    
    await message.edit_text(
        f"🎛 *Настройки загрузки аудио*\n\n"
        f"⏱ *Длительность:* {dur_bar} {format_duration(duration)}\n"
        f"   {dur_color} {dur_speed}\n\n"
        f"📦 *Размер:* {size_bar} {size} MB\n"
        f"   {size_color} {size_speed}\n\n"
        f"💡 *Нажми на кнопки для настройки:*\n"
        f"• -1/-5 мин или -5/-20 MB — точная настройка\n"
        f"• Значение — ввести своё число\n"
        f"• Прогресс — информация",
        reply_markup=create_limits_keyboard(chat_id),
        parse_mode="Markdown"
    )


@router.message(LimitStates.waiting_for_duration)
async def process_duration_input(message: types.Message, state: FSMContext):
    """Обработка ввода длительности"""
    try:
        text = message.text.strip().lower()
        
        # Парсинг "5 мин" или "300"
        if "мин" in text or "min" in text:
            value = int(text.replace("мин", "").replace("min", "").strip()) * 60
        elif "сек" in text or "sec" in text:
            value = int(text.replace("сек", "").replace("sec", "").strip())
        else:
            value = int(text)
        
        # Проверка диапазона
        if value < MIN_DURATION or value > MAX_DURATION:
            await message.answer(
                f"❌ Значение вне диапазона ({format_duration(MIN_DURATION)} - {format_duration(MAX_DURATION)})\n"
                f"Попробуй ещё раз:"
            )
            return
        
        # Сохранение
        chat_id = str(message.chat.id)
        limits = load_user_limits(chat_id)
        limits["duration"] = value
        save_user_limits(chat_id, limits)
        
        await message.answer(
            f"✅ Длительность установлена: {format_duration(value)}\n"
            f"Открой настройки снова, чтобы увидеть изменения.",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🎛 Лимиты")]], resize_keyboard=True)
        )
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат.\n"
            f"Примеры:\n"
            f"• 300 (секунды)\n"
            f"• 5 мин (минуты)\n"
            f"Попробуй ещё раз:"
        )


@router.message(LimitStates.waiting_for_size)
async def process_size_input(message: types.Message, state: FSMContext):
    """Обработка ввода размера"""
    try:
        text = message.text.strip().lower()
        value = int(text.replace("mb", "").replace("мб", "").strip())
        
        # Проверка диапазона
        if value < MIN_SIZE or value > MAX_SIZE:
            await message.answer(
                f"❌ Значение вне диапазона ({MIN_SIZE} - {MAX_SIZE} MB)\n"
                f"Попробуй ещё раз:"
            )
            return
        
        # Сохранение
        chat_id = str(message.chat.id)
        limits = load_user_limits(chat_id)
        limits["size"] = value
        save_user_limits(chat_id, limits)
        
        await message.answer(
            f"✅ Размер установлен: {value} MB\n"
            f"Открой настройки снова, чтобы увидеть изменения.",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🎛 Лимиты")]], resize_keyboard=True)
        )
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат.\n"
            f"Пример: 50\n"
            f"Попробуй ещё раз:"
        )


def get_limits_button():
    """Кнопка настроек лимитов"""
    return KeyboardButton(text="🎛 Лимиты")


def get_search_params_for_chat(chat_id):
    """
    Получение параметров поиска на основе лимитов пользователя.
    Возвращает dict для search_media_content().
    """
    limits = load_user_limits(chat_id)
    duration = limits.get("duration", 1800)
    size = limits.get("size", 50)
    
    # Определяем количество результатов на основе лимитов
    if duration <= 300 and size <= 10:
        # Быстрый режим — больше результатов
        max_results = 10
    elif duration <= 1800 and size <= 50:
        # Баланс
        max_results = 5
    else:
        # Максимум — меньше результатов (долгая загрузка)
        max_results = 3
    
    return {
        "max_results": max_results,
        "max_duration_sec": duration,
        "max_filesize_mb": size,
    }
