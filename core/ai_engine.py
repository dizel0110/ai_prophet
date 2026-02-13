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
    
    # 2026: Прямой путь через Роутер без лишних префиксов
    BASE_ROUTER_URL = "https://router.huggingface.co"
    model_id = HF_TASKS.get(task, HF_TASKS["text"])
    
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "x-wait-for-model": "true"
    }
    
    try:
        if task == "text":
            # Используем самый надежный OpenAI-совместимый путь
            api_url = f"{BASE_ROUTER_URL}/v1/chat/completions"
            payload = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text}
                ],
                "max_tokens": 500,
                "temperature": 0.7
            }
            response = requests.post(api_url, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                logger.info(f"✅ HF V1 Chat Success for {model_id}")
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                # Попытка №2: Если v1 не сработал, пробуем старый /models/ путь, но через роутер
                fallback_url = f"{BASE_ROUTER_URL}/hf-inference/models/{model_id}"
                payload_alt = {"inputs": text, "parameters": {"max_new_tokens": 500}}
                response = requests.post(fallback_url, headers=headers, json=payload_alt, timeout=60)
        
        else:
            # Для медиа (аудио/фото)
            api_url = f"{BASE_ROUTER_URL}/hf-inference/models/{model_id}"
            if task == "vision" and image_path:
                with open(image_path, "rb") as f: data = f.read()
                response = requests.post(api_url, headers=headers, data=data, timeout=60)
            elif task == "audio" and image_path:
                with open(image_path, "rb") as f: data = f.read()
                headers["Content-Type"] = "audio/ogg"
                response = requests.post(api_url, headers=headers, data=data, timeout=60)
            else:
                return None

        if response.status_code != 200:
            logger.error(f"❌ HF Router Error {response.status_code} for {model_id}: {response.text[:150]}")
            return None

        result = response.json()
        if isinstance(result, dict):
            return result.get('text', result.get('generated_text', str(result)))
        if isinstance(result, list) and len(result) > 0:
            item = result[0]
            if isinstance(item, dict):
                resp = item.get('generated_text', item.get('text', ''))
                return resp.split("Prophet:")[-1].strip() if "Prophet:" in resp else resp
        return str(result)

    except Exception as e:
        logger.error(f"❌ HF Engine Exception: {e}")
        return None

def reset_chat(chat_id, model_name=None):
    if model_name: _chats.pop(f"{chat_id}_{model_name}", None)
    else:
        keys = [k for k in _chats if k.startswith(f"{chat_id}_")]
        for k in keys: _chats.pop(k, None)

def get_client():
    return gemini_client
