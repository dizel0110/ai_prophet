import os
import re
import logging
import asyncio
import random
import glob
import json
from datetime import datetime
from aiogram import Router, types, Bot, F
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from core.ai_engine import get_ai_chat, get_client, reset_chat, get_hf_response, transcribe_with_gemini, transcribe_local
from core.tools import web_search, search_media_content, AVAILABLE_FUNCTIONS
from core.tools import web_search, search_media_content, download_audio, AVAILABLE_FUNCTIONS
from config import FALLBACK_MODELS, TEMP_DIR
from google.genai import types as genai_types

logger = logging.getLogger(__name__)
router = Router()

# Путь к файлу настроек
SETTINGS_FILE = os.path.join(TEMP_DIR, "user_settings.json")

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception: return {}
    return {}

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")

user_settings = load_settings()

def cleanup_file(path):
    """Безопасное удаление файла"""
    try:
        if path and os.path.exists(path):
            os.remove(path)
            logger.info(f"🗑️ Удален временный файл: {path}")
    except Exception as e:
        logger.error(f"❌ Ошибка удаления {path}: {e}")

def cleanup_user_temp(chat_id):
    """Удаление всех старых файлов конкретного пользователя"""
    pattern = os.path.join(TEMP_DIR, f"task_{chat_id}_*")
    for f in glob.glob(pattern):
        cleanup_file(f)
    pattern_audio = os.path.join(TEMP_DIR, f"audio_{chat_id}_*")
    for f in glob.glob(pattern_audio):
        cleanup_file(f)

def get_main_menu():
    web_app_url = "https://dizel0110.github.io/ai_prophet/"
    kb = [
        [KeyboardButton(text="📱 Открыть Mini App", web_app=WebAppInfo(url=web_app_url))],
        [KeyboardButton(text="🔮 Предсказание"), KeyboardButton(text="🎙 Голос Судьбы")],
        [KeyboardButton(text="🖼 Видение"), KeyboardButton(text="⚙️ Настройки")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_settings_menu(current_engine):
    engines = {
        "auto": "🤖 Авто (Gemini -> HF)",
        "gemini": "💎 Только Gemini",
        "hf": "🧿 Только Hugging Face"
    }
    kb = []
    for code, name in engines.items():
        prefix = "✅ " if current_engine == code else ""
        kb.append([KeyboardButton(text=f"{prefix}{name}")])
    kb.append([KeyboardButton(text="⬅️ Назад")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_voice_confirmation_keyboard(chat_id, text):
    """
    Создает inline-клавиатуру для подтверждения голосового сообщения.
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Сохраняем текст в user_settings для последующего выполнения
    voice_confirm_key = f"voice_confirm_{chat_id}"
    user_settings.setdefault(chat_id, {})['pending_voice_text'] = text
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выполнить", callback_data=f"voice_confirm:{chat_id}"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"voice_edit:{chat_id}")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"voice_cancel:{chat_id}")
        ]
    ])
    return kb

def parse_steps_and_create_kb(text, chat_id):
    """Парсит текст на наличие 'ШАГ:' и создает клавиатуру"""
    kb = []
    lines = text.split('\n')
    new_text_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        if stripped_line and (stripped_line.upper().startswith("ШАГ:") or stripped_line.upper().startswith("STEP:")):
            step_text = stripped_line.split(":", 1)[1].strip().strip("[]")
            # Telegram limit: 64 bytes. Префикс "vision_task:custom:" = 19 байт. Остается 45 байт.
            # Кириллица в UTF-8 = 2 байта/символ, поэтому берем max 20 символов.
            callback_val = step_text[:20]
            btn_text = step_text[:30] + "..." if len(step_text) > 30 else step_text
            kb.append([InlineKeyboardButton(text=f"🔮 {btn_text}", callback_data=f"vision_task:custom:{callback_val}")])
        else:
            new_text_lines.append(line)
    
    # Всегда добавляем кнопку своего варианта
    kb.append([InlineKeyboardButton(text="⌨️ Свой вариант", callback_data="vision_task:manual")])
    
    remaining_text = "\n".join(new_text_lines).strip()
    return remaining_text, InlineKeyboardMarkup(inline_keyboard=kb)

def parse_and_execute_tools(text, chat_id: str = None):
    """
    Парсит текст на наличие маркеров инструментов и выполняет их.
    Поддерживает: [MEDIA: query, type, count] и [PLAYLIST: genre, mood, count]
    
    chat_id: ID чата для загрузки пользовательских лимитов
    
    Returns:
        tuple: (clean_text, result)
        result может быть:
            - dict с ключом "type": "playlist" | "single_audio"
            - None если маркеры не найдены
    """
    import re

    # 1. Сначала ищем новый маркер [MEDIA: ...]
    media_pattern = r'\[MEDIA:\s*([^,]+),\s*([^,]+)(?:,\s*(\d+))?\]'
    match_media = re.search(media_pattern, text, re.IGNORECASE)

    if match_media:
        query = match_media.group(1).strip()
        m_type = match_media.group(2).strip().lower() # 'audio' или 'video'
        count = int(match_media.group(3)) if match_media.group(3) else 5

        logger.info(f"📹 Обнаружен маркер MEDIA: query={query}, type={m_type}, count={count}")

        # Вызываем универсальный поиск медиа с chat_id
        result = search_media_content(query=query, media_type=m_type, count=count, chat_id=chat_id)

        # Убираем маркер
        clean_text = re.sub(media_pattern, '', text, flags=re.IGNORECASE).strip()
        
        # Определяем тип результата
        if result.get("count", 0) > 1:
            # Плейлист
            return clean_text, {"type": "playlist", "data": result}
        else:
            # Одиночный трек
            return clean_text, {"type": "single_audio", "data": result}

    # 2. Ищем старый маркер [PLAYLIST: ...] для совместимости
    playlist_pattern = r'\[PLAYLIST:\s*([^,]+),\s*([^,\]]+)(?:,\s*(\d+))?\]'
    match_playlist = re.search(playlist_pattern, text, re.IGNORECASE)

    if match_playlist:
        genre = match_playlist.group(1).strip()
        mood = match_playlist.group(2).strip()
        count = int(match_playlist.group(3)) if match_playlist.group(3) else 5

        logger.info(f"🎵 Обнаружен маркер PLAYLIST (legacy): genre={genre}, mood={mood}")

        # Преобразуем в MEDIA запрос
        query = f"Best {genre} songs {mood} vibe"
        result = search_media_content(query=query, media_type='audio', count=count, chat_id=chat_id)

        clean_text = re.sub(playlist_pattern, '', text, flags=re.IGNORECASE).strip()
        
        # Определяем тип результата
        if result.get("count", 0) > 1:
            return clean_text, {"type": "playlist", "data": result}
        else:
            return clean_text, {"type": "single_audio", "data": result}

    return text, None

def get_adaptive_greeting(username):
    hour = datetime.now().hour
    if 0 <= hour < 6: return f"🔮 *Доброй ночи, {username}.* Эфир чист для глубоких прозрений..."
    if 6 <= hour < 12: return f"🌅 *С рассветом, {username}.* Первый луч разума — самый яркий."
    if 12 <= hour < 18: return f"🔆 *Приветствую, {username}.* Я готов к анализу твоих образов."
    return f"🌑 *Добрый вечер, {username}.* Погружаемся в тайны нейросетей?"

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    username = message.from_user.first_name or "путник"
    greeting = get_adaptive_greeting(username)
    
    welcome_text = (
        f"{greeting}\n\n"
        f"Я AI Prophet — твой мультимодальный ИИ-компаньон.\n\n"
        f"🎯 *Что я умею:*\n"
        f"• 🖼 Анализировать фото и изображения\n"
        f"• 🎙 Распознавать голосовые сообщения\n"
        f"• 🎵 Искать и скачивать музыку (плейлисты!)\n"
        f"• 🔮 Отвечать на вопросы и давать предсказания\n"
        f"• 🌐 Искать свежую информацию в сети\n\n"
        f"🎹 *Быстрые команды:*\n"
        f"• `/playlist Pink Floyd 5` — создать плейлист\n"
        f"• `/help` — полная справка по всем командам\n\n"
        f"👇 *Выбери действие в меню ниже или просто напиши мне!*"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

@router.message(Command("playlist"))
async def cmd_playlist(message: types.Message, bot: Bot):
    """
    Команда /playlist для явного запроса плейлиста.
    Использование: /playlist <жанр/исполнитель> [количество]
    Примеры:
        /playlist Pink Floyd 5
        /playlist рок 80х
        /playlist ambient для сна 3
    """
    from core.tools import search_media_content, send_playlist
    
    chat_id = str(message.chat.id)
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer(
            "🎵 *Использование:*\n"
            "`/playlist <жанр/исполнитель> [количество]`\n\n"
            "Примеры:\n"
            "`/playlist Pink Floyd 5`\n"
            "`/playlist рок 80х`\n"
            "`/playlist ambient для сна 3`",
            parse_mode="Markdown"
        )
        return
    
    # Парсим аргументы
    query_parts = args[1:-1] if len(args) > 2 and args[-1].isdigit() else args[1:]
    count = int(args[-1]) if len(args) > 1 and args[-1].isdigit() else 5
    query = " ".join(query_parts)
    
    # Ограничиваем количество
    count = min(count, 10)  # Максимум 10 треков
    
    status_msg = await message.answer(f"🎵 *Ищу плейлист: {query}* ({count} треков)...", parse_mode="Markdown")
    
    # Поиск музыки
    result = search_media_content(query=query, media_type='audio', count=count, chat_id=chat_id)
    
    if result.get("count", 0) > 0:
        # Отправляем текст плейлиста
        await message.answer(result.get("text", "🎵 Плейлист найден"), parse_mode="Markdown")
        
        # Отправляем треки
        tracks = result.get("tracks", [])
        playlist_result = await send_playlist(
            bot=bot,
            chat_id=message.chat.id,
            tracks=tracks,
            status_msg=status_msg,
            chat_id_str=chat_id
        )
        
        # Итоговый отчет
        if playlist_result["sent"] > 0:
            await message.answer(f"✅ *Плейлист готов!* Отправлено {playlist_result['sent']} из {len(tracks)} треков", parse_mode="Markdown")
        elif playlist_result["failed"] > 0:
            await message.answer(f"⚠️ Не удалось скачать {playlist_result['failed']} треков. Попробуй другой запрос.", parse_mode="Markdown")
    else:
        await status_msg.edit_text("😔 Не удалось найти музыку по этому запросу. Попробуй другой жанр или исполнителя.")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """
    Команда /help — описание всех возможностей бота.
    """
    help_text = (
        "📖 *Полный список команд AI Prophet*\n\n"
        "🔮 *Основные команды:*\n"
        "`/start` — Запустить бота и показать главное меню\n"
        "`/help` — Показать эту справку\n"
        "`/playlist` — Создать плейлист музыки\n\n"
        "🎵 *Музыкальные команды:*\n"
        "`/playlist <жанр/исполнитель> [кол-во]` — Создать плейлист\n"
        "Примеры:\n"
        "• `/playlist Pink Floyd 5`\n"
        "• `/playlist рок 80х`\n"
        "• `/playlist ambient для сна 3`\n\n"
        "🎛 *Кнопки меню:*\n"
        "• 🔮 *Предсказание* — задать вопрос оракулу\n"
        "• 🎙 *Голос Судьбы* — отправить голосовое сообщение\n"
        "• 🖼 *Видение* — отправить фото для анализа\n"
        "• 🎵 *Музыка* — найти музыку по запросу\n"
        "• ⚙️ *Настройки* — выбрать движок (Gemini/HF/Auto)\n"
        "• 🎛 *Лимиты* — настроить лимиты на аудио\n"
        "• ℹ️ *Помощь* — краткая инструкция\n\n"
        "💡 *Советы:*\n"
        "• Голосовые до 60 сек — быстрое распознавание\n"
        "• Для музыки пиши: 'найти Pink Floyd', 'рок 80х', 'ambient для сна'\n"
        "• ⏱️ Короткие треки (<5 мин) скачиваются за секунды\n"
        "• 🕐 Длинные треки (30+ мин) могут загружаться несколько минут\n\n"
        "🔧 *Технические команды:*\n"
        "`/dizel0110` — VIP меню (для разработчика)\n\n"
        "_Бот использует Gemini 2.5 Flash и Hugging Face (Qwen/Whisper)_"
    )
    await message.answer(help_text, parse_mode="Markdown")

@router.message(F.photo)
async def handle_photo(message: types.Message, bot: Bot):
    chat_id = str(message.chat.id)
    
    photo = message.photo[-1]
    file_name = f"task_{chat_id}_{int(datetime.now().timestamp())}.jpg"
    file_path = os.path.join(TEMP_DIR, file_name)
    
    await bot.download(photo, destination=file_path)
    user_settings[chat_id] = {'pending_photo': file_path}
    
    engine = user_settings.get(chat_id, {}).get('engine', 'auto')
    status_msg = await message.answer("🌀 *Вхожу в транс прозрения...*")
    
    if engine != "hf":
        logger.info(f"🔮 User {chat_id} uses {engine} for initial vision.")
        for model_name in FALLBACK_MODELS:
            try:
                chat = get_ai_chat(chat_id, model_name)
                if not chat: continue
                
                with open(file_path, 'rb') as f: bytes_data = f.read()
                prompt = "Ты — AI Prophet. Кратко опиши фото и предложи 3 варианта: текст, детали, предсказание."
                response = chat.send_message(
                    message=[prompt, genai_types.Part.from_bytes(data=bytes_data, mime_type='image/jpeg')]
                )
                
                if response.text:
                    clean_text, kb = parse_steps_and_create_kb(response.text, chat_id)
                    icon = "🤖" if engine == "auto" else "💎"
                    try:
                        await status_msg.edit_text(f"{icon} *Мой взор запечатлел:* \n\n{clean_text}", parse_mode="Markdown")
                    except Exception:
                        await status_msg.edit_text(f"{icon} Мой взор запечатлел:\n\n{clean_text}")
                    
                    await message.answer("Следующий шаг?", reply_markup=kb)
                    return
            except Exception as e:
                logger.warning(f"Vision failure on {model_name}: {e}")
                reset_chat(chat_id, model_name)
                continue
    else:
        logger.info(f"🧿 User {chat_id} forced HF for initial vision.")
    
    # HF FALLBACK: Ритуал интерпретации туманных образов
    hf_caption = get_hf_response(image_path=file_path, task="vision")
    if hf_caption:
        # Просим Mistral интерпретировать сухой технический результат от Vision-модели
        interpretation_prompt = f"Как AI Prophet, протрактуй это видение: {hf_caption}. Будь мистичен и краток. В конце предложи следующий шаг."
        interpretation = get_hf_response(text=interpretation_prompt, task="text")
        
        raw_text = interpretation or f"Вижу это: {hf_caption}. Эфир плотен для деталей."
        clean_text, kb = parse_steps_and_create_kb(raw_text, chat_id)
        
        final_text = f"🧿 *Прозрение через HF:* \n\n_{hf_caption}_\n\n{clean_text}"
        await status_msg.edit_text(final_text)
        await message.answer("Следующий шаг?", reply_markup=kb)
    else:
        await status_msg.edit_text("📸 *Образ получен.* Каналы зашумлены, но я готов обсудить фото текстом.")
        await message.answer("Воспользуйся меню:", reply_markup=get_main_menu())

async def handle_vision_action(message, bot, chat_id, user_text):
    chat_id = str(chat_id)
    pending_info = user_settings.get(chat_id, {})
    path = pending_info.get('pending_photo')
    engine = user_settings.get(chat_id, {}).get('engine', 'auto')
    status_msg = await message.answer("🔮 *Свершаю чудо...*")
    
    success = False
    if engine != "hf":
        for model in FALLBACK_MODELS:
            try:
                chat = get_ai_chat(chat_id, model)
                full_prompt = f"Как AI Prophet, выполни волю: {user_text}. В конце предложи следующий шаг."
                
                if path and os.path.exists(path):
                    with open(path, 'rb') as f: bytes_data = f.read()
                    response = chat.send_message(
                        message=[full_prompt, genai_types.Part.from_bytes(data=bytes_data, mime_type='image/jpeg')]
                    )
                else:
                    response = chat.send_message(message=full_prompt)
                
                if response.text:
                    clean_text, kb = parse_steps_and_create_kb(response.text, chat_id)
                    icon = "🤖" if engine == "auto" else "💎"
                    await status_msg.edit_text(f"{icon} {clean_text}")
                    await message.answer("Следующий шаг?", reply_markup=kb)
                    success = True
                    break
            except Exception:
                reset_chat(chat_id, model)
                continue
    
    if not success:
        # Безопасная проверка: файл мог быть удален или задача чисто текстовая
        can_do_vision = path and os.path.exists(path)
        hf_res = get_hf_response(text=user_text, image_path=path if can_do_vision else None, task="vision" if can_do_vision else "text")
        if hf_res:
            if status_msg: await status_msg.edit_text("🧿 *Прозрение свершилось через резервный канал:*")
            clean_text, kb = parse_steps_and_create_kb(hf_res, chat_id)
            await message.answer(f"🧿 {clean_text}", reply_markup=kb)
            success = True

    if success and path:
        cleanup_file(path)
        user_settings[chat_id].pop('pending_photo', None)

@router.callback_query(F.data.startswith("vision_task:"))
async def vision_task_callback(callback: types.CallbackQuery, bot: Bot):
    data = callback.data.split(":")
    task = data[1]
    
    if task == "manual":
        await callback.answer("Жду твоего повеления...")
        await callback.message.answer("⌨️ *Напиши свой запрос к этому фото:*", parse_mode="Markdown")
        return

    await callback.answer("Свершаю...")
    
    if task == "custom":
        user_text = data[2]
    else:
        prompts = {"text": "Извлеки весь текст и код.", "summary": "Резюмируй кратко."}
        user_text = prompts.get(task, "Продолжай анализ.")
        
    await handle_vision_action(callback.message, bot, callback.message.chat.id, user_text)


@router.message(F.voice | F.audio)
async def handle_audio(message: types.Message, bot: Bot):
    chat_id = str(message.chat.id)

    audio = message.voice or message.audio
    file_name = f"audio_{chat_id}_{int(datetime.now().timestamp())}.ogg"
    file_path = os.path.join(TEMP_DIR, file_name)
    wav_path = file_path.replace('.ogg', '.wav')

    await bot.download(audio, destination=file_path)
    engine = user_settings.get(chat_id, {}).get('engine', 'auto')
    status_msg = await message.answer(f"👂 *Слушаю ({engine})...*")

    logger.info(f"🎙 Processing audio for {chat_id} via {engine}")

    # Конвертация OGG → WAV для совместимости
    try:
        import ffmpeg
        logger.info("🔄 Конвертация OGG → WAV...")
        ffmpeg.input(file_path).output(
            wav_path,
            acodec='pcm_s16le',
            ac=1,
            ar='16000'
        ).run(quiet=True, overwrite_output=True)
        logger.info(f"✅ WAV создан: {wav_path}")
        transcribe_path = wav_path
    except Exception as e:
        logger.warning(f"⚠️ ffmpeg не доступен, используем OGG: {e}")
        transcribe_path = file_path

    if engine == "hf":
        logger.info("🔄 Запуск локальной транскрибации (wav2vec2)...")
        text = transcribe_local(transcribe_path)
        logger.info(f"📥 Локальная транскрибация результат: {text[:50] if text else 'None'}...")
    else:
        logger.info("🔄 Запуск Gemini транскрибации...")
        text = transcribe_with_gemini(transcribe_path)
        logger.info(f"📥 Gemini результат: {text[:50] if text else 'None'}...")
        # Если Gemini не справился, пробуем HF как бэкап
        if not text:
            logger.info("♻️ Gemini Transcription failed, falling back to HF.")
            text = get_hf_response(image_path=transcribe_path, task="audio")
            logger.info(f"📥 HF Whisper результат (fallback): {text[:50] if text else 'None'}...")

    cleanup_file(file_path)
    if transcribe_path != file_path:
        cleanup_file(transcribe_path)

    if text:
        logger.info(f"✅ Audio transcribed: {text[:50]}...")

        # Показываем распознанный текст с кнопками подтверждения
        await message.answer(
            f"👤 *Распознано:* \n\n_{text}_\n\n"
            f"🔮 *Подтвердите выполнение:*",
            reply_markup=get_voice_confirmation_keyboard(chat_id, text),
            parse_mode="Markdown"
        )
    else:
        await status_msg.edit_text("😔 Эфир слишком зашумлен, не смог разобрать ни слова...")


@router.message()
async def handle_text(message: types.Message, bot: Bot):
    chat_id = str(message.chat.id)
    text = message.text
    if not text: return

    # Проверка на редактирование голосового сообщения
    if user_settings.get(chat_id, {}).get('pending_voice_edit'):
        # Пользователь ввёл текст для редактирования распознанного голоса
        user_settings.setdefault(chat_id, {})['pending_voice_text'] = text
        user_settings[chat_id].pop('pending_voice_edit', None)
        
        await message.answer(
            f"✏️ *Текст изменён:* \n\n_{text}_\n\n"
            f"🔮 *Выполнить?*",
            reply_markup=get_voice_confirmation_keyboard(chat_id, text),
            parse_mode="Markdown"
        )
        return

    if text == "⚙️ Настройки":
        engine = user_settings.get(chat_id, {}).get('engine', 'auto')
        await message.answer("🛠 *Настройки Оракула*\n\nВыбери основной источник мудрости:",
                           reply_markup=get_settings_menu(engine), parse_mode="Markdown")
        return

    if text == "ℹ️ Помощь":
        # Перенаправляем на команду /help
        await cmd_help(message)
        return

    if "🤖 Авто" in text: user_settings.setdefault(chat_id, {})['engine'] = 'auto'
    elif "💎 Только Gemini" in text: user_settings.setdefault(chat_id, {})['engine'] = 'gemini'
    elif "🧿 Только Hugging Face" in text: user_settings.setdefault(chat_id, {})['engine'] = 'hf'
    
    if any(x in text for x in ["🤖 Авто", "💎 Только Gemini", "🧿 Только Hugging Face"]):
        save_settings(user_settings) # Сохраняем при изменении
        await message.answer("✅ *Источник изменен.*", reply_markup=get_main_menu(), parse_mode="Markdown")
        return

    if text == "⬅️ Назад":
        await message.answer("Возвращаемся в главный чертог.", reply_markup=get_main_menu())
        return

    # Остальная логика handle_text...
    status_msg = await message.answer("🧘 *Медитирую над твоими словами...*")
    await conduct_ai_ritual(message, bot, message.text, status_msg)

async def conduct_ai_ritual(message: types.Message, bot: Bot, input_text: str, status_msg=None):
    chat_id = str(message.chat.id)
    engine = user_settings.get(chat_id, {}).get('engine', 'auto')
    
    if not input_text: return
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    
    if user_settings.get(chat_id, {}).get('pending_photo'):
        await handle_vision_action(message, bot, chat_id, input_text)
        return

    if engine == "hf":
        if status_msg: await status_msg.edit_text("🧿 *Прямое подключение к каналу Hugging Face...*")
        else: status_msg = await message.answer("🧿 *Прямое подключение к каналу Hugging Face...*")

        hf_res = get_hf_response(text=input_text, task="text")
        if hf_res:
            logger.info(f"✅ HF Response received for user {chat_id}")

            # Parse and execute tools с chat_id
            clean_text, tool_result = parse_and_execute_tools(hf_res, chat_id=chat_id)

            await status_msg.edit_text("✨ *Ответ получен через поток HF:*")
            await message.answer(f"🧿 {clean_text}")

            # Send tool result if any
            if tool_result:
                if tool_result.get("type") == "playlist":
                    # Плейлист — отправляем через send_playlist
                    from core.tools import send_playlist
                    playlist_data = tool_result.get("data", {})
                    tracks = playlist_data.get("tracks", [])
                    
                    await message.answer(f"🎵 {playlist_data.get('text', 'Загрузка плейлиста...')}")
                    
                    # Запускаем отправку плейлиста
                    result = await send_playlist(
                        bot=bot,
                        chat_id=message.chat.id,
                        tracks=tracks,
                        status_msg=None,
                        chat_id_str=chat_id
                    )
                    
                    if result["sent"] > 0:
                        await message.answer(f"✅ Отправлено {result['sent']} из {len(tracks)} треков")
                    elif result["failed"] > 0:
                        await message.answer(f"⚠️ Не удалось скачать {result['failed']} треков")
                        
                elif tool_result.get("type") == "single_audio":
                    # Одиночный трек — показываем кнопки
                    playlist_data = tool_result.get("data", {})
                    text_result = playlist_data.get("text", "")
                    tracks = playlist_data.get("tracks", [])
                    query = playlist_data.get("query", "")

                    # Пытаемся найти ВСЕ ссылки YouTube для кнопок
                    import re
                    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

                    # Ищем ссылки (youtu.be или youtube.com)
                    links = re.findall(r'https://(?:www\.)?youtu(?:be\.com/watch\?v=|\.be/)([\w-]+)', text_result)
                    buttons = []

                    if links:
                        # Создаем ряд кнопок: [⬇️ 1] [⬇️ 2] ...
                        buttons_row = []
                        for i, video_id in enumerate(links, 1):
                            # Лимит 5 кнопок в ряд, чтобы не засорять
                            if i > 5: break
                            buttons_row.append(
                                InlineKeyboardButton(text=f"⬇️ {i}", callback_data=f"dl_audio:{video_id}")
                            )
                        buttons.append(buttons_row)
                    
                    # Добавляем кнопку "Скачать всё" для плейлистов
                    if len(tracks) > 1 and query:
                        # Кнопка "Скачать всё" с данными для плейлиста
                        buttons.append([
                            InlineKeyboardButton(
                                text=f"🎧 Скачать всё ({len(tracks)} тр.)",
                                callback_data=f"dl_playlist:{query}:{len(tracks)}"
                            )
                        ])

                    kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

                    await message.answer(f"🎵 {text_result}", reply_markup=kb, disable_web_page_preview=True)
            return
        else:
            logger.warning(f"⚠️ HF Failed for {chat_id}, falling back to Gemini despite settings.")
            if status_msg: await status_msg.edit_text("🌀 *Канал HF зашумлен, обращаюсь к звездам Google...*")
            # Не делаем return, идем ниже к Gemini

    # Логика Web Search
    trigger_words = ["найди", "погугли", "что слышно о", "курс", "цена"]
    text_lower = input_text.lower()
    
    if any(word in text_lower for word in trigger_words):
        status_msg = await message.answer("🔎 *Обращаюсь к мировому эфиру за информацией...*", parse_mode="Markdown")
        search_res = web_search(input_text)
        
        full_prompt = (
            f"Используя свежие данные из поиска:\n\n{search_res}\n\n"
            f"Ответь на запрос пользователя: {input_text}\n"
            f"Стиль: Пророческий. Ссылайся на полученную информацию."
        )
        await status_msg.edit_text("🧘 *Медитирую над потоком данных...*")
        
        for model in FALLBACK_MODELS:
            try:
                chat = get_ai_chat(chat_id, model)
                response = chat.send_message(message=full_prompt)
                clean_text, kb = parse_steps_and_create_kb(response.text, chat_id)
                await status_msg.edit_text(clean_text)
                await message.answer("Мои прозрения верны?", reply_markup=kb)
                if response.text:
                    clean_text, kb = parse_steps_and_create_kb(response.text, chat_id)
                    await status_msg.edit_text(clean_text)
                    await message.answer("Мои прозрения верны?", reply_markup=kb)
                return
            except Exception:
                reset_chat(chat_id, model)
                continue

    gemini_exhausted = False
    for model in FALLBACK_MODELS:
        if gemini_exhausted: break
        try:
            chat = get_ai_chat(chat_id, model)
            response = chat.send_message(message=input_text)
            
            # --- ЛОГИКА ОБРАБОТКИ ИНСТРУМЕНТОВ ---
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if part.call:
                        fn_name = part.call.name
                        args = part.call.args
                        logger.info(f"🛠 ИИ вызывает инструмент: {fn_name} с аргументами {args}")
                        
                        if status_msg: await status_msg.edit_text(f"⚒ *Задействую инструмент:* `{fn_name}`...")
                        
                        if fn_name in AVAILABLE_FUNCTIONS:
                            result = AVAILABLE_FUNCTIONS[fn_name](**args)
                            # Отправляем ответ инструмента обратно модели
                            response = chat.send_message(
                                message=genai_types.Part.from_function_response(
                                    name=fn_name,
                                    response={"result": result}
                                )
                            )
                        else:
                            logger.error(f"❌ Инструмент {fn_name} не найден")

            if response.text:
                clean_text, kb = parse_steps_and_create_kb(response.text, chat_id)
                icon = "🤖" if engine == "auto" else "💎"
                if status_msg:
                    await status_msg.edit_text(f"{icon} {clean_text}")
                    await message.answer("Следующий шаг?", reply_markup=kb)
                else:
                    await message.answer(f"{icon} {clean_text}", reply_markup=kb)
                return
        except Exception as e:
            if "429" in str(e): 
                logger.warning("🚫 Gemini Quota Exhausted. Switching to HF immediately.")
                gemini_exhausted = True
            reset_chat(chat_id, model)
            continue
    
    if status_msg: await status_msg.edit_text("🌀 *Эфир Google зашумлен, открываю канал Hugging Face...*")
    
    hf_res = get_hf_response(text=input_text, task="text")
    if hf_res:
        # Парсим и выполняем инструменты
        clean_text, tool_result = parse_and_execute_tools(hf_res)
        
        if status_msg: 
            await status_msg.edit_text("🧿 *Поток данных из облака HF сформирован:*")
            if clean_text.strip():
                await message.answer(f"🧿 {clean_text}")
        else:
            if clean_text.strip():
                await message.answer(f"🧿 {clean_text}")
        
        # Если был вызван инструмент, отправляем результат
        if tool_result:
            await message.answer(tool_result, parse_mode="Markdown")
    else:
        final_text = "😔 Сегодня звезды не отвечают мне... Попробуй позже."
        if status_msg: 
            await status_msg.edit_text(final_text)
            await message.answer("Вернись, когда эфир очистится.", reply_markup=get_main_menu())
        else: 
            await message.answer(final_text, reply_markup=get_main_menu())

@router.callback_query(F.data.startswith("dl_audio:"))
async def handle_download_callback(callback: types.CallbackQuery, bot: Bot):
    import os
    from aiogram.types import FSInputFile
    from core.tools import download_audio

    video_id = callback.data.split(":")[1]
    url = f"https://www.youtube.com/watch?v={video_id}"
    chat_id = str(callback.message.chat.id)

    await callback.answer("⏳ Начинаю магию конвертации...")
    status_msg = await bot.send_message(chat_id, f"⬇️ Скачиваю и конвертирую: {url}")

    # Передаём chat_id для загрузки пользовательских лимитов
    file_path, title, duration = download_audio(url, chat_id=chat_id)

    if file_path and os.path.exists(file_path):
        try:
            duration_text = f" ({duration} сек)" if duration else ""
            await status_msg.edit_text(f"📤 Отправляю: {title}{duration_text}...")
            audio_file = FSInputFile(file_path)
            # Отправляем с реальным названием
            await bot.send_audio(
                callback.message.chat.id,
                audio_file,
                title=title,
                performer="AI Prophet Media",
                caption=f"🎧 *{title}*{duration_text}\n🔗 [Источник]({url})"
            )
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit_text(f"❌ Ошибка отправки: {e}")
        finally:
            # Чистим файл
            if os.path.exists(file_path):
                os.remove(file_path)
    else:
        await status_msg.edit_text("❌ Не удалось скачать аудио. Возможно, видео слишком длинное или недоступно.")

@router.callback_query(F.data.startswith("dl_playlist:"))
async def handle_playlist_callback(callback: types.CallbackQuery, bot: Bot):
    """
    Обработка кнопки 'Скачать всё' для плейлиста.
    Данные: dl_playlist:<query>:<count>
    """
    from core.tools import search_media_content, send_playlist
    import re
    
    # Парсим данные: dl_playlist:query:count
    data = callback.data.split(":", 2)
    if len(data) < 3:
        await callback.answer("❌ Неверный формат запроса")
        return
    
    query = data[1]
    try:
        count = int(data[2])
    except ValueError:
        count = 5
    
    chat_id = str(callback.message.chat.id)
    
    await callback.answer("⏳ Ищу плейлист...")
    status_msg = await bot.send_message(chat_id, f"🎵 *Ищу плейлист: {query}* ({count} треков)...", parse_mode="Markdown")
    
    # Поиск музыки
    result = search_media_content(query=query, media_type='audio', count=count, chat_id=chat_id)
    
    if result.get("count", 0) > 0:
        # Отправляем текст плейлиста
        await callback.message.answer(result.get("text", "🎵 Плейлист найден"), parse_mode="Markdown")
        
        # Отправляем треки
        tracks = result.get("tracks", [])
        playlist_result = await send_playlist(
            bot=bot,
            chat_id=callback.message.chat.id,
            tracks=tracks,
            status_msg=status_msg,
            chat_id_str=chat_id
        )
        
        # Итоговый отчет
        if playlist_result["sent"] > 0:
            await callback.message.answer(f"✅ *Плейлист готов!* Отправлено {playlist_result['sent']} из {len(tracks)} треков", parse_mode="Markdown")
        elif playlist_result["failed"] > 0:
            await callback.message.answer(f"⚠️ Не удалось скачать {playlist_result['failed']} треков. Попробуй другой запрос.", parse_mode="Markdown")
    else:
        await status_msg.edit_text("😔 Не удалось найти музыку по этому запросу.")


@router.callback_query(F.data.startswith("voice_"))
async def handle_voice_callback(callback: types.CallbackQuery, bot: Bot):
    """
    Обработка кнопок подтверждения голосовых сообщений.
    """
    data = callback.data.split(":")
    action = data[0]
    chat_id = data[1] if len(data) > 1 else str(callback.message.chat.id)
    
    if action == "voice_confirm":
        # Получаем сохранённый текст и выполняем
        pending_text = user_settings.get(chat_id, {}).get('pending_voice_text')
        
        if pending_text:
            await callback.answer("✅ Выполняю...")
            await callback.message.answer("🧿 *Медитирую над смыслом...*")
            await conduct_ai_ritual(callback.message, bot, pending_text, None)
            
            # Очищаем сохранённый текст
            user_settings.get(chat_id, {}).pop('pending_voice_text', None)
        else:
            await callback.answer("❌ Текст не найден. Отправьте голосовое ещё раз.")
    
    elif action == "voice_edit":
        await callback.answer("✏️ Введите ваш текст:")
        user_settings.setdefault(chat_id, {})['pending_voice_edit'] = True
    
    elif action == "voice_cancel":
        await callback.answer("❌ Отменено")
        # Очищаем сохранённый текст
        user_settings.get(chat_id, {}).pop('pending_voice_text', None)
