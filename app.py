# Hugging Face Spaces Entry Point
from main import start_bot, start_web
import multiprocessing
import asyncio
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Запуск веб-сервера (для пинга HF)
    p_web = multiprocessing.Process(target=start_web)
    p_web.start()
    
    try:
        # Запуск бота
        asyncio.run(start_bot())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        p_web.terminate()
