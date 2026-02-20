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
from core.ai_engine import get_ai_chat, get_client, reset_chat, get_hf_response, transcribe_with_gemini
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

def parse_and_execute_tools(text):
    """
    Парсит текст на наличие маркеров инструментов и выполняет их.
    Поддерживает: [MEDIA: query, type, count] и [PLAYLIST: genre, mood, count]
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
        
        # Вызываем универсальный поиск медиа
        result = search_media_content(query=query, media_type=m_type, count=count)
        
        # Убираем маркер
        clean_text = re.sub(media_pattern, '', text, flags=re.IGNORECASE).strip()
        return clean_text, result

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
        result = search_media_content(query=query, media_type='audio', count=count)
        
        clean_text = re.sub(playlist_pattern, '', text, flags=re.IGNORECASE).strip()
        return clean_text, result
    
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
    await message.answer(
        f"{get_adaptive_greeting(username)}\n\nЯ AI Prophet. Пришли фото или спроси о чем угодно.",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

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

@router.message()
async def handle_text(message: types.Message, bot: Bot):
    chat_id = str(message.chat.id)
    text = message.text
    if not text: return

    if text == "⚙️ Настройки":
        engine = user_settings.get(chat_id, {}).get('engine', 'auto')
        await message.answer("🛠 *Настройки Оракула*\n\nВыбери основной источник мудрости:", 
                           reply_markup=get_settings_menu(engine), parse_mode="Markdown")
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
            
            # Parse and execute tools
            clean_text, tool_result = parse_and_execute_tools(hf_res)
            
            await status_msg.edit_text("✨ *Ответ получен через поток HF:*")
            await message.answer(f"🧿 {clean_text}")
            
            # Send tool result if any
            if tool_result:
                # Пытаемся найти ВСЕ ссылки YouTube для кнопок
                import re
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                
                # Ищем ссылки (youtu.be или youtube.com)
                links = re.findall(r'https://(?:www\.)?youtu(?:be\.com/watch\?v=|\.be/)([\w-]+)', tool_result)
                kb = None
                
                if links:
                    # Создаем ряд кнопок: [⬇️ 1] [⬇️ 2] ...
                    buttons_row = []
                    for i, video_id in enumerate(links, 1):
                        # Лимит 5 кнопок в ряд, чтобы не засорять
                        if i > 5: break
                        buttons_row.append(
                            InlineKeyboardButton(text=f"⬇️ {i}", callback_data=f"dl_audio:{video_id}")
                        )
                    
                    kb = InlineKeyboardMarkup(inline_keyboard=[buttons_row])
                
                await message.answer(f"🎵 {tool_result}", reply_markup=kb, disable_web_page_preview=True)
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
    
    await callback.answer("⏳ Начинаю магию конвертации...")
    status_msg = await bot.send_message(callback.message.chat.id, f"⬇️ Скачиваю и конвертирую: {url}")
    
    file_path, title = download_audio(url)
    
    if file_path and os.path.exists(file_path):
        try:
            await status_msg.edit_text(f"📤 Отправляю: {title}...")
            audio_file = FSInputFile(file_path)
            # Отправляем с реальным названием
            await bot.send_audio(
                callback.message.chat.id, 
                audio_file, 
                title=title, 
                performer="AI Prophet Media",
                caption=f"🎧 *{title}*\n🔗 [Источник]({url})"
            )
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit_text(f"❌ Ошибка отправки: {e}")
        finally:
            # Чистим файл
            if os.path.exists(file_path):
                os.remove(file_path)
            cleanup_file(file_path)
    else:
        await status_msg.edit_text("❌ Не удалось скачать аудио. Возможно, видео слишком длинное или недоступно.")

@router.message(F.voice | F.audio)
async def handle_audio(message: types.Message, bot: Bot):
    chat_id = str(message.chat.id)
    # Не чистим всё подряд, только файлы этого же типа если нужно
    
    audio = message.voice or message.audio
    file_name = f"audio_{chat_id}_{int(datetime.now().timestamp())}.ogg"
    file_path = os.path.join(TEMP_DIR, file_name)
    
    await bot.download(audio, destination=file_path)
    engine = user_settings.get(chat_id, {}).get('engine', 'auto')
    status_msg = await message.answer(f"👂 *Слушаю ({engine})...*")
    
    logger.info(f"🎙 Processing audio for {chat_id} via {engine}")
    
    if engine == "hf":
        text = get_hf_response(image_path=file_path, task="audio")
    else:
        text = transcribe_with_gemini(file_path)
        # Если Gemini не справился, пробуем HF как бэкап
        if not text:
            logger.info("♻️ Gemini Transcription failed, falling back to HF.")
            text = get_hf_response(image_path=file_path, task="audio")
    
    cleanup_file(file_path)
    
    if text:
        logger.info(f"✅ Audio transcribed: {text[:50]}...")
        # Отправляем транскрипцию как отдельное сообщение, чтобы она не стерлась в истории
        await message.answer(f"👤 *Прочитал в эфире:* \n\n_{text}_", parse_mode="Markdown")
        # Создаем новый статус для процесса раздумий
        status_msg = await message.answer("🧿 *Медитирую над смыслом...*")
        await conduct_ai_ritual(message, bot, text, status_msg)
    else:
        await status_msg.edit_text("😔 Эфир слишком зашумлен, не смог разобрать ни слова...")
