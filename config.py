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

# АКТУАЛЬНЫЕ МОДЕЛИ (Февраль 2026)
FALLBACK_MODELS = [
    'gemini-3-flash-preview', # Флагман 2026 года
    'gemini-2.5-flash',       # Основная стабильная база
    'gemini-2.5-pro'
]

# Модели для HF Router (OpenAI Compatible)
# Qwen2.5-7B-Instruct подтвержден как рабочий на роутере
HF_TASKS = {
    "text": "Qwen/Qwen2.5-7B-Instruct",            
    "vision": "meta-llama/Llama-3.2-11B-Vision-Instruct", # Классика вижена для роутера
    "audio": "openai/whisper-large-v3", 
    "reasoning": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B" 
}

SYSTEM_PROMPT = (
    "Ты — AI Prophet (ИИ Пророк). Твой разум опирается на мощь Gemini 3 и DeepSeek.\n"
    "Стиль: мудрый, технологичный, лаконичный. Ты видишь суть вещей через код и образы.\n"
    "ВАЖНО: Если ты предлагаешь действия или следующие шаги, ВСЕГДА пиши их в формате:\n"
    "ШАГ: [Краткое название для кнопки]\n"
    "Это необходимо для магического интерфейса."
)

# Упрощенный промпт для HF (без требования шагов)
HF_SYSTEM_PROMPT = (
    "Ты — AI Prophet (ИИ Пророк). Твой разум опирается на мощь Qwen и DeepSeek.\n"
    "Стиль: мудрый, технологичный, лаконичный. Ты видишь суть вещей через код и образы.\n"
    "Отвечай естественно и по существу. Будь дружелюбен и полезен.\n\n"
    "ВАЖНО: Если пользователь просит создать музыкальный плейлист, используй формат:\n"
    "[PLAYLIST: жанр, настроение, количество]\n"
    "Количество — опционально (по умолчанию 5 треков).\n"
    "Примеры:\n"
    "- [PLAYLIST: Ambient, Концентрация]\n"
    "- [PLAYLIST: Rock, Энергия, 10]\n"
    "- [PLAYLIST: Lo-Fi, Релакс, 3]"
)
