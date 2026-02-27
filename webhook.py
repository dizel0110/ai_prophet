# -*- coding: utf-8 -*-
"""
Webhook режим для Hugging Face Spaces
Telegram сам отправляет обновления на наш сервер
"""

import os
import logging
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from config import TOKEN, PORT
from handlers import messages, vip, limits
from core.network import apply_dns_patch

logger = logging.getLogger(__name__)

# Инициализация
apply_dns_patch()
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Регистрация роутеров
dp.include_router(vip.router)
dp.include_router(limits.router)
dp.include_router(messages.router)

# FastAPI приложение
app = FastAPI()

@app.get("/")
async def root():
    """Health check"""
    return {"status": "AI Prophet Webhook is Running"}

@app.get("/webhook")
async def get_webhook():
    """Проверка webhook"""
    return {"status": "ok", "mode": "webhook"}

@app.post("/webhook")
async def webhook_handler(request: Request):
    """Обработка обновлений от Telegram"""
    try:
        update = await request.json()
        await dp.feed_update(bot, update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

@app.on_event("startup")
async def on_startup():
    """Настройка webhook при старте"""
    # Получаем URL текущего Space
    space_id = os.getenv("SPACE_ID", "")
    if space_id:
        webhook_url = f"https://{space_id}.hf.space/webhook"
        logger.info(f"📡 Setting webhook: {webhook_url}")
        await bot.set_webhook(webhook_url, drop_pending_updates=True)
        logger.info("✅ Webhook установлен")
    else:
        logger.warning("⚠️ SPACE_ID не найден, webhook не установлен")

@app.on_event("shutdown")
async def on_shutdown():
    """Удаление webhook при остановке"""
    logger.info("🛑 Удаляем webhook...")
    await bot.delete_webhook()
    await bot.session.close()
