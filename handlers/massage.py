import os
import json
import glob
import logging
from aiogram import types, Router, F
from aiogram.filters import Command, BaseFilter
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import get_base_url, GEM_BOT_URL, TEMP_DIR, DATA_DIR

from core.agents import (
    MassageConsultationOrchestrator, format_consultation_results,
    get_massage_music, MASSAGE_MUSIC_GENRES,
    get_agent_def, AgentBase,
)
import asyncio
from core.agents.agent_factory import SpecialistFactory, get_specialists, remove_specialist
from core.questionnaire import MassageQuestionnaire, QUESTIONNAIRE_STEPS, QUESTIONNAIRE_STEPS_OPTIONAL, load_steps

logger = logging.getLogger(__name__)
router = Router()


class InQuestionnaireFilter(BaseFilter):
    def __init__(self):
        import config
        self.settings_file = os.path.join(config.DATA_DIR, "user_settings.json")

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

SETTINGS_FILE = os.path.join(DATA_DIR, "user_settings.json")


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
    from handlers.messages import user_settings, save_settings as msg_save
    chat_str = str(callback.message.chat.id)
    user_settings.setdefault(chat_str, {})["specialist_chat"] = name
    msg_save(user_settings)
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
    is_optional = data.get("massage_optional_mode", False)
    steps = QUESTIONNAIRE_STEPS_OPTIONAL if is_optional else QUESTIONNAIRE_STEPS
    total = len(steps)

    if step_idx >= total:
        if is_optional:
            await _finish_questionnaire(chat_id, message)
        else:
            await _ask_optional_trigger(chat_id, message)
        return

    step = steps[step_idx]

    if step["type"] == "choice":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=opt, callback_data=f"mc_q_{step['key']}:{opt}")] for opt in step["options"]
        ])
        await message.answer(f"*Вопрос {step_idx + 1}/{total}*\n\n{step['question']}", parse_mode="Markdown", reply_markup=kb)

    elif step["type"] == "multi_choice":
        skip_label = "⏭ Нет заболеваний" if step["key"] in ("chronic_diseases", "contraindications_absolute") else "⏭ Ничего из списка"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"☐ {opt}", callback_data=f"mc_q_toggle:{opt}")] for opt in step["options"]
        ] + [
            [InlineKeyboardButton(text="✅ Готово", callback_data="mc_q_done")],
            [InlineKeyboardButton(text=skip_label, callback_data="mc_q_skip")]
        ])
        await message.answer(f"*Вопрос {step_idx + 1}/{total}*\n\n{step['question']}", parse_mode="Markdown", reply_markup=kb)

    elif step["type"] == "consent":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"mc_q_{step['key']}:yes")],
            [InlineKeyboardButton(text="❌ Отказываюсь", callback_data=f"mc_q_{step['key']}:no")]
        ])
        await message.answer(f"*Вопрос {step_idx + 1}/{total}*\n\n{step['question']}", parse_mode="Markdown", reply_markup=kb)

    elif step["type"] == "number":
        _set_user_data(chat_id, "massage_waiting_input", step["key"])
        await message.answer(f"*Вопрос {step_idx + 1}/{total}*\n\n{step['question']}\n\n_Введи число_", parse_mode="Markdown")

    else:
        _set_user_data(chat_id, "massage_waiting_input", step["key"])
        await message.answer(f"*Вопрос {step_idx + 1}/{total}*\n\n{step['question']}\n\n_Просто напиши ответ_", parse_mode="Markdown")


async def _ask_optional_trigger(chat_id, message: types.Message):
    if not QUESTIONNAIRE_STEPS_OPTIONAL:
        await _finish_questionnaire(chat_id, message)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Да, добавить детали", callback_data="mc_optional_yes")],
        [InlineKeyboardButton(text="⏭ Нет, всё указал", callback_data="mc_optional_no")]
    ])
    await message.answer(
        "✅ *Основная анкета заполнена!*\n\n"
        "Хочешь добавить дополнительную информацию для более точной диагностики?\n"
        "_(сон, стресс, активность, травмы, состояние кожи и т.д.)_",
        parse_mode="Markdown",
        reply_markup=kb
    )


@router.callback_query(lambda c: c.data in ("mc_optional_yes", "mc_optional_no"))
async def on_mc_optional_choice(callback: types.CallbackQuery):
    await callback.answer()
    chat_id = callback.message.chat.id
    if callback.data == "mc_optional_yes":
        _set_user_data(chat_id, "massage_optional_mode", True)
        _set_user_data(chat_id, "massage_q_index", 0)
        await _ask_question(chat_id, callback.message)
    else:
        await _finish_questionnaire(chat_id, callback.message)


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
        step_idx = _get_user_data(chat_id).get("massage_q_index", 0)
        is_optional = _get_user_data(chat_id).get("massage_optional_mode", False)
        steps = QUESTIONNAIRE_STEPS_OPTIONAL if is_optional else QUESTIONNAIRE_STEPS
        step = steps[step_idx]
        target_key = step["key"]

        if target_key == "chronic_diseases":
            items = list(q.chronic_diseases)
            if opt in items: items.remove(opt)
            else: items.append(opt)
            q.chronic_diseases = items
        elif target_key == "contraindications_absolute":
            items = list(q.contraindications_absolute)
            if opt in items: items.remove(opt)
            else: items.append(opt)
            q.contraindications_absolute = items

        _save_questionnaire(chat_id, q)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{'✅' if c in items else '☐'} {c}", callback_data=f"mc_q_toggle:{c}")] for c in step["options"]
        ] + [
            [InlineKeyboardButton(text="✅ Готово", callback_data="mc_q_done")],
            [InlineKeyboardButton(text="⏭ Ничего из списка", callback_data="mc_q_skip")]
        ])
        await callback.message.edit_reply_markup(reply_markup=kb)
        return

    if ":" in data:
        _, value = data.split(":", 1)
        key = data.replace(f"mc_q_", "").split(":")[0]
        actual_key = None
        all_steps = QUESTIONNAIRE_STEPS + QUESTIONNAIRE_STEPS_OPTIONAL
        for s in all_steps:
            if s["key"] == key:
                actual_key = key
                break
        if not actual_key:
            for s in all_steps:
                if s["key"].startswith(key):
                    actual_key = s["key"]
                    break
        if actual_key:
            if actual_key == "informed_consent":
                setattr(q, actual_key, value == "yes")
            elif actual_key in ("is_pregnant", "has_fever", "has_inflammation"):
                setattr(q, actual_key, value.lower() in ("да", "yes", "true"))
            elif actual_key == "gender":
                setattr(q, actual_key, value)
            else:
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
    is_optional = data.get("massage_optional_mode", False)
    steps = QUESTIONNAIRE_STEPS_OPTIONAL if is_optional else QUESTIONNAIRE_STEPS

    step = None
    for s in steps:
        if s["key"] == waiting_key:
            step = s
            break

    if step is None:
        return

    if step["type"] == "number":
        try:
            setattr(q, step["key"], int(text))
        except ValueError:
            try:
                setattr(q, step["key"], float(text))
            except ValueError:
                await message.answer("Пожалуйста, введите число")
                return
    elif step["type"] == "text":
        setattr(q, step["key"], text)

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

    try:
        orchestrator = MassageConsultationOrchestrator()
        results = await orchestrator.run_consultation(
            questionnaire_text=q.to_text(),
            photo_paths=photos if photos else None,
            video_paths=videos if videos else None,
        )
    except Exception as e:
        logger.error(f"Consultation failed: {e}", exc_info=True)
        _set_user_data(chat_id, "massage_step", "done")
        _cleanup_massage_temp(chat_id)
        await msg.edit_text(
            "😔 *Система диагностики временно недоступна.*\n\n"
            "Попробуй позже или напиши свой вопрос текстом — я отвечу сам.\n\n"
            "Анкета сохранена, мы её не потеряли.",
            parse_mode="Markdown"
        )
        return

    _set_user_data(chat_id, "massage_step", "done")
    _cleanup_massage_temp(chat_id)

    await msg.delete()

    formatted = format_consultation_results(results)
    await callback.message.answer(formatted, parse_mode="Markdown")

    final_text = results.get("final_expert", {}).get("content", "")

    # Парсим рекомендованных врачей из финального эксперта
    referred_doctors = _parse_doctor_referrals(final_text)
    is_approved = "не допущен" not in final_text.lower() and "требуется консультация врача" not in final_text.lower()

    if is_approved:
        next_text = (
            "💡 *Что дальше?*\n\n"
            "1. 📅 Запишись на сеанс — открой салон ниже\n"
            "2. 🎵 Создай плейлист для массажа\n"
            "3. 💬 Спроси у AI Prophet в общем чате\n\n"
            "Или начни новую консультацию: /massage"
        )
        buttons = [
            [InlineKeyboardButton(text="🖐 Открыть салон", web_app=WebAppInfo(url=_massage_url()))],
            [InlineKeyboardButton(text="🎵 Музыка для сеанса", callback_data="massage_music")],
        ]
    else:
        # Авто-создание ИИ-специалистов из рекомендаций
        created = []
        for role in referred_doctors:
            try:
                sp = await asyncio.to_thread(SpecialistFactory.create, chat_id, role)
                if sp:
                    created.append(sp.name)
            except Exception as e:
                logger.warning(f"Failed to create specialist for '{role}': {e}")

        _set_user_data(chat_id, "massage_referral_specialists", created)
        _set_user_data(chat_id, "massage_questionnaire_text", q.to_text())

        next_text = (
            "💡 *Что дальше?*\n\n"
            "1. 🩺 Проконсультируйся с созданными ИИ-специалистами\n"
            "2. ✅ После консультаций нажми «Запросить итог»\n"
            "3. 🔄 Пройди консультацию заново: /massage\n"
        )
        buttons = [
            [InlineKeyboardButton(text="🧑‍⚕️ Мои специалисты", callback_data="mc_specialist")],
            [InlineKeyboardButton(text="✅ Запросить итог", callback_data="mc_final_review")],
            [InlineKeyboardButton(text="🎵 Музыка для сеанса", callback_data="massage_music")],
        ]

        if created:
            next_text = (
                f"🧑‍⚕️ *Рекомендованные консультации*\n\n"
                f"Финальный эксперт направил к: {', '.join(referred_doctors)}.\n\n"
                f"✨ Я создал ИИ-специалистов: {', '.join(created)}.\n\n"
                "Напиши каждому свой вопрос в чате — они ответят на основе твоих данных.\n"
                "После консультаций нажми «Запросить итог» для окончательного решения."
            )

    await callback.message.answer(
        next_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


def _parse_doctor_referrals(final_text: str) -> list:
    """Извлечь список врачей из финального заключения."""
    doctors = []
    for line in final_text.split("\n"):
        lower = line.strip().lower()
        if "к какому врачу" not in lower and "обратиться" not in lower:
            continue
        # Убираем нумерованный префикс и текст до ":"
        text = line.split(":", 1)[-1].strip() if ":" in line else line
        # После "обратиться" берём остаток (регистронезависимо)
        idx = text.lower().find("обратиться")
        if idx >= 0:
            text = text[idx + len("обратиться"):].strip()
        # Разбиваем по ","
        for part in text.split(","):
            part = part.strip().strip(".")
            # Берём текст до "—" если есть
            name = part.split("—")[0].strip() if "—" in part else part
            # Убираем предлоги "к ", "ко "
            for prefix in ["к ", "ко "]:
                if name.lower().startswith(prefix):
                    name = name[len(prefix):].strip()
                    break
            # Пропускаем остаточные стоп-слова
            if not name or name.lower() in ("что", "для", "на", "с", "и", "в", "о"):
                continue
            if name and len(name) > 2 and name not in doctors:
                doctors.append(name)
    return doctors


@router.callback_query(lambda c: c.data == "mc_final_review")
async def on_mc_final_review(callback: types.CallbackQuery):
    """Повторный запуск финального эксперта после консультаций со специалистами."""
    await callback.answer("⏳ Собираю результаты...")
    chat_id = callback.message.chat.id
    msg = await callback.message.answer("⏳ *Анализирую консультации специалистов...*", parse_mode="Markdown")

    q_text = _get_user_data(chat_id).get("massage_questionnaire_text", "")
    specialist_names = _get_user_data(chat_id).get("massage_referral_specialists", [])

    # Собираем историю консультаций
    convs_file = os.path.join(TEMP_DIR, "specialist_convs.json")
    specialist_context = ""
    if os.path.exists(convs_file):
        try:
            with open(convs_file, "r", encoding="utf-8") as f:
                all_convs = json.load(f)
            chat_str = str(chat_id)
            for sp_name in specialist_names:
                key = f"{chat_str}:{sp_name}"
                conv = all_convs.get(key, [])
                if conv:
                    lines = [f"\n=== Консультация с {sp_name} ==="]
                    for turn in conv[-10:]:
                        role = "Клиент" if turn.get("role") == "user" else sp_name
                        lines.append(f"{role}: {turn.get('content', '')[:300]}")
                    specialist_context += "\n".join(lines) + "\n"
        except Exception as e:
            logger.warning(f"Failed to load specialist convs: {e}")

    try:
        from core.agents.agent_base import AgentBase
        final_def = get_agent_def("final_expert")
        qa_def = get_agent_def("questionnaire_analyst")
        expert = AgentBase("final_expert", "Финальный Эксперт", final_def.get("role", ""), "text")

        context = f"=== ИСХОДНАЯ АНКЕТА ===\n{q_text}\n"
        if specialist_context:
            context += f"\n=== РЕЗУЛЬТАТЫ КОНСУЛЬТАЦИЙ СО СПЕЦИАЛИСТАМИ ==={specialist_context}\n"
        context += "\nНа основе всех данных, включая консультации специалистов, дай ОКОНЧАТЕЛЬНОЕ ЗАКЛЮЧЕНИЕ."

        result = await asyncio.to_thread(expert.process_text, context)
        content = result.get("content", "") if isinstance(result, dict) else str(result)

        await msg.delete()

        is_approved_final = "не допущен" not in content.lower() and "требуется консультация врача" not in content.lower()

        lines = ["✅ *ИТОГ ПОСЛЕ КОНСУЛЬТАЦИЙ СПЕЦИАЛИСТОВ*\n", content]
        await callback.message.answer("\n".join(lines), parse_mode="Markdown")

        if is_approved_final:
            await callback.message.answer(
                "💡 *Теперь ты допущен к массажу!*\n\nЗапишись на сеанс через салон.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🖐 Открыть салон", web_app=WebAppInfo(url=_massage_url()))],
                    [InlineKeyboardButton(text="🎵 Музыка для сеанса", callback_data="massage_music")],
                ])
            )
        else:
            await callback.message.answer(
                "💡 *К сожалению, противопоказания сохраняются.*\n\n"
                "Рекомендую обратиться к профильному врачу очно.\n"
                "Можешь начать новую консультацию: /massage",
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Final review failed: {e}", exc_info=True)
        await msg.edit_text("😔 Не удалось получить итог. Попробуй позже или /massage заново.")


# === ОБРАБОТКА ДАННЫХ ИЗ MINI APP ===
async def _handle_prophet_action(message: types.Message, action: str):
    """Обработка действий из Prophet Mini App (plain string actions)."""
    chat_id = str(message.chat.id)
    if action == "daily_prediction":
        from handlers.messages import conduct_ai_ritual
        status_msg = await message.answer("🧘 *Медитирую над твоими словами...*")
        await conduct_ai_ritual(message, message.bot, "🔮 Предсказание", status_msg)
    elif action == "vision_info":
        from handlers.messages import conduct_ai_ritual
        status_msg = await message.answer("🧘 *Медитирую над твоими словами...*")
        await conduct_ai_ritual(message, message.bot, "🖼 Видение", status_msg)
    elif action == "playlist_wizard":
        from handlers.messages import user_settings, save_settings
        user_settings.setdefault(chat_id, {})['playlist_step'] = 'artist'
        user_settings[chat_id]['playlist_draft'] = {'items': []}
        save_settings(user_settings)
        await message.answer(
            "🎵 *Мастер Плейлистов*\n\nНапиши имя артиста или название трека для поиска:",
            parse_mode="Markdown"
        )
    elif action == "import_json":
        await message.answer(
            "📥 *Импорт Плейлистов*\n\nПросто скинь мне JSON-файл с плейлистом или бэкапом библиотеки.",
            parse_mode="Markdown"
        )
    elif action == "library":
        from handlers.messages import handle_pl_library
        await handle_pl_library(
            types.CallbackQuery(
                id="0", from_user=message.from_user,
                chat_instance="0", message=message, data="pl_library"
            )
        )


@router.message(F.web_app_data)
async def on_massage_webapp_data(message: types.Message):
    if not message.web_app_data:
        return
    raw = message.web_app_data.data
    # Prophet Mini App: plain string action
    if not raw.startswith("{"):
        await _handle_prophet_action(message, raw)
        return
    try:
        data = json.loads(raw)
        if data.get("type") != "massage_consult":
            return
    except (json.JSONDecodeError, KeyError):
        return

    chat_id = message.chat.id
    q = MassageQuestionnaire.from_dict({k: v for k, v in data.items() if k != "type"})
    if data.get("age"):
        try: q.age = int(data["age"])
        except ValueError: pass
    if data.get("height"):
        try: q.height = int(data["height"])
        except ValueError: pass
    if data.get("weight"):
        try: q.weight = int(data["weight"])
        except ValueError: pass

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
