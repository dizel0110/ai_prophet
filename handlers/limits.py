"""
Настройки лимитов скачивания аудио
Интерактивный выбор с визуализацией
"""

import os
import json
import logging
from aiogram import Router, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)
router = Router()

# Путь к файлу настроек пользователя
LIMITS_FILE = "temp/user_limits.json"

# Пресеты лимитов
PRESETS = {
    "fast": {"duration": 300, "size": 10, "label": "⚡ Быстро (до 5 мин, 10 MB)"},
    "balanced": {"duration": 1800, "size": 50, "label": "⚖️ Баланс (до 30 мин, 50 MB)"},
    "max": {"duration": 3600, "size": 100, "label": "🐢 Максимум (до 60 мин, 100 MB)"},
}

def load_user_limits(chat_id):
    """Загрузка настроек пользователя"""
    if os.path.exists(LIMITS_FILE):
        try:
            with open(LIMITS_FILE, 'r', encoding='utf-8') as f:
                all_limits = json.load(f)
                return all_limits.get(str(chat_id), PRESETS["balanced"])
        except Exception:
            pass
    return PRESETS["balanced"].copy()

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
    with open(LIMITS_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_limits, f, ensure_ascii=False, indent=2)

def format_duration(seconds):
    """Форматирование длительности"""
    if seconds < 60:
        return f"{seconds} сек"
    elif seconds < 3600:
        return f"{seconds // 60} мин"
    else:
        return f"{seconds // 3600} ч {seconds % 3600 // 60} мин"

def get_limit_status_color(duration, size):
    """Определение цвета статуса"""
    if duration <= 300 and size <= 10:
        return "🟢", "быстро"
    elif duration <= 1800 and size <= 50:
        return "🟡", "нормально"
    else:
        return "🔴", "долго"

def create_limits_keyboard(chat_id):
    """Создание клавиатуры настроек лимитов"""
    limits = load_user_limits(chat_id)
    
    # Текущие значения
    duration = limits.get("duration", 1800)
    size = limits.get("size", 50)
    color, speed = get_limit_status_color(duration, size)
    
    # Визуализация ползунков
    duration_bar = create_progress_bar(duration, 300, 1800, 3600)
    size_bar = create_progress_bar(size, 10, 50, 100)
    
    kb = [
        # Пресеты
        [
            InlineKeyboardButton(text="⚡ Быстро", callback_data="limit_preset:fast"),
            InlineKeyboardButton(text="⚖️ Баланс", callback_data="limit_preset:balanced"),
            InlineKeyboardButton(text="🐢 Максимум", callback_data="limit_preset:max"),
        ],
        # Длительность
        [
            InlineKeyboardButton(text="⏱️ -5 мин", callback_data="limit_duration:-300"),
            InlineKeyboardButton(text=f"⏱ {format_duration(duration)}", callback_data="limit_info:duration"),
            InlineKeyboardButton(text="⏱️ +5 мин", callback_data="limit_duration:300"),
        ],
        # Размер
        [
            InlineKeyboardButton(text="📦 -10 MB", callback_data="limit_size:-10"),
            InlineKeyboardButton(text=f"📦 {size} MB", callback_data="limit_info:size"),
            InlineKeyboardButton(text="📦 +10 MB", callback_data="limit_size:10"),
        ],
        # Сохранение
        [
            InlineKeyboardButton(text="💾 Сохранить", callback_data="limit_save"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="limit_cancel"),
        ],
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=kb)

def create_progress_bar(value, min_val, mid_val, max_val):
    """Создание визуального прогресс-бара"""
    # Нормализация (0-100%)
    if value <= mid_val:
        percent = (value - min_val) / (mid_val - min_val) * 50
    else:
        percent = 50 + (value - mid_val) / (max_val - mid_val) * 50
    
    percent = max(0, min(100, percent))
    filled = int(percent / 5)
    
    bar = "█" * filled + "░" * (20 - filled)
    return f"[{bar}]"

@router.callback_query(F.data.startswith("limit_"))
async def handle_limit_callback(callback: types.CallbackQuery):
    """Обработка кнопок настроек лимитов"""
    chat_id = callback.message.chat.id
    data = callback.data.split(":")
    action = data[0]
    
    limits = load_user_limits(chat_id)
    duration = limits.get("duration", 1800)
    size = limits.get("size", 50)
    
    if action == "limit_preset":
        preset = data[1]
        if preset in PRESETS:
            limits = PRESETS[preset].copy()
            duration = limits["duration"]
            size = limits["size"]
    
    elif action == "limit_duration":
        change = int(data[1])
        duration = max(60, min(3600, duration + change))
        limits["duration"] = duration
    
    elif action == "limit_size":
        change = int(data[1])
        size = max(5, min(200, size + change))
        limits["size"] = size
    
    elif action == "limit_save":
        save_user_limits(chat_id, limits)
        color, speed = get_limit_status_color(duration, size)
        await callback.answer(f"✅ Сохранено! ({speed})", show_alert=True)
        await callback.message.edit_text(
            f"💾 *Настройки сохранены!*\n\n"
            f"⏱ Длительность: {format_duration(duration)}\n"
            f"📦 Размер: {size} MB\n"
            f"🚀 Скорость: {color} {speed}",
            reply_markup=create_limits_keyboard(chat_id),
            parse_mode="Markdown"
        )
        return
    
    elif action == "limit_cancel":
        await callback.message.delete()
        return
    
    elif action == "limit_info":
        param = data[1]
        if param == "duration":
            info = (
                "⏱ *Длительность аудио*\n\n"
                "🟢 До 5 мин — мгновенно\n"
                "🟡 5-30 мин — 1-3 мин загрузки\n"
                "🔴 30+ мин — 3-10 мин загрузки"
            )
        else:
            info = (
                "📦 *Размер файла*\n\n"
                "🟢 До 10 MB — быстро\n"
                "🟡 10-50 MB — нормально\n"
                "🔴 50+ MB — долго"
            )
        await callback.answer(info, show_alert=True)
        return
    
    # Обновление сообщения
    color, speed = get_limit_status_color(duration, size)
    duration_bar = create_progress_bar(duration, 300, 1800, 3600)
    size_bar = create_progress_bar(size, 10, 50, 100)
    
    await callback.message.edit_text(
        f"🎛 *Настройки загрузки аудио*\n\n"
        f"⏱ *Длительность:* {duration_bar} {format_duration(duration)}\n"
        f"   🟢 Короткие (<5 мин) — быстро\n"
        f"   🟡 Средние (5-30 мин) — нормально\n"
        f"   🔴 Длинные (30+ мин) — долго\n\n"
        f"📦 *Размер:* {size_bar} {size} MB\n"
        f"   🟢 До 10 MB — мгновенно\n"
        f"   🟡 До 50 MB — нормально\n"
        f"   🔴 До 100+ MB — долго\n\n"
        f"🚀 *Текущий режим:* {color} {speed}",
        reply_markup=create_limits_keyboard(chat_id),
        parse_mode="Markdown"
    )

def get_limits_button():
    """Кнопка настроек лимитов"""
    return KeyboardButton(text="🎛 Лимиты")
