import logging
import threading
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)


def _send_tg_sync(chat_id: int, text: str) -> bool:
    """Send Telegram message via Bot API directly (sync, no asyncio)."""
    try:
        from config import TOKEN
        import requests
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        r = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }, timeout=10)
        if r.status_code != 200:
            logger.warning(f"TG notify to {chat_id}: {r.status_code} {r.text[:200]}")
        return r.status_code == 200
    except Exception as e:
        logger.warning(f"TG notify to {chat_id}: {e}")
        return False


def notify_booking_created(client_chat_id: int, masseur_chat_id: int,
                           service: str, slot_date: str, start_time: str,
                           client_name: str = "") -> None:
    text = (
        f"\U0001f4c5 *Новая запись на сеанс*\n\n"
        f"\U0001f464 Клиент: {client_name or f'ID {client_chat_id}'}\n"
        f"\U0001f486 Услуга: {service or 'Не указана'}\n"
        f"\U0001f4c6 Дата: {slot_date}\n"
        f"\u23f1 Время: {start_time}\n"
        f"\U0001f194 {client_chat_id}"
    )
    _send_tg_sync(masseur_chat_id, text)


def notify_booking_confirmed(client_chat_id: int, masseur_chat_id: int,
                             slot_date: str, start_time: str) -> None:
    c_text = (
        f"\u2705 *Запись подтверждена*\n\n"
        f"\U0001f4c6 {slot_date} в {start_time}\n"
        f"\u0416\u0434\u0451\u043c \u0432\u0430\u0441!"
    )
    _send_tg_sync(client_chat_id, c_text)
    m_text = (
        f"\u2705 *Клиент подтвердил запись*\n\n"
        f"\U0001f4c6 {slot_date} в {start_time}\n"
        f"\U0001f194 {client_chat_id}"
    )
    _send_tg_sync(masseur_chat_id, m_text)


def notify_booking_cancelled(client_chat_id: int, masseur_chat_id: int,
                             slot_date: str, start_time: str,
                             by: str = "client") -> None:
    who = "клиент" if by == "client" else "массажист"
    m_text = (
        f"\u274c *Запись отменена ({who})*\n\n"
        f"\U0001f4c6 {slot_date} в {start_time}\n"
        f"\U0001f194 {client_chat_id}"
    )
    _send_tg_sync(masseur_chat_id, m_text)
    if by == "masseur":
        c_text = (
            f"\u274c *Ваша запись отменена массажистом*\n\n"
            f"\U0001f4c6 {slot_date} в {start_time}\n"
            f"\u0421\u0432\u044f\u0436\u0438\u0442\u0435\u0441\u044c \u0441 \u0441\u0430\u043b\u043e\u043d\u043e\u043c \u0434\u043b\u044f \u0443\u0442\u043e\u0447\u043d\u0435\u043d\u0438\u044f."
        )
        _send_tg_sync(client_chat_id, c_text)
