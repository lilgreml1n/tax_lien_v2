from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from app.database import engine

router = APIRouter(prefix="/calendar", tags=["Calendar"])


class EventIn(BaseModel):
    state: str
    county: Optional[str] = None
    event_date: date
    event_type: str = "auction"
    url: Optional[str] = None
    notes: Optional[str] = None


class EventOut(EventIn):
    id: int
    created_at: Optional[str] = None


@router.post("/events", tags=["Calendar"])
def create_event(event: EventIn):
    """Add a tax lien auction or deadline to the calendar."""
    with engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO calendar_events (state, county, event_date, event_type, url, notes)
                    VALUES (:state, :county, :event_date, :event_type, :url, :notes)"""),
            event.model_dump()
        )
        row = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    return {"id": row, "status": "created"}


@router.get("/events", tags=["Calendar"])
def list_events(state: Optional[str] = None, month: Optional[int] = None, year: Optional[int] = None, limit: int = 50):
    """List calendar events. Filter by state, month, year."""
    query = "SELECT * FROM calendar_events WHERE 1=1"
    params = {}

    if state:
        query += " AND state = :state"
        params["state"] = state
    if month and year:
        query += " AND MONTH(event_date) = :month AND YEAR(event_date) = :year"
        params["month"] = month
        params["year"] = year
    elif month:
        query += " AND MONTH(event_date) = :month"
        params["month"] = month

    query += " ORDER BY event_date ASC LIMIT :limit"
    params["limit"] = limit

    with engine.connect() as conn:
        rows = conn.execute(text(query), params).mappings().all()
    return rows


@router.get("/this-month", tags=["Calendar"])
def this_month(state: Optional[str] = None):
    """What tax lien events are happening this month?"""
    now = datetime.now()
    return list_events(state=state, month=now.month, year=now.year)


@router.get("/next-month", tags=["Calendar"])
def next_month(state: Optional[str] = None):
    """What tax lien events are coming next month?"""
    now = datetime.now()
    m = now.month + 1
    y = now.year
    if m > 12:
        m = 1
        y += 1
    return list_events(state=state, month=m, year=y)


@router.delete("/events/{event_id}", tags=["Calendar"])
def delete_event(event_id: int):
    """Remove a calendar event."""
    with engine.begin() as conn:
        result = conn.execute(text("DELETE FROM calendar_events WHERE id = :id"), {"id": event_id})
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"status": "deleted"}


# ── Notification toggle ───────────────────────────────────────────────────────

@router.get("/notifications/status", tags=["Calendar"])
def notifications_status():
    """Check whether auction reminders are enabled or disabled."""
    with engine.connect() as conn:
        val = conn.execute(text(
            "SELECT value FROM system_settings WHERE key_name = 'notifications_enabled'"
        )).scalar()
    enabled = str(val).lower() == "true"
    return {"notifications_enabled": enabled, "status": "on" if enabled else "off"}


@router.post("/notifications/enable", tags=["Calendar"])
def enable_notifications():
    """Turn auction email reminders ON."""
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE system_settings SET value = 'true' WHERE key_name = 'notifications_enabled'"
        ))
    return {"notifications_enabled": True, "status": "Reminders turned ON"}


@router.post("/notifications/disable", tags=["Calendar"])
def disable_notifications():
    """Turn auction email reminders OFF."""
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE system_settings SET value = 'false' WHERE key_name = 'notifications_enabled'"
        ))
    return {"notifications_enabled": False, "status": "Reminders turned OFF"}
