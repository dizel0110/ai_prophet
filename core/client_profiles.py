import json
import time
import logging
import os
import threading
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

PROFILES_PATH = DATA_DIR / "client_profiles.json"
RECORDS_PATH = DATA_DIR / "consultation_records.json"

_lock = threading.Lock()


@dataclass
class ConsultationRecord:
    consult_id: str = ""
    date: float = 0.0
    chat_id: int = 0
    recommended_technique: str = ""
    pain_location: str = ""
    pain_type: str = ""
    complaints: str = ""
    music_genre: str = ""
    photo_count: int = 0
    video_count: int = 0
    referral_specialists: List[str] = field(default_factory=list)
    has_contraindications: bool = False
    age: int = 0
    gender: str = ""


@dataclass
class ClientProfile:
    chat_id: int = 0
    first_name: str = ""
    phone: str = ""
    first_visit: float = 0.0
    last_visit: float = 0.0
    total_consultations: int = 0
    consultations: List[ConsultationRecord] = field(default_factory=list)
    latest_questionnaire: Dict[str, Any] = field(default_factory=dict)


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load {path}: {e}")
    return {}


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_records() -> dict:
    return _load_json(RECORDS_PATH)


def _save_records(data: dict) -> None:
    _save_json(RECORDS_PATH, data)


def _load_profiles() -> dict:
    return _load_json(PROFILES_PATH)


def _save_profiles(data: dict) -> None:
    _save_json(PROFILES_PATH, data)


def save_consultation(
    chat_id: int,
    questionnaire: dict,
    recommended_technique: str = "",
    music_genre: str = "",
    photo_count: int = 0,
    video_count: int = 0,
    referral_specialists: Optional[List[str]] = None,
    final_expert_text: str = "",
    first_name: str = "",
    phone: str = "",
) -> None:
    with _lock:
        profiles = _load_profiles()
        records = _load_records()

        chat_key = str(chat_id)
        now = time.time()
        consult_id = f"c_{chat_id}_{int(now)}"

        if chat_key not in profiles:
            profiles[chat_key] = {
                "chat_id": chat_id,
                "first_name": first_name or "",
                "phone": phone or questionnaire.get("phone", ""),
                "first_visit": now,
                "last_visit": now,
                "total_consultations": 0,
                "consultations": [],
                "latest_questionnaire": {},
            }

        profile = profiles[chat_key]

        if first_name:
            profile["first_name"] = first_name
        if phone:
            profile["phone"] = phone
        elif questionnaire.get("phone"):
            profile["phone"] = questionnaire["phone"]

        record = {
            "consult_id": consult_id,
            "date": now,
            "chat_id": chat_id,
            "recommended_technique": recommended_technique,
            "pain_location": questionnaire.get("pain_location", ""),
            "pain_type": questionnaire.get("pain_type", ""),
            "complaints": questionnaire.get("complaints", ""),
            "music_genre": music_genre,
            "photo_count": photo_count,
            "video_count": video_count,
            "referral_specialists": referral_specialists or [],
            "has_contraindications": bool(
                questionnaire.get("contraindications_absolute")
                or questionnaire.get("temp_contraindications")
            ),
            "age": questionnaire.get("age", 0),
            "gender": questionnaire.get("gender", ""),
        }

        profile.setdefault("consultations", []).append(record)
        profile["latest_questionnaire"] = questionnaire
        profile["last_visit"] = now
        profile["total_consultations"] = len(profile["consultations"])

        records[consult_id] = {
            "chat_id": chat_id,
            "date": now,
            "technique": recommended_technique,
        }

        _save_profiles(profiles)
        _save_records(records)
        logger.info(f"Saved consultation {consult_id} for chat {chat_id}")


def get_profile(chat_id: int) -> Optional[Dict[str, Any]]:
    profiles = _load_profiles()
    return profiles.get(str(chat_id))


def get_consultation_count(chat_id: int) -> int:
    p = get_profile(chat_id)
    return p["total_consultations"] if p else 0


def get_timeline(chat_id: int) -> List[Dict[str, Any]]:
    p = get_profile(chat_id)
    if not p:
        return []
    return list(reversed(p.get("consultations", [])))


def get_all_profiles() -> List[Dict[str, Any]]:
    profiles = _load_profiles()
    result = []
    for chat_key, p in profiles.items():
        p["_chat_id"] = int(chat_key)
        result.append(p)
    result.sort(key=lambda x: x.get("last_visit", 0), reverse=True)
    return result


def get_stats() -> Dict[str, Any]:
    profiles = _load_profiles()
    records = _load_records()

    total_clients = len(profiles)
    total_consultations = sum(p.get("total_consultations", 0) for p in profiles.values())
    today = time.time()
    today_start = today - (today % 86400)

    technique_counts: Dict[str, int] = {}
    gender_counts: Dict[str, int] = {}
    age_groups: Dict[str, int] = {"18-30": 0, "31-45": 0, "46+": 0}
    today_count = 0
    pain_locations: Dict[str, int] = {}
    music_genres: Dict[str, int] = {}

    for p in profiles.values():
        gender = p.get("latest_questionnaire", {}).get("gender", "").lower()
        if "жен" in gender:
            gender_counts["female"] = gender_counts.get("female", 0) + 1
        elif "муж" in gender:
            gender_counts["male"] = gender_counts.get("male", 0) + 1
        else:
            gender_counts["unknown"] = gender_counts.get("unknown", 0) + 1

        age = p.get("latest_questionnaire", {}).get("age", 0)
        if 18 <= age <= 30:
            age_groups["18-30"] += 1
        elif 31 <= age <= 45:
            age_groups["31-45"] += 1
        elif age >= 46:
            age_groups["46+"] += 1

        for c in p.get("consultations", []):
            tech = c.get("recommended_technique", "")
            if tech:
                technique_counts[tech] = technique_counts.get(tech, 0) + 1
            pl = c.get("pain_location", "")
            if pl:
                key = pl[:30]
                pain_locations[key] = pain_locations.get(key, 0) + 1
            mg = c.get("music_genre", "")
            if mg:
                music_genres[mg] = music_genres.get(mg, 0) + 1
            cd = c.get("date", 0)
            if cd >= today_start:
                today_count += 1

    sorted_techniques = sorted(technique_counts.items(), key=lambda x: -x[1])[:10]

    return {
        "total_clients": total_clients,
        "total_consultations": total_consultations,
        "today_consultations": today_count,
        "top_techniques": [{"name": k, "count": v} for k, v in sorted_techniques],
        "gender": gender_counts,
        "age_groups": age_groups,
        "top_pain_locations": sorted(pain_locations.items(), key=lambda x: -x[1])[:5],
        "top_music_genres": sorted(music_genres.items(), key=lambda x: -x[1])[:5],
    }
