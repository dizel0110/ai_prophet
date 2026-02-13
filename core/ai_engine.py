import logging
import requests
import os
from google import genai
from google.genai import types as genai_types
from config import GEMINI_KEY, HF_TOKEN, SYSTEM_PROMPT, FALLBACK_MODELS, HF_TASKS

logger = logging.getLogger(__name__)

# Клиент Gemini
gemini_client = genai.Client(api_key=GEMINI_KEY)
_chats = {}

def get_ai_chat(chat_id, model_name=None):
    if not model_name: model_name = FALLBACK_MODELS[0]
    session_key = f"{chat_id}_{model_name}"
    
    if session_key not in _chats:
        try:
            _chats[session_key] = gemini_client.chats.create(
                model=model_name,
                config=genai_types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.7
                )
            )
            logger.info(f"🆕 AI Session Created: {session_key}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to init {model_name}: {e}")
            return None
    return _chats[session_key]

def get_hf_response(text=None, image_path=None, task="text"):
    if not HF_TOKEN: return "Ошибка: HF_TOKEN не настроен."
    
    # ФЕВРАЛЬ 2026: ПРЯМОЙ РОУТЕР (без hf-inference префикса для v1)
    # И новый путь для бинарных данных
    model_id = HF_TASKS.get(task, HF_TASKS["text"])
    
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "x-wait-for-model": "true"
    }
    
    try:
        if task == "text":
            # Роутер на основном домене v1
            api_url = "https://router.huggingface.co/v1/chat/completions"
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": f"{SYSTEM_PROMPT}\n\n{text}"}],
                "max_tokens": 500
            }
            response = requests.post(api_url, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                logger.info(f"✅ HF V1 Chat Success for {model_id}")
                return response.json()['choices'][0]['message']['content']
            else:
                logger.warning(f"⚠️ HF V1 failed ({response.status_code}), trying models path...")
        
        # Запасной путь и путь для МЕДИА
        api_url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
        
        if task == "vision" and image_path:
            with open(image_path, "rb") as f: data = f.read()
            response = requests.post(api_url, headers=headers, data=data, timeout=60)
        elif task == "audio" and image_path:
            with open(image_path, "rb") as f: data = f.read()
            response = requests.post(api_url, headers=headers, data=data, timeout=60)
        elif task == "text":
            response = requests.post(api_url, headers=headers, json={"inputs": text}, timeout=60)
        else:
            return None

        if response.status_code != 200:
            logger.error(f"❌ HF Router Error {response.status_code} for {model_id}: {response.text[:200]}")
            return None

        result = response.json()
        logger.info(f"✅ HF {task} result received.")
        
        if isinstance(result, dict):
            return result.get('text', result.get('generated_text', str(result)))
        if isinstance(result, list) and len(result) > 0:
            item = result[0]
            if isinstance(item, dict):
                resp = item.get('generated_text', item.get('text', ''))
                return resp
        return str(result)

    except Exception as e:
        logger.error(f"❌ HF Engine Exception: {e}")
        return None

def transcribe_with_gemini(file_path):
    """Использует Gemini для транскрибации аудио"""
    try:
        model = FALLBACK_MODELS[0]
        with open(file_path, 'rb') as f: bytes_data = f.read()
        
        # Gemini 3/2.5 отлично понимают аудио
        prompt = "Транскрибируй это аудио сообщение максимально точно. Напиши только текст."
        response = gemini_client.models.generate_content(
            model=model,
            contents=[prompt, genai_types.Part.from_bytes(data=bytes_data, mime_type='audio/ogg')]
        )
        if response.text:
            return response.text.strip()
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
