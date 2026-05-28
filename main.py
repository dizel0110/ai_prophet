# -*- coding: utf-8 -*-
# Copyright (c) 2026 dizel0110
# Project: AI Prophet (The bridge between ancient wisdom and future intelligence)
# Licensed under the Apache License, Version 2.0
# -----------------------------------------------------------------------------

import os
import json
import time
import asyncio
import logging
import multiprocessing
import uvicorn
from datetime import datetime
from pathlib import Path
from aiogram import Bot, Dispatcher
import uuid
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from config import TOKEN, PORT, PLATFORM
from core.network import apply_dns_patch
from handlers import messages, vip, limits, massage

# Настройка логов
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"bot_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s:%(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
logging.getLogger("google.genai").setLevel(logging.WARNING)
import time
logger = logging.getLogger(__name__)

# Проверка: работаем на HF Spaces?
IS_HF_SPACE = os.getenv("SPACE_ID") is not None

# FastAPI приложение
app = FastAPI()

# Раздача статики (Mini App)
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Dispatcher создаётся ОДИН раз на весь lifecycle
dp = Dispatcher()
dp.include_router(vip.router)
dp.include_router(limits.router)
dp.include_router(massage.router)
dp.include_router(messages.router)

# Webhook routes (только на HF Spaces, после dp — чтобы не красть роутеры)
if IS_HF_SPACE:
    try:
        from webhook_only import setup_webhook_routes
        setup_webhook_routes(app)
    except RuntimeError:
        logger.info("📡 Webhook routes пропущены (роутеры уже в dp)")

@app.get("/")
async def root():
    mode_map = {"hf": "HF Spaces", "render": "Render.com", "local": "Polling (Local)"}
    mode = mode_map.get(PLATFORM, PLATFORM)
    return {"status": f"AI Prophet ({mode})", "platform": PLATFORM}

@app.post("/api/specialist/chat")
async def api_specialist_chat(req: dict):
    from core.agents.agent_factory import SpecialistFactory, get_specialist, get_specialists
    chat_id = req.get("chat_id")
    name = req.get("name", "")
    message_text = req.get("message", "")
    if not chat_id or not name or not message_text:
        return {"ok": False, "error": "Missing chat_id, name, or message"}
    specialist = get_specialist(chat_id, name)
    if not specialist:
        return {"ok": False, "error": f"Specialist '{name}' not found"}
    result = SpecialistFactory.chat(chat_id, specialist, message_text)
    if result.is_success():
        return {"ok": True, "response": result.content, "name": result.agent_name}
    return {"ok": False, "error": "AI engine failed"}

@app.post("/api/specialist/list")
async def api_specialist_list(req: dict):
    from core.agents.agent_factory import get_specialists
    chat_id = req.get("chat_id")
    if not chat_id:
        return {"ok": False, "error": "Missing chat_id"}
    from core.agents.agent_factory import BUILT_IN_AGENTS
    sps = get_specialists(chat_id)
    built_names = {b["name"].lower() for b in BUILT_IN_AGENTS}
    result = []
    for s in sps:
        is_built = s.name.lower() in built_names
        item = {
            "name": s.name,
            "role": s.role_description,
            "skills": s.skills,
            "built_in": is_built,
            "badge": next((b["badge"] for b in BUILT_IN_AGENTS if b["name"].lower() == s.name.lower()), "🛠️"),
        }
        if not is_built and hasattr(s, "communication_schema") and s.communication_schema:
            item["communication_schema"] = s.communication_schema
        result.append(item)
    return {"ok": True, "specialists": result}

@app.post("/api/specialist/create")
async def api_specialist_create(req: dict):
    from core.agents.agent_factory import SpecialistFactory, get_specialist
    chat_id = req.get("chat_id")
    role = req.get("role", "")
    name = req.get("name", "")
    if not chat_id:
        return {"ok": False, "error": "Missing chat_id"}
    if not role and not name:
        return {"ok": False, "error": "Provide role or name"}
    sp = SpecialistFactory.create(chat_id=chat_id, role_description=role, name=name or None)
    if sp:
        result = {"ok": True, "name": sp.name, "role": sp.role_description, "skills": sp.skills}
        if hasattr(sp, "communication_schema") and sp.communication_schema:
            result["communication_schema"] = sp.communication_schema
        return result
    return {"ok": False, "error": "Failed to create specialist"}

@app.post("/api/specialist/delete")
async def api_specialist_delete(req: dict):
    from core.agents.agent_factory import remove_specialist, BUILT_IN_AGENTS
    chat_id = req.get("chat_id")
    name = req.get("name", "")
    if not chat_id or not name:
        return {"ok": False, "error": "Missing chat_id or name"}
    if name.lower() in {b["name"].lower() for b in BUILT_IN_AGENTS}:
        return {"ok": False, "error": "Нельзя удалить встроенного специалиста"}
    return {"ok": remove_specialist(chat_id, name)}


@app.post("/api/specialist/edit")
async def api_specialist_edit(req: dict):
    from core.agents.agent_factory import update_specialist
    chat_id = req.get("chat_id")
    old_name = req.get("old_name", "")
    new_name = req.get("new_name", "")
    new_role = req.get("new_role", "")
    if not chat_id or not old_name:
        return {"ok": False, "error": "Missing chat_id or old_name"}
    if not new_name and not new_role:
        return {"ok": False, "error": "Provide new_name or new_role"}
    ok = update_specialist(chat_id, old_name, new_name, new_role)
    return {"ok": ok}


@app.post("/api/specialist/submit")
async def api_specialist_submit(req: dict):
    from core.agents.agent_factory import SpecialistFactory, get_specialist
    chat_id = req.get("chat_id")
    name = req.get("name", "")
    structured_data = req.get("structured_data", {})
    user_message = req.get("message", "")
    if not chat_id or not name:
        return {"ok": False, "error": "Missing chat_id or name"}
    specialist = get_specialist(chat_id, name)
    if not specialist:
        return {"ok": False, "error": f"Specialist '{name}' not found"}
    # Build context from structured data
    context_parts = []
    for group in ("required", "optional"):
        for field in structured_data.get(group, []):
            label = field.get("label", field.get("key", ""))
            value = field.get("value", "")
            if value:
                context_parts.append(f"{label}: {value}")
    context_str = "\n".join(context_parts) if context_parts else ""
    full_message = user_message
    if context_str:
        full_message = f"[Анкета клиента]\n{context_str}\n\n[Сообщение]\n{user_message}" if user_message else f"[Анкета клиента]\n{context_str}"
    result = SpecialistFactory.chat(chat_id, specialist, full_message)
    if result.is_success():
        return {"ok": True, "response": result.content, "name": result.agent_name}
    return {"ok": False, "error": "AI engine failed"}


# ──────────────────── Music Player API ────────────────────

MUSIC_SETTINGS_FILE = os.path.join("temp", "user_music.json")


def _load_music_settings() -> dict:
    if not os.path.exists(MUSIC_SETTINGS_FILE):
        return {}
    try:
        with open(MUSIC_SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_music_settings(data: dict):
    os.makedirs("temp", exist_ok=True)
    try:
        with open(MUSIC_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save music settings: {e}")


@app.post("/api/music/ai-search")
async def api_music_ai_search(req: dict):
    from core.music_player import ai_search_tracks, get_tracks_duration
    query = req.get("query", "").strip()
    if not query:
        return {"ok": False, "error": "Missing query"}
    tracks = ai_search_tracks(query)
    total_dur = get_tracks_duration(tracks)
    return {"ok": True, "tracks": tracks, "query": query, "total_duration": total_dur}


@app.post("/api/music/search")
async def api_music_search(req: dict):
    from core.music_player import search_tracks, get_tracks_duration
    query = req.get("query", "").strip()
    if not query:
        return {"ok": False, "error": "Missing query"}
    tracks = search_tracks(query)
    total_dur = get_tracks_duration(tracks)
    return {"ok": True, "tracks": tracks, "query": query, "total_duration": total_dur}


@app.get("/api/music/genres")
async def api_music_genres():
    from core.music_player import get_all_genres
    return {"ok": True, "genres": get_all_genres()}


@app.post("/api/music/tracks")
async def api_music_tracks(req: dict):
    from core.music_player import get_tracks
    chat_id = req.get("chat_id", 0)
    genre = req.get("genre", "")
    if not genre:
        return {"ok": False, "error": "Missing genre"}
    tracks = get_tracks(genre, chat_id)
    return {"ok": True, "tracks": tracks, "genre": genre}


@app.post("/api/music/save_playlist")
async def api_music_save_playlist(req: dict):
    chat_id = str(req.get("chat_id", ""))
    name = req.get("name", "Мой плейлист")
    tracks = req.get("tracks", [])
    if not chat_id or not tracks:
        return {"ok": False, "error": "Missing chat_id or tracks"}
    data = _load_music_settings()
    if chat_id not in data:
        data[chat_id] = {"playlists": []}
    playlist = {"name": name, "tracks": tracks, "created": time.time()}
    data[chat_id]["playlists"].append(playlist)
    _save_music_settings(data)
    return {"ok": True, "playlist": playlist}


@app.post("/api/music/playlists")
async def api_music_playlists(req: dict):
    chat_id = str(req.get("chat_id", ""))
    if not chat_id:
        return {"ok": False, "error": "Missing chat_id"}
    data = _load_music_settings()
    playlists = data.get(chat_id, {}).get("playlists", [])
    return {"ok": True, "playlists": playlists}


@app.post("/api/music/delete_playlist")
async def api_music_delete_playlist(req: dict):
    chat_id = str(req.get("chat_id", ""))
    index = req.get("index", -1)
    if not chat_id or index < 0:
        return {"ok": False, "error": "Missing chat_id or index"}
    data = _load_music_settings()
    playlists = data.get(chat_id, {}).get("playlists", [])
    if index < len(playlists):
        playlists.pop(index)
        _save_music_settings(data)
        return {"ok": True}
    return {"ok": False, "error": "Invalid index"}


@app.post("/api/music/import_playlists")
async def api_music_import_playlists(req: dict):
    chat_id = str(req.get("chat_id", ""))
    playlists = req.get("playlists", [])
    if not chat_id or not playlists:
        return {"ok": False, "error": "Missing chat_id or playlists"}
    data = _load_music_settings()
    if chat_id not in data:
        data[chat_id] = {}
    existing = data[chat_id].get("playlists", [])
    imported = 0
    for pl in playlists:
        name = pl.get("name", "Импорт")
        tracks = pl.get("tracks", [])
        if not tracks:
            continue
        existing.append({"name": name, "tracks": tracks})
        imported += 1
    data[chat_id]["playlists"] = existing
    _save_music_settings(data)
    return {"ok": True, "count": imported}


USER_AUDIO_DIR = os.path.join("user_audio")

@app.post("/api/music/upload")
async def api_music_upload(chat_id: str = Form(...), file: UploadFile = File(...)):
    if not chat_id or not file:
        return {"ok": False, "error": "Missing chat_id or file"}
    if not file.filename:
        return {"ok": False, "error": "Empty filename"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma", ".opus"):
        return {"ok": False, "error": "Unsupported format. Use mp3, wav, ogg, flac, m4a, aac, wma, opus"}
    user_dir = os.path.join(USER_AUDIO_DIR, chat_id)
    os.makedirs(user_dir, exist_ok=True)
    file_id = str(uuid.uuid4())[:8]
    safe_name = f"{file_id}{ext}"
    path = os.path.join(user_dir, safe_name)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    title = os.path.splitext(file.filename)[0]
    url = f"/api/music/user_audio/{chat_id}/{safe_name}"
    return {"ok": True, "track": {"title": title, "url": url, "source": "upload", "file_id": file_id}}


@app.get("/api/music/user_audio/{chat_id}/{filename}")
async def serve_user_audio(chat_id: str, filename: str):
    import re
    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", filename):
        return {"ok": False, "error": "Invalid filename"}
    path = os.path.join(USER_AUDIO_DIR, chat_id, filename)
    if not os.path.exists(path):
        return {"ok": False, "error": "File not found"}
    return FileResponse(path, media_type="audio/mpeg")


def start_web():
    uvicorn.run(app, host="0.0.0.0", port=PORT)

async def start_bot_polling():
    """Polling режим для локальной разработки"""
    apply_dns_patch()

    # Очистка временной папки при старте
    from config import TEMP_DIR
    import shutil
    if os.path.exists(TEMP_DIR):
        try:
            for item in os.listdir(TEMP_DIR):
                item_path = os.path.join(TEMP_DIR, item)
                if os.path.isfile(item_path): os.remove(item_path)
                elif os.path.isdir(item_path): shutil.rmtree(item_path)
            logger.info("🧹 Временная папка очищена")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось полностью очистить temp: {e}")
    else: os.makedirs(TEMP_DIR)

    from aiogram.types import BotCommand
    from config import HF_TOKEN, GEMINI_KEY

    telegram_api_url = os.getenv("TELEGRAM_API_URL")
    if telegram_api_url:
        from aiogram.client.session.aiohttp import AiohttpSession
        from aiogram.client.telegram import TelegramAPIServer
        server = TelegramAPIServer.from_base(telegram_api_url)
        session = AiohttpSession()
        session.api = server
        bot = Bot(token=TOKEN, session=session)
        logger.info(f"🔗 Кастомный Telegram API: {telegram_api_url}")
    elif IS_HF_SPACE:
        PROXY_URL = os.getenv("PROXY_URL")
        if PROXY_URL:
            from aiogram.client.session.aiohttp import AiohttpSession
            logger.info(f"🔗 HF Spaces: используем прокси {PROXY_URL}")
            session = AiohttpSession(proxy=PROXY_URL)
            bot = Bot(token=TOKEN, session=session)
        else:
            logger.error("❌ HF Spaces: установите PROXY_URL или TELEGRAM_API_URL")
            raise RuntimeError("PROXY_URL or TELEGRAM_API_URL required on HF Spaces")
    else:
        bot = Bot(token=TOKEN)

    # Регистрация команд для подсказок (autocomplete)
    commands = [
        BotCommand(command="start", description="Запустить Пророка и открыть меню"),
        BotCommand(command="help", description="Показать все возможности"),
        BotCommand(command="playlist", description="Собрать свой плейлист"),
        BotCommand(command="playlist_example", description="Примеры и обучение (Академия)"),
        BotCommand(command="massage", description="🖐 Массажный салон"),
        BotCommand(command="specialist", description="🧑‍⚕️ Создать специалиста-консультанта"),
        BotCommand(command="specialists", description="Список специалистов"),
        BotCommand(command="dismiss", description="Удалить специалиста"),
        BotCommand(command="settings", description="Выбрать мозг бота (Gemini/HF)"),
        BotCommand(command="dizel0110", description="Вход в VIP режим"),
        BotCommand(command="stop", description="Остановить текущие действия")
    ]
    await bot.set_my_commands(commands)

    if not HF_TOKEN: logger.warning("⚠️ HF_TOKEN is not set! Voice and WebSearch fallback will fail.")
    else: logger.info(f"✅ HF_TOKEN is loaded (prefix: {HF_TOKEN[:5]}...)")

    logger.info(f"🚀 AI Prophet Modular System Started at {datetime.now().strftime('%H:%M:%S')}")

    # На HF Spaces не удаляем webhook (блокируется исходящие)
    if not IS_HF_SPACE:
        await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)

if __name__ == "__main__":
    multiprocessing.freeze_support()

    # Запуск веб-сервера
    p_web = multiprocessing.Process(target=start_web)
    p_web.start()

    logger.info("🛰️ Система авто-восстановления Пророка запущена (Бесконечный цикл)")

    # Polling на всех платформах (на HF блокируется без PROXY_URL)
    platform_name = {"hf": "HF Spaces", "render": "Render.com", "local": "Local"}.get(PLATFORM, PLATFORM)
    logger.info(f"📡 {platform_name}: Запуск polling режима")
    while True:
        try:
            asyncio.run(start_bot_polling())
        except (KeyboardInterrupt, SystemExit):
            logger.info("🛑 Бот остановлен вручную.")
            break
        except Exception as e:
            logger.error(f"🧨 КРИТИЧЕСКИЙ СБОЙ В ЦИКЛЕ: {e}")
            logger.info("⏳ Попытка воскрешения через 15 секунд...")
            time.sleep(15)

    p_web.terminate()
