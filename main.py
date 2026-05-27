# -*- coding: utf-8 -*-
# Copyright (c) 2026 dizel0110
# Project: AI Prophet (The bridge between ancient wisdom and future intelligence)
# Licensed under the Apache License, Version 2.0
# -----------------------------------------------------------------------------

import os
import asyncio
import logging
import multiprocessing
import uvicorn
from datetime import datetime
from pathlib import Path
from aiogram import Bot, Dispatcher
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from config import TOKEN, PORT, PLATFORM
from core.network import apply_dns_patch
from handlers import messages, vip, limits, massage

# Настройка логов
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"bot_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s:%(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
logging.getLogger("google.genai").setLevel(logging.WARNING)
import time
logger = logging.getLogger(__name__)

# Проверка: работаем на HF Spaces?
IS_HF_SPACE = os.getenv("SPACE_ID") is not None

# FastAPI приложение
app = FastAPI()

# Раздача статики (Mini App)
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Dispatcher создаётся ОДИН раз на весь lifecycle
dp = Dispatcher()
dp.include_router(vip.router)
dp.include_router(limits.router)
dp.include_router(massage.router)
dp.include_router(messages.router)

# Webhook routes (только на HF Spaces, после dp — чтобы не красть роутеры)
if IS_HF_SPACE:
    try:
        from webhook_only import setup_webhook_routes
        setup_webhook_routes(app)
    except RuntimeError:
        logger.info("📡 Webhook routes пропущены (роутеры уже в dp)")

@app.get("/")
async def root():
    mode_map = {"hf": "HF Spaces", "render": "Render.com", "local": "Polling (Local)"}
    mode = mode_map.get(PLATFORM, PLATFORM)
    return {"status": f"AI Prophet ({mode})", "platform": PLATFORM}

def start_web():
    uvicorn.run(app, host="0.0.0.0", port=PORT)

async def start_bot_polling():
    """Polling режим для локальной разработки"""
    apply_dns_patch()

    # Очистка временной папки при старте
    from config import TEMP_DIR
    import shutil
    if os.path.exists(TEMP_DIR):
        try:
            for item in os.listdir(TEMP_DIR):
                item_path = os.path.join(TEMP_DIR, item)
                if os.path.isfile(item_path): os.remove(item_path)
                elif os.path.isdir(item_path): shutil.rmtree(item_path)
            logger.info("🧹 Временная папка очищена")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось полностью очистить temp: {e}")
    else: os.makedirs(TEMP_DIR)

    from aiogram.types import BotCommand
    from config import HF_TOKEN, GEMINI_KEY

    telegram_api_url = os.getenv("TELEGRAM_API_URL")
    if telegram_api_url:
        from aiogram.client.session.aiohttp import AiohttpSession
        from aiogram.client.telegram import TelegramAPIServer
        server = TelegramAPIServer.from_base(telegram_api_url)
        session = AiohttpSession()
        session.api = server
        bot = Bot(token=TOKEN, session=session)
        logger.info(f"🔗 Кастомный Telegram API: {telegram_api_url}")
    elif IS_HF_SPACE:
        PROXY_URL = os.getenv("PROXY_URL")
        if PROXY_URL:
            from aiogram.client.session.aiohttp import AiohttpSession
            logger.info(f"🔗 HF Spaces: используем прокси {PROXY_URL}")
            session = AiohttpSession(proxy=PROXY_URL)
            bot = Bot(token=TOKEN, session=session)
        else:
            logger.error("❌ HF Spaces: установите PROXY_URL или TELEGRAM_API_URL")
            raise RuntimeError("PROXY_URL or TELEGRAM_API_URL required on HF Spaces")
    else:
        bot = Bot(token=TOKEN)

    # Регистрация команд для подсказок (autocomplete)
    commands = [
        BotCommand(command="start", description="Запустить Пророка и открыть меню"),
        BotCommand(command="help", description="Показать все возможности"),
        BotCommand(command="playlist", description="Собрать свой плейлист"),
        BotCommand(command="playlist_example", description="Примеры и обучение (Академия)"),
        BotCommand(command="massage", description="🖐 Массажный салон"),
        BotCommand(command="settings", description="Выбрать мозг бота (Gemini/HF)"),
        BotCommand(command="dizel0110", description="Вход в VIP режим"),
        BotCommand(command="stop", description="Остановить текущие действия")
    ]
    await bot.set_my_commands(commands)

    if not HF_TOKEN: logger.warning("⚠️ HF_TOKEN is not set! Voice and WebSearch fallback will fail.")
    else: logger.info(f"✅ HF_TOKEN is loaded (prefix: {HF_TOKEN[:5]}...)")

    logger.info(f"🚀 AI Prophet Modular System Started at {datetime.now().strftime('%H:%M:%S')}")

    # На HF Spaces не удаляем webhook (блокируется исходящие)
    if not IS_HF_SPACE:
        await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # Запуск веб-сервера
    p_web = multiprocessing.Process(target=start_web)
    p_web.start()

    logger.info("🛰️ Система авто-восстановления Пророка запущена (Бесконечный цикл)")

    # Polling на всех платформах (на HF блокируется без PROXY_URL)
    platform_name = {"hf": "HF Spaces", "render": "Render.com", "local": "Local"}.get(PLATFORM, PLATFORM)
    logger.info(f"📡 {platform_name}: Запуск polling режима")
    while True:
        try:
            asyncio.run(start_bot_polling())
        except (KeyboardInterrupt, SystemExit):
            logger.info("🛑 Бот остановлен вручную.")
            break
        except Exception as e:
            logger.error(f"🧨 КРИТИЧЕСКИЙ СБОЙ В ЦИКЛЕ: {e}")
            logger.info("⏳ Попытка воскрешения через 15 секунд...")
            time.sleep(15)

    p_web.terminate()
