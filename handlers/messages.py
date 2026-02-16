import os
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
from core.ai_engine import get_ai_chat, get_client, reset_chat, get_hf_response, transcribe_with_gemini
from core.tools import web_search, search_media_content, AVAILABLE_FUNCTIONS
from config import FALLBACK_MODELS, TEMP_DIR
from google.genai import types as genai_types
from handlers.limits import load_user_limits, create_limits_keyboard

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
        [KeyboardButton(text="🖼 Видение"), KeyboardButton(text="🎵 Музыка")],
        [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🎛 Лимиты")],
        [KeyboardButton(text="ℹ️ Помощь")]
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

def parse_and_execute_tools(text, chat_id: str = None):
    """
    Парсит текст на наличие маркеров инструментов и выполняет их.
    Поддерживает: [MEDIA: query, type, count] и [PLAYLIST: genre, mood, count]

    chat_id: ID чата для загрузки пользовательских лимитов
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
        result = search_media_content(query=query, media_type='audio', count=count, chat_id=chat_id)

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

    if text == "🎛 Лимиты":
        limits = load_user_limits(chat_id)
        await message.answer(
            f"🎛 *Настройки загрузки аудио*\n\n"
            f"⏱ Длительность: {limits.get('duration', 1800) // 60} мин\n"
            f"📦 Размер: {limits.get('size', 50)} MB\n\n"
            f"Нажми на кнопки ниже для настройки:",
            reply_markup=create_limits_keyboard(chat_id),
            parse_mode="Markdown"
        )
        return

    if text == "ℹ️ Помощь":
        help_text = (
            "📖 *Инструкция AI Prophet*\n\n"
            "🎙 *Голос Судьбы* — отправь голосовое сообщение, бот распознает и ответит.\n"
            "🖼 *Видение* — отправь фото, бот проанализирует его.\n"
            "🎵 *Музыка* — напиши жанр/настроение, бот найдёт трек.\n"
            "🔮 *Предсказание* — задай вопрос, получи ответ.\n\n"
            "⚙️ *Настройки* — выбери движок (Gemini/HF/Auto).\n\n"
            "💡 *Советы:*\n"
            "• Голосовые до 60 сек — быстрое распознавание\n"
            "• Для музыки пиши: 'найти Pink Floyd', 'рок 80х', 'ambient для сна'\n"
            "• ⏱️ Короткие треки (<5 мин) скачиваются за секунды\n"
            "• 🕐 Длинные треки (30+ мин) могут загружаться несколько минут"
        )
        await message.answer(help_text, parse_mode="Markdown")
        return

    if text == "🎵 Музыка":
        await message.answer(
            "🎶 *Поиск музыки*\n\n"
            "Напиши жанр, исполнителя или настроение:\n"
            "• 'найти Pink Floyd'\n"
            "• 'рок 80х'\n"
            "• 'ambient для сна'\n"
            "• 'лучшие хиты 2024'\n\n"
            "⏱️ *Время загрузки:*\n"
            "• Короткие треки (<5 мин) — ~10-30 сек\n"
            "• Средние треки (5-30 мин) — ~1-3 мин\n"
            "• Длинные треки (30+ мин) — ~3-10 мин\n\n"
            "📦 *Лимиты:*\n"
            "• Макс. длительность: 30 мин\n"
            "• Макс. размер: 100 MB",
            parse_mode="Markdown"
        )
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

    # Проверка на музыкальные запросы
    music_triggers = ["найти музыку", "найди песню", "скачай трек", "включи музыку"]
    if any(trigger in text.lower() for trigger in music_triggers):
        status_msg = await message.answer("🎵 *Ищу музыку...*")
        await conduct_ai_ritual(message, bot, text, status_msg)
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
        # Парсим и выполняем инструменты с chat_id
        clean_text, tool_result = parse_and_execute_tools(hf_res, chat_id=chat_id)
        
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
    # download_audio возвращает 3 значения: (file_path, title, duration)
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
        await status_msg.edit_text("❌ Не удалось скачать аудио. Попробуй другой трек или напиши текстом.")

@router.message(F.voice | F.audio)
async def handle_audio(message: types.Message, bot: Bot):
    chat_id = str(message.chat.id)
    audio = message.voice or message.audio
    file_name = f"audio_{chat_id}_{int(datetime.now().timestamp())}.ogg"
    file_path = os.path.join(TEMP_DIR, file_name)

    # Скачиваем файл
    await bot.download(audio, destination=file_path)

    # Проверяем, что файл скачался успешно
    if not os.path.exists(file_path):
        logger.error(f"❌ Не удалось скачать аудио: {file_path}")
        await message.answer("😔 Не удалось сохранить аудио. Попробуй ещё раз.")
        return

    file_size = os.path.getsize(file_path)
    if file_size == 0:
        logger.error(f"❌ Пустой аудио файл: {file_path}")
        await message.answer("😔 Аудио файл пуст. Попробуй ещё раз.")
        cleanup_file(file_path)
        return

    logger.info(f"📥 Аудио скачано: {file_path}, {file_size / 1024:.1f} KB")

    engine = user_settings.get(chat_id, {}).get('engine', 'auto')
    status_msg = await message.answer(f"👂 *Слушаю ({engine})...*")

    logger.info(f"🎙 Processing audio for {chat_id} via {engine}")

    # Таймаут зависит от типа аудио: voice (до 60 сек) или audio (файл, может быть длиннее)
    audio_duration = 60 if message.voice else 90

    text = None

    # === ЛОГИКА С FALLBACK ДЛЯ ЛЮБОГО ДВИЖКА ===
    if engine == "hf":
        # Пробуем HF сначала
        text = get_hf_response(image_path=file_path, task="audio")
        logger.info(f"🧿 HF Transcription result: {text[:50] if text else 'None'}...")

        # Если HF не справился, пробуем Gemini как бэкап
        if not text:
            logger.info("♻️ HF failed, falling back to Gemini.")
            text = transcribe_with_gemini(file_path, timeout_sec=audio_duration)
            logger.info(f"💎 Gemini Fallback result: {text[:50] if text else 'None'}...")

    elif engine == "gemini":
        # Пробуем Gemini сначала
        text = transcribe_with_gemini(file_path, timeout_sec=audio_duration)
        logger.info(f"💎 Gemini Transcription result: {text[:50] if text else 'None'}...")

        # Если Gemini не справился, пробуем HF как бэкап
        if not text:
            logger.info("♻️ Gemini failed, falling back to HF.")
            text = get_hf_response(image_path=file_path, task="audio")
            logger.info(f"🧿 HF Fallback result: {text[:50] if text else 'None'}...")

    else:  # engine == "auto"
        # Auto: сначала Gemini (быстрее), потом HF
        text = transcribe_with_gemini(file_path, timeout_sec=audio_duration)
        logger.info(f"💎 Gemini (auto) result: {text[:50] if text else 'None'}...")

        if not text:
            logger.info("♻️ Gemini failed, falling back to HF.")
            text = get_hf_response(image_path=file_path, task="audio")
            logger.info(f"🧿 HF Fallback result: {text[:50] if text else 'None'}...")

    cleanup_file(file_path)

    if text:
        logger.info(f"✅ Audio transcribed: {text[:50]}...")
        await message.answer(f"👤 *Прочитал в эфире:* \n\n_{text}_", parse_mode="Markdown")
        status_msg = await message.answer("🧿 *Медитирую над смыслом...*")
        await conduct_ai_ritual(message, bot, text, status_msg)
    else:
        await status_msg.edit_text("😔 Эфир слишком зашумлен, не смог разобрать ни слова... Попробуй ещё раз или напиши текстом.")
