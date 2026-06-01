import os
import json
import logging

import requests as req

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_ENABLED, DATA_DIR

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS profiles (
  chat_id BIGINT PRIMARY KEY,
  first_name TEXT DEFAULT '',
  username TEXT DEFAULT '',
  phone TEXT DEFAULT '',
  full_name TEXT DEFAULT '',
  is_admin BOOLEAN DEFAULT false,
  is_masseur BOOLEAN DEFAULT false,
  is_test BOOLEAN DEFAULT false,
  has_questionnaire BOOLEAN DEFAULT false,
  questionnaire_data JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS consultations (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT NOT NULL REFERENCES profiles(chat_id),
  consultation_date TIMESTAMPTZ DEFAULT now(),
  recommended_technique TEXT DEFAULT '',
  music_genre TEXT DEFAULT '',
  complaints TEXT DEFAULT '',
  contraindications JSONB DEFAULT '[]',
  photo_count INT DEFAULT 0,
  video_count INT DEFAULT 0,
  is_test BOOLEAN DEFAULT false,
  questionnaire_snapshot JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS diary_entries (
  id BIGSERIAL PRIMARY KEY,
  masseur_chat_id BIGINT NOT NULL,
  client_chat_id BIGINT REFERENCES profiles(chat_id),
  session_date TIMESTAMPTZ DEFAULT now(),
  planned_technique TEXT DEFAULT '',
  actual_technique TEXT DEFAULT '',
  notes TEXT DEFAULT '',
  subjective_feeling INT DEFAULT 5,
  pain_level INT DEFAULT 0,
  is_test BOOLEAN DEFAULT false
);

CREATE TABLE IF NOT EXISTS time_slots (
  id BIGSERIAL PRIMARY KEY,
  masseur_chat_id BIGINT NOT NULL,
  slot_date DATE NOT NULL,
  start_time TIME NOT NULL,
  duration_min INT NOT NULL DEFAULT 60,
  service_name TEXT DEFAULT '',
  status TEXT DEFAULT 'free',
  client_chat_id BIGINT,
  booking_id BIGINT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bookings (
  id BIGSERIAL PRIMARY KEY,
  client_chat_id BIGINT NOT NULL REFERENCES profiles(chat_id),
  masseur_chat_id BIGINT NOT NULL,
  slot_id BIGINT REFERENCES time_slots(id),
  service_name TEXT DEFAULT '',
  duration_min INT DEFAULT 60,
  status TEXT DEFAULT 'pending',
  is_first_visit BOOLEAN DEFAULT true,
  client_note TEXT DEFAULT '',
  masseur_note TEXT DEFAULT '',
  cancelled_by TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT now(),
  confirmed_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS masseur_settings (
  chat_id BIGINT PRIMARY KEY REFERENCES profiles(chat_id),
  email TEXT DEFAULT '',
  notify_tg BOOLEAN DEFAULT true,
  notify_email BOOLEAN DEFAULT false,
  calendar_type TEXT DEFAULT 'none',
  working_hours JSONB DEFAULT '{}',
  break_start TIME DEFAULT '13:00',
  break_end TIME DEFAULT '13:30',
  cancel_deadline_min INT DEFAULT 60,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS admin_users (
  chat_id BIGINT PRIMARY KEY REFERENCES profiles(chat_id),
  username TEXT DEFAULT '',
  added_by BIGINT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_consultations_chat_id ON consultations(chat_id);
CREATE INDEX IF NOT EXISTS idx_diary_masseur ON diary_entries(masseur_chat_id);
CREATE INDEX IF NOT EXISTS idx_diary_client ON diary_entries(client_chat_id);
CREATE INDEX IF NOT EXISTS idx_slots_date ON time_slots(slot_date);
CREATE INDEX IF NOT EXISTS idx_slots_masseur ON time_slots(masseur_chat_id);
CREATE INDEX IF NOT EXISTS idx_slots_status ON time_slots(status);
CREATE INDEX IF NOT EXISTS idx_bookings_client ON bookings(client_chat_id);
CREATE INDEX IF NOT EXISTS idx_bookings_masseur ON bookings(masseur_chat_id);
"""


def _sb_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _sb_req(method: str, path: str, data: dict = None):
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{path.lstrip('/')}"
    try:
        resp = req.request(method, url, json=data, headers=_sb_headers(), timeout=15)
        if resp.status_code >= 400 and resp.status_code != 201:
            logger.debug(f"Supabase {method} {path}: {resp.status_code}")
            return None
        return resp.json() if resp.content else {}
    except Exception as e:
        logger.warning(f"Supabase request failed: {e}")
        return None


def check_tables_exist() -> bool:
    """Check if profiles table exists via REST API HEAD request."""
    resp = _sb_req("HEAD", "profiles?limit=1")
    return resp is not None


def init_schema():
    """Auto-create tables on startup via direct Postgres connection."""
    if not SUPABASE_ENABLED:
        logger.info("Supabase not configured — skipping DB")
        return False

    if check_tables_exist():
        logger.info("Supabase tables already exist")
        return True

    # Need DB URL for direct SQL (requires DB password)
    db_url = os.getenv("SUPABASE_DB_URL", "")
    if not db_url:
        logger.warning("SUPABASE_DB_URL not set — tables must be created manually")
        logger.warning("Run script from internal/supabase_schema.sql in Supabase SQL Editor")
        return False

    try:
        import psycopg2
        conn = psycopg2.connect(db_url, connect_timeout=10)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(SCHEMA_SQL)
        cur.close()
        conn.close()
        logger.info("Supabase tables created")
        return True
    except Exception as e:
        logger.error(f"Failed to create Supabase tables: {e}")
        return False


def upsert(table: str, data: dict, conflict_col: str = "chat_id"):
    """Upsert a row via REST API."""
    path = f"{table}?on_conflict={conflict_col}"
    return _sb_req("POST", path, data)


def query(table: str, params: dict = None) -> list:
    """Query rows from a table."""
    import urllib.parse
    path = table
    if params:
        qs = urllib.parse.urlencode(params)
        path = f"{table}?{qs}"
    result = _sb_req("GET", path)
    return result if isinstance(result, list) else []


def migrate_from_json():
    """One-time migration from JSON files to Supabase."""
    if not SUPABASE_ENABLED:
        return

    if not check_tables_exist():
        logger.warning("Tables don't exist, skipping migration")
        return

    # 1. Profiles
    settings_path = os.path.join(DATA_DIR, "user_settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                users = json.load(f)
            for cid_str, data in users.items():
                q = data.get("massage_questionnaire") or {}
                upsert("profiles", {
                    "chat_id": int(cid_str),
                    "first_name": data.get("first_name", ""),
                    "username": data.get("username", ""),
                    "phone": q.get("phone", ""),
                    "full_name": q.get("full_name", ""),
                    "has_questionnaire": bool(q),
                    "questionnaire_data": json.dumps(q, ensure_ascii=False),
                })
            logger.info(f"Migrated {len(users)} profiles")
        except Exception as e:
            logger.warning(f"Profile migration: {e}")

    # 2. Consultations
    prof_path = os.path.join(DATA_DIR, "client_profiles.json")
    if os.path.exists(prof_path):
        try:
            with open(prof_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for cid_str, profile in data.items():
                for cons in profile.get("consultations", []):
                    upsert("consultations", {
                        "chat_id": int(cid_str),
                        "consultation_date": cons.get("date", ""),
                        "recommended_technique": cons.get("recommended_technique", ""),
                        "music_genre": cons.get("music_genre", ""),
                        "complaints": cons.get("complaints", ""),
                        "contraindications": json.dumps(cons.get("contraindications", [])),
                        "photo_count": cons.get("photo_count", 0),
                        "video_count": cons.get("video_count", 0),
                        "is_test": profile.get("is_test", False),
                        "questionnaire_snapshot": json.dumps(cons.get("questionnaire_snapshot", {}), ensure_ascii=False),
                    })
            logger.info("Migrated consultations")
        except Exception as e:
            logger.warning(f"Consultation migration: {e}")

    # 3. Admin users
    admin_path = os.path.join(DATA_DIR, "admin_ids_extras.json")
    if os.path.exists(admin_path):
        try:
            with open(admin_path, "r", encoding="utf-8") as f:
                admins = json.load(f)
            for cid_str, info in admins.items():
                upsert("admin_users", {
                    "chat_id": int(cid_str),
                    "username": info.get("username", ""),
                })
            logger.info(f"Migrated {len(admins)} admin users")
        except Exception as e:
            logger.warning(f"Admin migration: {e}")
