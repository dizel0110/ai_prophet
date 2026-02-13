import logging
import requests
import os
import base64
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
    
    model_id = HF_TASKS.get(task, HF_TASKS["text"])
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
        "x-wait-for-model": "true"
    }
    
    try:
        # ПУТЬ 2026: Все через OpenAI-совместимый Роутер
        api_url = "https://router.huggingface.co/v1/chat/completions"
        
        if task == "vision" and image_path:
            with open(image_path, "rb") as f:
                encoded_image = base64.b64encode(f.read()).decode('utf-8')
            
            payload = {
                "model": model_id,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": text or "Опиши это изображение как AI Prophet."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                    ]
                }],
                "max_tokens": 500
            }
        elif task == "audio" and image_path:
            # Для аудио Роутер 2026 требует multipart или прямой путь к v1/audio/transcriptions
            # Но самый надежный - прямой домен Hugging Face v1
            audio_url = f"https://router.huggingface.co/v1/audio/transcriptions"
            with open(image_path, "rb") as f:
                files = {"file": f}
                audio_headers = {"Authorization": f"Bearer {HF_TOKEN}"}
                response = requests.post(audio_url, headers=audio_headers, files=files, data={"model": model_id}, timeout=60)
                if response.status_code == 200:
                    return response.json().get('text', '')
                else:
                    # Fallback to direct model path for binary
                    api_url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
                    with open(image_path, "rb") as f: data = f.read()
                    response = requests.post(api_url, headers=audio_headers, data=data, timeout=60)
                    if response.status_code == 200:
                        res = response.json()
                        return res[0].get('text', '') if isinstance(res, list) else res.get('text', str(res))
                    return None
        else:
            # Обычный текст
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": f"{SYSTEM_PROMPT}\n\n{text}"}],
                "max_tokens": 500
            }

        if task != "audio":
            response = requests.post(api_url, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ HF {task} success via Router V1")
                return result['choices'][0]['message']['content']
            else:
                logger.error(f"❌ HF Router Error {response.status_code}: {response.text[:200]}")
                return None

    except Exception as e:
        logger.error(f"❌ HF Engine Exception: {e}")
        return None

def transcribe_with_gemini(file_path):
    """Использует Gemini для транскрибации аудио (самый надежный путь 2026)"""
    try:
        with open(file_path, 'rb') as f: bytes_data = f.read()
        # Используем Gemini 1.5 Flash как самую стабильную для аудио-задач
        response = gemini_client.models.generate_content(
            model='gemini-1.5-flash',
            contents=[
                "Транскрибируй это аудио максимально точно. Напиши только текст.",
                genai_types.Part.from_bytes(data=bytes_data, mime_type='audio/ogg')
            ]
        )
        if response.text:
            logger.info("✅ Gemini Audio Transcription Success")
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
