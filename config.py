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

# ТОЧНЫЕ ИМЕНА МОДЕЛЕЙ (Актуально на Февраль 2026)
FALLBACK_MODELS = [
    'gemini-3-flash-preview', # Новинка: скорость и ум
    'gemini-2.5-flash',       # Стабильный стандарт
    'gemini-2.5-flash-lite',  # Макс. квоты
    'gemini-1.5-flash'        # Самый надежный резерв
]

# Оптимизированные модели для HF (Inference API Free Tier)
HF_TASKS = {
    "text": "meta-llama/Llama-3.2-3B-Instruct",      # Быстрая и стабильная
    "vision": "Salesforce/blip-image-captioning-large", # Всегда онлайн
    "audio": "openai/whisper-large-v3-turbo",         # Скорость и точность
    "reasoning": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B" 
}

SYSTEM_PROMPT = (
    "Ты — AI Prophet (ИИ Пророк). Твой разум опирается на мощь Gemini 2.5 и Llama 4.\n"
    "Стиль: мудрый, технологичный, лаконичный. Ты видишь суть вещей через код и образы.\n"
    "ВАЖНО: Если ты предлагаешь действия или следующие шаги, ВСЕГДА пиши их в формате:\n"
    "ШАГ: [Краткое название для кнопки]\n"
    "Это необходимо для магического интерфейса."
)
