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
import asyncio
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from config import TOKEN
from handlers import messages, vip, limits, massage

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# НЕ создаём новое FastAPI приложение!
# Используем то, которое импортируется из main.py

def setup_webhook_routes(fastapi_app: FastAPI):
    """Регистрирует webhook endpoints и создаёт своего бота"""

    PROXY_URL = os.getenv("PROXY_URL")
    bot = Bot(token=TOKEN)
    webhook_dp = Dispatcher()
    webhook_dp.include_router(vip.router)
    webhook_dp.include_router(limits.router)
    webhook_dp.include_router(massage.router)
    webhook_dp.include_router(messages.router)

    async def init_bot_proxy():
        if PROXY_URL:
            logger.info(f"🔄 Используем прокси: {PROXY_URL}")
            await bot.session.close()
            bot.session = AiohttpSession(proxy=PROXY_URL)
            logger.info("✅ Прокси настроен")
        else:
            logger.warning("⚠️ PROXY_URL не настроен. Бот не сможет отправлять сообщения на HF Spaces.")

    @fastapi_app.get("/webhook")
    async def get_webhook():
        return {"status": "ok", "mode": "webhook"}

    @fastapi_app.post("/webhook")
    async def webhook_handler(request: Request):
        try:
            update_dict = await request.json()
            update = types.Update(**update_dict)
            logger.info(f"📥 Получено обновление: id={update.update_id}, type={update.event_type}")
            await webhook_dp.feed_update(bot, update)
            logger.info(f"✅ Обновление обработано: id={update.update_id}")
            return {"status": "ok"}
        except Exception as e:
            import traceback
            logger.error(f"Webhook error: {e}\n{traceback.format_exc()}")
            return {"status": "error", "message": str(e)}

    @fastapi_app.on_event("startup")
    async def on_startup():
        await init_bot_proxy()
        space_id = os.getenv("SPACE_ID")
        if space_id:
            space_slug = space_id.replace("/", "-").replace("_", "-")
            webhook_url = f"https://{space_slug}.hf.space/webhook"
            logger.info(f"📡 HF Spaces detected: {space_id}")
            logger.info(f"📡 Webhook URL: {webhook_url}")
            logger.info(f"📝 Установка: https://api.telegram.org/bot<TOKEN>/setWebhook?url={webhook_url}")
        else:
            logger.info("📡 Локальный режим — используется polling (main.py)")

    @fastapi_app.on_event("shutdown")
    async def on_shutdown():
        logger.info("🛑 Остановка бота...")
        await bot.session.close()
        logger.info("✅ Сессия бота закрыта")

    logger.info("✅ Webhook routes зарегистрированы")
