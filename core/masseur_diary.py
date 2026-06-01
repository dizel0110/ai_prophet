import json
import time
import logging
import threading
from typing import Optional, Dict, Any, List
from pathlib import Path
from core.supabase_manager import SUPABASE_ENABLED, upsert, _sb_req

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

DIARY_PATH = DATA_DIR / "masseur_diary.json"
MASSEURS_PATH = DATA_DIR / "masseurs.json"

_lock = threading.Lock()


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load {path}: {e}")
    return {}


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ──────────────────── Diary ────────────────────


def add_diary_entry(chat_id: int, masseur_chat_id: int, entry: dict) -> bool:
    """Save a post-session diary entry from a masseur about a client session.
    
    entry fields:
        technique (str): что делали
        intensity (str): легкий/средний/глубокий
        tools (str): масло, аромат, банки и т.д.
        tissue_state (str): состояние тканей
        client_feedback (str): реакция клиента
        recommendations (str): рекомендации на след. раз
        rating (int): оценка 1-5
        notes (str): свободные заметки
    """
    with _lock:
        data = _load_json(DIARY_PATH)
        key = str(chat_id)
        if key not in data:
            data[key] = []
        entry["masseur_chat_id"] = masseur_chat_id
        entry["created_at"] = time.time()
        data[key].append(entry)
        _save_json(DIARY_PATH, data)
    if SUPABASE_ENABLED:
        supabase_entry = {k: v for k, v in entry.items()}
        supabase_entry["client_chat_id"] = chat_id
        supabase_entry["session_date"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(entry.get("created_at", time.time())))
        _sb_req("POST", "diary_entries", supabase_entry)
    logger.info(f"Diary entry saved for chat {chat_id} by masseur {masseur_chat_id}")
    return True


def get_diary(chat_id: int) -> List[Dict[str, Any]]:
    """Get all diary entries for a client, newest first."""
    data = _load_json(DIARY_PATH)
    entries = data.get(str(chat_id), [])
    entries = list(reversed(entries))
    return entries


def get_all_diary_entries() -> Dict[str, List[Dict[str, Any]]]:
    """Get all diary entries grouped by client chat_id."""
    return _load_json(DIARY_PATH)


# ──────────────────── Masseur Roles ────────────────────


def get_masseurs() -> List[Dict[str, Any]]:
    """Get list of all registered masseurs."""
    data = _load_json(MASSEURS_PATH)
    return list(data.values())


def get_masseur(chat_id: int) -> Optional[Dict[str, Any]]:
    """Get a single masseur by chat_id."""
    data = _load_json(MASSEURS_PATH)
    return data.get(str(chat_id))


def set_masseur(chat_id: int, name: str, specialties: List[str] = None) -> bool:
    """Register or update a masseur (dual-write: JSON + Supabase)."""
    entry = {
        "chat_id": chat_id,
        "name": name,
        "specialties": specialties or [],
        "created_at": time.time(),
    }
    with _lock:
        data = _load_json(MASSEURS_PATH)
        data[str(chat_id)] = entry
        _save_json(MASSEURS_PATH, data)
    if SUPABASE_ENABLED:
        upsert("masseur_settings", entry)
    return True


def remove_masseur(chat_id: int) -> bool:
    """Remove a masseur (dual-delete: JSON + Supabase)."""
    with _lock:
        data = _load_json(MASSEURS_PATH)
        if str(chat_id) in data:
            del data[str(chat_id)]
            _save_json(MASSEURS_PATH, data)
        else:
            return False
    if SUPABASE_ENABLED:
        _sb_req("DELETE", f"masseur_settings?chat_id=eq.{chat_id}")
    return True


def is_masseur(chat_id: int) -> bool:
    """Check if a user is a registered masseur."""
    return get_masseur(chat_id) is not None
