import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
PORT = int(os.getenv("PORT", 7860))
OWNER_USERNAME = "dizel0110"

# Директории
TEMP_DIR = "temp"
if not os.path.exists(TEMP_DIR): os.makedirs(TEMP_DIR)

# ТОЧНЫЕ ИМЕНА МОДЕЛЕЙ НА 2026 ГОД
# Имена без префикса 'models/', библиотека сама их добавит если нужно
FALLBACK_MODELS = [
    'gemini-2.5-flash',       # Флагман скорости и ума
    'gemini-2.5-flash-lite',  # Массивный масштаб, минимум лимитов
    'gemini-1.5-flash',       # Вечная классика (Stable)
    'gemini-1.5-flash-8b'    # Самая быстрая для простых задач
]

# Оптимизированные модели для HF (Inference API Free Tier)
# Выбираем те, что точно работают в Serverless режиме
HF_TASKS = {
    "text": "meta-llama/Llama-3.1-8B-Instruct",      # Всегда в онлайне
    "vision": "microsoft/phi-3-vision-128k-instruct", # Современное легкое зрение
    "audio": "openai/whisper-small",                  # Легче, чем turbo, меньше падений
    "reasoning": "deepseek-ai/DeepSeek-R1-Distill-Llama-8B" # Интеллект DeepSeek в легком весе
}

SYSTEM_PROMPT = (
    "Ты — AI Prophet (ИИ Пророк). Твой разум опирается на мощь Gemini 2.5 и Llama 4.\n"
    "Стиль: мудрый, технологичный, лаконичный. Ты видишь суть вещей через код и образы."
)
