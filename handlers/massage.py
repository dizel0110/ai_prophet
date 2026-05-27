import os
import json
import glob
import logging
from aiogram import types, Router, F
from aiogram.filters import Command, BaseFilter
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import get_base_url, GEM_BOT_URL, TEMP_DIR

from core.agents import MassageConsultationOrchestrator, format_consultation_results, get_massage_music, MASSAGE_MUSIC_GENRES
from core.agents.agent_factory import SpecialistFactory, get_specialists, remove_specialist
from core.questionnaire import MassageQuestionnaire, QUESTIONNAIRE_STEPS

logger = logging.getLogger(__name__)
router = Router()


class InQuestionnaireFilter(BaseFilter):
    def __init__(self):
        self.settings_file = os.path.join(TEMP_DIR, "user_settings.json")

    async def __call__(self, message: types.Message) -> bool:
        if not os.path.exists(self.settings_file):
            return False
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            chat_settings = settings.get(str(message.chat.id), {})
            step = chat_settings.get("massage_step")
            if step == "create_specialist":
                return True
            return (step == "questionnaire"
                    and chat_settings.get("massage_waiting_input") is not None)
        except Exception:
            return False

SETTINGS_FILE = os.path.join(TEMP_DIR, "user_settings.json")


def _load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")


def _massage_url() -> str:
    return f"{get_base_url()}/static/massage/index.html"


def get_massage_menu():
    url = _massage_url()
    kb = [
        [KeyboardButton(text="🖐 Открыть салон", web_app=WebAppInfo(url=url))],
        [KeyboardButton(text="⬅️ Главное меню")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# === ХЕНДЛЕР КОМАНДЫ /massage ===
@router.message(Command("massage"))
async def cmd_massage(message: types.Message):
    url = _massage_url()
    text = (
        "🖐 *Мастерская Массажа*\n\n"
        "AI Prophet поможет расслабить тело.\n"
        "Мы — супружеская команда профессиональных мастеров массажа.\n"
        "Классика, антицеллюлитный, спортивный, стоун-терапия и другие техники.\n\n"
        "👇 Открой салон и выбери услугу"
    )
    inline_kb = [
        [InlineKeyboardButton(text="🖐 Открыть салон", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton(text="🧑‍⚕️ AI-консультация", callback_data="mc_start")],
        [InlineKeyboardButton(text="🎵 Музыка для массажа", callback_data="massage_music")],
        [InlineKeyboardButton(text="🧑‍⚕️ Создать специалиста", callback_data="mc_specialist")],
    ]
    if GEM_BOT_URL:
        inline_kb.append([InlineKeyboardButton(text="🤖 GEM-бот помощник", url=GEM_BOT_URL)])
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb),
    )
    await message.answer("Кнопка быстрого доступа:", reply_markup=get_massage_menu())


# === СОЗДАТЬ СПЕЦИАЛИСТА ===
@router.callback_query(lambda c: c.data == "mc_specialist")
async def on_mc_specialist(callback: types.CallbackQuery):
    await callback.answer()
    chat_id = callback.message.chat.id
    sps = get_specialists(chat_id)
    rows = []
    for s in sps:
        rows.append([InlineKeyboardButton(text=f"💬 {s.name}", callback_data=f"mc_spchat_{s.name}")])
    if rows:
        rows.append([InlineKeyboardButton(text="🗑 Удалить специалиста", callback_data="mc_spdel")])
    rows.append([InlineKeyboardButton(text="➕ Создать нового", callback_data="mc_spnew")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="mc_back")])
    txt = "🧑‍⚕️ *Твои специалисты*" + ("\n\nНажми на имя, чтобы задать вопрос." if sps else "\n\nУ тебя пока нет специалистов. Создай нового!")
    await callback.message.edit_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(lambda c: c.data == "mc_spnew")
async def on_mc_spnew(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🧑‍⚕️ *Создание нового специалиста*\n\n"
        "Напиши, какой специалист тебе нужен.\n"
        "Например: *эксперт по стоун-терапии* или *консультант по ЛФК*\n\n"
        "Я создам персонального консультанта под твой запрос.",
        parse_mode="Markdown",
    )
    _set_user_data(callback.message.chat.id, "massage_step", "create_specialist")


@router.callback_query(lambda c: c.data and c.data.startswith("mc_spchat_"))
async def on_mc_spchat(callback: types.CallbackQuery):
    await callback.answer()
    name = callback.data.replace("mc_spchat_", "")
    from handlers.messages import _create_and_show_specialist
    settings = _load_settings()
    settings[str(callback.message.chat.id)]["specialist_chat"] = name
    _save_settings(settings)
    await callback.message.edit_text(
        f"💬 Ты общаешься со специалистом *{name}*.\n"
        "Просто напиши ему сообщение.\n\n"
        "Чтобы выйти из диалога — напиши `/exit_specialist`.",
        parse_mode="Markdown",
    )


@router.message(Command("exit_specialist"))
async def on_exit_specialist(message: types.Message):
    chat_id = str(message.chat.id)
    settings = _load_settings()
    if chat_id in settings and "specialist_chat" in settings[chat_id]:
        del settings[chat_id]["specialist_chat"]
        _save_settings(settings)
        await message.answer("✅ Вышел из диалога со специалистом.")
    else:
        await message.answer("Ты не в диалоге со специалистом.")


@router.callback_query(lambda c: c.data == "mc_spdel")
async def on_mc_spdel(callback: types.CallbackQuery):
    await callback.answer()
    chat_id = callback.message.chat.id
    sps = get_specialists(chat_id)
    rows = []
    for s in sps:
        rows.append([InlineKeyboardButton(text=f"🗑 {s.name}", callback_data=f"mc_spdel_{s.name}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="mc_specialist")])
    await callback.message.edit_text(
        "Выбери специалиста для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("mc_spdel_"))
async def on_mc_spdel_confirm(callback: types.CallbackQuery):
    await callback.answer()
    name = callback.data.replace("mc_spdel_", "")
    chat_id = callback.message.chat.id
    if remove_specialist(chat_id, name):
        await callback.message.edit_text(f"✅ Специалист *{name}* удалён.", parse_mode="Markdown")
    else:
        await callback.message.edit_text(f"❌ Не удалось удалить специалиста.")


# === МУЗЫКА ДЛЯ МАССАЖА ===
@router.callback_query(lambda c: c.data == "massage_music")
async def on_massage_music(callback: types.CallbackQuery):
    await callback.answer()
    rows = []
    genres = list(MASSAGE_MUSIC_GENRES.keys())
    for i in range(0, len(genres), 2):
        row = []
        row.append(InlineKeyboardButton(text=MASSAGE_MUSIC_GENRES[genres[i]]["name"], callback_data=f"mc_music_{genres[i]}"))
        if i + 1 < len(genres):
            row.append(InlineKeyboardButton(text=MASSAGE_MUSIC_GENRES[genres[i + 1]]["name"], callback_data=f"mc_music_{genres[i + 1]}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🎶 Случайный плейлист", callback_data="mc_music_random")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="mc_back")])
    await callback.message.edit_text(
        "🎵 *Выбери жанр для массажного плейлиста:*\n\n"
        "Кураторская подборка проверенных треков. Нажми на жанр — "
        "я покажу тебе ссылки на проверенную музыку для твоего сеанса.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("mc_music_"))
async def on_mc_music(callback: types.CallbackQuery):
    genre_key = callback.data.replace("mc_music_", "")
    if genre_key == "random":
        import random
        genre_key = random.choice(list(MASSAGE_MUSIC_GENRES.keys()))

    genre_data = get_massage_music(genre_key)
    if not genre_data or not genre_data["tracks"]:
        await callback.answer("Не нашлось треков для этого жанра", show_alert=True)
        return

    await callback.answer(f"🎵 {genre_data['genre']}")
    lines = [f"🎵 *{genre_data['genre']}* — проверенные треки:\n"]
    for i, track in enumerate(genre_data["tracks"], 1):
        lines.append(f"{i}. [{track['title']}]({track['url']})")

    from core.tools import search_media_content, send_playlist
    search_result = search_media_content(query=genre_data["query"], media_type="audio", count=5, chat_id=str(callback.message.chat.id))
    if search_result.get("text"):
        lines.append(f"\n🔮 *Дополнительно:*")
        await callback.message.answer("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)
        await callback.message.answer(f"_{search_result['text']}_", parse_mode="Markdown")
        await send_playlist(callback.bot, callback.message.chat.id, search_result.get("tracks", []), chat_id_str=str(callback.message.chat.id))
    else:
        lines.append("\n_Нажми на ссылку, чтобы открыть трек_")
        await callback.message.answer("\n".join(lines), parse_mode="Markdown", disable_web_page_preview=True)


@router.callback_query(lambda c: c.data == "mc_back")
async def on_mc_back(callback: types.CallbackQuery):
    await callback.answer()
    url = _massage_url()
    text = (
        "🖐 *Мастерская Массажа*\n\n"
        "AI Prophet поможет расслабить тело.\n"
        "Мы — супружеская команда профессиональных мастеров массажа.\n"
        "Классика, антицеллюлитный, спортивный, стоун-терапия и другие техники.\n\n"
        "👇 Открой салон и выбери услугу"
    )
    inline_kb = [
        [InlineKeyboardButton(text="🖐 Открыть салон", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton(text="🧑‍⚕️ AI-консультация", callback_data="mc_start")],
        [InlineKeyboardButton(text="🎵 Музыка для массажа", callback_data="massage_music")],
    ]
    if GEM_BOT_URL:
        inline_kb.append([InlineKeyboardButton(text="🤖 GEM-бот помощник", url=GEM_BOT_URL)])
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_kb))


# === AI-КОНСУЛЬТАЦИЯ (АНКЕТИРОВАНИЕ) ===
def _get_user_data(chat_id) -> dict:
    settings = _load_settings()
    return settings.get(str(chat_id), {})


def _set_user_data(chat_id, key, value):
    settings = _load_settings()
    chat_str = str(chat_id)
    if chat_str not in settings:
        settings[chat_str] = {}
    settings[chat_str][key] = value
    _save_settings(settings)


def _get_questionnaire(chat_id) -> MassageQuestionnaire:
    data = _get_user_data(chat_id)
    q_data = data.get("massage_questionnaire", {})
    return MassageQuestionnaire.from_dict(q_data)


def _save_questionnaire(chat_id, questionnaire: MassageQuestionnaire):
    _set_user_data(chat_id, "massage_questionnaire", questionnaire.to_dict())


def _cleanup_massage_temp(chat_id):
    """Удаление временных файлов массажной консультации."""
    patterns = [
        f"massage_photo_{chat_id}_*", f"massage_video_{chat_id}_*",
        f"massage_doc_{chat_id}_*", f"frame_*",
    ]
    for pat in patterns:
        for f in glob.glob(os.path.join(TEMP_DIR, pat)):
            try:
                os.remove(f)
            except Exception:
                pass


@router.callback_query(lambda c: c.data == "mc_start")
async def on_mc_start(callback: types.CallbackQuery):
    await callback.answer()
    chat_id = callback.message.chat.id
    _cleanup_massage_temp(chat_id)
    _set_user_data(chat_id, "massage_step", "questionnaire")
    _set_user_data(chat_id, "massage_q_index", 0)
    _set_user_data(chat_id, "massage_photos", [])
    _set_user_data(chat_id, "massage_videos", [])

    q = MassageQuestionnaire()
    _save_questionnaire(chat_id, q)

    await callback.message.answer(
        "🧑‍⚕️ *AI-консультация массажного салона*\n\n"
        "Я задам несколько вопросов, чтобы подобрать idealьный массаж для тебя.\n"
        "Также ты сможешь загрузить фото/видео для визуальной диагностики.\n\n"
        "_Отвечай на вопросы, или нажми /stop в любой момент._\n"
        "👇 *Начнём!*",
        parse_mode="Markdown"
    )
    await _ask_question(chat_id, callback.message)


@router.message(Command("stop"))
async def on_mc_stop(message: types.Message):
    chat_id = message.chat.id
    data = _get_user_data(chat_id)
    if data.get("massage_step") in ("questionnaire", "media", "done"):
        _cleanup_massage_temp(chat_id)
        _set_user_data(chat_id, "massage_step", None)
        _set_user_data(chat_id, "massage_waiting_input", None)
        for key in list(data.keys()):
            if key.startswith("massage_"):
                _set_user_data(chat_id, key, None)
        await message.answer(
            "🛑 *Консультация отменена.*\n\n"
            "Можешь начать заново: /massage",
            parse_mode="Markdown"
        )


async def _ask_question(chat_id, message: types.Message):
    data = _get_user_data(chat_id)
    step_idx = data.get("massage_q_index", 0)

    if step_idx >= len(QUESTIONNAIRE_STEPS):
        await _finish_questionnaire(chat_id, message)
        return

    step = QUESTIONNAIRE_STEPS[step_idx]

    if step["type"] == "choice":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=opt, callback_data=f"mc_q_{step['key']}:{opt}")] for opt in step["options"]
        ])
        await message.answer(f"*Вопрос {step_idx + 1}/{len(QUESTIONNAIRE_STEPS)}*\n\n{step['question']}", parse_mode="Markdown", reply_markup=kb)

    elif step["type"] == "multi_choice":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"☐ {opt}", callback_data=f"mc_q_toggle:{opt}")] for opt in step["options"]
        ] + [
            [InlineKeyboardButton(text="✅ Готово", callback_data="mc_q_done")],
            [InlineKeyboardButton(text="⏭ Нет заболеваний", callback_data="mc_q_skip")]
        ])
        await message.answer(f"*Вопрос {step_idx + 1}/{len(QUESTIONNAIRE_STEPS)}*\n\n{step['question']}", parse_mode="Markdown", reply_markup=kb)

    else:
        _set_user_data(chat_id, "massage_waiting_input", step["key"])
        await message.answer(f"*Вопрос {step_idx + 1}/{len(QUESTIONNAIRE_STEPS)}*\n\n{step['question']}\n\n_Просто напиши ответ_", parse_mode="Markdown")


@router.callback_query(lambda c: c.data and c.data.startswith("mc_q_"))
async def on_mc_q_callback(callback: types.CallbackQuery):
    await callback.answer()
    data = callback.data
    chat_id = callback.message.chat.id
    q = _get_questionnaire(chat_id)

    if data == "mc_q_skip":
        _set_user_data(chat_id, "massage_q_index", _get_user_data(chat_id).get("massage_q_index", 0) + 1)
        await _ask_question(chat_id, callback.message)
        return

    if data == "mc_q_done":
        _set_user_data(chat_id, "massage_q_index", _get_user_data(chat_id).get("massage_q_index", 0) + 1)
        await _ask_question(chat_id, callback.message)
        return

    if data.startswith("mc_q_toggle:"):
        opt = data.replace("mc_q_toggle:", "")
        diseases = q.chronic_diseases.copy()
        if opt in diseases:
            diseases.remove(opt)
        else:
            diseases.append(opt)
        q.chronic_diseases = diseases
        _save_questionnaire(chat_id, q)

        step_idx = _get_user_data(chat_id).get("massage_q_index", 0)
        step = QUESTIONNAIRE_STEPS[step_idx]
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{'✅' if opt in diseases else '☐'} {opt}", callback_data=f"mc_q_toggle:{opt}")] for opt in step["options"]
        ] + [
            [InlineKeyboardButton(text="✅ Готово", callback_data="mc_q_done")],
            [InlineKeyboardButton(text="⏭ Нет заболеваний", callback_data="mc_q_skip")]
        ])
        await callback.message.edit_reply_markup(reply_markup=kb)
        return

    if ":" in data:
        _, value = data.split(":", 1)
        key = data.replace(f"mc_q_", "").split(":")[0]
        actual_key = None
        for s in QUESTIONNAIRE_STEPS:
            if s["key"] == key:
                actual_key = key
                break
        if not actual_key:
            for s in QUESTIONNAIRE_STEPS:
                if s["key"].startswith(key):
                    actual_key = s["key"]
                    break
        if actual_key:
            setattr(q, actual_key, value)
            _save_questionnaire(chat_id, q)

    _set_user_data(chat_id, "massage_q_index", _get_user_data(chat_id).get("massage_q_index", 0) + 1)
    await _ask_question(chat_id, callback.message)


@router.message(InQuestionnaireFilter())
async def on_mc_text_input(message: types.Message):
    chat_id = message.chat.id
    data = _get_user_data(chat_id)
    waiting_key = data.get("massage_waiting_input")

    text = message.text.strip()

    # Режим создания специалиста
    if data.get("massage_step") == "create_specialist":
        from handlers.messages import _create_and_show_specialist
        _set_user_data(chat_id, "massage_step", None)
        await _create_and_show_specialist(message, chat_id, text)
        return

    q = _get_questionnaire(chat_id)

    if waiting_key == "contraindications" and text.lower() != "/skip":
        lines = text.split("\n")
        for line in lines:
            lower = line.lower()
            if "беремен" in lower: q.is_pregnant = True
            if "температур" in lower or "воспален" in lower: q.has_fever = True
            if "операц" in lower: q.recent_surgery = line
            if "аллерг" in lower: q.has_allergies = True; q.allergies_description = line
        q.additional_info = text
    elif waiting_key == "diseases" and text.lower() != "/skip":
        for d in ["гипертония", "диабет", "сердечно", "варикоз", "тромбоз", "онколог", "кожн"]:
            if d in text.lower() and d not in q.chronic_diseases:
                q.chronic_diseases.append(d)
    elif waiting_key == "lifestyle":
        q.work_type = text
        q.physical_activity = text
    elif waiting_key == "additional":
        q.additional_info = text
    elif waiting_key == "medications":
        q.medications = text
    elif waiting_key == "complaints":
        q.complaints = text
    elif waiting_key == "pain_location":
        q.pain_location = text
    elif waiting_key == "full_name":
        q.full_name = text
    elif waiting_key == "age":
        try:
            q.age = int(text)
        except ValueError:
            await message.answer("Пожалуйста, введите число (ваш возраст)")
            return

    _save_questionnaire(chat_id, q)
    _set_user_data(chat_id, "massage_waiting_input", None)
    _set_user_data(chat_id, "massage_q_index", data.get("massage_q_index", 0) + 1)
    await _ask_question(chat_id, message)


async def _finish_questionnaire(chat_id, message: types.Message):
    q = _get_questionnaire(chat_id)
    _set_user_data(chat_id, "massage_step", "media")

    await message.answer(
        "✅ *Анкета заполнена!*\n\n"
        "Теперь ты можешь загрузить:\n"
        "📸 *Фото спины/осанки* — для визуальной диагностики\n"
        "🎥 *Видео* — для анализа движений (по желанию)\n"
        "📄 *Анализы/документы* — если есть\n\n"
        "_Просто отправь мне фото или видео._\n"
        "Когда закончишь — нажми кнопку.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧑‍⚕️ Запустить анализ", callback_data="mc_analyze")],
            [InlineKeyboardButton(text="⏭ Пропустить загрузку", callback_data="mc_analyze")],
        ])
    )


@router.message(F.photo)
async def on_mc_photo(message: types.Message):
    chat_id = message.chat.id
    data = _get_user_data(chat_id)
    if data.get("massage_step") not in ("media", "questionnaire"):
        return

    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    ext = os.path.splitext(file.file_path or ".jpg")[1] or ".jpg"
    dest = os.path.join(TEMP_DIR, f"massage_photo_{chat_id}_{photo.file_id[:8]}{ext}")
    await message.bot.download_file(file.file_path, dest)

    photos = data.get("massage_photos", [])
    photos.append(dest)
    _set_user_data(chat_id, "massage_photos", photos)

    count = len(photos)
    await message.answer(f"✅ Фото #{count} сохранено. Можешь загрузить ещё или нажми «Запустить анализ».")


@router.message(F.video | F.document)
async def on_mc_video(message: types.Message):
    chat_id = message.chat.id
    data = _get_user_data(chat_id)
    if data.get("massage_step") not in ("media", "questionnaire"):
        return

    if message.video:
        file = await message.bot.get_file(message.video.file_id)
        ext = os.path.splitext(file.file_path or ".mp4")[1] or ".mp4"
        dest = os.path.join(TEMP_DIR, f"massage_video_{chat_id}_{message.video.file_id[:8]}{ext}")
    elif message.document:
        file = await message.bot.get_file(message.document.file_id)
        ext = os.path.splitext(file.file_path or ".pdf")[1] or ".pdf"
        dest = os.path.join(TEMP_DIR, f"massage_doc_{chat_id}_{message.document.file_id[:8]}{ext}")
    else:
        return

    await message.bot.download_file(file.file_path, dest)
    videos = data.get("massage_videos", [])
    videos.append(dest)
    _set_user_data(chat_id, "massage_videos", videos)

    count = len(videos)
    await message.answer(f"✅ Файл #{count} сохранён. Можешь загрузить ещё или нажми «Запустить анализ».")


@router.callback_query(lambda c: c.data == "mc_analyze")
async def on_mc_analyze(callback: types.CallbackQuery):
    await callback.answer("🧑‍⚕️ Запускаю анализ...")
    chat_id = callback.message.chat.id
    msg = await callback.message.answer("⏳ *Запускаю команду специалистов...*\nЭто займёт 1–2 минуты.", parse_mode="Markdown")

    q = _get_questionnaire(chat_id)
    data = _get_user_data(chat_id)
    photos = data.get("massage_photos", [])
    videos = data.get("massage_videos", [])

    orchestrator = MassageConsultationOrchestrator()
    results = await orchestrator.run_consultation(
        questionnaire_text=q.to_text(),
        photo_paths=photos if photos else None,
        video_paths=videos if videos else None,
    )

    _set_user_data(chat_id, "massage_step", "done")
    _cleanup_massage_temp(chat_id)

    await msg.delete()

    formatted = format_consultation_results(results)
    await callback.message.answer(formatted, parse_mode="Markdown")

    await callback.message.answer(
        "💡 *Что дальше?*\n\n"
        "1. Запишись на сеанс через салон\n"
        "2. Создай плейлист для массажа 🎵\n"
        "3. Спроси у AI Prophet в общем чате\n\n"
        "Или начни новую консультацию: /massage",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🖐 Открыть салон", web_app=WebAppInfo(url=_massage_url()))],
            [InlineKeyboardButton(text="🎵 Музыка для сеанса", callback_data="massage_music")],
        ])
    )


# === ОБРАБОТКА ДАННЫХ ИЗ MINI APP ===
@router.message(F.web_app_data)
async def on_massage_webapp_data(message: types.Message):
    if not message.web_app_data:
        return
    try:
        data = json.loads(message.web_app_data.data)
        if data.get("type") != "massage_consult":
            return
    except (json.JSONDecodeError, KeyError):
        return

    chat_id = message.chat.id
    q = MassageQuestionnaire(
        full_name=data.get("name", ""),
        age=int(data.get("age", 0)) if data.get("age") else 0,
        gender=data.get("gender", ""),
        complaints=data.get("complaints", ""),
        pain_location=data.get("pain_location", ""),
        chronic_diseases=data.get("diseases", []),
        medications=data.get("medications", ""),
        additional_info=data.get("extra", ""),
    )
    for ci in data.get("contraindications", []):
        ci_lower = ci.lower()
        if "беремен" in ci_lower: q.is_pregnant = True
        if "температур" in ci_lower or "воспален" in ci_lower: q.has_fever = True

    _cleanup_massage_temp(chat_id)
    _save_questionnaire(chat_id, q)
    _set_user_data(chat_id, "massage_step", "media")
    _set_user_data(chat_id, "massage_photos", [])
    _set_user_data(chat_id, "massage_videos", [])

    await message.answer(
        "✅ *Анкета получена из Mini App!*\n\n"
        "Теперь ты можешь загрузить:\n"
        "📸 *Фото спины/осанки* — для визуальной диагностики\n"
        "🎥 *Видео* — для анализа движений (по желанию)\n\n"
        "_Когда закончишь — нажми кнопку._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧑‍⚕️ Запустить анализ", callback_data="mc_analyze")],
        ])
    )


# === СТАРЫЕ КОЛЛБЭКИ ДЛЯ СОВМЕСТИМОСТИ ===
@router.callback_query(lambda c: c.data and c.data.startswith("pl_"))
async def on_playlist_genre(callback: types.CallbackQuery):
    genre_map = {
        "pl_ambient": "ambient spa relaxing music",
        "pl_classic": "classical piano relaxing massage",
        "pl_nature": "nature sounds water birds meditation",
        "pl_jazz": "jazz lounge chill relaxation",
        "pl_spa": "spa relaxation massage music",
        "pl_thai": "thai massage traditional music",
    }
    query = genre_map.get(callback.data, "relaxing massage music")
    await callback.answer(f"🔮 Ищу: {query}")
    from core.tools import search_media_content, send_playlist
    result = search_media_content(query=query, media_type="audio", count=5, chat_id=str(callback.message.chat.id))
    if result.get("text"):
        await callback.message.answer(f"🔮 *Атмосфера:*\n_{result['text']}_", parse_mode="Markdown")
    await send_playlist(callback.bot, callback.message.chat.id, result.get("tracks", []), chat_id_str=str(callback.message.chat.id))
