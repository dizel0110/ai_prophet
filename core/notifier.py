import logging
import threading
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

_BOT = None

def _get_bot():
    global _BOT
    if _BOT is None:
        try:
            from config import TOKEN
            from aiogram import Bot
            _BOT = Bot(token=TOKEN)
        except Exception as e:
            logger.warning(f"Telegram Bot not available: {e}")
            _BOT = False
    return _BOT if _BOT is not False else None


async def _send_tg(chat_id: int, text: str) -> bool:
    bot = _get_bot()
    if not bot:
        logger.warning(f"Cannot send TG message to {chat_id}: bot not available")
        return False
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        return True
    except Exception as e:
        logger.warning(f"TG notify to {chat_id}: {e}")
        return False


def _fire_and_forget(coro):
    """Run a coroutine in a background thread with its own event loop."""
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro)
        except Exception as e:
            logger.debug(f"Notification failed: {e}")
        finally:
            loop.close()
    threading.Thread(target=run, daemon=True).start()


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
    _fire_and_forget(_send_tg(masseur_chat_id, text))


def notify_booking_confirmed(client_chat_id: int, masseur_chat_id: int,
                             slot_date: str, start_time: str) -> None:
    c_text = (
        f"\u2705 *Запись подтверждена*\n\n"
        f"\U0001f4c6 {slot_date} в {start_time}\n"
        f"\u0416\u0434\u0451\u043c \u0432\u0430\u0441!"
    )
    _fire_and_forget(_send_tg(client_chat_id, c_text))
    m_text = (
        f"\u2705 *Клиент подтвердил запись*\n\n"
        f"\U0001f4c6 {slot_date} в {start_time}\n"
        f"\U0001f194 {client_chat_id}"
    )
    _fire_and_forget(_send_tg(masseur_chat_id, m_text))


def notify_booking_cancelled(client_chat_id: int, masseur_chat_id: int,
                             slot_date: str, start_time: str,
                             by: str = "client") -> None:
    who = "клиент" if by == "client" else "массажист"
    m_text = (
        f"\u274c *Запись отменена ({who})*\n\n"
        f"\U0001f4c6 {slot_date} в {start_time}\n"
        f"\U0001f194 {client_chat_id}"
    )
    _fire_and_forget(_send_tg(masseur_chat_id, m_text))
    if by == "masseur":
        c_text = (
            f"\u274c *Ваша запись отменена массажистом*\n\n"
            f"\U0001f4c6 {slot_date} в {start_time}\n"
            f"\u0421\u0432\u044f\u0436\u0438\u0442\u0435\u0441\u044c \u0441 \u0441\u0430\u043b\u043e\u043d\u043e\u043c \u0434\u043b\u044f \u0443\u0442\u043e\u0447\u043d\u0435\u043d\u0438\u044f."
        )
        _fire_and_forget(_send_tg(client_chat_id, c_text))
