import logging
import os
import base64
import requests
from google import genai
from google.genai import types as genai_types
from config import GEMINI_KEY, HF_TOKEN, SYSTEM_PROMPT, HF_SYSTEM_PROMPT, FALLBACK_MODELS, HF_TASKS

logger = logging.getLogger(__name__)

# Чистка ключей
CLEAN_HF_TOKEN = HF_TOKEN.strip() if HF_TOKEN else None

# Клиенты
gemini_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None
_chats = {}

def get_ai_chat(chat_id, model_name=None):
    if not gemini_client: return None
    if not model_name: model_name = FALLBACK_MODELS[0]
    session_key = f"{chat_id}_{model_name}"
    
    if session_key not in _chats:
        try:
            # ПОКА ОТКЛЮЧАЕМ ИНСТРУМЕНТЫ ДЛЯ СТАБИЛЬНОСТИ
            _chats[session_key] = gemini_client.chats.create(
                model=model_name,
                config=genai_types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.7
                )
            )
            logger.info(f"🆕 AI Session Created (Stable Mode): {session_key}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to init {model_name}: {e}")
            return None
    return _chats[session_key]

def get_hf_response(text=None, image_path=None, task="text"):
    if not CLEAN_HF_TOKEN: return "Ошибка: HF_TOKEN не настроен."
    
    model_id = HF_TASKS.get(task, HF_TASKS["text"])
    api_url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {CLEAN_HF_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        if task == "vision" and image_path:
            with open(image_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": text or "Опиши это фото."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}
                ]}],
                "max_tokens": 500
            }
        else:
            # Обычный текст
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": f"{HF_SYSTEM_PROMPT}\n\n{text}"}],
                "max_tokens": 500
            }

        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            logger.error(f"❌ HF Error {response.status_code}: {response.text}")
            return None

    except Exception as e:
        logger.error(f"❌ HF Engine Exception: {e}")
        return None

def transcribe_with_gemini(file_path):
    try:
        with open(file_path, 'rb') as f: bytes_data = f.read()
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                "Транскрибируй это аудио максимально точно.",
                genai_types.Part.from_bytes(data=bytes_data, mime_type='audio/ogg')
            ]
        )
        return response.text.strip() if response.text else None
    except Exception as e:
        logger.error(f"❌ Gemini Transcription Error: {e}")
    return None

def reset_chat(chat_id, model_name=None):
    if model_name: _chats.pop(f"{chat_id}_{model_name}", None)
    else:
        keys = [k for k in _chats if k.startswith(f"{chat_id}_")]
        for k in keys: _chats.pop(k, None)

def get_client():
    return gemini_client
