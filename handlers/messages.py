import os
import logging
import asyncio
import random
import glob
from datetime import datetime
from aiogram import Router, types, Bot, F
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from core.ai_engine import get_ai_chat, get_client, reset_chat, get_hf_response
from core.tools import web_search
from config import FALLBACK_MODELS, TEMP_DIR
from google.genai import types as genai_types

logger = logging.getLogger(__name__)
router = Router()
user_settings = {}

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
    """Возвращает стандартную клавиатуру с Mini App"""
    web_app_url = "https://dizel0110.github.io/ai_prophet/"
    kb = [[KeyboardButton(text="📱 Открыть Mini App", web_app=WebAppInfo(url=web_app_url))]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def parse_steps_and_create_kb(text, chat_id):
    """Парсит текст на наличие 'ШАГ:' и создает клавиатуру"""
    kb = []
    lines = text.split('\n')
    new_text_lines = []
    
    for line in lines:
        if line.strip().startswith("ШАГ:"):
            step_text = line.replace("ШАГ:", "").strip().strip("[]")
            # Telegram limit is 64 bytes for callback_data
            # "vision_task:custom:" is 19 bytes. Остается 45.
            callback_val = step_text[:40]
            btn_text = step_text[:30] + "..." if len(step_text) > 30 else step_text
            kb.append([InlineKeyboardButton(text=f"🔮 {btn_text}", callback_data=f"vision_task:custom:{callback_val}")])
        else:
            new_text_lines.append(line)
    
    # Всегда добавляем кнопку своего варианта
    kb.append([InlineKeyboardButton(text="⌨️ Свой вариант", callback_data="vision_task:manual")])
    
    remaining_text = "\n".join(new_text_lines).strip()
    return remaining_text, InlineKeyboardMarkup(inline_keyboard=kb)

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
    chat_id = message.chat.id
    
    photo = message.photo[-1]
    file_name = f"task_{chat_id}_{int(datetime.now().timestamp())}.jpg"
    file_path = os.path.join(TEMP_DIR, file_name)
    
    await bot.download(photo, destination=file_path)
    user_settings[chat_id] = {'pending_photo': file_path}
    
    status_msg = await message.answer("🌀 *Вхожу в транс прозрения...*")
    
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
                try:
                    await status_msg.edit_text(f"🧿 *Мой взор запечатлел:* \n\n{clean_text}", parse_mode="Markdown")
                except Exception:
                    await status_msg.edit_text(f"🧿 Мой взор запечатлел:\n\n{clean_text}")
                
                await message.answer("Что мне совершить?", reply_markup=kb)
                return
        except Exception as e:
            logger.warning(f"Vision failure on {model_name}: {e}")
            reset_chat(chat_id, model_name)
            continue
    
    # HF FALLBACK: Ритуал интерпретации туманных образов
    hf_caption = get_hf_response(image_path=file_path, task="vision")
    if hf_caption:
        await status_msg.edit_text("🧿 *Вижу туманный образ... Грезю о его значении...*")
        # Просим Mistral интерпретировать сухой технический результат от Vision-модели
        interpretation_prompt = f"Как AI Prophet, протрактуй это видение: {hf_caption}. Будь мистичен и краток. В конце предложи следующий шаг."
        interpretation = get_hf_response(text=interpretation_prompt, task="text")
        
        final_text = f"🧿 *Мой взор затуманен, но я вижу:* \n\n_{hf_caption}_\n\n{interpretation or 'Эфир слишком плотен для точных слов...'}"
        clean_text, kb = parse_steps_and_create_kb(final_text, chat_id)
        
        await status_msg.edit_text(clean_text)
        await message.answer("Следующий шаг?", reply_markup=kb)
    else:
        await status_msg.edit_text("📸 *Образ получен.* Каналы зашумлены, но я готов обсудить фото текстом.")
        await message.answer("Воспользуйся меню:", reply_markup=get_main_menu())

async def handle_vision_action(message, bot, chat_id, user_text):
    pending_info = user_settings.get(chat_id, {})
    path = pending_info.get('pending_photo')
    status_msg = await message.answer("🔮 *Свершаю чудо...*")
    
    success = False
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
                await status_msg.edit_text(clean_text)
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
            await message.answer(hf_res, reply_markup=get_main_menu())
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

@router.message(F.text)
async def handle_text(message: types.Message, bot: Bot):
    status_msg = await message.answer("🧘 *Медитирую над твоими словами...*")
    await conduct_ai_ritual(message, bot, message.text, status_msg)

async def conduct_ai_ritual(message: types.Message, bot: Bot, input_text: str, status_msg=None):
    chat_id = message.chat.id
    if not input_text: return
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    
    if user_settings.get(chat_id, {}).get('pending_photo'):
        await handle_vision_action(message, bot, chat_id, input_text)
        return

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
            if response.text:
                clean_text, kb = parse_steps_and_create_kb(response.text, chat_id)
                if status_msg:
                    await status_msg.edit_text(clean_text)
                    await message.answer("Следующий шаг?", reply_markup=kb)
                else:
                    await message.answer(clean_text, reply_markup=kb)
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
        if status_msg: 
            # Нельзя прикреплять ReplyKeyboardMarkup к edit_text. 
            # Просто редактируем статус и присылаем ответ новым сообщением.
            await status_msg.edit_text("🧿 *Поток данных из облака HF сформирован:*")
            await message.answer(hf_res, reply_markup=get_main_menu())
        else: 
            await message.answer(hf_res, reply_markup=get_main_menu())
    else:
        final_text = "😔 Сегодня звезды не отвечают мне... Попробуй позже."
        if status_msg: 
            await status_msg.edit_text(final_text)
            await message.answer("Вернись, когда эфир очистится.", reply_markup=get_main_menu())
        else: 
            await message.answer(final_text, reply_markup=get_main_menu())

@router.message(F.voice | F.audio)
async def handle_audio(message: types.Message, bot: Bot):
    chat_id = message.chat.id
    # Не чистим всё подряд, только файлы этого же типа если нужно
    
    audio = message.voice or message.audio
    file_name = f"audio_{chat_id}_{int(datetime.now().timestamp())}.ogg"
    file_path = os.path.join(TEMP_DIR, file_name)
    
    await bot.download(audio, destination=file_path)
    status_msg = await message.answer("👂 *Внимательно слушаю твой голос...*")
    
    text = get_hf_response(image_path=file_path, task="audio")
    cleanup_file(file_path)
    
    if text:
        # Не редактируем status_msg здесь, передаем его внутрь для финального ответа
        await status_msg.edit_text(f"👤 *Твои слова:* \n\n_{text}_\n\n_Медитирую над смыслом..._", parse_mode="Markdown")
        await conduct_ai_ritual(message, bot, text, status_msg)
    else:
        await status_msg.edit_text("😔 Не смог разобрать голос.")
