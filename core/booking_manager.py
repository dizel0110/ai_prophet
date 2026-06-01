import json
import time
import logging
from datetime import datetime, timedelta, date, time as dtime
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

SLOTS_PATH = DATA_DIR / "time_slots.json"
BOOKINGS_PATH = DATA_DIR / "bookings.json"

DEFAULT_WORK_HOURS = {"start": "09:00", "end": "18:00"}
DEFAULT_DURATIONS = [30, 60, 90]
DEFAULT_CANCEL_DEADLINE_MIN = 60

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

def _load_json(path: Path) -> list:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load {path}: {e}")
    return []

def _save_json(path: Path, data: list) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

_sb_req_fn = None
_sb_query_fn = None
_sb_checked = False

def _try_supabase():
    global _sb_checked
    if _sb_checked:
        return _sb_req_fn, _sb_query_fn
    _sb_checked = True
    try:
        from core.supabase_manager import SUPABASE_ENABLED, check_tables_exist, _sb_req, query as sb_query
        if SUPABASE_ENABLED and check_tables_exist():
            return _sb_req, sb_query
    except Exception as e:
        logger.debug(f"Supabase not available: {e}")
    return None, None

def _init_sb():
    global _sb_req_fn, _sb_query_fn
    if _sb_req_fn is None and not _sb_checked:
        r, q = _try_supabase()
        _sb_req_fn = r
        _sb_query_fn = q
    return _sb_req_fn, _sb_query_fn

# ──────────────────── Masseurs ────────────────────

def get_available_masseurs() -> List[Dict[str, Any]]:
    """Return list of masseurs with their working hours."""
    sb_req, sb_query = _init_sb()
    if sb_req:
        masseurs = sb_query("masseur_settings")
        if isinstance(masseurs, list) and masseurs:
            result = []
            for m in masseurs:
                wh = m.get("working_hours", {})
                if isinstance(wh, str):
                    try: wh = json.loads(wh)
                    except: wh = {}
                result.append({
                    "chat_id": m["chat_id"],
                    "name": m.get("email", "").split("@")[0] or f"Массажист {m['chat_id']}",
                    "working_hours": wh,
                    "break_start": str(m.get("break_start", "13:00")),
                    "break_end": str(m.get("break_end", "13:30")),
                    "cancel_deadline_min": m.get("cancel_deadline_min", DEFAULT_CANCEL_DEADLINE_MIN),
                })
            return result
    from core.masseur_diary import get_masseurs
    masseurs = get_masseurs()
    return [{
        "chat_id": m["chat_id"],
        "name": m.get("name", f"Массажист {m['chat_id']}"),
        "working_hours": DEFAULT_WORK_HOURS,
        "break_start": "13:00",
        "break_end": "13:30",
        "cancel_deadline_min": DEFAULT_CANCEL_DEADLINE_MIN,
        "specialties": m.get("specialties", []),
    } for m in masseurs]

# ──────────────────── Time Slots ────────────────────

def _time_to_min(t_str: str) -> int:
    h, m = t_str.split(":")
    return int(h) * 60 + int(m)

def _min_to_time(mins: int) -> str:
    return f"{mins // 60:02d}:{mins % 60:02d}"

def _date_range(start_date: str, days: int = 7):
    """Yield date strings from start_date for N days."""
    try:
        dt = date.fromisoformat(start_date)
    except:
        dt = date.today()
    for i in range(days):
        yield dt.isoformat()
        dt += timedelta(days=1)

def generate_slots(masseur_chat_id: int, start_date: str = None, days: int = 7,
                   work_hours: dict = None, durations: list = None,
                   break_start: str = "13:00", break_end: str = "13:30") -> List[Dict[str, Any]]:
    """Generate time slots for a masseur for the next N days."""
    if work_hours is None:
        work_hours = DEFAULT_WORK_HOURS
    if durations is None:
        durations = DEFAULT_DURATIONS
    wh_start = _time_to_min(work_hours.get("start", "09:00"))
    wh_end = _time_to_min(work_hours.get("end", "18:00"))
    br_start = _time_to_min(break_start)
    br_end = _time_to_min(break_end)

    slots = []
    dt_start = date.today().isoformat() if not start_date else start_date
    for day_str in _date_range(dt_start, days):
        slot_time = wh_start
        while slot_time + min(durations) <= wh_end:
            in_break = br_start < slot_time < br_end or br_start < slot_time + min(durations) < br_end
            if not in_break:
                for dur in sorted(durations):
                    if slot_time + dur <= wh_end:
                        next_br = br_start < slot_time + dur < br_end
                        if not next_br:
                            slots.append({
                                "masseur_chat_id": masseur_chat_id,
                                "slot_date": day_str,
                                "start_time": _min_to_time(slot_time),
                                "duration_min": dur,
                                "status": "free",
                                "client_chat_id": None,
                                "booking_id": None,
                            })
                        break
            slot_time += 30
    return slots

def _slot_key(slot: dict) -> str:
    return f"{slot['masseur_chat_id']}:{slot['slot_date']}:{slot['start_time']}:{slot['duration_min']}"

def _save_slots(slots: list):
    sb_req, _ = _init_sb()
    if sb_req and slots:
        try:
            import requests as req_lib
            from config import SUPABASE_URL, SUPABASE_SERVICE_KEY
            headers = {
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            }
            url = SUPABASE_URL.rstrip("/") + "/rest/v1/time_slots"
            req_lib.post(url, json=slots, headers=headers, timeout=10)
        except Exception as e:
            logger.warning(f"Supabase batch slot save: {e}")
    existing = _load_json(SLOTS_PATH)
    keys = {_slot_key(s) for s in existing}
    for s in slots:
        if _slot_key(s) not in keys:
            existing.append(s)
            keys.add(_slot_key(s))
    _save_json(SLOTS_PATH, existing)

def get_free_slots(masseur_chat_id: int, slot_date: str = None) -> List[Dict[str, Any]]:
    """Get free slots for a masseur on a given date."""
    sb_req, sb_query = _init_sb()
    if sb_req:
        params = {"masseur_chat_id": f"eq.{masseur_chat_id}", "status": "eq.free"}
        if slot_date:
            params["slot_date"] = f"eq.{slot_date}"
        slots = sb_query("time_slots", params)
        if isinstance(slots, list):
            return slots
    slots = _load_json(SLOTS_PATH)
    result = [s for s in slots
              if s.get("masseur_chat_id") == masseur_chat_id
              and s.get("status") == "free"
              and (slot_date is None or s.get("slot_date") == slot_date)]
    if not result:
        sd = slot_date or date.today().isoformat()
        generated = generate_slots(masseur_chat_id, sd, days=3)
        _save_slots(generated)
        result = [s for s in generated
                  if s.get("status") == "free"
                  and (slot_date is None or s.get("slot_date") == slot_date)]
    return result

# ──────────────────── Bookings ────────────────────

def create_booking(client_chat_id: int, masseur_chat_id: int,
                   slot_date: str, start_time: str, duration_min: int = 60,
                   service_name: str = "", note: str = "",
                   is_first_visit: bool = False) -> Optional[Dict[str, Any]]:
    """Create a new booking (status: pending)."""
    sb_req, sb_query = _init_sb()
    booking = {
        "client_chat_id": client_chat_id,
        "masseur_chat_id": masseur_chat_id,
        "service_name": service_name,
        "duration_min": duration_min,
        "status": "pending",
        "is_first_visit": is_first_visit,
        "client_note": note,
        "created_at": datetime.utcnow().isoformat(),
    }
    if sb_req:
        result = sb_req("POST", "bookings", booking)
        if result is not None:
            booking_id = result.get("id") if isinstance(result, dict) else None
            if not booking_id:
                b_list = sb_query("bookings", {"client_chat_id": f"eq.{client_chat_id}", "status": "eq.pending", "order": "created_at.desc", "limit": "1"})
                booking_id = b_list[0]["id"] if isinstance(b_list, list) and b_list else None
            if booking_id:
                sb_req("PATCH", f"time_slots?masseur_chat_id=eq.{masseur_chat_id}&slot_date=eq.{slot_date}&start_time=eq.{start_time}&duration_min=eq.{duration_min}", {"status": "reserved", "client_chat_id": client_chat_id, "booking_id": booking_id})
    bookings = _load_json(BOOKINGS_PATH)
    booking["id"] = int(time.time() * 1000) % 10000000000
    booking["slot_date"] = slot_date
    booking["start_time"] = start_time
    bookings.append(booking)
    _save_json(BOOKINGS_PATH, bookings)
    try:
        from core.notifier import notify_booking_created
        notify_booking_created(client_chat_id, masseur_chat_id, service_name, slot_date, start_time)
    except Exception as e:
        logger.debug(f"Notify create: {e}")
    return booking

def confirm_booking(booking_id: int) -> bool:
    """Confirm a pending booking."""
    sb_req, sb_query = _init_sb()
    if sb_req:
        sb_req("PATCH", f"bookings?id=eq.{booking_id}", {"status": "confirmed", "confirmed_at": datetime.utcnow().isoformat()})
        b = sb_query("bookings", {"id": f"eq.{booking_id}"})
        if isinstance(b, list) and b:
            slot = b[0]
            sb_req("PATCH", f"time_slots?id=eq.{slot.get('slot_id', 0)}", {"status": "booked"})
    bookings = _load_json(BOOKINGS_PATH)
    for b in bookings:
        if b.get("id") == booking_id:
            b["status"] = "confirmed"
            b["confirmed_at"] = time.time()
            _save_json(BOOKINGS_PATH, bookings)
            try:
                from core.notifier import notify_booking_confirmed
                notify_booking_confirmed(b.get("client_chat_id"), b.get("masseur_chat_id"), b.get("slot_date"), b.get("start_time"))
            except Exception as e:
                logger.debug(f"Notify confirm: {e}")
            return True
    return False

def cancel_booking(booking_id: int, cancelled_by: str = "client") -> dict:
    """Cancel a booking. Returns {ok, reason, can_cancel}."""
    sb_req, sb_query = _init_sb()
    if sb_req:
        b = sb_query("bookings", {"id": f"eq.{booking_id}"})
        if isinstance(b, list) and b:
            bk = b[0]
            if bk.get("status") == "cancelled":
                return {"ok": False, "reason": "already_cancelled", "message": "Уже отменено"}
            deadline = DEFAULT_CANCEL_DEADLINE_MIN
            m_settings = sb_query("masseur_settings", {"chat_id": f"eq.{bk['masseur_chat_id']}"})
            if isinstance(m_settings, list) and m_settings:
                deadline = m_settings[0].get("cancel_deadline_min", DEFAULT_CANCEL_DEADLINE_MIN)
            created = bk.get("created_at", "")
            if created and isinstance(created, str):
                try:
                    from datetime import datetime, timezone
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if (datetime.now(timezone.utc) - created_dt).total_seconds() / 60 > deadline:
                        return {"ok": False, "reason": "past_deadline", "can_cancel": False, "message": f"Отмена недоступна — до сеанса меньше {deadline} мин. Позвоните массажисту."}
                except:
                    pass
            sb_req("PATCH", f"bookings?id=eq.{booking_id}", {"status": "cancelled", "cancelled_by": cancelled_by, "cancelled_at": datetime.utcnow().isoformat()})
            slot_id = bk.get("slot_id")
            if slot_id:
                sb_req("PATCH", f"time_slots?id=eq.{slot_id}", {"status": "free", "client_chat_id": None, "booking_id": None})
            return {"ok": True, "reason": "cancelled", "message": "Запись отменена"}
    bookings = _load_json(BOOKINGS_PATH)
    for b in bookings:
        if b.get("id") == booking_id:
            if b.get("status") == "cancelled":
                return {"ok": False, "reason": "already_cancelled", "message": "Уже отменено"}
            b["status"] = "cancelled"
            b["cancelled_by"] = cancelled_by
            b["cancelled_at"] = time.time()
            _save_json(BOOKINGS_PATH, bookings)
            try:
                from core.notifier import notify_booking_cancelled
                notify_booking_cancelled(b.get("client_chat_id"), b.get("masseur_chat_id"), b.get("slot_date"), b.get("start_time"), cancelled_by)
            except Exception as e:
                logger.debug(f"Notify cancel: {e}")
            return {"ok": True, "reason": "cancelled", "message": "Запись отменена"}
    return {"ok": False, "reason": "not_found", "message": "Запись не найдена"}

def get_bookings(for_chat_id: int = None, by_masseur: bool = False,
                 status: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Get bookings for a client or masseur."""
    sb_req, sb_query = _init_sb()
    if sb_req:
        key = "masseur_chat_id" if by_masseur else "client_chat_id"
        params = {key: f"eq.{for_chat_id}"}
        if status:
            params["status"] = f"eq.{status}"
        params["order"] = "created_at.desc"
        params["limit"] = str(limit)
        result = sb_query("bookings", params)
        if isinstance(result, list):
            return result
    bookings = _load_json(BOOKINGS_PATH)
    result = bookings
    if for_chat_id:
        key = "masseur_chat_id" if by_masseur else "client_chat_id"
        result = [b for b in result if b.get(key) == for_chat_id]
    if status:
        result = [b for b in result if b.get("status") == status]
    return sorted(result, key=lambda x: x.get("created_at", 0), reverse=True)[:limit]

# ──────────────────── Workload ────────────────────

def get_workload(masseur_chat_id: int, week_start: str = None) -> Dict[str, Any]:
    """Get workload stats for a masseur for a given week."""
    sb_req, sb_query = _init_sb()
    slots_today = slots_week = booked_today = booked_week = 0
    today = date.today().isoformat()

    if sb_req:
        all_slots = sb_query("time_slots", {"masseur_chat_id": f"eq.{masseur_chat_id}"})
        if isinstance(all_slots, list):
            slots_week = len(all_slots)
            slots_today = len([s for s in all_slots if s.get("slot_date") == today])
            booked_week = len([s for s in all_slots if s.get("status") in ("booked", "reserved")])
            booked_today = len([s for s in all_slots if s.get("slot_date") == today and s.get("status") in ("booked", "reserved")])

    slots = _load_json(SLOTS_PATH)
    m_slots = [s for s in slots if s.get("masseur_chat_id") == masseur_chat_id]
    if not sb_req:
        slots_week = len(m_slots)
        slots_today = len([s for s in m_slots if s.get("slot_date") == today])
        booked_week = len([s for s in m_slots if s.get("status") in ("booked", "reserved")])
        booked_today = len([s for s in m_slots if s.get("slot_date") == today and s.get("status") in ("booked", "reserved")])

    pct = (booked_week / slots_week * 100) if slots_week > 0 else 0
    level = "low" if pct < 50 else ("medium" if pct < 80 else "high")
    level_label = {"low": "🟢 Низкая", "medium": "🟡 Средняя", "high": "🔴 Высокая"}
    return {
        "slots_today": slots_today,
        "slots_week": slots_week,
        "booked_today": booked_today,
        "booked_week": booked_week,
        "load_pct": round(pct, 0),
        "load_level": level,
        "load_label": level_label[level],
    }
