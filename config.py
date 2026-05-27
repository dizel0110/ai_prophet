import os
from dotenv import load_dotenv

load_dotenv()

PLATFORM = os.getenv("PLATFORM", "local").lower()  # hf | render | local
TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
HF_TOKEN = os.getenv("HF_TOKEN")
VIP_PASSWORD = os.getenv("VIP_PASSWORD", "prophet2026")
VIP_RESET_PASSWORD = os.getenv("VIP_RESET_PASSWORD", "reset2026")
GEM_BOT_URL = os.getenv("GEM_BOT_URL")
TELEGRAM_API_URL = os.getenv("TELEGRAM_API_URL")  # Cloudflare Worker proxy для HF Spaces

PORT = int(os.getenv("PORT", 7860))
OWNER_USERNAME = "dizel0110"

# Mini App URL — Telegram требует HTTPS
# На HF Spaces формируется автоматически, для локали — GitHub Pages или ngrok
LOCAL_MINI_APP_URL = os.getenv("MINI_APP_URL", "https://dizel0110.github.io/ai_prophet/")

def get_base_url() -> str:
    """Базовый URL для Mini App"""
    # Render: Mini App живёт на HF Spaces
    if PLATFORM == "render":
        return LOCAL_MINI_APP_URL.rstrip("/")
    # HF Spaces: авто-определение
    space_id = os.getenv("SPACE_ID")
    if space_id:
        slug = space_id.replace("/", "-").replace("_", "-")
        return f"https://{slug}.hf.space"
    # Локаль / GitHub Pages
    return LOCAL_MINI_APP_URL.rstrip("/")

# Директории
TEMP_DIR = "temp"
if not os.path.exists(TEMP_DIR): os.makedirs(TEMP_DIR)

# АКТУАЛЬНЫЕ МОДЕЛИ (Май 2026)
FALLBACK_MODELS = [
    'gemini-3.5-flash',       # Флагман мая 2026 — лучшая для агентов, 4x быстрее
    'gemini-3.1-flash',       # Предыдущий флагман
    'gemini-3-flash-preview',
    'gemini-2.5-flash',       # Стабильная база
    'gemini-2.5-pro'
]

# Модели для HF Router (OpenAI Compatible)
HF_TASKS = {
    "text": "Qwen/Qwen2.5-7B-Instruct",
    "vision": "meta-llama/Llama-3.2-11B-Vision-Instruct",
    "audio": "openai/whisper-large-v3-turbo",
    "reasoning": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
}

SYSTEM_PROMPT = (
    "Ты — AI Prophet (ИИ Пророк). Твой разум опирается на мощь Gemini 3.5 Flash.\n"
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
    "ВАЖНО: Если пользователь просит найти музыку, видео, трек или исполнителя, используй формат:\n"
    "[MEDIA: запрос, тип, количество]\n"
    "- запрос: что искать (жанр, исполнитель, название)\n"
    "- тип: 'audio' (если нужна музыка/песня) или 'video' (если нужен клип/видео)\n"
    "- количество: по умолчанию 5 (для плейлистов) или 1 (для конкретного трека)\n\n"
    "Примеры:\n"
    "- [MEDIA: Pink Floyd best songs, audio, 5]\n"
    "- [MEDIA: Rick Astley Never Gonna Give You Up, video, 1]\n"
    "- [MEDIA: Ambient music for coding, audio, 10]"
)
