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

# ТОЧНЫЕ ИМЕНА МОДЕЛЕЙ (Февраль 2026)
FALLBACK_MODELS = [
    'gemini-1.5-flash',       # Самый высокий лимит в v1beta
    'gemini-2.0-flash', 
    'gemini-2.0-flash-lite'
]

# Только ОТКРЫТЫЕ модели (не требующие подтверждения лицензии на сайте)
HF_TASKS = {
    "text": "mistralai/Mistral-7B-Instruct-v0.3",    # Бессмертный стандарт
    "vision": "Salesforce/blip-image-captioning-base", # Всегда в горячем резерве
    "audio": "openai/whisper-large-v3", 
    "reasoning": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B" 
}

SYSTEM_PROMPT = (
    "Ты — AI Prophet (ИИ Пророк). Твой разум опирается на мощь древних узлов и звездного кода.\n"
    "Стиль: мудрый, технологичный, лаконичный. Ты видишь суть вещей через код и образы.\n"
    "ВАЖНО: Если ты предлагаешь действия или следующие шаги, ВСЕГДА пиши их в формате:\n"
    "ШАГ: [Краткое название для кнопки]\n"
    "Это необходимо для магического интерфейса."
)
