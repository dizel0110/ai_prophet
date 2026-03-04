# -*- coding: utf-8 -*-
"""
Telegram Webhook для Hugging Face Spaces

КРИТИЧЕСКАЯ ПРОБЛЕМА: HF Spaces блокирует исходящие запросы к api.telegram.org
Решение: Использовать HTTP прокси или запустить бота на другой платформе

Варианты решения:
1. Запустить бота на VPS/Railway/Render (рекомендуется)
2. Использовать HTTP прокси для обхода блокировки
3. Использовать polling режим локально

Этот файл оставлен для совместимости, но на HF Spaces бот не сможет
отправлять ответы без прокси.
"""

import os
import logging
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import ClientSession
from config import TOKEN
from handlers import messages, vip, limits

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# Проверяем наличие прокси
PROXY_URL = os.getenv("PROXY_URL")  # Например: http://proxy.example.com:8080

# Инициализация бота
if PROXY_URL:
    logger.info(f"🔄 Используем прокси: {PROXY_URL}")
    # Создаём сессию с прокси
    from aiohttp import ClientSession, TCPConnector
    connector = TCPConnector(ssl=False)
    session = ClientSession(connector=connector, trust_env=True)
    aiohttp_session = AiohttpSession(session=session)
    bot = Bot(token=TOKEN, session=aiohttp_session)
else:
    logger.warning("⚠️ PROXY_URL не настроен. Бот не сможет отправлять сообщения на HF Spaces.")
    logger.warning("📝 Добавьте в HF Spaces → Settings → Secrets:")
    logger.warning("📝 PROXY_URL=http://47.243.107.235:8080  (бесплатный прокси)")
    logger.warning("📝 Или используйте другую платформу (Oracle Cloud, Railway, Render)")
    bot = Bot(token=TOKEN)

dp = Dispatcher()

# Регистрация роутеров
dp.include_router(vip.router)
dp.include_router(limits.router)
dp.include_router(messages.router)

# НЕ создаём новое FastAPI приложение!
# Используем то, которое импортируется из main.py

def setup_webhook_routes(fastapi_app: FastAPI):
    """
    Регистрирует webhook endpoints в существующем FastAPI приложении
    """

    @fastapi_app.get("/webhook")
    async def get_webhook():
        """Проверка webhook"""
        return {"status": "ok", "mode": "webhook"}

    @fastapi_app.post("/webhook")
    async def webhook_handler(request: Request):
        """
        Обработка обновлений от Telegram
        """
        try:
            # Получаем JSON от Telegram
            update_dict = await request.json()
            update = types.Update(**update_dict)

            logger.info(f"📥 Получено обновление: id={update.update_id}, type={update.event_type}")

            # Обрабатываем через Dispatcher
            await dp.feed_update(bot, update)

            logger.info(f"✅ Обновление обработано: id={update.update_id}")
            return {"status": "ok"}
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Webhook error: {e}")
            logger.error(f"Traceback:\n{error_trace}")
            # Возвращаем 200 даже при ошибке, чтобы Telegram не спамил
            return {"status": "error", "message": str(e)}

    @fastapi_app.on_event("startup")
    async def on_startup():
        """Настройка webhook при старте"""
        space_id = os.getenv("SPACE_ID")

        if space_id:
            # Формируем правильный URL: space_id может быть "username/space-name" или "username_space_name"
            # Для HF Spaces URL формат: https://username-space-name.hf.space (все символы → дефисы)
            space_slug = space_id.replace("/", "-").replace("_", "-")

            webhook_url = f"https://{space_slug}.hf.space/webhook"

            logger.info(f"📡 HF Spaces detected: {space_id}")
            logger.info(f"📡 Webhook URL: {webhook_url}")
            logger.info("📝 HF Spaces блокирует исходящие запросы — webhook должен быть установлен вручную")
            logger.info(f"📝 URL для установки: https://api.telegram.org/bot<TOKEN>/setWebhook?url={webhook_url}")
        else:
            logger.info("📡 Локальный режим — используется polling (main.py)")

    @fastapi_app.on_event("shutdown")
    async def on_shutdown():
        """Очистка при остановке"""
        logger.info("🛑 Остановка бота...")
        # Не удаляем webhook при shutdown на HF Spaces
        # Webhook остаётся установленным для следующего запуска
        await bot.session.close()
        logger.info("✅ Сессия бота закрыта")

    logger.info("✅ Webhook routes зарегистрированы")
