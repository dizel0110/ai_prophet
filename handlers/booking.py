import json
import os
import logging
import html
from datetime import datetime, date, time as dtime, timedelta
from typing import Optional

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)

import config
from core.booking_manager import (
    get_available_masseurs, get_free_slots, create_booking,
    confirm_booking, cancel_booking, get_bookings,
)

logger = logging.getLogger(__name__)
router = Router()

SERVICES = [
    "Классический массаж",
    "Антицеллюлитный массаж",
    "Спортивный массаж",
    "Массаж спины и шеи",
    "Стоун-терапия",
    "Медовый массаж",
    "Тайский массаж",
    "Массаж лица",
    "Аромамассаж",
    "Бамбуковый массаж",
    "Лимфодренажный массаж",
    "Экспресс-программа",
]

# ─── State helpers ───

SETTINGS_PATH = os.path.join(config.DATA_DIR, "user_settings.json")

def _load_settings() -> dict:
    if os.path.exists(SETTINGS_PATH):
        try:
            return json.loads(open(SETTINGS_PATH, "r", encoding="utf-8").read())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load {SETTINGS_PATH}: {e}")
    return {}

def _save_settings(data: dict):
    s = json.dumps(data, ensure_ascii=False, indent=2)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        f.write(s)

def _get_state(chat_id: int) -> dict:
    s = _load_settings()
    return s.get(str(chat_id), {}).get("booking_state", {})

def _set_state(chat_id: int, state: dict):
    s = _load_settings()
    key = str(chat_id)
    if key not in s:
        s[key] = {}
    s[key]["booking_state"] = state
    _save_settings(s)

def _clear_state(chat_id: int):
    s = _load_settings()
    key = str(chat_id)
    if key in s and "booking_state" in s[key]:
        del s[key]["booking_state"]
    _save_settings(s)

# ─── Helpers ───

def _esc(text: str) -> str:
    """Escape markdown special chars."""
    return html.escape(text)

def _weekday_name(d: date) -> str:
    names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return names[d.weekday()]

def _format_date(d: date) -> str:
    months = ["янв", "фев", "мар", "апр", "мая", "июн",
              "июл", "авг", "сен", "окт", "ноя", "дек"]
    return f"{d.day} {months[d.month - 1]}"

# ─── /book command ───

@router.message(Command("book"))
async def cmd_book(message: types.Message):
    chat_id = message.chat.id
    masseurs = get_available_masseurs()
    if not masseurs:
        await message.answer("❌ Нет доступных массажистов. Попробуйте позже.")
        return
    if len(masseurs) == 1:
        _set_state(chat_id, {"masseur_chat_id": masseurs[0]["chat_id"], "step": "date_select"})
        await _show_date_picker(message, masseurs[0]["chat_id"])
        return
    kb = []
    for m in masseurs:
        name = m.get("name", f"Массажист {m['chat_id']}")
        kb.append([InlineKeyboardButton(text=f"💆 {name}", callback_data=f"bk_ms_{m['chat_id']}")])
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="bk_cancel")])
    await message.answer(
        "📅 *Запись на сеанс*\n\nВыберите массажиста:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
    )

# ─── Callback handlers ───

@router.callback_query(lambda c: c.data == "bk_cancel")
async def on_bk_cancel(call: types.CallbackQuery):
    await call.answer()
    _clear_state(call.message.chat.id)
    await call.message.edit_text("❌ Запись отменена.")

@router.callback_query(lambda c: c.data.startswith("bk_ms_"))
async def on_bk_masseur(call: types.CallbackQuery):
    await call.answer()
    masseur_chat_id = int(call.data.replace("bk_ms_", ""))
    _set_state(call.message.chat.id, {"masseur_chat_id": masseur_chat_id, "step": "date_select"})
    await _show_date_picker(call.message, masseur_chat_id)

@router.callback_query(lambda c: c.data.startswith("bk_date_"))
async def on_bk_date(call: types.CallbackQuery):
    await call.answer()
    date_str = call.data.replace("bk_date_", "")
    chat_id = call.message.chat.id
    st = _get_state(chat_id)
    if not st:
        await call.message.edit_text("❌ Сессия истекла. Начните заново: /book")
        return
    st["slot_date"] = date_str
    st["step"] = "time_select"
    _set_state(chat_id, st)
    await _show_time_slots(call.message, st["masseur_chat_id"], date_str)

@router.callback_query(lambda c: c.data.startswith("bk_time_"))
async def on_bk_time(call: types.CallbackQuery):
    await call.answer()
    raw = call.data.replace("bk_time_", "")
    parts = raw.split("_")
    if len(parts) < 2:
        return
    start_time = parts[0]
    duration_min = int(parts[1])
    chat_id = call.message.chat.id
    st = _get_state(chat_id)
    if not st:
        await call.message.edit_text("❌ Сессия истекла. Начните заново: /book")
        return
    st["start_time"] = start_time
    st["duration_min"] = duration_min
    st["step"] = "service_select"
    _set_state(chat_id, st)
    await _show_service_picker(call.message)

@router.callback_query(lambda c: c.data.startswith("bk_svc_"))
async def on_bk_service(call: types.CallbackQuery):
    await call.answer()
    idx = int(call.data.replace("bk_svc_", ""))
    chat_id = call.message.chat.id
    st = _get_state(chat_id)
    if not st:
        await call.message.edit_text("❌ Сессия истекла. Начните заново: /book")
        return
    service = SERVICES[idx] if 0 <= idx < len(SERVICES) else "Классический массаж"
    st["service_name"] = service
    st["step"] = "confirm"
    _set_state(chat_id, st)
    await _show_confirm(call.message, st)

@router.callback_query(lambda c: c.data == "bk_confirm")
async def on_bk_confirm(call: types.CallbackQuery):
    await call.answer()
    chat_id = call.message.chat.id
    st = _get_state(chat_id)
    if not st:
        await call.message.edit_text("❌ Сессия истекла. Начните заново: /book")
        return
    booking = create_booking(
        client_chat_id=chat_id,
        masseur_chat_id=st["masseur_chat_id"],
        slot_date=st["slot_date"],
        start_time=st["start_time"],
        duration_min=st.get("duration_min", 60),
        service_name=st.get("service_name", "Классический массаж"),
    )
    if booking:
        await call.message.edit_text(
            f"✅ *Запись создана!*\n\n"
            f"📆 {st['slot_date']} в {st['start_time']}\n"
            f"💆 {st.get('service_name', 'Классический массаж')}\n"
            f"🆔 №{booking.get('id')}\n\n"
            f"Статус: ⏳ ожидает подтверждения\n"
            f"Массажист получил уведомление.",
            parse_mode="Markdown",
        )
    else:
        await call.message.edit_text("❌ Ошибка при создании записи. Попробуйте позже.")
    _clear_state(chat_id)

@router.callback_query(lambda c: c.data == "bk_back")
async def on_bk_back(call: types.CallbackQuery):
    await call.answer()
    chat_id = call.message.chat.id
    st = _get_state(chat_id)
    if not st:
        await call.message.edit_text("❌ Сессия истекла. Начните заново: /book")
        return
    step = st.get("step")
    if step == "date_select":
        await cmd_book(call.message)
    elif step == "time_select":
        await _show_date_picker(call.message, st["masseur_chat_id"])
    elif step == "service_select":
        await _show_time_slots(call.message, st["masseur_chat_id"], st.get("slot_date", ""))
    elif step == "confirm":
        await _show_service_picker(call.message)
    else:
        await cmd_book(call.message)

# ─── /my_bookings command ───

@router.message(Command("my_bookings"))
async def cmd_my_bookings(message: types.Message):
    chat_id = message.chat.id
    bookings = get_bookings(chat_id)
    if not bookings:
        await message.answer("📭 У вас нет записей.")
        return
    lines = ["📋 *Мои записи:*\n"]
    for b in bookings[:10]:
        status_icon = {"pending": "⏳", "confirmed": "✅", "cancelled": "❌"}.get(b.get("status", ""), "❓")
        lines.append(
            f"{status_icon} {b.get('slot_date', '?')} в {b.get('start_time', '?')}\n"
            f"   💆 {b.get('service_name', '—')} / {b.get('duration_min', 60)}мин\n"
            f"   🆔 №{b.get('id')} — {b.get('status', '?')}"
        )
    await message.answer("\n".join(lines), parse_mode="Markdown")

# ─── Step renderers ───

async def _show_date_picker(msg: types.Message, masseur_chat_id: int, edit: bool = True):
    today = date.today()
    kb = []
    row = []
    # Day headers
    for i, dn in enumerate(["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]):
        row.append(InlineKeyboardButton(text=f" {dn} ", callback_data="bk_noop"))
    kb.append(row)
    # Calendar grid — show next 14 days
    days_shown = []
    for i in range(14):
        d = today + timedelta(days=i)
        days_shown.append(d)
    # Blank cells before first day
    first_dow = days_shown[0].weekday()  # Monday=0
    row = []
    for _ in range(first_dow):
        row.append(InlineKeyboardButton(text="  ", callback_data="bk_noop"))
    for d in days_shown:
        lbl = str(d.day)
        dow = d.weekday()
        cb = f"bk_date_{d.isoformat()}"
        btn = InlineKeyboardButton(text=lbl, callback_data=cb)
        row.append(btn)
        if dow == 6:  # Sunday = end of row
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="bk_cancel")])
    text = "📅 *Выберите дату:*"
    if edit:
        await msg.edit_text(text, parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    else:
        await msg.answer(text, parse_mode="Markdown",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def _show_time_slots(msg: types.Message, masseur_chat_id: int, slot_date: str):
    slots = get_free_slots(masseur_chat_id, slot_date)
    if not slots:
        await msg.edit_text(
            f"😕 На {_format_date(date.fromisoformat(slot_date))} нет свободных слотов.\n"
            f"Попробуйте другую дату: /book",
        )
        return
    kb = []
    for s in slots:
        t = s["start_time"]
        dur = s["duration_min"]
        label = f"{t} ({dur}мин)"
        kb.append([InlineKeyboardButton(text=label, callback_data=f"bk_time_{t}_{dur}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="bk_back")])
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="bk_cancel")])
    await msg.edit_text(
        f"🕐 *Свободные слоты на {_format_date(date.fromisoformat(slot_date))}:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
    )

async def _show_service_picker(msg: types.Message):
    kb = []
    for i, svc in enumerate(SERVICES):
        kb.append([InlineKeyboardButton(text=svc, callback_data=f"bk_svc_{i}")])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="bk_back")])
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="bk_cancel")])
    await msg.edit_text(
        "💆 *Выберите услугу:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
    )

async def _show_confirm(msg: types.Message, st: dict):
    text = (
        "📋 *Подтверждение записи*\n\n"
        f"📆 Дата: {st.get('slot_date', '?')}\n"
        f"⏱ Время: {st.get('start_time', '?')}\n"
        f"⏳ Длительность: {st.get('duration_min', 60)} мин\n"
        f"💆 Услуга: {st.get('service_name', '?')}\n\n"
        f"Всё верно?"
    )
    kb = [
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="bk_confirm")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="bk_back")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="bk_cancel")],
    ]
    await msg.edit_text(text, parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# ─── Ignore no-op button ───

@router.callback_query(lambda c: c.data == "bk_noop")
async def on_bk_noop(call: types.CallbackQuery):
    await call.answer()
