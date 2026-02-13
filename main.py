# -*- coding: utf-8 -*-
# Copyright (c) 2026 dizel0110
# Project: AI Prophet (The bridge between ancient wisdom and future intelligence)
# Licensed under the Apache License, Version 2.0
# -----------------------------------------------------------------------------

import asyncio
import logging
import multiprocessing
import uvicorn
from aiogram import Bot, Dispatcher
from fastapi import FastAPI
from config import TOKEN, PORT
from core.network import apply_dns_patch
from handlers import messages, vip

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI для Hugging Face
app = FastAPI()
@app.get("/")
async def root(): return {"status": "AI Prophet Modular is Running"}

def start_web():
    uvicorn.run(app, host="0.0.0.0", port=PORT)

async def start_bot():
    apply_dns_patch()
    
    from config import HF_TOKEN, GEMINI_KEY
    if not HF_TOKEN: logger.warning("⚠️ HF_TOKEN is not set! Voice and WebSearch fallback will fail.")
    else: logger.info(f"✅ HF_TOKEN is loaded (prefix: {HF_TOKEN[:5]}...)")
    
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    
    # Регистрация роутеров
    dp.include_router(vip.router)
    dp.include_router(messages.router)
    
    logger.info(f"🚀 AI Prophet Modular System Started at {datetime.now().strftime('%H:%M:%S')}")
    # Очищаем очередь старых сообщений, чтобы избежать конфликтов при перезапуске
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    # Запуск веб-сервера
    p_web = multiprocessing.Process(target=start_web)
    p_web.start()
    
    try:
        asyncio.run(start_bot())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopped.")
    finally:
        p_web.terminate()
