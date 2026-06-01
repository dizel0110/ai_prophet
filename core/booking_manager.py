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
                    "name": m.get("name") or m.get("email", "").split("@")[0] or f"Массажист {m['chat_id']}",
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
                   break_start: str = "13:00", break_end: str = "13:30",
                   tz_offset: int = None) -> List[Dict[str, Any]]:
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
    if tz_offset is not None:
        now = datetime.utcnow() + timedelta(minutes=tz_offset)
    else:
        now = datetime.now()
    now_min = now.hour * 60 + now.minute
    for day_str in _date_range(dt_start, days):
        slot_time = wh_start
        while slot_time + min(durations) <= wh_end:
            in_break = br_start < slot_time < br_end or br_start < slot_time + min(durations) < br_end
            is_past = day_str == date.today().isoformat() and slot_time <= now_min
            if not in_break and not is_past:
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

def get_free_slots(masseur_chat_id: int, slot_date: str = None, tz_offset: int = None) -> List[Dict[str, Any]]:
    """Get free slots for a masseur on a given date."""
    result = None
    sb_req, sb_query = _init_sb()
    if sb_req:
        params = {"masseur_chat_id": f"eq.{masseur_chat_id}", "status": "eq.free"}
        if slot_date:
            params["slot_date"] = f"eq.{slot_date}"
        slots = sb_query("time_slots", params)
        if isinstance(slots, list):
            result = slots
    if result is None:
        slots = _load_json(SLOTS_PATH)
        result = [s for s in slots
                  if s.get("masseur_chat_id") == masseur_chat_id
                  and s.get("status") == "free"
                  and (slot_date is None or s.get("slot_date") == slot_date)]
    if not result:
        sd = slot_date or date.today().isoformat()
        generated = generate_slots(masseur_chat_id, sd, days=3, tz_offset=tz_offset)
        _save_slots(generated)
        result = [s for s in generated
                  if s.get("status") == "free"
                  and (slot_date is None or s.get("slot_date") == slot_date)]
    return result


def get_all_slots_for_client(masseur_chat_id: int, slot_date: str, tz_offset: int = None) -> List[Dict[str, Any]]:
    """Get ALL slots (free/reserved/booked) for a client booking view."""
    slots = _load_json(SLOTS_PATH)
    result = [s for s in slots
              if s.get("masseur_chat_id") == masseur_chat_id
              and s.get("slot_date") == slot_date]
    if not result:
        generated = generate_slots(masseur_chat_id, slot_date, days=3, tz_offset=tz_offset)
        _save_slots(generated)
        result = [s for s in generated if s.get("slot_date") == slot_date]
    return result


def get_booked_slots_for_month(masseur_chat_id: int, year: int, month: int, tz_offset: int = None) -> dict:
    """Get slot count per day for a month: {date: {total: N, free: N}}."""
    from calendar import monthrange
    _, days_in_month = monthrange(year, month)
    prefix = f"{year:04d}-{month:02d}"
    all_slots = _load_json(SLOTS_PATH)
    # Filter slots for this masseur in this month
    day_map = {}
    for s in all_slots:
        if s.get("masseur_chat_id") != masseur_chat_id:
            continue
        sd = s.get("slot_date", "")
        if not sd.startswith(prefix):
            continue
        key = sd
        if key not in day_map:
            day_map[key] = {"total": 0, "free": 0}
        day_map[key]["total"] += 1
        if s.get("status") == "free":
            day_map[key]["free"] += 1
    # Also query Supabase for extra data
    sb_req, sb_query = _init_sb()
    if sb_req:
        start_date = f"{prefix}-01"
        end_date = f"{prefix}-{days_in_month:02d}"
        sb_slots = sb_query("time_slots", {
            "masseur_chat_id": f"eq.{masseur_chat_id}",
            "slot_date": f"gte.{start_date}",
            "slot_date": f"lte.{end_date}",
        })
        if isinstance(sb_slots, list):
            for s in sb_slots:
                sd = s.get("slot_date", "")
                if sd not in day_map:
                    day_map[sd] = {"total": 0, "free": 0}
                day_map[sd]["total"] = max(day_map[sd]["total"], day_map[sd].get("_sb_total", 0) + 1)
                day_map[sd]["_sb_total"] = day_map[sd].get("_sb_total", 0) + 1
                if s.get("status") == "free":
                    day_map[sd]["free"] += 1
    # Fill missing days
    for d in range(1, days_in_month + 1):
        ds = f"{prefix}-{d:02d}"
        if ds not in day_map:
            day_map[ds] = {"total": 0, "free": 0}
    # Cleanup internal keys
    for v in day_map.values():
        v.pop("_sb_total", None)
    return day_map


# ──────────────────── Bookings ────────────────────

def create_booking(client_chat_id: int, masseur_chat_id: int,
                   slot_date: str, start_time: str, duration_min: int = 60,
                   service_name: str = "", note: str = "",
                   is_first_visit: bool = False,
                   client_username: str = "") -> Optional[Dict[str, Any]]:
    """Create a new booking (status: pending). Returns None if limit exceeded."""
    # Check pending limit: max 2 pending bookings per client
    existing = get_bookings(for_chat_id=client_chat_id, status="pending")
    if len(existing) >= 2:
        logger.warning(f"Client {client_chat_id} has {len(existing)} pending bookings, rejecting")
        return None
    sb_req, sb_query = _init_sb()
    booking = {
        "client_chat_id": client_chat_id,
        "masseur_chat_id": masseur_chat_id,
        "service_name": service_name,
        "duration_min": duration_min,
        "slot_date": slot_date,
        "start_time": start_time,
        "status": "pending",
        "is_first_visit": is_first_visit,
        "client_note": note,
        "client_username": client_username,
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
    bookings.append(booking)
    _save_json(BOOKINGS_PATH, bookings)
    booking_id = booking.get("id")
    errors = []
    if sb_req:
        try:
            from core.notifier import notify_booking_created
            notify_booking_created(client_chat_id, masseur_chat_id, service_name, slot_date, start_time, client_username, booking_id)
        except Exception as e:
            logger.warning(f"Notify create failed: {e}")
            errors.append("notify")
    if errors:
        booking["_errors"] = errors
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
                logger.warning(f"Notify confirm failed: {e}")
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
                logger.warning(f"Notify cancel failed: {e}")
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
        if isinstance(result, list) and result:
            sb_result = result
            return result
    bookings = _load_json(BOOKINGS_PATH)
    result = bookings
    if for_chat_id:
        key = "masseur_chat_id" if by_masseur else "client_chat_id"
        result = [b for b in result if b.get(key) == for_chat_id]
    if status:
        result = [b for b in result if b.get("status") == status]
    return sorted(result, key=lambda x: x.get("created_at", 0), reverse=True)[:limit]


def get_masseur_slots(masseur_id: int, slot_date: str) -> List[Dict[str, Any]]:
    """Get ALL slots for a masseur on a date with status and booking info."""
    slots = _load_json(SLOTS_PATH)
    bookings = _load_json(BOOKINGS_PATH)
    booking_map = {}
    for b in bookings:
        bid = b.get("id") or b.get("booking_id")
        if bid:
            booking_map[bid] = b
    result = []
    for s in slots:
        if s.get("masseur_chat_id") == masseur_id and s.get("slot_date") == slot_date:
            bid = s.get("booking_id", 0)
            status = s.get("status", "free")
            entry = {
                "start_time": s["start_time"],
                "duration_min": s.get("duration_min", 30),
                "status": status,
                "booking_id": bid,
            }
            if bid and bid in booking_map:
                entry["service_name"] = booking_map[bid].get("service_name", "—")
                entry["client_chat_id"] = booking_map[bid].get("client_chat_id")
            result.append(entry)
    result.sort(key=lambda x: x["start_time"])
    return result


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
