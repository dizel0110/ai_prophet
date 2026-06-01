import json
import time
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from pathlib import Path
from core.supabase_manager import SUPABASE_ENABLED, upsert, _sb_req

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
    if SUPABASE_ENABLED:
        profile_payload = {
            "chat_id": chat_id,
            "first_name": profile.get("first_name", ""),
            "phone": profile.get("phone", ""),
            "full_name": questionnaire.get("full_name", ""),
            "has_questionnaire": True,
            "is_test": profile.get("is_test", False),
            "questionnaire_data": questionnaire,
        }
        upsert("profiles", profile_payload)
        cons_payload = {
            "chat_id": chat_id,
            "consultation_date": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            "recommended_technique": recommended_technique,
            "music_genre": music_genre,
            "complaints": questionnaire.get("complaints", ""),
            "photo_count": photo_count,
            "video_count": video_count,
            "is_test": profile.get("is_test", False),
            "questionnaire_snapshot": questionnaire,
        }
        _sb_req("POST", "consultations", cons_payload)


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


def get_stats(filter_test: bool = True) -> Dict[str, Any]:
    profiles = _load_profiles()
    records = _load_records()

    if filter_test:
        profiles = {k: v for k, v in profiles.items() if not v.get("is_test")}

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
            if isinstance(cd, str):
                try:
                    from datetime import datetime
                    cd_dt = datetime.fromisoformat(cd.replace("Z", "+00:00"))
                    cd_ts = cd_dt.timestamp()
                except Exception:
                    cd_ts = 0
            else:
                cd_ts = float(cd)
            if cd_ts >= today_start:
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


_TEST_NAMES = [
    "Иван Петров", "Мария Иванова", "Алексей Смирнов", "Елена Кузнецова",
    "Дмитрий Попов", "Ольга Васильева", "Сергей Новиков", "Анна Козлова",
    "Михаил Зайцев", "Наталья Морозова", "Андрей Волков", "Татьяна Соколова",
    "Павел Белов", "Юлия Романова", "Артём Крылов", "Екатерина Орлова",
]

_TEST_COMPLAINTS = [
    "Боль в пояснице после работы за компьютером",
    "Напряжение в шее и плечах, головные боли",
    "Ноющая боль в пояснице после сна",
    "Сколиоз, асимметрия плеч",
    "Остеохондроз шейного отдела",
    "Боли в коленях после бега",
    "Усталость в ногах к вечеру",
    "Мигрени, зажимы в верхней части спины",
    "Боли в грудном отделе при сидении",
    "Хроническое напряжение в пояснице",
    "Бессонница на фоне стресса, напряжение в спине",
    "Сутулость, боли между лопатками",
    "Травма поясницы 2 года назад, периодические боли",
    "Грыжа L4-L5, наблюдение",
]

_TEST_TECHNIQUES = [
    "Классический массаж спины",
    "Шведский массаж всего тела",
    "Массаж шейно-воротниковой зоны",
    "Стоун-терапия с элементами лимфодренажа",
    "Спортивный массаж",
    "Антицеллюлитный массаж",
    "Тайский массаж спины",
    "Миофасциальный релиз",
]

_TEST_MUSIC_GENRES = ["Ambient", "Nature", "Jazz", "Classical", "Spa", "Binaural"]
_TEST_PAIN_LOCATIONS = ["Поясница", "Шея", "Плечи", "Грудной отдел", "Ноги", "Поясница и крестец"]
_TEST_PAIN_TYPES = ["Хроническая", "Острая", "Тянущая", "Ноющая", "Резкая"]


def _next_test_chat_id() -> int:
    profiles = _load_profiles()
    used = set()
    for k, v in profiles.items():
        if v.get("is_test"):
            try:
                used.add(int(k))
            except ValueError:
                pass
    # Find next free id in range 90000000-90999999
    base = 90000000
    while base in used:
        base += 1
    return base


import random


def create_test_patient() -> Optional[Dict[str, Any]]:
    """Create a test patient with realistic data. Returns profile dict."""
    now = time.time()
    chat_id = _next_test_chat_id()
    name = random.choice(_TEST_NAMES)
    age = random.randint(22, 65)
    gender = "Мужской" if random.random() < 0.4 else "Женский"
    phone = f"+7000{random.randint(100000, 999999)}"
    complaints = random.choice(_TEST_COMPLAINTS)
    pain_loc = random.choice(_TEST_PAIN_LOCATIONS)
    pain_type = random.choice(_TEST_PAIN_TYPES)
    technique = random.choice(_TEST_TECHNIQUES)
    music = random.choice(_TEST_MUSIC_GENRES)
    consultations_count = random.randint(1, 4)

    profile = {
        "chat_id": chat_id,
        "first_name": name,
        "phone": phone,
        "first_visit": now - consultations_count * random.randint(7, 60) * 86400,
        "last_visit": now - random.randint(0, 14) * 86400,
        "total_consultations": consultations_count,
        "consultations": [],
        "latest_questionnaire": {},
        "is_test": True,
    }

    questionnaire = {
        "full_name": name,
        "age": age,
        "gender": gender,
        "phone": phone,
        "complaints": complaints,
        "pain_location": pain_loc,
        "pain_type": pain_type,
    }

    for i in range(consultations_count):
        c_date = profile["first_visit"] + i * random.randint(5, 30) * 86400
        c_tech = random.choice(_TEST_TECHNIQUES)
        c_music = random.choice(_TEST_MUSIC_GENRES)
        record = {
            "consult_id": f"c_{chat_id}_{int(c_date)}",
            "date": c_date,
            "chat_id": chat_id,
            "recommended_technique": c_tech,
            "pain_location": pain_loc,
            "pain_type": pain_type,
            "complaints": complaints if i == consultations_count - 1 else random.choice(_TEST_COMPLAINTS),
            "music_genre": c_music,
            "photo_count": random.randint(0, 3),
            "video_count": random.randint(0, 1),
            "referral_specialists": [],
            "has_contraindications": random.random() < 0.15,
            "age": age,
            "gender": gender,
            "is_test": True,
        }
        profile["consultations"].append(record)

    profile["latest_questionnaire"] = questionnaire

    with _lock:
        profiles = _load_profiles()
        chat_key = str(chat_id)
        profiles[chat_key] = profile
        # Add records
        records = _load_records()
        for c in profile["consultations"]:
            records[c["consult_id"]] = {
                "chat_id": chat_id,
                "date": c["date"],
                "technique": c["recommended_technique"],
                "is_test": True,
            }
        _save_profiles(profiles)
        _save_records(records)

    if SUPABASE_ENABLED:
        upsert("profiles", {
            "chat_id": chat_id,
            "first_name": name,
            "phone": phone,
            "full_name": name,
            "has_questionnaire": True,
            "is_test": True,
            "questionnaire_data": questionnaire,
        })
        for c in profile["consultations"]:
            _sb_req("POST", "consultations", {
                "chat_id": chat_id,
                "consultation_date": datetime.fromtimestamp(c["date"], tz=timezone.utc).isoformat(),
                "recommended_technique": c["recommended_technique"],
                "music_genre": c["music_genre"],
                "complaints": c["complaints"],
                "photo_count": c["photo_count"],
                "video_count": c["video_count"],
                "is_test": True,
                "questionnaire_snapshot": questionnaire,
            })

    logger.info(f"Created test patient {chat_id}: {name}")
    return profile


def delete_test_patient(chat_id: int) -> bool:
    """Delete a test patient by chat_id. Returns True if deleted."""
    with _lock:
        profiles = _load_profiles()
        chat_key = str(chat_id)
        if chat_key not in profiles or not profiles[chat_key].get("is_test"):
            return False
        # Remove consultation records
        records = _load_records()
        for c in profiles[chat_key].get("consultations", []):
            cid = c.get("consult_id", "")
            records.pop(cid, None)
        _save_records(records)
        # Remove profile
        del profiles[chat_key]
        _save_profiles(profiles)
    if SUPABASE_ENABLED:
        _sb_req("DELETE", f"consultations?chat_id=eq.{chat_id}")
        _sb_req("DELETE", f"profiles?chat_id=eq.{chat_id}")
    logger.info(f"Deleted test patient {chat_id}")
    return True
