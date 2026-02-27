# -*- coding: utf-8 -*-
"""
Telegram Webhook для Hugging Face Spaces
Работает ТОЛЬКО через входящие соединения от Telegram
Исходящие запросы к api.telegram.org НЕ используются
"""

import os
import logging
from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher, types
from aiogram.methods import TelegramMethod
from aiogram.client.session.aiohttp import AiohttpSession
from config import TOKEN, PORT
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

app = FastAPI()

@app.get("/")
async def root():
    """Health check"""
    space_id = os.getenv("SPACE_ID", "local")
    return {
        "status": "AI Prophet Webhook",
        "mode": "webhook_only",
        "space_id": space_id
    }

@app.get("/webhook")
async def get_webhook():
    """Проверка webhook"""
    return {"status": "ok", "mode": "webhook"}

@app.post("/webhook")
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

@app.on_event("startup")
async def on_startup():
    """Настройка webhook при старте"""
    space_id = os.getenv("SPACE_ID")
    
    if space_id:
        # Формируем URL текущего Space
        webhook_url = f"https://{space_id}.hf.space/webhook"
        
        logger.info(f"📡 HF Spaces detected: {space_id}")
        logger.info(f"📡 Webhook URL: {webhook_url}")
        logger.info("⚠️ ВАЖНО: Вам нужно ВРУЧНУЮ установить webhook через BotFather")
        logger.info(f"   Отправьте @BotFather: /setwebhook {webhook_url}")
        
        # Пытаемся установить webhook (может не сработать из-за блокировки)
        try:
            await bot.set_webhook(webhook_url, drop_pending_updates=True)
            logger.info("✅ Webhook установлен автоматически")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось установить webhook автоматически: {e}")
            logger.info("📝 Установите webhook вручную через @BotFather")
    else:
        logger.warning("⚠️ SPACE_ID не найден. Запустите на HF Spaces для webhook.")

@app.on_event("shutdown")
async def on_shutdown():
    """Очистка при остановке"""
    logger.info("🛑 Остановка бота...")
    try:
        await bot.delete_webhook()
        logger.info("✅ Webhook удалён")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось удалить webhook: {e}")
    
    await bot.session.close()
