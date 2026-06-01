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
  client_chat_id BIGINT NOT NULL,
  session_date TIMESTAMPTZ DEFAULT now(),
  technique TEXT DEFAULT '',
  intensity TEXT DEFAULT '',
  tools TEXT DEFAULT '',
  tissue_state TEXT DEFAULT '',
  client_feedback TEXT DEFAULT '',
  recommendations TEXT DEFAULT '',
  rating INT DEFAULT 5,
  notes TEXT DEFAULT '',
  is_test BOOLEAN DEFAULT false
);

ALTER TABLE diary_entries ADD COLUMN IF NOT EXISTS technique TEXT DEFAULT '';
ALTER TABLE diary_entries ADD COLUMN IF NOT EXISTS intensity TEXT DEFAULT '';
ALTER TABLE diary_entries ADD COLUMN IF NOT EXISTS tools TEXT DEFAULT '';
ALTER TABLE diary_entries ADD COLUMN IF NOT EXISTS tissue_state TEXT DEFAULT '';
ALTER TABLE diary_entries ADD COLUMN IF NOT EXISTS client_feedback TEXT DEFAULT '';
ALTER TABLE diary_entries ADD COLUMN IF NOT EXISTS recommendations TEXT DEFAULT '';
ALTER TABLE diary_entries ADD COLUMN IF NOT EXISTS rating INT DEFAULT 5;

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
  client_username TEXT DEFAULT '',
  masseur_note TEXT DEFAULT '',
  cancelled_by TEXT DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT now(),
  confirmed_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS masseur_settings (
  chat_id BIGINT PRIMARY KEY,
  name TEXT DEFAULT '',
  specialties JSONB DEFAULT '[]',
  created_at DOUBLE PRECISION DEFAULT 0,
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

ALTER TABLE masseur_settings DROP CONSTRAINT IF EXISTS masseur_settings_chat_id_fkey;
ALTER TABLE masseur_settings ADD COLUMN IF NOT EXISTS name TEXT DEFAULT '';
ALTER TABLE masseur_settings ADD COLUMN IF NOT EXISTS specialties JSONB DEFAULT '[]';
ALTER TABLE masseur_settings ADD COLUMN IF NOT EXISTS created_at DOUBLE PRECISION DEFAULT 0;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS client_username TEXT DEFAULT '';
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS slot_date TEXT DEFAULT '';
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS start_time TEXT DEFAULT '';

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
    }


def _sb_req(method: str, path: str, data: dict = None):
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{path.lstrip('/')}"
    try:
        resp = req.request(method, url, json=data, headers=_sb_headers(), timeout=15)
        if resp.status_code >= 400 and resp.status_code != 201:
            logger.warning(f"Supabase {method} {path}: {resp.status_code} {resp.text[:200]}")
            return None
        return resp.json() if resp.content else {}
    except Exception as e:
        logger.warning(f"Supabase request failed: {e}")
        return None


def check_tables_exist() -> bool:
    """Check if profiles table exists via REST API."""
    resp = _sb_req("GET", "profiles?limit=1")
    return isinstance(resp, list)


SQL_FILE_HINT = "internal/supabase_schema.sql"


def _log_manual_sql_instructions():
    logger.warning("=" * 60)
    logger.warning("Supabase: tables not found and auto-creation failed.")
    logger.warning("")
    logger.warning("To create tables manually:")
    logger.warning(f"  1. Open: https://supabase.com/dashboard/project/{SUPABASE_URL.split('.')[0].split('//')[1]}/sql/new")
    logger.warning(f"  2. Copy content from: {SQL_FILE_HINT}")
    logger.warning("  3. Paste into SQL Editor → Run")
    logger.warning("  4. Restart the bot")
    logger.warning("")
    logger.warning("Or enable Connection Pooler in Project Settings → Database")
    logger.warning("and set SUPABASE_DB_URL to the Session pooler connection string.")
    logger.warning("=" * 60)


def _run_sql_via_db_url(db_url: str) -> bool:
    """Try to execute schema SQL via a direct Postgres connection (psycopg2)."""
    try:
        import psycopg2
        conn = psycopg2.connect(db_url, connect_timeout=10)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(SCHEMA_SQL)
        cur.close()
        conn.close()
        logger.info("Supabase tables created via direct DB connection")
        return True
    except ImportError:
        logger.warning("psycopg2 not installed — can't auto-create tables")
        return False
    except Exception as e:
        logger.warning(f"DB connection failed: {e}")
        return False


def init_schema():
    """Auto-create/migrate tables on startup.
    
    Runs CREATE TABLE IF NOT EXISTS + ALTER TABLE ADD COLUMN IF NOT EXISTS
    on every startup (idempotent). Safe for existing tables.
    """
    if not SUPABASE_ENABLED:
        logger.info("Supabase not configured — using JSON file storage")
        return False

    # Check if tables already exist
    tables_exist = check_tables_exist()
    if tables_exist:
        logger.info("Supabase tables exist, running migrations...")
    else:
        logger.info("Supabase tables not found, creating...")

    # Always try to run SQL (CREATE IF NOT EXISTS + ALTER TABLE ADD COLUMN IF NOT EXISTS)
    db_url = os.getenv("SUPABASE_DB_URL", "")
    if db_url:
        if _run_sql_via_db_url(db_url):
            return True
    else:
        logger.warning("SUPABASE_DB_URL not set — auto-migrations skipped")
        logger.warning("To apply schema fixes, run this SQL in Supabase SQL Editor:")
        for line in SCHEMA_SQL.strip().split("\n"):
            logger.warning(f"  {line}")
        if tables_exist:
            return True

    if not tables_exist:
        _log_manual_sql_instructions()
    return False


def upsert(table: str, data: dict, conflict_col: str = "chat_id"):
    """Upsert a row via REST API (requires unique constraint on conflict_col)."""
    def _try(data, path_override=None):
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{(path_override or table).lstrip('/')}"
        headers = _sb_headers()
        headers["Prefer"] = "resolution=merge-duplicates"
        try:
            resp = req.request("POST", url, json=data, headers=headers, timeout=15)
            if resp.status_code >= 400:
                logger.warning(f"Supabase upsert {path_override or table}: {resp.status_code} {resp.text[:200]}")
                return None
            return resp.json() if resp.content else {}
        except Exception as e:
            logger.warning(f"Supabase upsert failed: {e}")
            return None
    path = f"{table}?on_conflict={conflict_col}"
    resp = _try(data, path)
    if resp is None:
        resp = _try(data, table)
    return resp


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

    # 1. Profiles (from user_settings or client_profiles)
    migrated_profiles = 0
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
                migrated_profiles += 1
        except Exception as e:
            logger.warning(f"Profile migration (user_settings): {e}")

    # Also migrate from client_profiles.json (has is_test flag)
    prof_path = os.path.join(DATA_DIR, "client_profiles.json")
    if os.path.exists(prof_path):
        try:
            with open(prof_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for cid_str, profile in data.items():
                q = profile.get("latest_questionnaire") or {}
                upsert("profiles", {
                    "chat_id": int(cid_str),
                    "first_name": profile.get("first_name", ""),
                    "phone": q.get("phone", ""),
                    "full_name": q.get("full_name", ""),
                    "has_questionnaire": bool(q),
                    "is_test": profile.get("is_test", False),
                    "questionnaire_data": json.dumps(q, ensure_ascii=False),
                })
                migrated_profiles += 1
        except Exception as e:
            logger.warning(f"Profile migration (client_profiles): {e}")
    if migrated_profiles:
        logger.info(f"Migrated {migrated_profiles} profiles")

    # 2. Consultations (plain POST — no unique constraint conflict to handle)
    prof_path = os.path.join(DATA_DIR, "client_profiles.json")
    migrated_cons = 0
    if os.path.exists(prof_path):
        try:
            with open(prof_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for cid_str, profile in data.items():
                for cons in profile.get("consultations", []):
                    raw_date = cons.get("date", "")
                    # Convert Unix timestamp to ISO format
                    if isinstance(raw_date, (int, float)) and raw_date > 1e9:
                        from datetime import datetime, timezone
                        raw_date = datetime.fromtimestamp(raw_date, tz=timezone.utc).isoformat()
                    elif not raw_date:
                        raw_date = None
                    result = _sb_req("POST", "consultations", {
                        "chat_id": int(cid_str),
                        "consultation_date": raw_date,
                        "recommended_technique": cons.get("recommended_technique", ""),
                        "music_genre": cons.get("music_genre", ""),
                        "complaints": cons.get("complaints", ""),
                        "contraindications": json.dumps(cons.get("contraindications", []), ensure_ascii=False),
                        "photo_count": cons.get("photo_count", 0),
                        "video_count": cons.get("video_count", 0),
                        "is_test": profile.get("is_test", False),
                        "questionnaire_snapshot": json.dumps(cons.get("questionnaire_snapshot", {}), ensure_ascii=False),
                    })
                    if result is not None:
                        migrated_cons += 1
            if migrated_cons:
                logger.info(f"Migrated {migrated_cons} consultations")
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

    # 4. Masseurs → masseur_settings
    masseurs_path = os.path.join(DATA_DIR, "masseurs.json")
    if os.path.exists(masseurs_path):
        try:
            with open(masseurs_path, "r", encoding="utf-8") as f:
                masseurs = json.load(f)
            for cid_str, info in masseurs.items():
                upsert("masseur_settings", {
                    "chat_id": int(cid_str),
                    "name": info.get("name", ""),
                    "specialties": info.get("specialties", []),
                    "created_at": info.get("created_at", 0),
                })
            logger.info(f"Migrated {len(masseurs)} masseurs")
        except Exception as e:
            logger.warning(f"Masseur migration: {e}")


def restore_from_supabase():
    """Pull data FROM Supabase TO JSON files.
    
    Runs after migrate_from_json(). On HF Spaces rebuild (empty data/),
    this repopulates JSON files from Supabase so the bot sees all data.
    """
    if not SUPABASE_ENABLED:
        return
    if not check_tables_exist():
        logger.info("Supabase tables don't exist — nothing to restore")
        return

    from datetime import datetime, timezone

    # 1. Profiles → user_settings.json
    profiles = query("profiles")
    if profiles:
        out = {}
        for p in profiles:
            cid = str(p["chat_id"])
            qdata = p.get("questionnaire_data")
            if isinstance(qdata, str):
                try:
                    qdata = json.loads(qdata)
                except Exception:
                    qdata = {}
            out[cid] = {
                "first_name": p.get("first_name", ""),
                "username": p.get("username", ""),
                "massage_questionnaire": qdata if isinstance(qdata, dict) else {},
            }
        settings_path = os.path.join(DATA_DIR, "user_settings.json")
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        logger.info(f"Restored {len(out)} profiles → user_settings.json")

    # 2. Consultations → client_profiles.json
    cons = query("consultations")
    if cons:
        # Group consultations by chat_id
        grouped = {}
        for c in cons:
            cid = str(c["chat_id"])
            if cid not in grouped:
                # Fetch profile data for this user
                pdata = query("profiles", {"chat_id": f"eq.{c['chat_id']}"})
                profile_info = pdata[0] if pdata else {}
                qdata = profile_info.get("questionnaire_data", {})
                if isinstance(qdata, str):
                    try:
                        qdata = json.loads(qdata)
                    except Exception:
                        qdata = {}
                grouped[cid] = {
                    "chat_id": c["chat_id"],
                    "first_name": profile_info.get("first_name", ""),
                    "phone": profile_info.get("phone", ""),
                    "full_name": profile_info.get("full_name", ""),
                    "is_test": c.get("is_test", False),
                    "first_visit": "",
                    "last_visit": "",
                    "total_consultations": 0,
                    "consultations": [],
                    "latest_questionnaire": qdata,
                }
            grouped[cid]["consultations"].append({
                "date": c.get("consultation_date", ""),
                "recommended_technique": c.get("recommended_technique", ""),
                "music_genre": c.get("music_genre", ""),
                "complaints": c.get("complaints", ""),
                "contraindications": c.get("contraindications", []),
                "photo_count": c.get("photo_count", 0),
                "video_count": c.get("video_count", 0),
                "questionnaire_snapshot": c.get("questionnaire_snapshot", {}),
            })
        for cid, g in grouped.items():
            g["total_consultations"] = len(g["consultations"])
            dates = [c["date"] for c in g["consultations"] if c["date"]]
            if dates:
                g["first_visit"] = min(dates)
                g["last_visit"] = max(dates)
        prof_path = os.path.join(DATA_DIR, "client_profiles.json")
        with open(prof_path, "w", encoding="utf-8") as f:
            json.dump(grouped, f, ensure_ascii=False, indent=2)
        logger.info(f"Restored {len(cons)} consultations → client_profiles.json")

    # 3. Admin users → admin_ids_extras.json
    admins = query("admin_users")
    if admins:
        out = {}
        for a in admins:
            out[str(a["chat_id"])] = {
                "username": a.get("username", ""),
                "added_by": a.get("added_by"),
            }
        admin_path = os.path.join(DATA_DIR, "admin_ids_extras.json")
        with open(admin_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        logger.info(f"Restored {len(admins)} admin users → admin_ids_extras.json")

    # 4. Time slots → time_slots.json
    slots = query("time_slots")
    if slots:
        slots_path = os.path.join(DATA_DIR, "time_slots.json")
        with open(slots_path, "w", encoding="utf-8") as f:
            json.dump(slots, f, ensure_ascii=False, indent=2)
        logger.info(f"Restored {len(slots)} time slots → time_slots.json")

    # 5. Bookings → bookings.json
    bookings = query("bookings")
    if bookings:
        bookings_path = os.path.join(DATA_DIR, "bookings.json")
        with open(bookings_path, "w", encoding="utf-8") as f:
            json.dump(bookings, f, ensure_ascii=False, indent=2)
        logger.info(f"Restored {len(bookings)} bookings → bookings.json")

    # 6. Masseur settings → masseurs.json
    masseurs = query("masseur_settings")
    if masseurs:
        out = {}
        for m in masseurs:
            out[str(m["chat_id"])] = {
                "chat_id": m["chat_id"],
                "name": m.get("name", ""),
                "specialties": m.get("specialties", []),
                "created_at": m.get("created_at", 0),
            }
        masseurs_path = os.path.join(DATA_DIR, "masseurs.json")
        with open(masseurs_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        logger.info(f"Restored {len(masseurs)} masseurs → masseurs.json")

    # 7. Diary entries → masseur_diary.json (grouped by client_chat_id)
    diary = query("diary_entries")
    if diary:
        grouped = {}
        for d in diary:
            cid = str(d.get("client_chat_id", ""))
            grouped.setdefault(cid, []).append(d)
        diary_path = os.path.join(DATA_DIR, "masseur_diary.json")
        with open(diary_path, "w", encoding="utf-8") as f:
            json.dump(grouped, f, ensure_ascii=False, indent=2)
        logger.info(f"Restored {len(diary)} diary entries → masseur_diary.json")

    logger.info("Supabase → JSON restore complete")
