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

# ТОЧНЫЕ ИМЕНА МОДЕЛЕЙ (Проверенные на проде)
FALLBACK_MODELS = [
    'gemini-2.5-flash-lite',  # Работает! (но лимиты 20/день)
    'gemini-2.5-flash', 
    'gemini-1.5-flash', 
    'gemini-1.5-pro'
]

# Оптимизированные модели для HF (Inference API Free Tier)
HF_TASKS = {
    "text": "meta-llama/Llama-3.2-3B-Instruct",      # Легкая и стабильная
    "vision": "Salesforce/blip-image-captioning-large", # Безотказная
    "audio": "openai/whisper-tiny",                  # Молниеносная транскрипция
    "reasoning": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B" 
}

SYSTEM_PROMPT = (
    "Ты — AI Prophet (ИИ Пророк). Твой разум опирается на мощь Gemini 2.5 и Llama 4.\n"
    "Стиль: мудрый, технологичный, лаконичный. Ты видишь суть вещей через код и образы.\n"
    "ВАЖНО: Если ты предлагаешь действия или следующие шаги, ВСЕГДА пиши их в формате:\n"
    "ШАГ: [Краткое название для кнопки]\n"
    "Это необходимо для магического интерфейса."
)
