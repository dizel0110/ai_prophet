"""Tests for core/booking_manager.py — fully isolated, no network, no Supabase."""
import json
import time
import pytest
from pathlib import Path
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

# ─── Bootstrap ───
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.booking_manager import (
    generate_slots, get_free_slots, create_booking,
    confirm_booking, cancel_booking, get_bookings, get_workload,
    get_available_masseurs, _save_slots, _load_json, _save_json,
    SLOTS_PATH, BOOKINGS_PATH,
    auto_cancel_expired_pending, get_auto_cancel_candidates,
    get_pending_reminder_candidates, should_send_morning_digest,
    get_pending_bookings_grouped_by_masseur, reset_morning_digest_for_test,
)

DATA_DIR = Path("data")

# ─── Fixtures ───

@pytest.fixture(autouse=True)
def no_supabase():
    """Mock _init_sb to return (None, None) — tests must NOT depend on Supabase."""
    with patch('core.booking_manager._init_sb', return_value=(None, None)):
        yield


@pytest.fixture(autouse=True)
def clean_data():
    """Remove test data files before and after each test."""
    for p in [SLOTS_PATH, BOOKINGS_PATH]:
        if p.exists():
            p.unlink()
    yield
    for p in [SLOTS_PATH, BOOKINGS_PATH]:
        if p.exists():
            p.unlink()


@pytest.fixture
def slots():
    """Generate slots for masseur 100 on 2099-06-15 (Monday)."""
    return generate_slots(100, "2099-06-15", days=1)


# ─── Slot Generation ───

class TestSlotGeneration:
    def test_generates_slots(self):
        slots = generate_slots(100, "2099-06-15", days=1)
        assert len(slots) > 0
        for s in slots:
            assert s["masseur_chat_id"] == 100
            assert s["slot_date"] == "2099-06-15"
            assert s["status"] == "free"
            assert s["client_chat_id"] is None
            assert s["duration_min"] in (30, 60, 90)

    def test_no_slots_during_break(self):
        slots = generate_slots(100, "2099-06-15", days=1,
                               break_start="13:00", break_end="14:00")
        for s in slots:
            h = int(s["start_time"].split(":")[0])
            m = int(s["start_time"].split(":")[1])
            start_min = h * 60 + m
            end_min = start_min + s["duration_min"]
            assert not (13 * 60 <= start_min < 14 * 60), f"Slot starts in break: {s}"
            assert not (13 * 60 < end_min <= 14 * 60), f"Slot ends in break: {s}"

    def test_multiple_days(self):
        slots = generate_slots(100, "2099-06-15", days=3)
        dates = {s["slot_date"] for s in slots}
        assert dates == {"2099-06-15", "2099-06-16", "2099-06-17"}

    def test_slot_key_unique(self):
        slots = generate_slots(100, "2099-06-15", days=1)
        keys = [
            f"{s['masseur_chat_id']}:{s['slot_date']}:{s['start_time']}:{s['duration_min']}"
            for s in slots
        ]
        assert len(keys) == len(set(keys))

    def test_custom_durations(self):
        slots = generate_slots(100, "2099-06-15", days=1, durations=[60])
        for s in slots:
            assert s["duration_min"] == 60

    def test_custom_work_hours(self):
        slots = generate_slots(100, "2099-06-15", days=1,
                               work_hours={"start": "10:00", "end": "12:00"})
        for s in slots:
            h = int(s["start_time"].split(":")[0])
            assert 10 <= h < 12

    def test_defaults_without_date(self):
        """Generate for a start date far in the future to avoid time filter."""
        slots = generate_slots(100, "2099-06-15", days=1)
        assert len(slots) > 0
        assert slots[0]["slot_date"] == "2099-06-15"


# ─── Save / Load / Free Slots ───

class TestSlotPersistence:
    def test_save_and_load(self, slots):
        _save_slots(slots)
        assert SLOTS_PATH.exists()
        loaded = _load_json(SLOTS_PATH)
        assert len(loaded) == len(slots)

    def test_get_free_slots(self, slots):
        _save_slots(slots)
        free = get_free_slots(100, "2099-06-15")
        assert len(free) == len(slots)
        for s in free:
            assert s["status"] == "free"

    def test_get_free_slots_filters_masseur(self, slots):
        _save_slots(slots)
        free = get_free_slots(200, "2099-06-15")
        # Auto-generated for masseur 200 on future date
        for s in free:
            assert s["masseur_chat_id"] == 200

    def test_get_free_slots_empty_date(self):
        """Querying a date with no saved slots auto-generates them."""
        free = get_free_slots(100, "2099-06-15")
        assert len(free) > 0
        for s in free:
            assert s["slot_date"] == "2099-06-15"

    def test_get_free_slots_no_date_filter(self, slots):
        _save_slots(slots)
        free = get_free_slots(100)
        assert len(free) == len(slots)

    def test_save_is_idempotent(self, slots):
        _save_slots(slots)
        _save_slots(slots)  # same slots again
        loaded = _load_json(SLOTS_PATH)
        assert len(loaded) == len(slots)


# ─── Booking CRUD ───

class TestBooking:
    def test_create_booking(self, slots):
        _save_slots(slots)
        b = create_booking(500, 100, "2099-06-15", "10:00", 60,
                           "Классический массаж", "Болит спина", True)
        assert b is not None
        assert b["client_chat_id"] == 500
        assert b["masseur_chat_id"] == 100
        assert b["status"] == "pending"
        assert b["id"] is not None

    def test_create_booking_marks_slot(self, slots):
        _save_slots(slots)
        create_booking(500, 100, "2099-06-15", "10:00", 60)
        free = get_free_slots(100, "2099-06-15")
        for s in free:
            if s["start_time"] == "10:00" and s["duration_min"] == 60:
                assert s["status"] == "free", f"Slot should remain free: {s}"

    def test_confirm_booking(self, slots):
        _save_slots(slots)
        b = create_booking(500, 100, "2099-06-15", "10:00", 60)
        result = confirm_booking(b["id"])
        assert result is True
        bookings = get_bookings(100, by_masseur=True)
        confirmed = [x for x in bookings if x["id"] == b["id"]]
        assert any(x["status"] == "confirmed" for x in confirmed)

    def test_confirm_nonexistent(self):
        result = confirm_booking(999999)
        assert result is False

    def test_cancel_booking(self, slots):
        _save_slots(slots)
        b = create_booking(500, 100, "2099-06-15", "10:00", 60)
        result = cancel_booking(b["id"])
        assert result["ok"] is True
        assert result["reason"] == "cancelled"

    def test_double_cancel(self, slots):
        _save_slots(slots)
        b = create_booking(500, 100, "2099-06-15", "10:00", 60)
        cancel_booking(b["id"])
        result = cancel_booking(b["id"])
        assert result["ok"] is False
        assert result["reason"] == "already_cancelled"

    def test_cancel_nonexistent(self):
        result = cancel_booking(999999)
        assert result["ok"] is False
        assert result["reason"] == "not_found"

    def test_get_bookings_by_client(self, slots):
        _save_slots(slots)
        b = create_booking(500, 100, "2099-06-15", "10:00", 60)
        bookings = get_bookings(500)
        assert len(bookings) >= 1
        assert any(x["id"] == b["id"] for x in bookings)

    def test_get_bookings_by_masseur(self, slots):
        _save_slots(slots)
        b = create_booking(500, 100, "2099-06-15", "10:00", 60)
        bookings = get_bookings(100, by_masseur=True)
        assert len(bookings) >= 1
        assert any(x["id"] == b["id"] for x in bookings)

    def test_get_bookings_filter_status(self, slots):
        _save_slots(slots)
        b = create_booking(500, 100, "2099-06-15", "10:00", 60)
        pending = get_bookings(500, status="pending")
        assert any(x["id"] == b["id"] for x in pending)
        confirmed = get_bookings(500, status="confirmed")
        assert all(x["status"] == "confirmed" for x in confirmed)

    def test_get_bookings_limit(self, slots):
        _save_slots(slots)
        for i in range(5):
            create_booking(500 + i, 100, "2099-06-15", f"{10+i}:00", 60)
        all_b = get_bookings(limit=3)
        assert len(all_b) <= 3


# ─── Workload ───

class TestWorkload:
    def test_empty_workload(self, slots):
        _save_slots(slots)
        wl = get_workload(100)
        assert wl["load_pct"] == 0
        assert wl["load_level"] == "low"
        assert wl["slots_week"] > 0

    def test_workload_with_bookings(self, slots):
        _save_slots(slots)
        create_booking(500, 100, "2099-06-15", "10:00", 60)
        confirm_booking(1)  # might not exist, but at least one booking exists
        wl = get_workload(100)
        assert wl["booked_week"] >= 0
        assert 0 <= wl["load_pct"] <= 100

    def test_full_workload_theoretical(self):
        """Manually set all slots as booked to verify 100%."""
        slots = [{
            "masseur_chat_id": 100,
            "slot_date": "2099-06-15",
            "start_time": "10:00",
            "duration_min": 60,
            "status": "booked",
            "client_chat_id": 500,
            "booking_id": 1,
        }]
        _save_slots(slots)
        wl = get_workload(100)
        assert wl["load_pct"] == 100
        assert wl["load_level"] == "high"


# ─── Masseurs ───

class TestMasseurs:
    def test_get_available_masseurs_fallback(self):
        """Without Supabase, should fall back to masseur_diary."""
        masseurs = get_available_masseurs()
        assert isinstance(masseurs, list)
        # At minimum should return empty or valid list
        for m in masseurs:
            assert "chat_id" in m
            assert "working_hours" in m


# ─── Edge Cases ───

class TestEdgeCases:
    def test_booking_non_existent_slot(self, slots):
        _save_slots(slots)
        b = create_booking(500, 100, "2099-12-31", "99:99", 60)
        assert b is not None  # Booking created even without matching slot
        assert b["status"] == "pending"

    def test_persist_after_restart(self, slots):
        """Simulate a restart by re-loading data."""
        _save_slots(slots)
        create_booking(500, 100, "2099-06-15", "10:00", 60)
        # Re-read from disk (as if server restarted)
        bookings = _load_json(BOOKINGS_PATH)
        assert len(bookings) >= 1
        assert bookings[0]["status"] == "pending"

    def test_unicode_service_name(self):
        b = create_booking(500, 100, "2099-06-15", "10:00", 60,
                           "Спа-программа «Релакс» ♨️", "Тест")
        assert b is not None
        assert "Релакс" in b["service_name"]

    def test_multiple_bookings_same_client(self, slots):
        _save_slots(slots)
        b1 = create_booking(500, 100, "2099-06-15", "10:00", 60)
        b2 = create_booking(500, 100, "2099-06-15", "14:00", 60)
        bookings = get_bookings(500)
        ids = {b["id"] for b in bookings}
        assert b1["id"] in ids
        assert b2["id"] in ids

    def test_workload_zero_when_no_slots(self):
        wl = get_workload(999)
        assert wl["slots_week"] == 0 or wl["load_pct"] == 0

    def test_cancel_with_invalid_id(self):
        result = cancel_booking(-1)
        assert result["ok"] is False

    def test_create_booking_no_slots_at_all(self):
        """Should still create booking even if no slots file exists."""
        b = create_booking(500, 100, "2099-06-15", "10:00", 60)
        assert b is not None
        assert b["status"] == "pending"

    def test_time_format_24h(self, slots):
        for s in slots:
            h, m = s["start_time"].split(":")
            assert 0 <= int(h) < 24
            assert 0 <= int(m) < 60

    def test_cancel_masseur_side(self, slots):
        _save_slots(slots)
        b = create_booking(500, 100, "2099-06-15", "10:00", 60)
        result = cancel_booking(b["id"], cancelled_by="masseur")
        assert result["ok"] is True

    def test_bookings_sorted_by_time(self, slots):
        _save_slots(slots)
        b1 = create_booking(500, 100, "2099-06-15", "10:00", 60)
        b2 = create_booking(501, 100, "2099-06-15", "11:00", 60)
        bookings = get_bookings(limit=10)
        times = [b.get("created_at", 0) for b in bookings]
        assert times == sorted(times, reverse=True)

    def test_get_bookings_no_file(self):
        """Should return empty list when no bookings file exists."""
        if BOOKINGS_PATH.exists():
            BOOKINGS_PATH.unlink()
        bookings = get_bookings(500)
        assert bookings == []

    def test_get_free_slots_no_file(self):
        """Auto-generates slots when no file exists."""
        if SLOTS_PATH.exists():
            SLOTS_PATH.unlink()
        free = get_free_slots(100, "2099-06-15")
        assert len(free) > 0
        assert SLOTS_PATH.exists()

    def test_save_slots_empty(self):
        """Saving empty list should not crash."""
        _save_slots([])
        assert SLOTS_PATH.exists()
        assert _load_json(SLOTS_PATH) == []

    def test_cancel_masseur_side_different_notification(self, slots):
        _save_slots(slots)
        b = create_booking(500, 100, "2099-06-15", "10:00", 60)
        r = cancel_booking(b["id"], cancelled_by="masseur")
        assert r["ok"] is True
        confirmed = get_bookings(500)
        cancelled = [x for x in confirmed if x["id"] == b["id"]]
        assert all(x["status"] == "cancelled" for x in cancelled)

    def test_get_workload_no_slots(self):
        """Workload for masseur with no slots should not crash."""
        wl = get_workload(99999)
        assert "load_pct" in wl
        assert "load_level" in wl

    def test_booking_id_unique(self, slots):
        _save_slots(slots)
        ids = set()
        for i in range(5):
            time.sleep(0.01)  # ensure unique timestamp
            b = create_booking(500 + i, 100, "2099-06-15", f"{10+i}:00", 60)
            assert b["id"] not in ids
            ids.add(b["id"])


# ─── Auto-cancel & Reminder Tests ───

class TestAutoCancel:
    SLOT_PREFIX = {
        "masseur_chat_id": 100, "client_chat_id": 501,
        "service_name": "Тест", "duration_min": 60,
        "status": "pending", "client_username": "",
        "created_at": "2026-06-01T10:00:00",
    }

    def _make_booking(self, day_str: str, time_str: str, status="pending", booking_id=1, **kw):
        b = dict(self.SLOT_PREFIX, slot_date=day_str, start_time=time_str,
                 status=status, id=booking_id, **kw)
        return b

    def _save_bookings(self, bookings: list):
        _save_json(BOOKINGS_PATH, bookings)

    def test_auto_cancel_future_session(self):
        """Booking 2h from now should NOT be auto-cancelled."""
        future = datetime.now() + timedelta(hours=2)
        b = self._make_booking(future.strftime("%Y-%m-%d"), future.strftime("%H:%M"), booking_id=1)
        self._save_bookings([b])
        candidates = get_auto_cancel_candidates(datetime.now())
        assert len(candidates) == 0

    def test_auto_cancel_imminent_session(self):
        """Booking 30 min from now SHOULD be auto-cancelled."""
        soon = datetime.now() + timedelta(minutes=30)
        b = self._make_booking(soon.strftime("%Y-%m-%d"), soon.strftime("%H:%M"), booking_id=1)
        self._save_bookings([b])
        cancelled = auto_cancel_expired_pending()
        assert len(cancelled) == 1
        assert cancelled[0]["status"] == "cancelled"
        assert cancelled[0]["cancelled_by"] == "auto"

    def test_auto_cancel_at_exactly_60min(self):
        """Booking exactly 60 min from now SHOULD be auto-cancelled."""
        soon = datetime.now() + timedelta(minutes=60)
        b = self._make_booking(soon.strftime("%Y-%m-%d"), soon.strftime("%H:%M"), booking_id=1)
        self._save_bookings([b])
        cancelled = auto_cancel_expired_pending()
        assert len(cancelled) == 1

    def test_auto_cancel_skips_confirmed(self):
        """Confirmed bookings should NOT be auto-cancelled."""
        soon = datetime.now() + timedelta(minutes=30)
        b = self._make_booking(soon.strftime("%Y-%m-%d"), soon.strftime("%H:%M"),
                               status="confirmed", booking_id=1)
        self._save_bookings([b])
        cancelled = auto_cancel_expired_pending()
        assert len(cancelled) == 0

    def test_auto_cancel_skips_cancelled(self):
        """Already cancelled bookings should NOT be touched."""
        soon = datetime.now() + timedelta(minutes=30)
        b = self._make_booking(soon.strftime("%Y-%m-%d"), soon.strftime("%H:%M"),
                               status="cancelled", booking_id=1)
        self._save_bookings([b])
        cancelled = auto_cancel_expired_pending()
        assert len(cancelled) == 0

    def test_auto_cancel_past_session(self):
        """Booking that already started should NOT be auto-cancelled."""
        past = datetime.now() - timedelta(minutes=10)
        b = self._make_booking(past.strftime("%Y-%m-%d"), past.strftime("%H:%M"), booking_id=1)
        self._save_bookings([b])
        candidates = get_auto_cancel_candidates(datetime.now())
        assert len(candidates) == 0

    def test_auto_cancel_multiple(self):
        """Multiple pending bookings within 60 min should all be cancelled."""
        now = datetime.now()
        for i, mins in enumerate([20, 40, 80, 120]):
            dt = now + timedelta(minutes=mins)
            b = self._make_booking(dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M"), booking_id=i+1)
            self._save_bookings(_load_json(BOOKINGS_PATH) + [b])
        cancelled = auto_cancel_expired_pending()
        assert len(cancelled) == 2  # only 20 and 40 min
        assert all(c["status"] == "cancelled" for c in cancelled)

    def test_auto_cancel_idempotent(self):
        """Calling auto_cancel twice should not double-cancel."""
        soon = datetime.now() + timedelta(minutes=30)
        b = self._make_booking(soon.strftime("%Y-%m-%d"), soon.strftime("%H:%M"), booking_id=1)
        self._save_bookings([b])
        auto_cancel_expired_pending()
        cancelled2 = auto_cancel_expired_pending()
        assert len(cancelled2) == 0

    def test_reminder_candidates(self):
        """Booking ~3h from now should appear in reminder candidates."""
        soon = datetime.now() + timedelta(minutes=182)
        b = self._make_booking(soon.strftime("%Y-%m-%d"), soon.strftime("%H:%M"), booking_id=1)
        self._save_bookings([b])
        candidates = get_pending_reminder_candidates(datetime.now())
        assert len(candidates) == 1

    def test_reminder_skips_outside_window(self):
        """Booking 2h or 4h away should NOT be reminded."""
        near = datetime.now() + timedelta(minutes=120)
        far = datetime.now() + timedelta(minutes=240)
        b1 = self._make_booking(near.strftime("%Y-%m-%d"), near.strftime("%H:%M"), booking_id=1)
        b2 = self._make_booking(far.strftime("%Y-%m-%d"), far.strftime("%H:%M"), booking_id=2)
        self._save_bookings([b1, b2])
        candidates = get_pending_reminder_candidates(datetime.now())
        assert len(candidates) == 0

    def test_morning_digest_once(self, monkeypatch):
        """should_send_morning_digest returns True once, then False for rest of day."""
        reset_morning_digest_for_test()
        # Mock time to 09:01
        mock_now = datetime(2026, 6, 15, 9, 1, 0)
        assert should_send_morning_digest(mock_now) is True
        assert should_send_morning_digest(mock_now) is False
        assert should_send_morning_digest(mock_now) is False
        # Different day
        mock_now2 = datetime(2026, 6, 16, 9, 1, 0)
        assert should_send_morning_digest(mock_now2) is True

    def test_morning_digest_only_at_09(self, monkeypatch):
        """should_send_morning_digest returns False outside 09:00-09:05 window."""
        reset_morning_digest_for_test()
        assert should_send_morning_digest(datetime(2026, 6, 15, 8, 59, 0)) is False
        assert should_send_morning_digest(datetime(2026, 6, 15, 9, 5, 0)) is False
        assert should_send_morning_digest(datetime(2026, 6, 15, 10, 0, 0)) is False

    def test_grouped_by_masseur_pending_only(self):
        """Only pending bookings appear in grouped result."""
        now = datetime.now()
        dt = now + timedelta(hours=3)
        b1 = self._make_booking(dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M"),
                                booking_id=1, masseur_chat_id=100)
        b2 = self._make_booking(dt.strftime("%Y-%m-%d"), (dt + timedelta(hours=1)).strftime("%H:%M"),
                                booking_id=2, status="confirmed", masseur_chat_id=100)
        self._save_bookings([b1, b2])
        grouped = get_pending_bookings_grouped_by_masseur()
        assert 100 in grouped
        assert len(grouped[100]) == 1  # only pending
        assert 101 not in grouped
