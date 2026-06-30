"""
PATHS Backend — Outreach availability + slot computation.

Given a list of HR availability windows (day-of-week + start/end times) and
an interview duration + buffer, generates a flat list of timezone-aware
candidate-facing slots over the next N days, skipping any overlap with
already-booked sessions for the same HR user.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]


@dataclass
class AvailabilityWindowDTO:
    day_of_week: int           # 0=Mon ... 6=Sun
    start_time: str            # "HH:MM"
    end_time: str              # "HH:MM"
    timezone: str = "UTC"


@dataclass
class Slot:
    start: datetime
    end: datetime
    timezone: str

    def to_dict(self) -> dict[str, str]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "timezone": self.timezone,
        }


def _tz(name: str):
    if ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001
        return timezone.utc


def _parse_hhmm(value: str) -> time:
    if not value:
        return time(0, 0)
    parts = value.split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    return time(hour=max(0, min(23, h)), minute=max(0, min(59, m)))


def generate_slots(
    *,
    windows: Iterable[AvailabilityWindowDTO],
    duration_minutes: int = 30,
    buffer_minutes: int = 10,
    horizon_days: int = 14,
    now: datetime | None = None,
    busy_intervals: Iterable[tuple[datetime, datetime]] | None = None,
    timezone_name: str = "UTC",
) -> list[Slot]:
    """Generate a flat list of bookable slots.

    Args:
        windows: HR availability windows (per day-of-week).
        duration_minutes: interview length.
        buffer_minutes: additional gap added after each slot before the
            next one starts.
        horizon_days: how many calendar days to expose to the candidate.
        now: current time (defaults to UTC now). Slots in the past are
            never returned.
        busy_intervals: list of (start, end) intervals to subtract — used
            to skip slots that overlap an already-booked outreach.
        timezone_name: candidate-facing timezone (output ISO strings carry
            this offset).
    """
    duration = max(5, int(duration_minutes))
    buffer = max(0, int(buffer_minutes))
    horizon = max(1, int(horizon_days))
    now_utc = now or datetime.now(timezone.utc)
    out_tz = _tz(timezone_name)
    busy = sorted(
        ((s, e) for s, e in (busy_intervals or []) if s and e and e > s),
        key=lambda x: x[0],
    )

    slots: list[Slot] = []
    today = now_utc.astimezone(out_tz).date()
    for offset in range(0, horizon):
        day = today + timedelta(days=offset)
        weekday = day.weekday()  # 0=Mon
        for w in windows:
            if w.day_of_week != weekday:
                continue
            window_tz = _tz(w.timezone or timezone_name)
            start_local = datetime.combine(day, _parse_hhmm(w.start_time), tzinfo=window_tz)
            end_local = datetime.combine(day, _parse_hhmm(w.end_time), tzinfo=window_tz)
            if end_local <= start_local:
                continue
            cursor = start_local
            step = timedelta(minutes=duration + buffer)
            while cursor + timedelta(minutes=duration) <= end_local:
                slot_start = cursor.astimezone(timezone.utc)
                slot_end = slot_start + timedelta(minutes=duration)
                if slot_start <= now_utc:
                    cursor += step
                    continue
                if _overlaps_busy(slot_start, slot_end, busy):
                    cursor += step
                    continue
                slots.append(
                    Slot(
                        start=slot_start.astimezone(out_tz),
                        end=slot_end.astimezone(out_tz),
                        timezone=timezone_name,
                    )
                )
                cursor += step
    return slots


def _overlaps_busy(
    start: datetime,
    end: datetime,
    busy: list[tuple[datetime, datetime]],
) -> bool:
    for b_start, b_end in busy:
        if start < b_end and b_start < end:
            return True
    return False


__all__ = ["AvailabilityWindowDTO", "Slot", "generate_slots"]
