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
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from core.ai_engine import get_ai_chat, get_client, reset_chat, get_hf_response, transcribe_with_gemini, transcribe_local
from core.tools import web_search, search_media_content, download_audio, AVAILABLE_FUNCTIONS
from core.agents.agent_factory import SpecialistFactory, get_specialists, get_specialist, remove_specialist, DynamicSpecialist
from config import FALLBACK_MODELS, TEMP_DIR, get_base_url
from google.genai import types as genai_types

logger = logging.getLogger(__name__)
router = Router()

# Quick-reply questions for specialist chat
_quick_replies: dict = {}
_qr_counter: int = 0

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

# Глобальные состояния
user_settings = load_settings()
_chats = {} 
active_cancellations = set()

# Глобальные примеры плейлистов для обучения
GLOBAL_EXAMPLES = [
    {
        "name": "🎸 Рок-Легенды",
        "items": [
            {"query": "Deep Purple", "count": 2},
            {"query": "Led Zeppelin", "count": 2}
        ],
        "desc": "Хиты классического рока, подобранные AI."
    },
    {
        "name": "🌊 Ночной Chill",
        "items": [
            {"query": "Lo-fi Hip Hop", "count": 3},
            {"query": "Ambient Rain", "count": 2}
        ],
        "desc": "Спокойная музыка для работы или сна."
    },
    {
        "name": "🎯 Коллекция Хитов",
        "items": [
            {"query": "Queen - Bohemian Rhapsody", "count": 1},
            {"query": "ABBA - Dancing Queen", "count": 1},
            {"query": "Nirvana - Smells Like Teen Spirit", "count": 1}
        ],
        "desc": "Пример точечного поиска конкретных песен."
    }
]

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
    patterns = [
        f"task_{chat_id}_*",
        f"audio_{chat_id}_*",
        f"massage_photo_{chat_id}_*",
        f"massage_video_{chat_id}_*",
        f"massage_doc_{chat_id}_*",
        f"frame_*",
    ]
    for pat in patterns:
        for f in glob.glob(os.path.join(TEMP_DIR, pat)):
            cleanup_file(f)

def get_main_menu(vip_mode: bool = False):
    """Главное меню: обычное или VIP"""
    web_app_url = f"{get_base_url()}/static/prophet/index.html"
    
    if vip_mode:
        # VIP меню
        kb = [
            [KeyboardButton(text="📱 Открыть Mini App", web_app=WebAppInfo(url=web_app_url))],
            [KeyboardButton(text="🔮 VIP Предсказание"), KeyboardButton(text="🎙 VIP Голос")],
            [KeyboardButton(text="🖼 VIP Видение"), KeyboardButton(text="🌐 VIP Поиск")],
            [KeyboardButton(text="🎵 VIP Музыка"), KeyboardButton(text="📚 Библиотека")],
            [KeyboardButton(text="🎛 Лимиты"), KeyboardButton(text="🔓 Выйти из VIP")]
        ]
    else:
        # Обычное HF меню
        kb = [
            [KeyboardButton(text="📱 Открыть Mini App", web_app=WebAppInfo(url=web_app_url))],
            [KeyboardButton(text="🔮 Предсказание"), KeyboardButton(text="🎙 Голос Судьбы")],
            [KeyboardButton(text="🖼 Видение"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="📚 Библиотека"), KeyboardButton(text="📥 Импорт")],
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
    
    # Проверяем VIP режим
    chat_id = str(message.chat.id)
    # Очищаем старые временные файлы пользователя перед началом сессии
    cleanup_user_temp(chat_id)
    is_vip = user_settings.get(chat_id, {}).get('vip_mode', False)

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
        f"• `/massage` — 🖐 Массажный салон (услуги, цены, запись)\n"
        f"• `/playlist Pink Floyd 5` — создать плейлист\n"
        f"• `/help` — полная справка по всем командам\n\n"
        f"👇 *Выбери действие в меню ниже или просто напиши мне!*"
    )

    await message.answer(
        welcome_text,
        reply_markup=get_main_menu(vip_mode=is_vip),
        parse_mode="Markdown"
    )

@router.message(Command("playlist"))
async def cmd_playlist(message: types.Message, bot: Bot):
    """Начало интерактивного мастера плейлистов"""
    chat_id = str(message.chat.id)
    text = message.text.strip()
    
    # Регулярка для быстрого ввода: /playlist Имя Группы 10
    match = re.match(r'/playlist\s+(.+?)\s+(\d+)$', text, re.IGNORECASE)
    
    if match:
        query = match.group(1)
        count = int(match.group(2))
        await message.answer(f"🎵 *Быстрый поиск:* {query} ({count} треков)...", parse_mode="Markdown")
        from core.tools import search_media_content, send_playlist
        result = search_media_content(query=query, media_type='audio', count=count, chat_id=chat_id)
        
        # Показываем описание (Пророчество)
        if result.get("text"):
            await message.answer(f"🔮 *Пророчество о подборке:*\n_{result['text']}_", parse_mode="Markdown")
            
        await send_playlist(bot, message.chat.id, result.get("tracks", []), chat_id_str=chat_id)
        return

    # Если просто /playlist или /playlist Группа (без числа)
    args = text.split(maxsplit=1)
    user_settings.setdefault(chat_id, {})
    
    if len(args) < 2:
        # Инициализируем мастер
        user_settings[chat_id]['playlist_step'] = 'artist'
        user_settings[chat_id]['playlist_draft'] = {'items': []}
        save_settings(user_settings)
        await message.answer(
            "🎸 *Мастер Плейлистов* (Шаг 1/3)\n\n"
            "Что добавим в подборку?\n\n"
            "• *Имя группы* — найду популярные хиты.\n"
            "• *Группа - Трек* — найду конкретную песню.\n"
            "• *Жанр/Настроение* — сделаю тематический микс.\n\n"
            "_💡 Вы сможете добавить несколько разных запросов, а я объединю их в один плейлист!_",
            parse_mode="Markdown"
        )
    else:
        # Сразу переходим к шагу 2 для этого артиста
        query = args[1]
        user_settings[chat_id]['playlist_step'] = 'count'
        user_settings[chat_id]['playlist_draft'] = {'items': []}
        user_settings[chat_id]['pending_artist'] = query
        save_settings(user_settings)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="5", callback_data="pl_count:5"), 
             InlineKeyboardButton(text="10", callback_data="pl_count:10")],
            [InlineKeyboardButton(text="15", callback_data="pl_count:15"),
             InlineKeyboardButton(text="⌨️ Своё число", callback_data="pl_count:custom")]
        ])
        await message.answer(
            f"✅ Артист: *{query}*\n\n"
            "Сколько треков этого исполнителя добавим в микс?",
            parse_mode="Markdown",
            reply_markup=kb
        )
@router.message(Command("playlist_example"))
async def cmd_playlist_example(message: types.Message):
    """Показывает примеры плейлистов для обучения"""
    text = (
        "🎓 *Академия Плейлистов*\n\n"
        "Я подготовил несколько примеров, чтобы показать, как можно комбинировать артистов и треки.\n\n"
        "Выбери один, чтобы мгновенно увидеть его состав:"
    )
    
    kb_list = []
    for i, ex in enumerate(GLOBAL_EXAMPLES):
        kb_list.append([InlineKeyboardButton(text=ex['name'], callback_data=f"pl_ex_view:{i}")])
    
    await message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list))


@router.message(Command("webhook_status"))
async def cmd_webhook_status(message: types.Message):
    """Проверка статуса webhook"""
    status_msg = await message.answer("📡 Проверяю статус webhook...")

    try:
        info = await bot.get_webhook_info()
        url = info.url
        pending = info.pending_update_count
        last_error = info.last_error_message
        last_error_date = info.last_error_date

        text = f"📡 *Статус Webhook:*\n\n"
        text += f"🔗 *URL:* `{url}`\n"
        text += f"⏳ *В очереди:* {pending}\n"

        if last_error:
            text += f"❌ *Последняя ошибка:* {last_error}\n"
            if last_error_date:
                from datetime import datetime
                error_time = datetime.fromtimestamp(last_error_date)
                text += f"🕒 *Время ошибки:* {error_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        else:
            text += f"✅ *Ошибок нет*\n"

        # Проверка текущего URL
        space_id = os.getenv("SPACE_ID")
        if space_id:
            space_slug = space_id.replace("/", "-").replace("_", "-")
            expected_url = f"https://{space_slug}.hf.space/webhook"

            if url == expected_url:
                text += f"\n✅ *URL совпадает с ожидаемым!*"
            else:
                text += f"\n⚠️ *URL не совпадает!*\n"
                text += f"Ожидался: `{expected_url}`\n"
                text += f"\nИсправьте:\n"
                text += f"`https://api.telegram.org/bot<TOKEN>/setWebhook?url={expected_url}`"

        await status_msg.edit_text(text, parse_mode="Markdown")
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка проверки: {e}")


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """
    Команда /help — полное руководство пользователя.
    """
    help_text = (
        "🔮 *AI Prophet: Твое музыкальное пророчество*\n\n"
        "✨ *Главная фишка: /playlist (Мастер Плейлистов)*\n"
        "Теперь ты можешь собирать сложные музыкальные миксы:\n"
        "1️⃣ Напиши `/playlist` для запуска мастера.\n"
        "2️⃣ Добавляй запросы (группы, жанры или `Группа - Трек`).\n"
        "3️⃣ Выбирай количество треков для каждого элемента.\n"
        "4️⃣ *Интерактивный список:* перед скачиванием ты можешь:\n"
        "   • 🔝 Поднять любимый трек на 1-е место.\n"
        "   • 🔀 Микс — перемешать порядок.\n"
        "   • 🔃 Реверс — перевернуть список.\n"
        "   • ✅/❌ Выбрать только нужные треки.\n\n"
        "🚀 *Быстрые команды:*\n"
        "• `/playlist Pink Floyd 5` — мгновенная подборка.\n"
        "• `/playlist_example` — обучение на примерах.\n"
        "• `/massage` — 🖐 Массажный салон (услуги, цены, запись).\n"
        "• `/specialist <роль>` — 🧑‍⚕️ создать специалиста-консультанта под твой запрос\n"
        "• `/specialists` — список твоих специалистов\n"
        "• `/dismiss <имя>` — удалить специалиста\n\n"
        "🎹 *Другие возможности:*\n"
        "• 🔮 *Предсказание* — задай вопрос, получи мудрость AI.\n"
        "• 🎙 *Голос Судьбы* — отправь голосовое, я его пойму.\n"
        "• 🖼 *Видение* — пришли фото для анализа.\n"
        "• ⚙️ *Настройки* — переключай движки (Gemini / HF).\n\n"
        "🔧 *Админ команды:*\n"
        "• `/webhook_status` — проверить статус webhook.\n\n"
        "💡 *Советы и лимиты:*\n"
        "• Все файлы скачиваются с реальными названиями.\n"
        "• В режиме загрузки ты увидишь живой *прогресс-бар*.\n"
        "• ⏱ *Стандартные лимиты:* до 30 мин и до 50 MB на файл.\n"
        "• ⚙️ Настрой свои правила через кнопку *🎛 Лимиты* в меню.\n"
        "• В конце каждого плейлиста я раскрою его *Ауру*.\n\n"
        "🧘 *Приятного погружения в звук!*"
    )
    await message.answer(help_text, parse_mode="Markdown")

@router.message(Command("specialist"))
async def cmd_specialist(message: types.Message):
    chat_id = int(message.chat.id)
    text = message.text.replace("/specialist", "", 1).strip()
    if not text:
        await message.answer(
            "🧑‍⚕️ *Создание специалиста*\n\n"
            "Напиши, какой специалист тебе нужен.\n"
            "Например: `/specialist эксперт по спортивному массажу для бегунов`\n\n"
            "Я создам персонального консультанта с этой ролью.\n\n"
            "Другие команды:\n"
            "• `/specialists` — список твоих специалистов\n"
            "• `/dismiss <имя>` — удалить специалиста",
            parse_mode="Markdown"
        )
        return
    await _create_and_show_specialist(message, chat_id, text)


@router.message(Command("specialists"))
async def cmd_specialists(message: types.Message):
    chat_id = int(message.chat.id)
    sps = get_specialists(chat_id)
    if not sps:
        await message.answer(
            "У тебя пока нет созданных специалистов.\n"
            "Создай: `/specialist <описание роли>`",
            parse_mode="Markdown"
        )
        return
    lines = ["🧑‍⚕️ *Твои специалисты:*\n"]
    for s in sps:
        lines.append(f"• *{s.name}* — {s.role_description[:50]}…")
    lines.append(f"\nВсего: {len(sps)}")
    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("dismiss"))
async def cmd_dismiss(message: types.Message):
    chat_id = int(message.chat.id)
    name = message.text.replace("/dismiss", "", 1).strip()
    if name:
        if remove_specialist(chat_id, name):
            await message.answer(f"✅ Специалист *{name}* удалён.", parse_mode="Markdown")
        else:
            await message.answer(f"❌ Специалист с именем *{name}* не найден.", parse_mode="Markdown")
        return
    sps = get_specialists(chat_id)
    if not sps:
        await message.answer("Нет специалистов для удаления.")
        return
    rows = [[InlineKeyboardButton(text=f"🗑 {s.name}", callback_data=f"dsp_del_{s.name}")] for s in sps]
    await message.answer("Выбери специалиста для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("dsp_del_"))
async def on_dsp_del_confirm(callback: types.CallbackQuery):
    await callback.answer()
    name = callback.data.replace("dsp_del_", "")
    chat_id = callback.message.chat.id
    if remove_specialist(chat_id, name):
        await callback.message.edit_text(f"✅ Специалист *{name}* удалён.", parse_mode="Markdown")
    else:
        await callback.message.edit_text(f"❌ Не удалось удалить специалиста.")


async def _create_and_show_specialist(message: types.Message, chat_id: int, role: str):
    status = await message.answer(f"🧑‍⚕️ Создаю специалиста: _{role}_…")
    specialist = SpecialistFactory.create(chat_id=int(chat_id), role_description=role)
    if not specialist:
        await status.edit_text("❌ Не удалось создать специалиста. Попробуй позже.")
        return

    lines = [f"✅ *Создан специалист:* {specialist.name}"]
    if specialist.role_description:
        lines.append(f"\n📋 *Роль:* {specialist.role_description}")
    if specialist.skills:
        lines.append(f"\n🔧 *Навыки:* {specialist.skills}")
    lines.append(f"\n💬 Задай ему вопрос прямо сейчас!")

    await status.edit_text("\n".join(lines), parse_mode="Markdown")
    user_settings.setdefault(str(chat_id), {})["specialist_chat"] = specialist.name
    save_settings(user_settings)


async def _handle_create_specialist_auto(chat_id: int, role_description: str, message: types.Message):
    """Вызывается из function calling loop при запросе create_specialist."""
    await message.answer(f"🧑‍⚕️ Создаю специалиста: _{role_description}_…")
    specialist = SpecialistFactory.create(chat_id=chat_id, role_description=role_description)
    if not specialist:
        await message.answer("❌ Не удалось создать специалиста. Попробуй позже.")
        return None
    lines = [f"✅ *Создан специалист:* {specialist.name}"]
    if specialist.role_description:
        lines.append(f"\n📋 *Роль:* {specialist.role_description}")
    if specialist.skills:
        lines.append(f"\n🔧 *Навыки:* {specialist.skills}")
    lines.append(f"\n💬 Задай ему вопрос прямо сейчас или продолжай общение со мной.")
    await message.answer("\n".join(lines), parse_mode="Markdown")
    user_settings.setdefault(str(chat_id), {})["specialist_chat"] = specialist.name
    save_settings(user_settings)
    return specialist


def _is_chatting_with_specialist(chat_id_str: str) -> bool:
    settings = user_settings.get(chat_id_str, {})
    val = settings.get("specialist_chat")
    logger.info(f"_is_chatting_with_specialist: chat={chat_id_str} settings_keys={list(settings.keys())[:5]} specialist_chat={val}")
    return bool(val)


@router.message(F.photo)
async def handle_photo(message: types.Message, bot: Bot):
    chat_id = str(message.chat.id)

    photo = message.photo[-1]
    file_name = f"task_{chat_id}_{int(datetime.now().timestamp())}.jpg"
    file_path = os.path.join(TEMP_DIR, file_name)

    await bot.download(photo, destination=file_path)
    user_settings[chat_id] = {'pending_photo': file_path}

    # Проверяем VIP режим
    is_vip = user_settings.get(chat_id, {}).get('vip_mode', False)
    engine = user_settings.get(chat_id, {}).get('engine', 'auto')
    
    # VIP использует Gemini, обычный режим — только HF
    use_gemini = is_vip or engine == 'gemini'
    
    status_msg = await message.answer("🌀 *Вхожу в транс прозрения...*")

    if use_gemini:
        logger.info(f"🔮 VIP/User {chat_id} uses Gemini for vision.")
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
                    icon = "💎" if is_vip else "🤖"
                    try:
                        await status_msg.edit_text(f"{icon} *Мой взор запечатлел:* \n\n{clean_text}", parse_mode="Markdown")
                    except Exception:
                        await status_msg.edit_text(f"{icon} Мой взор запечатлел:\n\n{clean_text}")

                    await message.answer("Следующий шаг?", reply_markup=kb)
                    cleanup_file(file_path)
                    return
            except Exception as e:
                logger.warning(f"Vision failure on {model_name}: {e}")
                reset_chat(chat_id, model_name)
                continue
    
    # HF режим (обычный пользователь)
    logger.info(f"🧿 User {chat_id} uses HF for vision.")
    
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
    
    # Проверяем VIP режим
    is_vip = user_settings.get(chat_id, {}).get('vip_mode', False)
    engine = user_settings.get(chat_id, {}).get('engine', 'auto')
    
    # VIP режим всегда использует Gemini, обычный — только HF (локально)
    use_gemini = is_vip or engine == 'gemini'
    
    status_msg = await message.answer(f"👂 *Слушаю ({'VIP' if is_vip else engine})...*")

    logger.info(f"🎙 Processing audio for {chat_id} via {'Gemini (VIP)' if use_gemini else 'HF Local'}")

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

    if use_gemini:
        logger.info("🔄 Запуск Gemini транскрибации...")
        text = transcribe_with_gemini(transcribe_path)
        logger.info(f"📥 Gemini результат: {text[:50] if text else 'None'}...")
        # Если Gemini не справился, пробуем HF как бэкап
        if not text:
            logger.info("♻️ Gemini Transcription failed, falling back to HF Whisper.")
            text = get_hf_response(text=None, image_path=transcribe_path, task="audio")
            logger.info(f"📥 HF Whisper результат (fallback): {text[:50] if text else 'None'}...")
    else:
        logger.info("🔄 Запуск HF Whisper через Router...")
        text = get_hf_response(text=None, image_path=transcribe_path, task="audio")
        logger.info(f"📥 HF Whisper результат: {text[:50] if text else 'None'}...")

    cleanup_file(file_path)
    if transcribe_path != file_path:
        cleanup_file(transcribe_path)

    if text:
        logger.info(f"✅ Audio transcribed: {text[:50]}...")

        # Route голоса в активные контексты (массаж, специалист)
        int_chat_id = message.chat.id

        # 1. Массажная консультация
        massage_step = user_settings.get(chat_id, {}).get("massage_step")
        if massage_step == "questionnaire":
            await status_msg.delete()
            message.text = text
            from handlers.massage import on_mc_text_input
            await on_mc_text_input(message)
            return
        elif massage_step == "create_specialist":
            await status_msg.delete()
            _set_user_data(chat_id, "massage_step", None)
            save_settings(user_settings)
            message.text = text
            await _create_and_show_specialist(message, int_chat_id, text)
            return

        # 2. Специалист
        logger.info(f"Voice: checking specialist chat for {chat_id}")
        if _is_chatting_with_specialist(chat_id):
            sp_name = user_settings[chat_id].get("specialist_chat")
            logger.info(f"Voice: specialist_chat={sp_name}")
            if sp_name:
                specialist = get_specialist(int_chat_id, sp_name)
                logger.info(f"Voice: got specialist={specialist}")
                if specialist:
                    await status_msg.delete()
                    try:
                        result = SpecialistFactory.chat(chat_id=int_chat_id, specialist=specialist, user_message=text)
                        if result.is_success():
                            await message.answer(f"👤 *Распознано:* _{text}_", parse_mode="Markdown")
                            await message.answer(f"🧑‍⚕️ *{result.agent_name}:*\n\n{result.content}", parse_mode="Markdown")
                        else:
                            await message.answer("❌ Ошибка связи со специалистом.")
                    except Exception as e:
                        logger.error(f"Voice specialist chat error: {e}")
                        await message.answer("❌ Ошибка при общении со специалистом.")
                    return
                else:
                    del user_settings[chat_id]["specialist_chat"]
                    save_settings(user_settings)

        # 3. Обычный режим — показываем с подтверждением
        await message.answer(
            f"👤 *Распознано:* \n\n_{text}_\n\n"
            f"🔮 *Подтвердите выполнение:*",
            reply_markup=get_voice_confirmation_keyboard(chat_id, text),
            parse_mode="Markdown"
        )
    else:
        await status_msg.edit_text("😔 Эфир слишком зашумлен, не смог разобрать ни слова...")


@router.message(F.document)
async def handle_document(message: types.Message, bot: Bot):
    """Обработка входящих документов (для импорта бэкапа JSON)"""
    chat_id = str(message.chat.id)
    doc = message.document
    
    if doc.file_name.endswith('.json'):
        status_msg = await message.answer("📥 *Обнаружил JSON файл. Проверяю структуру бэкапа...*")
        
        # Скачиваем файл во временную папку
        file_name = f"import_{chat_id}.json"
        file_path = os.path.join(TEMP_DIR, file_name)
        await bot.download(doc, destination=file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Универсальный поиск данных библиотеки в JSON
            def find_library_data(obj):
                if isinstance(obj, dict):
                    if 'library' in obj and isinstance(obj['library'], list):
                        return obj['library']
                    for v in obj.values():
                        res = find_library_data(v)
                        if res: return res
                elif isinstance(obj, list):
                    # Если это просто список словарей, похожих на плейлисты
                    if obj and isinstance(obj[0], dict) and 'items' in obj[0]:
                        return obj
                return None

            new_lib = find_library_data(data)

            if new_lib:
                # Мержим библиотеку
                user_settings.setdefault(chat_id, {})
                old_lib = user_settings[chat_id].get('library', [])
                
                # Дедупликация и подсчет
                existing_names = {pl['name'] for pl in old_lib}
                added_count = 0
                skipped_count = 0
                
                for pl in new_lib:
                    if not isinstance(pl, dict) or 'name' not in pl or 'items' not in pl:
                        continue
                        
                    if pl['name'] not in existing_names:
                        old_lib.append(pl)
                        added_count += 1
                        existing_names.add(pl['name'])
                    else:
                        skipped_count += 1
                
                user_settings[chat_id]['library'] = old_lib
                
                # Попробуем также восстановить настройки если это полный бэкап
                if isinstance(data, dict) and chat_id in data:
                    for k, v in data[chat_id].items():
                        if k != 'library': user_settings[chat_id][k] = v
                elif isinstance(data, dict) and 'engine' in data:
                    user_settings[chat_id]['engine'] = data['engine']
                
                save_settings(user_settings)
                
                msg = f"✅ *Импорт завершен!*\n\n"
                msg += f"📥 Добавлено новых: `{added_count}`\n"
                if skipped_count > 0:
                    msg += f"⏩ Пропущено (уже есть): `{skipped_count}`\n"
                msg += f"📚 Всего в библиотеке: `{len(old_lib)}`\n"
                
                await status_msg.edit_text(msg, parse_mode="Markdown")
            else:
                await status_msg.edit_text("❌ *Ошибка:* Не удалось найти структуру плейлистов в этом файле. Убедитесь, что это JSON, созданный мной.")
                
        except Exception as e:
            logger.error(f"Import error: {e}")
            await status_msg.edit_text(f"❌ *Ошибка при чтении файла:* {str(e)}")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
    else:
        await message.answer("📁 *Файл получен.* К сожалению, я умею обрабатывать только `.json` бэкапы моей библиотеки музыки.")

@router.message()
def _extract_questions(text: str) -> list:
    """Extract question phrases ending with ? from AI response."""
    import re
    qs = re.findall(r'[^.!?]*\?', text)
    return [q.strip() for q in qs if len(q.strip()) > 5][:3]


async def handle_text(message: types.Message, bot: Bot):
    chat_id = str(message.chat.id)
    text = message.text
    if not text: return

    # Если пользователь общается со специалистом — перенаправляем
    is_sp = _is_chatting_with_specialist(chat_id)
    logger.info(f"handle_text specialist check: chat_id={chat_id} is_sp={is_sp}")
    if is_sp:
        sp_name = user_settings[chat_id].get("specialist_chat")
        logger.info(f"specialist_chat name: {sp_name}")
        if sp_name:
            specialist = get_specialist(int(chat_id), sp_name)
            logger.info(f"get_specialist result: {specialist}")
            if specialist:
                try:
                    result = SpecialistFactory.chat(chat_id=int(chat_id), specialist=specialist, user_message=text)
                    if result.is_success():
                        global _qr_counter
                        qs = _extract_questions(result.content)
                        base_text = f"🧑‍⚕️ *{result.agent_name}:*\n\n{result.content}"
                        if qs:
                            _qr_counter += 1
                            qid = str(_qr_counter)
                            _quick_replies[qid] = qs
                            kb = InlineKeyboardMarkup(inline_keyboard=[
                                [InlineKeyboardButton(text=q[:35], callback_data=f"sp_ask:{qid}:{i}")]
                                for i, q in enumerate(qs)
                            ])
                            await message.answer(base_text, parse_mode="Markdown", reply_markup=kb)
                        else:
                            await message.answer(base_text, parse_mode="Markdown")
                        if specialist.message_count == 1:
                            await message.answer("Отправь `/exit_specialist` чтобы выйти из диалога.")
                    else:
                        await message.answer("❌ Ошибка связи со специалистом.")
                    return
                except Exception as e:
                    logger.error(f"Specialist chat error: {e}")
                    await message.answer("❌ Ошибка при общении со специалистом.")
                    return
            else:
                del user_settings[chat_id]["specialist_chat"]
                save_settings(user_settings)

    # Проверка на ввод VIP пароля
    if user_settings.get(chat_id, {}).get('waiting_vip_password'):
        from handlers.vip import admin_cmd
        # Создаём фейковое сообщение с паролем
        message.text = f"/dizel0110 {text}"
        await admin_cmd(message)
        # Сбрасываем флаг после попытки
        user_settings.get(chat_id, {}).pop('waiting_vip_password', None)
        save_settings(user_settings)
        return

    # Кнопка "Выйти из VIP"
    if text == "🔓 Выйти из VIP":
        from handlers.vip import exit_vip
        await exit_vip(message)
        return

    # Проверка на команду сброса блокировки (если ввели текстом)
    if text.startswith("/resetvip"):
        from handlers.vip import reset_vip_lock
        message.text = text  # Сохраняем команду
        await reset_vip_lock(message)
        return

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

    if text == "📚 Библиотека":
        # Имитируем нажатие callback кнопки библиотеки
        await handle_pl_library(types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message, data="pl_library"))
        return

    if text == "🎛 Лимиты":
        from handlers.limits import load_user_limits, update_limits_message
        limits = load_user_limits(chat_id)
        await update_limits_message(message, chat_id, limits)
        return

    if text == "📥 Импорт" or text == "import_json":
        await message.answer(
            "📥 *Импорт Плейлистов По Проводу*\n\n"
            "Просто **скинь мне JSON-файл** с плейлистом или бэкапом библиотеки прямо здесь в чат.\n\n"
            "Я мигом всё расшифрую и добавлю в твой музыкальный арсенал!",
            parse_mode="Markdown"
        )
        return

    if text == "library":
        # Имитируем нажатие callback кнопки библиотеки
        await handle_pl_library(types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message, data="pl_library"))
        return

    if "🤖 Авто" in text: user_settings.setdefault(chat_id, {})['engine'] = 'auto'
    elif "💎 Только Gemini" in text: user_settings.setdefault(chat_id, {})['engine'] = 'gemini'
    elif "🧿 Только Hugging Face" in text: user_settings.setdefault(chat_id, {})['engine'] = 'hf'
    
    if any(x in text for x in ["🤖 Авто", "💎 Только Gemini", "🧿 Только Hugging Face"]):
        save_settings(user_settings) # Сохраняем при изменении
        chat_id = str(message.chat.id)
        is_vip = user_settings.get(chat_id, {}).get('vip_mode', False)
        await message.answer("✅ *Источник изменен.*", reply_markup=get_main_menu(vip_mode=is_vip), parse_mode="Markdown")
        return

    if text == "⬅️ Назад":
        chat_id = str(message.chat.id)
        is_vip = user_settings.get(chat_id, {}).get('vip_mode', False)
        await message.answer("Возвращаемся в главный чертог.", reply_markup=get_main_menu(vip_mode=is_vip))
        return

    # --- ЛОГИКА ШАГОВ ПЛЕЙЛИСТА ---
    state = user_settings.get(chat_id, {})
    step = state.get('playlist_step')

    if step in ['count', 'confirm']:
        # Блокируем случайный текст, когда нужно нажимать кнопки
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена / Выход", callback_data="pl_cancel")]
        ])
        await message.answer(
            "⚠️ *Мастер Плейлистов активен!*\n\n"
            "Пожалуйста, используйте кнопки выше для выбора или нажмите отмену, чтобы вернуться к обычному общению.",
            parse_mode="Markdown",
            reply_markup=kb
        )
        return

    if step == 'artist':
        if 'playlist_draft' not in state:
            state['playlist_draft'] = {'items': []}
            
        artist = message.text.strip()
        state['pending_artist'] = artist # Временно храним артиста пока не узнаем количество
        state['playlist_step'] = 'count'
        save_settings(user_settings)
        
        # Если есть дефис, вероятно это конкретный трек
        is_specific = " - " in artist
        
        kb_rows = [
            [InlineKeyboardButton(text="1 (Точно этот трек)" if is_specific else "1", callback_data="pl_count:1"),
             InlineKeyboardButton(text="3", callback_data="pl_count:3")],
            [InlineKeyboardButton(text="5", callback_data="pl_count:5"), 
             InlineKeyboardButton(text="10", callback_data="pl_count:10")],
            [InlineKeyboardButton(text="⌨️ Своё число", callback_data="pl_count:custom")]
        ]
        
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        
        await message.answer(
            f"✅ Запрос: *{artist}*\n\n"
            "Сколько треков по этому запросу добавить в плейлист?",
            parse_mode="Markdown",
            reply_markup=kb
        )
        return

    if step == 'playlist_naming':
        name = message.text.strip()
        draft = state.get('playlist_draft', {})
        items = draft.get('items', [])
        
        user_settings[chat_id].setdefault('library', [])
        new_playlist = {
            'name': name,
            'items': items,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        user_settings[chat_id]['library'].append(new_playlist)
        state['playlist_step'] = 'confirm'
        save_settings(user_settings)
        await message.answer(f"✅ Плейлист *{name}* сохранен в библиотеку!", parse_mode="Markdown")
        
        # --- ФИНАЛЬНЫЙ ШТРИХ: Отправка файла плейлиста ---
        try:
            # Создаем временный файл для этого конкретного плейлиста
            safe_name = re.sub(r'[^\w\-]', '_', name)
            filename = f"playlist_{safe_name}_{int(datetime.now().timestamp())}.json"
            filepath = os.path.join(TEMP_DIR, filename)
            
            # Структура бэкапа совместима с общим импортом
            export_data = {
                chat_id: {
                    "library": [new_playlist]
                }
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            await message.answer_document(
                FSInputFile(filepath),
                caption=f"📋 *Портативный Плейлист:* `{name}`\n\n_Сохрани этот файл — это твой личный ключ к этой подборке. Его можно переслать другу или импортировать обратно в меня в любой момент._",
                parse_mode="Markdown"
            )
            os.remove(filepath)
        except Exception as e:
            logger.error(f"Failed to send playlist file: {e}")
            
        await show_playlist_confirm(message, chat_id)
        return

    if step == 'count_input':
        try:
            count = int(message.text.strip())
            if not (1 <= count <= 30):
                await message.answer("⚠️ Пожалуйста, введите число от 1 до 30:")
                return
                
            artist = state.pop('pending_artist', 'Неизвестный')
            state.setdefault('playlist_draft', {}).setdefault('items', []).append({
                'query': artist,
                'count': count
            })
            state['playlist_step'] = 'confirm'
            save_settings(user_settings)
            
            await show_playlist_confirm(message, chat_id)
            return
        except (ValueError, KeyError):
            await message.answer("❌ Введите количество треков цифрами:")
            return

    # В противном случае - обычный ритуал
    status_msg = await message.answer("🧘 *Медитирую над твоими словами...*")
    await conduct_ai_ritual(message, bot, message.text, status_msg)

async def conduct_ai_ritual(message: types.Message, bot: Bot, input_text: str, status_msg=None):
    chat_id = str(message.chat.id)
    
    # Проверяем VIP режим
    is_vip = user_settings.get(chat_id, {}).get('vip_mode', False)
    engine = user_settings.get(chat_id, {}).get('engine', 'auto')
    
    # VIP использует Gemini, обычный — только HF
    use_gemini = is_vip or engine == 'gemini'

    if not input_text: return
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    if user_settings.get(chat_id, {}).get('pending_photo'):
        await handle_vision_action(message, bot, chat_id, input_text)
        return

    if use_gemini:
        # VIP режим — Gemini
        if status_msg: await status_msg.edit_text("💎 *Подключение к Gemini 3.5 Flash...*")
        else: status_msg = await message.answer("💎 *Подключение к Gemini 3.5 Flash...*")

        for model_name in FALLBACK_MODELS:
            try:
                chat = get_ai_chat(chat_id, model_name)
                if not chat: continue

                response = chat.send_message(input_text)
                if response.text:
                    clean_text, kb = parse_steps_and_create_kb(response.text, chat_id)

                    icon = "💎" if is_vip else "🤖"
                    await status_msg.edit_text(f"{icon} *Ответ получен через поток Gemini:*")
                    await message.answer(f"{icon} {clean_text}", reply_markup=kb)
                    return
            except Exception as e:
                logger.warning(f"Gemini failure on {model_name}: {e}")
                reset_chat(chat_id, model_name)
                continue

    # HF режим (обычный пользователь)
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

                # Пытаемся найти ссылки для кнопок
                buttons = []
                if tracks:
                    # Сохраняем результаты поиска для пользователя, чтобы кнопки работали по индексу
                    user_settings.setdefault(chat_id, {})['last_tracks'] = tracks
                    save_settings(user_settings)

                    buttons_row = []
                    for i, track in enumerate(tracks, 1):
                        if i > 10: break # Максимум 10 кнопок
                        
                        buttons_row.append(
                            InlineKeyboardButton(text=f"⬇️ {i}", callback_data=f"dl_track:{i-1}")
                        )
                        
                        if len(buttons_row) >= 5:
                            buttons.append(buttons_row)
                            buttons_row = []
                    
                    if buttons_row:
                        buttons.append(buttons_row)

                # Добавляем кнопку "Скачать всё" для плейлистов
                if len(tracks) > 1 and query:
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"🎧 Скачать всё ({len(tracks)} тр.)",
                            callback_data=f"dl_playlist:{query[:30]}:{len(tracks)}"
                        )
                    ])

                kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
                await message.answer(f"🎵 {text_result}", reply_markup=kb, disable_web_page_preview=True)
            return
        # HF ответил, но нет tool_result — всё равно выходим
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
                        
                        if fn_name == "create_specialist":
                            role = args.get("role_description", "специалист")
                            sp = await _handle_create_specialist_auto(message.chat.id, role, message)
                            result_text = f"Создан специалист '{sp.name}' с ролью: {sp.role_description}" if sp else "Не удалось создать специалиста"
                            response = chat.send_message(
                                message=genai_types.Part.from_function_response(
                                    name=fn_name,
                                    response={"result": result_text}
                                )
                            )
                        elif fn_name in AVAILABLE_FUNCTIONS:
                            result = AVAILABLE_FUNCTIONS[fn_name](**args)
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
        chat_id = str(message.chat.id)
        is_vip = user_settings.get(chat_id, {}).get('vip_mode', False)
        if status_msg:
            await status_msg.edit_text(final_text)
            await message.answer("Вернись, когда эфир очистится.", reply_markup=get_main_menu(vip_mode=is_vip))
        else:
            await message.answer(final_text, reply_markup=get_main_menu(vip_mode=is_vip))

@router.callback_query(F.data.startswith("dl_track:"))
async def handle_track_callback(callback: types.CallbackQuery, bot: Bot):
    """Скачивание трека по индексу из кэша поиска"""
    import os
    from aiogram.types import FSInputFile
    from core.tools import download_audio

    try:
        idx = int(callback.data.split(":")[1])
        chat_id = str(callback.message.chat.id)
        
        # Берем треки из кэша последнего поиска
        tracks = user_settings.get(chat_id, {}).get('last_tracks', [])
        
        if not tracks or idx >= len(tracks):
            await callback.answer("❌ Ссылка устарела, найдите музыку еще раз")
            return
            
        track = tracks[idx]
        url = track['url']
        title = track['title']

        await callback.answer(f"⏳ Начинаю загрузку: {title[:20]}...")
        
        # Кнопка отмены (пока просто для интерфейса, логику добавим следом)
        cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Прервать", callback_data=f"cancel_dl:{chat_id}")
        ]])
        
        status_msg = await bot.send_message(
            chat_id, 
            f"📥 *Подготовка к загрузке...*\n🎵 {title}", 
            parse_mode="Markdown",
            reply_markup=cancel_kb
        )

        import time
        last_update = [0] # Используем список для замыкания

        async def prog_cb(percent, speed, eta):
            now = time.time()
            if now - last_update[0] > 2.2: # Обновляем не чаще чем раз в 2.2 сек (лимиты TG)
                last_update[0] = now
                try:
                    p_val = float(percent.strip('%'))
                    bar_len = 10
                    filled = int(p_val / 10)
                    bar = "🔵" * filled + "⚪" * (bar_len - filled)
                    
                    text = (
                        f"📥 *Загрузка:* {percent}\n"
                        f"{bar}\n"
                        f"🚀 *Скорость:* {speed}\n"
                        f"⏳ *Осталось:* {eta}\n\n"
                        f"🎵 _{title}_"
                    )
                    # Обновляем сообщение
                    await status_msg.edit_text(text, parse_mode="Markdown", reply_markup=cancel_kb)
                except Exception as e: 
                    logger.debug(f"Progress update failed: {e}")
                
            # ПРОВЕРКА ОТМЕНЫ
            if chat_id in active_cancellations:
                return False
            return True

        # Обертка для синхронного вызова асинхронного колбека
        def sync_prog_cb(p, s, t):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(prog_cb(p, s, t), loop)
                else:
                    loop.run_until_complete(prog_cb(p, s, t))
            except: pass
            return True if chat_id not in active_cancellations else False

        # Скачиваем аудио с прогресс-баром
        file_path, real_title, duration = download_audio(url, chat_id=chat_id, progress_callback=sync_prog_cb)
        
        # Убираем флаг отмены если он был
        active_cancellations.discard(chat_id)

        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            size_mb = file_size / (1024 * 1024)
            size_text = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{file_size/1024:.1f} KB"
            
            duration_text = f" ({duration} сек)" if duration else ""
            await status_msg.edit_text(f"📤 *Отправляю:* {real_title or title}...")
            
            audio_file = FSInputFile(file_path)
            await bot.send_audio(
                callback.message.chat.id,
                audio_file,
                title=real_title or title,
                performer="AI Prophet",
                caption=f"🎧 *{real_title or title}*{duration_text}\n📦 `{size_text}` | 🔗 [Источник]({url})"
            )
            await status_msg.delete()
            os.remove(file_path)
        else:
            await status_msg.edit_text("❌ Не удалось скачать файл. Попробуйте другой источник.")
            
    except Exception as e:
        logger.error(f"Error in handle_track_callback: {e}")
        await callback.answer("❌ Произошла ошибка при загрузке")
async def handle_download_callback(callback: types.CallbackQuery, bot: Bot):
    import os
    from aiogram.types import FSInputFile
    from core.tools import download_audio

    video_id = callback.data.split(":")[1]
    url = f"https://www.youtube.com/watch?v={video_id}"
    chat_id = str(callback.message.chat.id)

    await callback.answer("⏳ Начинаю магию конвертации...")
    status_msg = await bot.send_message(chat_id, f"⬇️ Скачиваю и конвертирую: {url}")

    # Передаём chat_id для загрузки пользова��ельских лимитов
    file_path, title, duration = download_audio(url, chat_id=chat_id)

    if file_path and os.path.exists(file_path):
        try:
            file_size = os.path.getsize(file_path)
            size_mb = file_size / (1024 * 1024)
            size_text = f"{size_mb:.1f} MB" if size_mb >= 1 else f"{file_size/1024:.1f} KB"
            
            duration_text = f" ({duration} сек)" if duration else ""
            await status_msg.edit_text(f"📤 Отправляю: {title}{duration_text}...")
            audio_file = FSInputFile(file_path)
            # Отправляем с реальным названием
            await bot.send_audio(
                callback.message.chat.id,
                audio_file,
                title=title,
                performer="AI Prophet Media",
                caption=f"🎧 *{title}*{duration_text}\n📦 `{size_text}` | 🔗 [Источник]({url})"
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


@router.callback_query(F.data.startswith("sp_ask:"))
async def on_sp_ask(callback: types.CallbackQuery, bot: Bot):
    await callback.answer()
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        return
    qid, idx = parts[1], int(parts[2])
    question = _quick_replies.get(qid, [None])[idx] if qid in _quick_replies else None
    if not question:
        await callback.message.edit_text("⏳ Вопрос устарел, напиши сам.")
        return
    chat_id = str(callback.message.chat.id)
    sp_name = user_settings.get(chat_id, {}).get("specialist_chat")
    if not sp_name:
        await callback.message.answer("❌ Нет активного специалиста.")
        return
    specialist = get_specialist(int(chat_id), sp_name)
    if not specialist:
        await callback.message.answer("❌ Специалист не найден.")
        return
    result = SpecialistFactory.chat(chat_id=int(chat_id), specialist=specialist, user_message=question)
    if result.is_success():
        await callback.message.answer(f"🧑‍⚕️ *{result.agent_name}:*\n\n{result.content}", parse_mode="Markdown")
    else:
        await callback.message.answer("❌ Ошибка связи со специалистом.")


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
        await callback.answer("✏️ Введите новый текст:")
        # Сохраняем флаг и ждём следующее сообщение
        user_settings.setdefault(chat_id, {})['pending_voice_edit'] = True
        # Отправляем инструкцию
        await callback.message.answer(
            "✏️ *Введите исправленный текст:*\n\n"
            "_Просто отправьте сообщение с правильным текстом, и я выполню его._"
        )
        # Очищаем сохранённый текст
        user_settings.get(chat_id, {}).pop('pending_voice_text', None)

    elif action == "voice_cancel":
        await callback.answer("❌ Отменено")
        user_settings.get(chat_id, {}).pop('pending_voice_text', None)
        await callback.message.delete()

@router.callback_query(F.data.startswith("cancel_dl:"))
async def handle_cancel_callback(callback: types.CallbackQuery):
    chat_id = callback.data.split(":")[1]
    active_cancellations.add(chat_id)
    await callback.answer("🛑 Прерываю загрузку...")
    await callback.message.edit_text("❌ *Загрузка отменена пользователем*", parse_mode="Markdown")

@router.callback_query(F.data.startswith("pl_count:"))
async def handle_playlist_wizard_count(callback: types.CallbackQuery, bot: Bot):
    chat_id = str(callback.message.chat.id)
    data = callback.data.split(":")[1]
    
    state = user_settings.get(chat_id, {})
    
    if data == "custom":
        state['playlist_step'] = 'count_input'
        save_settings(user_settings)
        await callback.message.edit_text("⌨️ *Введите желаемое количество треков (от 1 до 30):*", parse_mode="Markdown")
        return

    count = int(data)
    if 'playlist_draft' not in state:
        await callback.answer("Ошибка сессии. Начни заново: /playlist")
        return
        
    artist = state.pop('pending_artist', 'Неизвестный')
    state['playlist_draft']['items'].append({
        'query': artist,
        'count': count
    })
    state['playlist_step'] = 'confirm'
    save_settings(user_settings)
    
    await show_playlist_confirm(callback, chat_id)

@router.callback_query(F.data == "pl_add_more")
async def handle_pl_add_more(callback: types.CallbackQuery):
    chat_id = str(callback.message.chat.id)
    user_settings[chat_id]['playlist_step'] = 'artist'
    save_settings(user_settings)
    await callback.message.edit_text(
        "📝 *Добавление элемента:*\n\n"
        "• Введите *Название группы* для подбора хитов.\n"
        "• Введите *Группа - Трек* для точного поиска.\n"
        "• Введите *Жанр* для тематической выборки.",
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "pl_search")
async def handle_pl_search(callback: types.CallbackQuery, bot: Bot):
    chat_id = str(callback.message.chat.id)
    state = user_settings.get(chat_id, {}).get('playlist_draft', {})
    items = state.get('items', [])
    
    if not items:
        await callback.answer("Список пуст!")
        return

    await callback.message.edit_text(f"🚀 Запускаю мега-поиск для {len(items)} запросов...")
    
    from core.tools import search_media_content
    all_tracks = []
    descriptions = []
    
    not_found = []
    
    for item in items:
        query = item['query']
        count = item['count']
        res = search_media_content(query=query, media_type='audio', count=count, chat_id=chat_id)
        
        tracks = res.get("tracks", [])
        if not tracks:
            not_found.append(query)
            continue

        desc = res.get("text")
        if desc: descriptions.append(desc)
        
        for t in tracks:
            t['selected'] = True 
            t['query_origin'] = query
        all_tracks.extend(tracks)
        
    if not_found:
        names = ", ".join(not_found)
        await callback.message.answer(f"⚠️ *Не удалось найти:* {names}")

    if not all_tracks:
        await callback.message.answer("😔 Совсем ничего не нашлось. Попробуйте изменить запросы.")
        return

    # Сохраняем найденное и описание
    user_settings[chat_id]['found_tracks'] = all_tracks
    user_settings[chat_id]['search_desc'] = "\n\n".join(descriptions)
    
    # Сбрасываем стейт мастера
    user_settings[chat_id].pop('playlist_step', None)
    save_settings(user_settings)
    
    await show_selection_menu(callback, chat_id)

async def show_selection_menu(callback: types.CallbackQuery, chat_id: str):
    """Показывает список найденных треков с возможностью выбора"""
    state = user_settings.get(chat_id, {})
    tracks = state.get('found_tracks', [])
    search_desc = state.get('search_desc', '')
    
    # Формируем текст списка
    text = "🔮 *Пророчество о плейлисте:*\n"
    if search_desc:
        text += f"_{search_desc[:500]}..._\n\n" # Ограничиваем длину
    
    text += "📋 *Список треков (отметьте нужные):*\n"
    kb_list = []
    
    for i, track in enumerate(tracks):
        status = "✅" if track.get('selected', True) else "❌"
        # Ещё короче название, чтобы влезло две кнопки
        short_title = track['title'][:20] + ".." if len(track['title']) > 22 else track['title']
        
        text += f"{i+1}. {status} [{track['title']}]({track['url']})\n"
        
        kb_list.append([
            InlineKeyboardButton(text=f"{status} {short_title}", callback_data=f"pl_toggle:{i}"),
            InlineKeyboardButton(text="🔝", callback_data=f"pl_top:{i}")
        ])
    
    kb_list.append([
        InlineKeyboardButton(text="🔀 Микс", callback_data="pl_shuffle"),
        InlineKeyboardButton(text="🔃 Реверс", callback_data="pl_reverse"),
        InlineKeyboardButton(text="🚀 СКАЧАТЬ", callback_data="pl_dl_final")
    ])
    kb_list.append([InlineKeyboardButton(text="🔄 Сброс / Новый поиск", callback_data="pl_add_more")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    
    try:
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    except:
        # Если текст слишком длинный, пробуем обновить только кнопки или отправить новое
        await callback.message.answer("Список треков (слишком длинный для одного сообщения):", reply_markup=kb)

@router.callback_query(F.data.startswith("pl_toggle:"))
async def handle_pl_toggle(callback: types.CallbackQuery):
    chat_id = str(callback.message.chat.id)
    idx = int(callback.data.split(":")[1])
    
    state = user_settings.get(chat_id, {})
    tracks = state.get('found_tracks', [])
    
    if 0 <= idx < len(tracks):
        tracks[idx]['selected'] = not tracks[idx].get('selected', True)
        save_settings(user_settings)
        await show_selection_menu(callback, chat_id)
    await callback.answer()

@router.callback_query(F.data == "pl_shuffle")
async def handle_pl_shuffle(callback: types.CallbackQuery):
    chat_id = str(callback.message.chat.id)
    state = user_settings.get(chat_id, {})
    tracks = state.get('found_tracks', [])
    
    if tracks:
        random.shuffle(tracks)
        save_settings(user_settings)
        await show_selection_menu(callback, chat_id)
    await callback.answer("🔀 Перемешано!")

@router.callback_query(F.data.startswith("pl_top:"))
async def handle_pl_top(callback: types.CallbackQuery):
    chat_id = str(callback.message.chat.id)
    idx = int(callback.data.split(":")[1])
    state = user_settings.get(chat_id, {})
    tracks = state.get('found_tracks', [])
    
    if 0 < idx < len(tracks):
        # Перемещаем трек в самое начало
        track = tracks.pop(idx)
        tracks.insert(0, track)
        save_settings(user_settings)
        await show_selection_menu(callback, chat_id)
    await callback.answer("🔝 Поднято в начало!")

@router.callback_query(F.data == "pl_reverse")
async def handle_pl_reverse(callback: types.CallbackQuery):
    chat_id = str(callback.message.chat.id)
    state = user_settings.get(chat_id, {})
    tracks = state.get('found_tracks', [])
    
    if tracks:
        tracks.reverse()
        save_settings(user_settings)
        await show_selection_menu(callback, chat_id)
    await callback.answer("🔃 Порядок изменен на обратный!")

@router.callback_query(F.data == "pl_dl_final")
async def handle_pl_download_selected(callback: types.CallbackQuery, bot: Bot):
    chat_id = str(callback.message.chat.id)
    state = user_settings.get(chat_id, {})
    tracks = state.get('found_tracks', [])
    
    selected_tracks = [t for t in tracks if t.get('selected', True)]
    
    if not selected_tracks:
        await callback.answer("❌ Ничего не выбрано!", show_alert=True)
        return
        
    await callback.message.edit_text(f"⏳ Начинаю загрузку {len(selected_tracks)} треков...")
    
    from core.tools import send_playlist
    # Очищаем стейт найденного чтобы не висело в памяти
    user_settings[chat_id].pop('found_tracks', None)
    save_settings(user_settings)
    
    await send_playlist(bot, callback.message.chat.id, selected_tracks, status_msg=callback.message, chat_id_str=chat_id)

async def show_playlist_confirm(message_or_callback, chat_id):
    """Общая функция для показа финального шага мастера"""
    state = user_settings.get(chat_id, {})
    draft = state.get('playlist_draft', {})
    items = draft.get('items', [])
    
    summary = []
    for i, item in enumerate(items, 1):
        icon = "🎯" if " - " in item['query'] else "🎸"
        summary.append(f"{i}. {icon} *{item['query']}* — {item['count']} шт.")
    
    summary_text = "\n".join(summary) if summary else "Пусто"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Найти сейчас", callback_data="pl_search")],
        [InlineKeyboardButton(text="➕ Добавить еще автора", callback_data="pl_add_more")],
        [InlineKeyboardButton(text="💾 Сохранить как шаблон", callback_data="pl_save_tpl")]
    ])
    
    text = (
        f"📊 *Ваша подборка:*\n\n"
        f"{summary_text}\n\n"
        "💡 *Подсказка:* Вы можете добавлять и конкретные песни, и целые группы. Я соберу всё в один микс.\n\n"
        "ℹ️ 🎯 — точный трек, 🎸 — подборка."
    )
    
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await message_or_callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
@router.callback_query(F.data == "pl_save_tpl")
async def handle_pl_save_tpl(callback: types.CallbackQuery):
    chat_id = str(callback.message.chat.id)
    state = user_settings.get(chat_id, {})
    
    # Переводим в состояние ввода имени
    state['playlist_step'] = 'playlist_naming'
    save_settings(user_settings)
    
    await callback.message.answer("📝 *Введите название для этого плейлиста:*", parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "pl_library")
async def handle_pl_library(callback: types.CallbackQuery):
    chat_id = str(callback.message.chat.id)
    lib = user_settings.get(chat_id, {}).get('library', [])
    
    if not lib:
        if callback.id == "0":
            await callback.message.answer("🛑 Ваша библиотека пока пуста.\n\n_Добавьте свой первый плейлист через Мастер или Импортируйте JSON-файл._", parse_mode="Markdown")
        else:
            await callback.answer("Библиотека пуста. Сохрани что-нибудь через /playlist!")
        return
        
    text = "📚 *Ваша Музыкальная Библиотека*\n_Выбери ритуал для запуска:_\n\n"
    kb_list = []
    
    total_tracks = 0
    for i, pl in enumerate(lib):
        items_count = len(pl.get('items', []))
        total_tracks += items_count
        text += f"{i+1}. 🎵 *{pl['name']}* (`{items_count}` треков)\n"
        kb_list.append([
            InlineKeyboardButton(text=f"▶️ {pl['name']}", callback_data=f"pl_launch:{i}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"pl_delete:{i}")
        ])
    
    text += f"\n📊 Всего в хранилище: `{total_tracks}` записей."
    
    kb_list.append([
        InlineKeyboardButton(text="📥 Импорт (JSON)", callback_data="pl_import_btn"),
        InlineKeyboardButton(text="📤 Бэкап (JSON)", callback_data="pl_export")
    ])
    kb_list.append([
        InlineKeyboardButton(text="➕ Новый", callback_data="pl_new"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="pl_cancel")
    ])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)
    try:
        if callback.id == "0": # Наш "фейковый" вызов из меню
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)
        else:
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    except Exception:
        await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)

@router.callback_query(F.data.startswith("pl_delete:"))
async def handle_pl_delete(callback: types.CallbackQuery):
    chat_id = str(callback.message.chat.id)
    idx = int(callback.data.split(":")[1])
    lib = user_settings.get(chat_id, {}).get('library', [])
    
    if 0 <= idx < len(lib):
        removed = lib.pop(idx)
        save_settings(user_settings)
        await callback.answer(f"🗑 Удалено: {removed['name']}")
        await handle_pl_library(callback)
    else:
        await callback.answer("Ошибка удаления!")

@router.callback_query(F.data == "pl_import_btn")
async def handle_pl_import_click(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "📥 *Для импорта просто отправь мне JSON-файл бэкапа или плейлиста.*",
        parse_mode="Markdown"
    )
    await cmd_playlist(callback.message, bot)
    await callback.answer()

@router.callback_query(F.data == "pl_export")
async def handle_pl_export(callback: types.CallbackQuery):
    chat_id = str(callback.message.chat.id)
    
    # Создаем временный файл специально для пользователя
    export_path = os.path.join(TEMP_DIR, f"backup_{chat_id}.json")
    user_data = {chat_id: user_settings.get(chat_id, {})}
    
    with open(export_path, 'w', encoding='utf-8') as f:
        json.dump(user_data, f, ensure_ascii=False, indent=2)
    
    await callback.message.answer_document(
        FSInputFile(export_path),
        caption="💾 *Твой переносной бэкап библиотеки.*\n\nЕсли бот «забудет» тебя (например, при переезде на новый сервер), просто перешли мне этот файл в будущем!",
        parse_mode="Markdown"
    )
    os.remove(export_path)
    await callback.answer()

@router.callback_query(F.data.startswith("pl_launch:"))
async def handle_pl_launch(callback: types.CallbackQuery, bot: Bot):
    chat_id = str(callback.message.chat.id)
    idx = int(callback.data.split(":")[1])
    lib = user_settings.get(chat_id, {}).get('library', [])
    
    if 0 <= idx < len(lib):
        pl = lib[idx]
        user_settings[chat_id]['playlist_draft'] = {'items': pl['items']}
        save_settings(user_settings)
        await handle_pl_search(callback, bot)
    else:
        await callback.answer("Ошибка!")

@router.callback_query(F.data.startswith("pl_ex_view:"))
async def handle_pl_ex_view(callback: types.CallbackQuery):
    idx = int(callback.data.split(":")[1])
    if 0 <= idx < len(GLOBAL_EXAMPLES):
        ex = GLOBAL_EXAMPLES[idx]
        items_text = "\n".join([f"• {item['query']} ({item['count']} шт.)" for item in ex['items']])
        
        text = (
            f"📋 *Пример: {ex['name']}*\n\n"
            f"{ex['desc']}\n\n"
            f"*Состав:*\n{items_text}\n\n"
            "Запустить этот поиск?"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 ЗАПУСТИТЬ", callback_data=f"pl_ex_run:{idx}")],
            [InlineKeyboardButton(text="💾 ДОБАВИТЬ В БИБЛИОТЕКУ", callback_data=f"pl_ex_save:{idx}")],
            [InlineKeyboardButton(text="⬅️ К примерам", callback_data="pl_ex_back")]
        ])
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)

@router.callback_query(F.data == "pl_ex_back")
async def handle_pl_ex_back(callback: types.CallbackQuery):
    await cmd_playlist_example(callback.message)
    await callback.answer()

@router.callback_query(F.data.startswith("pl_ex_save:"))
async def handle_pl_ex_save(callback: types.CallbackQuery):
    """Копирует пример из Академии в черновик плейлиста для редактирования/сохранения"""
    chat_id = str(callback.message.chat.id)
    idx = int(callback.data.split(":")[1])
    
    if 0 <= idx < len(GLOBAL_EXAMPLES):
        ex = GLOBAL_EXAMPLES[idx]
        user_settings.setdefault(chat_id, {})
        # Копируем данные примера в черновик
        user_settings[chat_id]['playlist_draft'] = {'items': ex['items']}
        user_settings[chat_id]['playlist_step'] = 'confirm'
        save_settings(user_settings)
        
        await callback.answer("📥 Копирую в мастер плейлистов...")
        # Показываем финальный шаг мастера, где уже есть кнопка "Сохранить как шаблон"
        await show_playlist_confirm(callback, chat_id)

@router.callback_query(F.data.startswith("pl_ex_run:"))
async def handle_pl_ex_run(callback: types.CallbackQuery, bot: Bot):
    chat_id = str(callback.message.chat.id)
    idx = int(callback.data.split(":")[1])
    if 0 <= idx < len(GLOBAL_EXAMPLES):
        ex = GLOBAL_EXAMPLES[idx]
        user_settings.setdefault(chat_id, {})['playlist_draft'] = {'items': ex['items']}
        save_settings(user_settings)
        await handle_pl_search(callback, bot)
    await callback.answer()


