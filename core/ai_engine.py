import logging
import os
import base64
import requests
import threading
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
    headers = {"Authorization": f"Bearer {CLEAN_HF_TOKEN}"}

    try:
        # === АУДИО (Whisper) ===
        if task == "audio" and image_path:
            api_url = f"https://api-inference.huggingface.co/models/{model_id}"

            with open(image_path, "rb") as f:
                audio_data = f.read()

            logger.info(f"🎵 HF Whisper: отправка {len(audio_data)} байт на {api_url}")
            logger.info(f"📁 Файл: {image_path}")

            # Whisper принимает аудио напрямую (binary data), без Content-Type
            headers = {"Authorization": f"Bearer {CLEAN_HF_TOKEN}"}
            logger.info(f"📤 Отправка запроса к HF Whisper...")
            response = requests.post(api_url, headers=headers, data=audio_data, timeout=120)

            logger.info(f"📥 HF Whisper response status: {response.status_code}")
            logger.info(f"📄 HF Whisper response headers: {dict(response.headers)}")

            if response.status_code == 200:
                result = response.json()
                logger.info(f"📦 HF Whisper response JSON: {result}")
                logger.info(f"✅ Whisper результат: {result.get('text', '')[:100]}...")
                return result.get("text", "").strip()
            else:
                logger.error(f"❌ HF Audio Error {response.status_code}: {response.text[:500]}")
                return None

        # === ВИЖЕН (Llama 3.2 Vision) ===
        elif task == "vision" and image_path:
            api_url = "https://router.huggingface.co/v1/chat/completions"
            headers["Content-Type"] = "application/json"

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
            response = requests.post(api_url, headers=headers, json=payload, timeout=60)

            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                logger.error(f"❌ HF Vision Error {response.status_code}: {response.text}")
                return None

        # === ТЕКСТ (Qwen) ===
        else:
            api_url = "https://router.huggingface.co/v1/chat/completions"
            headers["Content-Type"] = "application/json"

            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": f"{HF_SYSTEM_PROMPT}\n\n{text}"}],
                "max_tokens": 500
            }
            response = requests.post(api_url, headers=headers, json=payload, timeout=60)

            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                logger.error(f"❌ HF Text Error {response.status_code}: {response.text}")
                return None

    except Exception as e:
        logger.error(f"❌ HF Engine Exception: {e}")
        return None

def transcribe_with_gemini(file_path, timeout_sec=60):
    """
    Транскрибация аудио через Gemini с таймаутом.
    timeout_sec: макс. время ожидания (по умолчанию 60 сек для голосовых Telegram)
    """
    if not gemini_client:
        logger.error("❌ Gemini client not initialized")
        return None

    # Проверка существования файла
    if not os.path.exists(file_path):
        logger.error(f"❌ Файл не найден: {file_path}")
        return None

    file_size = os.path.getsize(file_path)
    logger.info(f"🎤 Gemini транскрибация: {file_size / 1024:.1f} KB")

    # Проверка на пустой файл
    if file_size == 0:
        logger.error("❌ Пустой аудио файл!")
        return None

    # Проверка на слишком большие файлы (>25 MB)
    if file_size > 25 * 1024 * 1024:
        logger.warning(f"⚠️ Файл слишком большой ({file_size} bytes), Gemini может отказать")

    result = {"response": None, "error": None}

    def _transcribe():
        try:
            with open(file_path, 'rb') as f:
                bytes_data = f.read()

            # Пробуем разные MIME types для совместимости
            # WAV после конвертации или OGG из Telegram
            mime_types_to_try = ['audio/wav', 'audio/wave', 'audio/opus', 'audio/ogg', 'audio/webm']

            for mime_type in mime_types_to_try:
                try:
                    logger.info(f"📦 Пробуем MIME={mime_type}")

                    response = gemini_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=[
                            "Транскрибируй это аудио максимально точно. Верни только текст без комментариев.",
                            genai_types.Part.from_bytes(data=bytes_data, mime_type=mime_type)
                        ],
                        config=genai_types.GenerateContentConfig(
                            temperature=0,
                        )
                    )

                    if response and response.text:
                        logger.info(f"✅ Gemini ответил с MIME={mime_type}: {response.text[:50]}...")
                        result["response"] = response
                        return
                    else:
                        logger.warning(f"⚠️ Пустой ответ с MIME={mime_type}")

                except Exception as mime_error:
                    logger.warning(f"❌ Ошибка с MIME={mime_type}: {mime_error}")
                    continue

            # Если все MIME types не сработали
            result["error"] = Exception("Все MIME types не сработали")

        except Exception as e:
            result["error"] = e
            logger.error(f"❌ Ошибка в _transcribe: {e}")

    # Запускаем в отдельном потоке с таймаутом
    thread = threading.Thread(target=_transcribe)
    thread.start()
    thread.join(timeout=timeout_sec)

    if thread.is_alive():
        logger.warning(f"⏱️ Gemini timeout после {timeout_sec} сек — аудио слишком длинное")
        return None

    # Проверяем результат
    if result["error"]:
        error_str = str(result["error"])
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            logger.warning("🚫 Gemini quota exceeded (429)")
        else:
            logger.error(f"❌ Gemini Transcription Error: {result['error']}")
        return None

    if result["response"] and result["response"].text:
        logger.info(f"✅ Gemini транскрибация успешна: {len(result['response'].text)} символов")
        return result["response"].text.strip()
    else:
        logger.warning("⚠️ Gemini вернул пустой ответ")
        return None

def reset_chat(chat_id, model_name=None):
    if model_name: _chats.pop(f"{chat_id}_{model_name}", None)
    else:
        keys = [k for k in _chats if k.startswith(f"{chat_id}_")]
        for k in keys: _chats.pop(k, None)

def get_client():
    return gemini_client
