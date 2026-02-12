import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")

# Базовый URL для Hugging Face Inference API через Router (актуально на Февраль 2026)
HF_ROUTER_BASE_URL = "https://router.huggingface.co/hf-inference/models/"

PORT = int(os.getenv("PORT", 7860))
OWNER_USERNAME = "dizel0110"

# Директории
TEMP_DIR = "temp"
if not os.path.exists(TEMP_DIR): os.makedirs(TEMP_DIR)

# ТОЧНЫЕ ИМЕНА МОДЕЛЕЙ (Февраль 2026)
FALLBACK_MODELS = [
    'gemini-2.0-flash',       # Основная активная
    'gemini-1.5-flash', 
    'gemini-2.0-flash-lite'
]

# Оптимизированные модели для HF (Router-Ready)
HF_TASKS = {
    "text": "Qwen/Qwen2.5-7B-Instruct",             # Рекомендуемая HF для роутера
    "vision": "Salesforce/blip-image-captioning-base", 
    "audio": "openai/whisper-large-v3", 
    "reasoning": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B" 
}

SYSTEM_PROMPT = (
    "Ты — AI Prophet (ИИ Пророк). Твой разум опирается на мощь Gemini 2.5 и Llama 4.\n"
    "Стиль: мудрый, технологичный, лаконичный. Ты видишь суть вещей через код и образы.\n"
    "ВАЖНО: Если ты предлагаешь действия или следующие шаги, ВСЕГДА пиши их в формате:\n"
    "ШАГ: [Краткое название для кнопки]\n"
    "Это необходимо для магического интерфейса."
)
