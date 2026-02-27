# -*- coding: utf-8 -*-
"""
Telegram Webhook для Hugging Face Spaces
Использует webhook response для отправки ответов без исходящих запросов
"""

import os
import logging
import json
from contextvars import ContextVar
from fastapi import FastAPI, Request
from fastapi.responses import Response
from aiogram import Bot, Dispatcher, types
from aiogram.methods.base import TelegramMethod
from config import TOKEN
from handlers import messages, vip, limits

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

# Context var для хранения webhook response
_webhook_response: ContextVar[TelegramMethod | None] = ContextVar('_webhook_response', default=None)

# Инициализация бота с кастомной сессией
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Регистрация роутеров
dp.include_router(vip.router)
dp.include_router(limits.router)
dp.include_router(messages.router)


@dp.update.middleware()
async def capture_webhook_response(handler, event, data):
    """
    Middleware перехватывает вызовы bot() и сохраняет их для webhook response
    """
    # Сохраняем оригинальный метод __call__ бота
    original_call = bot.__call__

    async def capture_call(method, *args, **kwargs):
        """Перехватывает вызов бота и сохраняет метод"""
        result = await original_call(method)
        # Сохраняем метод для webhook response
        _webhook_response.set(method)
        return result

    # Временно заменяем __call__
    bot.__call__ = capture_call

    try:
        # Вызываем хендлер
        return await handler(event, data)
    finally:
        # Восстанавливаем оригинальный метод
        bot.__call__ = original_call

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
        Обработка обновлений от Telegram с webhook response

        Telegram позволяет вернуть метод API прямо в HTTP response webhook'а.
        Это избегает необходимости делать исходящий запрос к api.telegram.org.
        """
        try:
            # Получаем JSON от Telegram
            update_dict = await request.json()
            update = types.Update(**update_dict)

            logger.info(f"📥 Получено обновление: id={update.update_id}, type={update.event_type}")

            # Сбрасываем webhook response перед обработкой
            _webhook_response.set(None)

            # Обрабатываем обновление
            await dp.feed_update(bot, update)

            # Проверяем, был ли сохранён webhook response
            response_method = _webhook_response.get()

            if response_method:
                logger.info(f"📤 Webhook response: {response_method.__class__.__name__}")
                # Сериализуем в JSON для Telegram
                response_data = response_method.model_dump(mode="json", by_alias=True)
                return Response(
                    content=json.dumps(response_data),
                    media_type="application/json"
                )

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
