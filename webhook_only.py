# -*- coding: utf-8 -*-
"""
Telegram Webhook для Hugging Face Spaces
Работает ТОЛЬКО через входящие соединения от Telegram
Исходящие запросы к api.telegram.org НЕ используются

ВАЖНО: Этот модуль НЕ создаёт своё FastAPI приложение,
а использует то, которое уже запущено в main.py
"""

import os
import logging
from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher, types
from config import TOKEN
from handlers import messages, vip, limits

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# Инициализация бота с кастомной сессией (только для webhook)
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
        Telegram сам отправляет POST запросы на этот endpoint
        """
        try:
            # Получаем JSON от Telegram
            update_dict = await request.json()
            update = types.Update(**update_dict)

            # Обрабатываем через Dispatcher
            await dp.feed_update(bot, update)

            return {"status": "ok"}
        except Exception as e:
            logger.error(f"Webhook error: {e}")
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
            logger.info("📝 Webhook должен быть установлен вручную через API Telegram")
            logger.info("📝 Проверьте: https://api.telegram.org/bot<TOKEN>/getWebhookInfo")
        else:
            logger.warning("⚠️ SPACE_ID не найден. Запустите на HF Spaces для webhook.")

    @fastapi_app.on_event("shutdown")
    async def on_shutdown():
        """Очистка при остановке"""
        logger.info("🛑 Остановка бота...")
        try:
            await bot.delete_webhook()
            logger.info("✅ Webhook удалён")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить webhook: {e}")

        await bot.session.close()

    logger.info("✅ Webhook routes зарегистрированы")
