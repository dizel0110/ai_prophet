import os
import json
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

RECORDS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "video_records.json")


def _load():
    if not os.path.exists(RECORDS_FILE):
        return {"records": []}
    try:
        with open(RECORDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load video_records: {e}")
        return {"records": []}


def _save(data):
    os.makedirs(os.path.dirname(RECORDS_FILE), exist_ok=True)
    with open(RECORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_record(client_chat_id: int, masseur_chat_id: int,
                file_id: str, file_unique_id: str,
                duration_min: int = 0, caption: str = "",
                is_training: bool = False) -> str:
    data = _load()
    record_id = uuid.uuid4().hex[:12]
    data["records"].append({
        "id": record_id,
        "client_chat_id": client_chat_id,
        "masseur_chat_id": masseur_chat_id,
        "file_id": file_id,
        "file_unique_id": file_unique_id,
        "date": int(datetime.utcnow().timestamp()),
        "duration_min": duration_min,
        "caption": caption,
        "is_training": is_training,
    })
    _save(data)
    return record_id


def get_records_for(user_chat_id: int, limit: int = 50):
    data = _load()
    result = []
    for r in reversed(data["records"]):
        if r["masseur_chat_id"] == user_chat_id or r["client_chat_id"] == user_chat_id:
            result.append(r)
            if len(result) >= limit:
                break
    return result


def get_record(record_id: str):
    data = _load()
    for r in data["records"]:
        if r["id"] == record_id:
            return r
    return None


def can_access(record: dict, user_chat_id: int) -> bool:
    return user_chat_id in (record["masseur_chat_id"], record["client_chat_id"])


def cleanup_old_data(max_age_days: int = 30):
    data = _load()
    cutoff = int(datetime.utcnow().timestamp()) - max_age_days * 86400
    before = len(data["records"])
    data["records"] = [r for r in data["records"] if r["date"] > cutoff]
    if len(data["records"]) < before:
        _save(data)
        logger.info(f"Video records cleanup: removed {before - len(data['records'])} old entries")
