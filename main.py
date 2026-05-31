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
from config import TOKEN, PORT, PLATFORM, DATA_DIR
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

# ──────────────────── Certificate decoder ────────────────────
CERTS_JSON = Path(__file__).parent / "static" / "massage" / "certificates" / "certs.json"
CERTS_DIR = Path(__file__).parent / "static" / "massage" / "certificates"

def decode_certs():
    """Decode base64 certificate PNGs from certs.json on startup."""
    if not CERTS_JSON.exists():
        logger.info("📜 certs.json not found, skipping certificate decode")
        return
    try:
        import base64
        CERTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(CERTS_JSON, "r", encoding="utf-8") as f:
            certs = json.load(f)
        for name, b64 in certs.items():
            path = CERTS_DIR / name
            if not path.exists():
                data = base64.b64decode(b64)
                with open(path, "wb") as f:
                    f.write(data)
                logger.info(f"📜 Decoded certificate: {name}")
    except Exception as e:
        logger.warning(f"⚠️ Certificate decode failed: {e}")

decode_certs()

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
    from core.questionnaire import MassageQuestionnaire
    from config import TEMP_DIR
    chat_id = req.get("chat_id")
    name = req.get("name", "")
    message_text = req.get("message", "")
    file_path = req.get("file_path", "")
    if not chat_id or not name:
        return {"ok": False, "error": "Missing chat_id or name"}
    if not message_text and not file_path:
        return {"ok": False, "error": "Missing message or file"}
    specialist = get_specialist(chat_id, name)
    if not specialist:
        return {"ok": False, "error": f"Specialist '{name}' not found"}
    # Validate file_path if provided
    if file_path:
        if not os.path.exists(file_path):
            file_path = ""
        elif not file_path.startswith(TEMP_DIR):
            file_path = ""
    # Load questionnaire context for this user
    user_context = ""
    try:
        q = massage._get_questionnaire(chat_id)
        if q and (q.full_name or q.complaints):
            user_context = q.to_text()
    except Exception:
        pass
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(SpecialistFactory.chat, chat_id, specialist, message_text, user_context=user_context, file_path=file_path),
            timeout=120
        )
        if result.is_success():
            return {"ok": True, "response": result.content, "name": result.agent_name}
        return {"ok": False, "error": "AI engine failed"}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "Превышено время ожидания ответа от AI"}
    except Exception as e:
        return {"ok": False, "error": f"Ошибка AI: {str(e)}"}


@app.post("/api/specialist/upload")
async def api_specialist_upload(chat_id: str = Form(...), file: UploadFile = File(...)):
    if not chat_id or not file:
        return {"ok": False, "error": "Missing chat_id or file"}
    if not file.filename:
        return {"ok": False, "error": "Empty filename"}
    ext = os.path.splitext(file.filename)[1].lower()
    allowed_image = (".jpg", ".jpeg", ".png", ".webp")
    allowed_video = (".mp4", ".mov", ".webm")
    if ext not in allowed_image and ext not in allowed_video:
        return {"ok": False, "error": f"Неподдерживаемый формат «{ext}». Допустимо: JPG/PNG/WebP (фото), MP4/MOV/WebM (видео)"}
    max_size = 50 * 1024 * 1024 if ext in allowed_video else 10 * 1024 * 1024
    if file.size and file.size > max_size:
        limit_mb = max_size // (1024 * 1024)
        actual_mb = file.size / (1024 * 1024)
        return {"ok": False, "error": f"Файл слишком большой ({actual_mb:.1f} МБ). Максимум {limit_mb} МБ"}
    from config import TEMP_DIR
    os.makedirs(TEMP_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())[:8]
    prefix = "sp_photo" if ext in allowed_image else "sp_video"
    safe_name = f"{prefix}_{chat_id}_{file_id}{ext}"
    path = os.path.join(TEMP_DIR, safe_name)
    try:
        content = await file.read()
        with open(path, "wb") as f:
            f.write(content)
    except Exception as e:
        return {"ok": False, "error": f"Ошибка сохранения: {str(e)}"}
    return {"ok": True, "file_path": path}


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
    try:
        sp = await asyncio.to_thread(SpecialistFactory.create, chat_id=chat_id, role_description=role, name=name or None)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
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
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(SpecialistFactory.chat, chat_id, specialist, full_message),
            timeout=120
        )
        if result.is_success():
            return {"ok": True, "response": result.content, "name": result.agent_name}
        return {"ok": False, "error": "AI engine failed"}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "Превышено время ожидания ответа от AI"}
    except Exception as e:
        return {"ok": False, "error": f"Ошибка AI: {str(e)}"}


# ──────────────────── Music Player API ────────────────────

MUSIC_SETTINGS_FILE = os.path.join(DATA_DIR, "user_music.json")


def _load_music_settings() -> dict:
    if not os.path.exists(MUSIC_SETTINGS_FILE):
        return {}
    try:
        with open(MUSIC_SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_music_settings(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
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


@app.get("/api/music/recommendation/{chat_id}")
async def api_music_recommendation(chat_id: int):
    """Вернуть сохранённую музыкальную рекомендацию после консультации."""
    ud = getattr(massage, "_get_user_data", lambda cid: {})(chat_id)
    rec = ud.get("massage_music_recommendation", {})
    return {"ok": True, "recommendation": rec}


@app.get("/api/music/user_audio/{chat_id}/{filename}")
async def serve_user_audio(chat_id: str, filename: str):
    import re
    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", filename):
        return {"ok": False, "error": "Invalid filename"}
    path = os.path.join(USER_AUDIO_DIR, chat_id, filename)
    if not os.path.exists(path):
        return {"ok": False, "error": "File not found"}
    return FileResponse(path, media_type="audio/mpeg")


# ──────────────────── Massage Upload API ────────────────────

MASSAGE_EXT_IMAGE = (".jpg", ".jpeg", ".png", ".webp")
MASSAGE_EXT_VIDEO = (".mp4", ".mov", ".webm")
MASSAGE_MAX_IMAGE = 10 * 1024 * 1024
MASSAGE_MAX_VIDEO = 50 * 1024 * 1024

MASSAGE_EXT_LABELS = {
    **{e: "фото (JPG/PNG/WebP, до 10 МБ)" for e in MASSAGE_EXT_IMAGE},
    **{e: "видео (MP4/MOV/WebM, до 50 МБ)" for e in MASSAGE_EXT_VIDEO},
}


@app.post("/api/massage/upload")
async def api_massage_upload(chat_id: str = Form(...), file: UploadFile = File(...)):
    if not chat_id or not file:
        return {"ok": False, "error": "Не указан chat_id или файл"}
    if not file.filename:
        return {"ok": False, "error": "Пустое имя файла"}
    ext = os.path.splitext(file.filename)[1].lower()
    is_image = ext in MASSAGE_EXT_IMAGE
    is_video = ext in MASSAGE_EXT_VIDEO
    if not is_image and not is_video:
        allowed = ", ".join(sorted(set(MASSAGE_EXT_LABELS.values())))
        return {"ok": False, "error": f"Неподдерживаемый формат «{ext}». Допустимо: {allowed}"}
    max_size = MASSAGE_MAX_IMAGE if is_image else MASSAGE_MAX_VIDEO
    if file.size and file.size > max_size:
        limit_mb = max_size // (1024 * 1024)
        actual_mb = file.size / (1024 * 1024)
        return {"ok": False, "error": f"Файл слишком большой ({actual_mb:.1f} МБ). Максимум {limit_mb} МБ для {'фото' if is_image else 'видео'}"}
    from config import TEMP_DIR
    os.makedirs(TEMP_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())[:8]
    prefix = "massage_photo" if is_image else "massage_video"
    safe_name = f"{prefix}_{chat_id}_{file_id}{ext}"
    path = os.path.join(TEMP_DIR, safe_name)
    try:
        content = await file.read()
        with open(path, "wb") as f:
            f.write(content)
    except Exception as e:
        return {"ok": False, "error": f"Ошибка сохранения файла: {str(e)}"}

    key = "massage_photos" if is_image else "massage_videos"
    from handlers.massage import _get_user_data, _set_user_data
    existing = _get_user_data(chat_id).get(key, [])
    existing.append(path)
    _set_user_data(chat_id, key, existing)
    _set_user_data(chat_id, "massage_step", "media")
    return {"ok": True, "file_path": path, "count": len(existing)}


# ──────────────────── Massage Analyze API ────────────────────

@app.post("/api/massage/analyze")
async def api_massage_analyze(req: dict):
    chat_id = str(req.get("chat_id", ""))
    if not chat_id:
        return {"ok": False, "error": "Missing chat_id"}
    from handlers.massage import _get_user_data, _set_user_data, _get_questionnaire, _cleanup_massage_temp
    from core.agents import MassageConsultationOrchestrator, format_consultation_results

    q = _get_questionnaire(chat_id)
    if not q or not q.full_name:
        return {"ok": False, "error": "Сначала заполни анкету. Начни с /massage или открой анкету в Mini App"}

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
        _set_user_data(chat_id, "massage_step", "done")
        _cleanup_massage_temp(chat_id)
        return {"ok": False, "error": f"Ошибка анализа: {str(e)}"}

    _set_user_data(chat_id, "massage_step", "done")
    _cleanup_massage_temp(chat_id)

    # Сохраняем в профиль клиента
    try:
        from core.client_profiles import save_consultation
        technique_text = results.get("technique_expert", {}).get("content", "")
        from handlers.massage import _parse_music_recommendation as _parse_mr
        music_rec_inner = _parse_mr(results.get("final_expert", {}).get("content", ""))
        save_consultation(
            chat_id=int(chat_id),
            questionnaire=q.to_dict() if hasattr(q, "to_dict") else {},
            recommended_technique=technique_text[:200],
            music_genre=music_rec_inner.get("genre", ""),
            photo_count=len(photos),
            video_count=len(videos),
            first_name=q.full_name if hasattr(q, "full_name") else "",
            phone=q.phone if hasattr(q, "phone") else "",
        )
    except Exception as e:
        logger.warning(f"Failed to save client profile: {e}")

    formatted = format_consultation_results(results)
    _set_user_data(chat_id, "massage_results", {
        "raw": results,
        "formatted": formatted,
    })

    # Парсим и возвращаем музыкальную рекомендацию
    from handlers.massage import _parse_music_recommendation
    final_text = results.get("final_expert", {}).get("content", "")
    music_rec = _parse_music_recommendation(final_text)
    if music_rec:
        _set_user_data(chat_id, "massage_music_recommendation", music_rec)

    return {"ok": True, "formatted": formatted, "has_photos": bool(photos), "has_videos": bool(videos), "music_recommendation": music_rec}


@app.get("/api/massage/results/{chat_id}")
async def api_massage_results(chat_id: str):
    from handlers.massage import _get_user_data
    data = _get_user_data(chat_id)
    results = data.get("massage_results")
    if not results:
        return {"ok": False, "error": "Анализ ещё не проведён"}
    return {"ok": True, "formatted": results.get("formatted", ""), "has_results": True}


@app.get("/api/massage/export/{chat_id}")
async def api_massage_export(chat_id: str):
    from handlers.massage import _get_user_data, _get_questionnaire
    import datetime

    data = _get_user_data(chat_id)
    q = _get_questionnaire(chat_id)

    export = {
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "chat_id": chat_id,
        "questionnaire": q.to_dict() if q.full_name else None,
        "photos": data.get("massage_photos", []),
        "videos": data.get("massage_videos", []),
        "analysis_results": data.get("massage_results"),
        "specialists": data.get("massage_specialists", {}),
        "referral_specialists": data.get("massage_referral_specialists", []),
    }

    has_data = any(v for v in [export["questionnaire"], export["analysis_results"]])
    if not has_data:
        return {"ok": False, "error": "Нет данных консультации для экспорта"}

    from fastapi.responses import Response
    json_str = json.dumps(export, ensure_ascii=False, indent=2, default=str)
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="consultation_{chat_id}_{datetime.datetime.utcnow().strftime("%Y%m%d")}.json"'}
    )


# ──────────────────── Booking API ────────────────────

BOOKING_DAYS_THRESHOLD = 30


@app.get("/api/massage/booking_check/{chat_id}")
async def api_booking_check(chat_id: int = 0):
    """Check if client can book — questionnaire must be recent (<30 days)."""
    if not chat_id:
        return {"ok": False, "error": "Missing chat_id"}

    from core.client_profiles import get_profile
    profile = get_profile(chat_id)

    if not profile:
        return {
            "ok": True,
            "can_book": False,
            "reason": "no_questionnaire",
            "message": (
                "📋 *Для записи на сеанс нужно заполнить медицинскую анкету.*\n\n"
                "Это важно для твоей безопасности: мы должны знать о противопоказаниях, "
                "хронических заболеваниях и текущем самочувствии, "
                "чтобы подобрать безопасную и эффективную технику массажа.\n\n"
                "🩺 *Заполни анкету — это займёт 2–3 минуты.*\n"
                "После анализа AI-специалисты подберут идеальный массаж!"
            ),
        }

    last_consultation = profile.get("last_visit", 0)
    now = time.time()
    days_since = (now - last_consultation) / 86400

    if days_since > BOOKING_DAYS_THRESHOLD:
        days = int(days_since)
        return {
            "ok": True,
            "can_book": False,
            "reason": "questionnaire_outdated",
            "days_since": days,
            "message": (
                f"🕐 *С твоего последнего визита прошло {days} дней.*\n\n"
                "За это время могло измениться самочувствие, появиться новые "
                "противопоказания или измениться хронические заболевания.\n\n"
                "🩺 *Пройди быстрый чек-ап — это займёт меньше минуты,*\n"
                "чтобы мы убедились, что массаж безопасен для тебя сейчас."
            ),
        }

    return {
        "ok": True,
        "can_book": True,
        "reason": "",
        "message": "",
    }


@app.post("/api/massage/booking_request")
async def api_booking_request(req: dict):
    """Save a booking request from the Mini App."""
    chat_id = str(req.get("chat_id", ""))
    name = req.get("name", "").strip()
    phone = req.get("phone", "").strip()
    service = req.get("service", "").strip()
    date = req.get("date", "").strip()
    note = req.get("note", "").strip()
    if not chat_id or not name or not phone:
        return {"ok": False, "error": "Missing required fields"}

    booking = {
        "chat_id": int(chat_id),
        "name": name,
        "phone": phone,
        "service": service,
        "date": date,
        "note": note,
        "created_at": time.time(),
    }

    bookings_file = os.path.join(DATA_DIR, "booking_requests.json")
    try:
        existing = []
        if os.path.exists(bookings_file):
            with open(bookings_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.append(booking)
        with open(bookings_file, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Booking request saved for chat {chat_id}: {service}")
    except Exception as e:
        logger.warning(f"Failed to save booking: {e}")

    return {"ok": True}


# ──────────────────── Massage Diary & Roles API ────────────────────

@app.post("/api/massage/diary/{chat_id}")
async def api_diary_add(chat_id: int, req: dict, masseur_chat_id: int = 0):
    """Add a diary entry for a client session (masseur writes post-session)."""
    if not chat_id or not masseur_chat_id:
        return {"ok": False, "error": "Missing chat_id or masseur_chat_id"}
    from core.masseur_diary import add_diary_entry
    entry = {k: req.get(k, "") for k in [
        "technique", "intensity", "tools", "tissue_state",
        "client_feedback", "recommendations", "notes", "planned_technique",
    ]}
    entry["rating"] = req.get("rating", 0)
    ok = add_diary_entry(chat_id, masseur_chat_id, entry)
    return {"ok": ok}


@app.get("/api/massage/diary/{chat_id}")
async def api_diary_get(chat_id: int):
    """Get all diary entries for a client."""
    from core.masseur_diary import get_diary
    entries = get_diary(chat_id)
    return {"ok": True, "entries": entries}


@app.get("/api/massage/diary_summary/{chat_id}")
async def api_diary_summary(chat_id: int):
    """Get diary summary for a client — combines with profile timeline."""
    from core.masseur_diary import get_diary
    from core.client_profiles import get_timeline, get_profile
    diary = get_diary(chat_id)
    timeline = get_timeline(chat_id)
    profile = get_profile(chat_id)
    pre_session = {}
    if profile and profile.get("consultations"):
        last_c = profile["consultations"][-1]
        pre_session = {
            "complaints": last_c.get("complaints", ""),
            "pain_location": last_c.get("pain_location", ""),
            "pain_type": last_c.get("pain_type", ""),
            "recommended_technique": last_c.get("recommended_technique", ""),
            "has_contraindications": last_c.get("has_contraindications", False),
            "age": last_c.get("age", 0),
            "gender": last_c.get("gender", ""),
            "total_consultations": len(profile.get("consultations", [])),
        }
    return {
        "ok": True,
        "diary": diary,
        "timeline": timeline,
        "profile": profile,
        "pre_session": pre_session,
    }


@app.get("/api/massage/pre_session/{chat_id}")
async def api_pre_session(chat_id: int):
    """Pre-session briefing for masseur: what AI recommends + client history."""
    from core.client_profiles import get_profile, get_timeline
    from core.masseur_diary import get_diary
    profile = get_profile(chat_id)
    if not profile:
        return {"ok": False, "error": "No profile"}
    consults = profile.get("consultations", [])
    last = consults[-1] if consults else {}
    diary = get_diary(chat_id)
    last_diary = diary[0] if diary else None
    briefing = {
        "client_name": profile.get("first_name", ""),
        "phone": profile.get("phone", ""),
        "age": last.get("age", 0),
        "gender": last.get("gender", ""),
        "total_visits": len(consults),
        "complaints": last.get("complaints", ""),
        "pain_location": last.get("pain_location", ""),
        "pain_type": last.get("pain_type", ""),
        "recommended_technique": last.get("recommended_technique", ""),
        "music_genre": last.get("music_genre", ""),
        "contraindications": last.get("has_contraindications", False),
        "last_date": last.get("date", 0),
        "last_diary": last_diary,
    }
    return {"ok": True, "briefing": briefing}


def _compute_delta(a: dict, b: dict) -> dict:
    """Compute what changed between two consultation records."""
    delta = {}
    # Pain
    if a.get("pain_location") != b.get("pain_location"):
        delta["pain_location"] = {"from": a.get("pain_location", ""), "to": b.get("pain_location", "")}
    if a.get("pain_type") != b.get("pain_type"):
        delta["pain_type"] = {"from": a.get("pain_type", ""), "to": b.get("pain_type", "")}
    # Technique
    if a.get("recommended_technique") != b.get("recommended_technique"):
        delta["technique"] = {"from": a.get("recommended_technique", ""), "to": b.get("recommended_technique", "")}
    # Contraindications
    a_ci = a.get("has_contraindications", False)
    b_ci = b.get("has_contraindications", False)
    if a_ci != b_ci:
        delta["contraindications"] = {"from": a_ci, "to": b_ci}
    # Music
    if a.get("music_genre") != b.get("music_genre"):
        delta["music"] = {"from": a.get("music_genre", ""), "to": b.get("music_genre", "")}
    # Days between
    if a.get("date") and b.get("date"):
        delta["days_between"] = int((b["date"] - a["date"]) / 86400)
    # Questionnaire fields (weight, bp, etc.)
    aq = a.get("questionnaire_snapshot", {})
    bq = b.get("questionnaire_snapshot", {})
    for field, label in [("weight", "Вес"), ("ad_puls", "Давление/пульс")]:
        av = aq.get(field, "")
        bv = bq.get(field, "")
        if av and bv and av != bv:
            delta[field] = {"from": av, "to": bv, "label": label}
    return delta


@app.get("/api/massage/client_path/{chat_id}")
async def api_client_path(chat_id: int):
    """Get client journey path with deltas between visits."""
    from core.client_profiles import get_profile, get_timeline
    timeline = get_timeline(chat_id)  # newest first
    if not timeline or len(timeline) < 1:
        return {"ok": False, "error": "Not enough data"}
    # Reverse to chronological order
    timeline = list(reversed(timeline))
    nodes = []
    for i, c in enumerate(timeline):
        node = {
            "visit": i + 1,
            "date": c.get("date", 0),
            "technique": c.get("recommended_technique", ""),
            "music": c.get("music_genre", ""),
            "complaints": c.get("complaints", ""),
            "pain_location": c.get("pain_location", ""),
            "pain_type": c.get("pain_type", ""),
            "has_contraindications": c.get("has_contraindications", False),
            "photo_count": c.get("photo_count", 0),
            "video_count": c.get("video_count", 0),
        }
        if i > 0:
            node["delta"] = _compute_delta(timeline[i - 1], c)
        else:
            node["delta"] = {}
        nodes.append(node)
    profile = get_profile(chat_id)
    return {
        "ok": True,
        "client_name": (profile or {}).get("first_name", ""),
        "visits": len(nodes),
        "nodes": nodes,
    }


@app.get("/api/education/{role}")
async def api_education(role: str):
    """Get education markdown content for a role: client / masseur / admin."""
    import os
    role_map = {"client": "education_client.md", "masseur": "education_masseur.md", "admin": "education_admin.md"}
    fname = role_map.get(role)
    if not fname:
        return {"ok": False, "error": "Invalid role. Use: client, masseur, admin"}
    fpath = os.path.join("config", fname)
    if not os.path.exists(fpath):
        return {"ok": False, "error": "Education file not found"}
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    return {"ok": True, "role": role, "content": content}


@app.post("/api/admin/test_client")
async def api_test_client_create(req: dict):
    from core.client_profiles import create_test_patient
    profile = create_test_patient()
    if not profile:
        return {"ok": False, "error": "Failed to create test patient"}
    return {"ok": True, "client": profile}


@app.post("/api/admin/test_client/delete")
async def api_test_client_delete(req: dict, chat_id: int = 0):
    if not chat_id:
        return {"ok": False, "error": "Missing chat_id"}
    from core.client_profiles import delete_test_patient
    ok = delete_test_patient(chat_id)
    return {"ok": ok}


@app.get("/api/admin/masseurs")
async def api_masseurs_list(chat_id: int = 0):
    """List all registered masseurs."""
    if not chat_id or not _is_chat_id_admin(chat_id):
        return {"ok": False, "error": "Access denied"}
    from core.masseur_diary import get_masseurs
    return {"ok": True, "masseurs": get_masseurs()}


@app.post("/api/admin/masseur")
async def api_masseur_set(req: dict):
    """Register or update a masseur (admin only)."""
    chat_id = int(req.get("chat_id", 0))
    name = req.get("name", "").strip()
    specialties = req.get("specialties", [])
    admin_chat = req.get("admin_chat", 0)
    if not admin_chat or not _is_chat_id_admin(admin_chat):
        return {"ok": False, "error": "Access denied"}
    if not chat_id or not name:
        return {"ok": False, "error": "Missing chat_id or name"}
    from core.masseur_diary import set_masseur
    set_masseur(chat_id, name, specialties)
    return {"ok": True}


# ──────────────────── Questionnaire API ────────────────────

@app.get("/api/questionnaire/steps")
async def api_questionnaire_steps():
    from core.questionnaire import QUESTIONNAIRE_STEPS, QUESTIONNAIRE_STEPS_OPTIONAL
    return {
        "required": [{k: v for k, v in s.items() if k != "children"} for s in QUESTIONNAIRE_STEPS],
        "optional": [{k: v for k, v in s.items() if k != "children"} for s in QUESTIONNAIRE_STEPS_OPTIONAL],
    }


@app.get("/api/questionnaire/steps_full")
async def api_questionnaire_steps_full():
    from core.questionnaire import QUESTIONNAIRE_STEPS, QUESTIONNAIRE_STEPS_OPTIONAL
    return {
        "required": QUESTIONNAIRE_STEPS,
        "optional": QUESTIONNAIRE_STEPS_OPTIONAL,
    }


@app.post("/api/questionnaire/save_progress")
async def api_questionnaire_save_progress(req: dict):
    """Save partial questionnaire progress (supports resume after close)."""
    chat_id = str(req.get("chat_id", ""))
    answers = req.get("answers", {})
    step_index = req.get("step_index", 0)
    showing_optional = req.get("showing_optional", False)
    if not chat_id:
        return {"ok": False, "error": "Missing chat_id"}
    from handlers.massage import _set_user_data
    _set_user_data(chat_id, "massage_questionnaire_progress", {
        "answers": answers,
        "step_index": step_index,
        "showing_optional": showing_optional,
        "timestamp": str(datetime.now()),
    })
    return {"ok": True}


@app.get("/api/questionnaire/progress/{chat_id}")
async def api_questionnaire_progress(chat_id: str):
    """Return saved questionnaire progress, if any."""
    from handlers.massage import _get_user_data, _get_questionnaire
    q = _get_questionnaire(chat_id)
    if q and q.full_name:
        return {"ok": True, "has_progress": False, "completed": True}
    data = _get_user_data(chat_id)
    progress = data.get("massage_questionnaire_progress")
    if progress and progress.get("answers"):
        return {"ok": True, "has_progress": True, **progress}
    return {"ok": True, "has_progress": False}


@app.post("/api/questionnaire/clear_progress")
async def api_questionnaire_clear_progress(req: dict):
    """Clear saved progress after successful submit."""
    chat_id = str(req.get("chat_id", ""))
    if not chat_id:
        return {"ok": False, "error": "Missing chat_id"}
    from handlers.massage import _set_user_data
    _set_user_data(chat_id, "massage_questionnaire_progress", None)
    return {"ok": True}


@app.post("/api/questionnaire/submit")
async def api_questionnaire_submit(req: dict):
    chat_id = str(req.get("chat_id", ""))
    data = req.get("data", {})
    if not chat_id or not data:
        return {"ok": False, "error": "Missing chat_id or data"}

    from core.questionnaire import MassageQuestionnaire
    q = MassageQuestionnaire.from_dict(data)
    if data.get("age"):
        try: q.age = int(data["age"])
        except ValueError: pass

    from handlers.massage import _save_questionnaire, _set_user_data, _cleanup_massage_temp
    _cleanup_massage_temp(chat_id)
    _save_questionnaire(chat_id, q)
    _set_user_data(chat_id, "massage_step", "media")
    _set_user_data(chat_id, "massage_photos", [])
    _set_user_data(chat_id, "massage_videos", [])
    _set_user_data(chat_id, "massage_questionnaire_progress", None)
    return {"ok": True}


@app.post("/api/questionnaire/minimal")
async def api_questionnaire_minimal(req: dict):
    """Minimal 4-field questionnaire for fast booking."""
    chat_id = str(req.get("chat_id", ""))
    data = req.get("data", {})
    if not chat_id or not data:
        return {"ok": False, "error": "Missing chat_id or data"}

    from core.questionnaire import MassageQuestionnaire
    q = MassageQuestionnaire()
    q.full_name = data.get("full_name", "").strip()
    q.phone = data.get("phone", "").strip()
    q.complaints = data.get("complaints", "").strip()
    q.contraindications_absolute = data.get("contraindications_absolute", [])
    q.informed_consent = bool(data.get("informed_consent", False))

    if not q.full_name or not q.phone:
        return {"ok": False, "error": "Имя и телефон обязательны"}

    from handlers.massage import _save_questionnaire, _set_user_data, _cleanup_massage_temp
    _cleanup_massage_temp(chat_id)
    _save_questionnaire(chat_id, q)
    _set_user_data(chat_id, "massage_questionnaire_progress", None)

    # Also save to profile
    from core.client_profiles import save_consultation
    try:
        save_consultation(
            chat_id=int(chat_id),
            questionnaire=q.to_dict(),
            first_name=q.full_name,
            phone=q.phone,
        )
    except Exception:
        pass

    return {"ok": True, "full_name": q.full_name}

# ──────────────────── Admin API ────────────────────

ADMIN_PERSIST_FILE = os.path.join(DATA_DIR, "admin_mode_persist.json")


def _load_admin_mode_persist() -> dict:
    if os.path.exists(ADMIN_PERSIST_FILE):
        try:
            with open(ADMIN_PERSIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_admin_mode_persist(data: dict):
    try:
        with open(ADMIN_PERSIST_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _is_chat_id_admin(chat_id: int) -> bool:
    from config import ADMIN_IDS
    return chat_id in ADMIN_IDS


@app.get("/api/admin/identify")
async def api_admin_identify(chat_id: int = 0, username: str = ""):
    """Check user role: admin, masseur, or client."""
    if not chat_id:
        return {"ok": False, "error": "Missing chat_id"}
    from config import OWNER_USERNAME
    is_admin = _is_chat_id_admin(chat_id) or (username and username.lower() == OWNER_USERNAME.lower())
    from core.masseur_diary import is_masseur
    is_mas = is_masseur(chat_id)
    persist = _load_admin_mode_persist()
    pref = persist.get(str(chat_id), "client")
    return {"ok": True, "is_admin": is_admin, "is_masseur": is_mas, "mode": pref}


@app.post("/api/admin/mode")
async def api_admin_mode(req: dict):
    """Toggle role mode: client/admin/masseur."""
    chat_id = str(req.get("chat_id", ""))
    mode = req.get("mode", "client")
    if not chat_id:
        return {"ok": False, "error": "Missing chat_id"}
    if mode not in ("client", "admin", "masseur"):
        return {"ok": False, "error": "Invalid mode"}
    persist = _load_admin_mode_persist()
    persist[chat_id] = mode
    _save_admin_mode_persist(persist)
    return {"ok": True, "mode": mode}


@app.get("/api/admin/clients")
async def api_admin_clients(chat_id: int = 0):
    """List all clients with questionnaire data (admin only)."""
    if not chat_id or not _is_chat_id_admin(chat_id):
        return {"ok": False, "error": "Access denied"}
    clients = []
    settings_path = os.path.join(DATA_DIR, "user_settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                all_data = json.load(f)
            from core.client_profiles import get_profile
            for cid, data in all_data.items():
                q = data.get("massage_questionnaire")
                if not q:
                    continue
                phone = (q.get("phone") or "").strip()
                name = (q.get("full_name") or "").strip()
                if not name:
                    continue
                profile = get_profile(int(cid))
                clients.append({
                    "chat_id": cid,
                    "name": name,
                    "phone": phone,
                    "has_photos": bool(data.get("massage_photos")),
                    "has_videos": bool(data.get("massage_videos")),
                    "has_results": bool(data.get("massage_results")),
                    "has_progress": bool(data.get("massage_questionnaire_progress")),
                    "total_consultations": profile["total_consultations"] if profile else 0,
                    "first_visit": profile["first_visit"] if profile else 0,
                    "last_visit": profile["last_visit"] if profile else 0,
                })
        except Exception:
            pass
    clients.sort(key=lambda c: c["name"].lower())
    return {"ok": True, "clients": clients}


@app.get("/api/admin/client/{target_chat_id}")
async def api_admin_client(target_chat_id: str, chat_id: int = 0):
    """Get full client data including export (admin only)."""
    if not chat_id or not _is_chat_id_admin(chat_id):
        return {"ok": False, "error": "Access denied"}
    from handlers.massage import _get_user_data, _get_questionnaire
    data = _get_user_data(target_chat_id)
    q = _get_questionnaire(target_chat_id)
    questionnaire = q.to_dict() if q else None
    results = data.get("massage_results")
    return {
        "ok": True,
        "questionnaire": questionnaire,
        "formatted": (results.get("formatted") if results else None),
        "photos": data.get("massage_photos", []),
        "videos": data.get("massage_videos", []),
    }


@app.get("/api/admin/stats")
async def api_admin_stats(chat_id: int = 0):
    """Dashboard statistics (admin only)."""
    if not chat_id or not _is_chat_id_admin(chat_id):
        return {"ok": False, "error": "Access denied"}
    from core.client_profiles import get_stats
    stats = get_stats()
    return {"ok": True, "stats": stats}


@app.get("/api/admin/client/{target_chat_id}/timeline")
async def api_admin_client_timeline(target_chat_id: int = 0, chat_id: int = 0):
    """Client consultation timeline (admin only)."""
    if not chat_id or not _is_chat_id_admin(chat_id):
        return {"ok": False, "error": "Access denied"}
    from core.client_profiles import get_timeline, get_profile
    timeline = get_timeline(target_chat_id)
    profile = get_profile(target_chat_id)
    return {"ok": True, "timeline": timeline, "profile": profile}

# ──────────────────── Server ────────────────────

def start_web():
    uvicorn.run(app, host="0.0.0.0", port=PORT)

async def start_bot_polling():
    """Polling режим для локальной разработки"""
    apply_dns_patch()

    # Очистка временной папки при старте
    import config as cfg
    import shutil
    os.makedirs(cfg.DATA_DIR, exist_ok=True)
    if os.path.exists(cfg.TEMP_DIR):
        try:
            for item in os.listdir(cfg.TEMP_DIR):
                item_path = os.path.join(cfg.TEMP_DIR, item)
                if os.path.isfile(item_path): os.remove(item_path)
                elif os.path.isdir(item_path): shutil.rmtree(item_path)
            logger.info("🧹 Временная папка очищена")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось полностью очистить temp: {e}")
    else: os.makedirs(cfg.TEMP_DIR)

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
