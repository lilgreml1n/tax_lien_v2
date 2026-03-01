"""
LienHunter Scheduler
Background thread that runs daily at 8am and sends auction reminders.

Reminder windows: 7 days out, 3 days out, 1 day out, day-of.
Tracks which reminders were already sent via columns on calendar_events.
"""
import threading
import time
from datetime import date, datetime, timedelta

from sqlalchemy import text

from app.database import engine
from app.notifications import send_reminder


REMINDER_DAYS = [7, 3, 1, 0]  # days before event to send reminders

# Column name → days before event
REMINDER_COLS = {
    "reminder_7d_sent": 7,
    "reminder_3d_sent": 3,
    "reminder_1d_sent": 1,
    "reminder_0d_sent": 0,
}


def notifications_enabled() -> bool:
    """Check the system_settings toggle."""
    try:
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT value FROM system_settings WHERE key_name = 'notifications_enabled'"
            )).scalar()
            return str(row).lower() == "true"
    except Exception:
        return True  # default on if DB unreachable


def check_and_send_reminders():
    """Query upcoming events and send any unsent reminders."""
    if not notifications_enabled():
        print("[Scheduler] Notifications disabled — skipping.", flush=True)
        return

    today = date.today()
    window_end = today + timedelta(days=8)  # look 8 days ahead

    print(f"[Scheduler] Checking reminders for {today}...", flush=True)

    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT id, state, county, event_date, event_type, url, notes,
                   reminder_7d_sent, reminder_3d_sent, reminder_1d_sent, reminder_0d_sent
            FROM calendar_events
            WHERE event_date BETWEEN :today AND :window_end
            ORDER BY event_date ASC
        """), {"today": today, "window_end": window_end}).mappings().all()

        for row in rows:
            row = dict(row)
            event_date = row["event_date"]
            if isinstance(event_date, datetime):
                event_date = event_date.date()
            days_until = (event_date - today).days

            for col, threshold in REMINDER_COLS.items():
                if days_until == threshold and not row.get(col):
                    sent = send_reminder(
                        county=row["county"],
                        state=row["state"],
                        event_date=event_date,
                        event_type=row["event_type"],
                        days_until=days_until,
                        url=row.get("url"),
                        notes=row.get("notes"),
                    )
                    if sent:
                        conn.execute(text(
                            f"UPDATE calendar_events SET {col} = 1 WHERE id = :id"
                        ), {"id": row["id"]})

    print(f"[Scheduler] Reminder check complete.", flush=True)


def _scheduler_loop():
    """Background thread: wake up every hour, fire at 8am local time."""
    print("[Scheduler] Started — will send reminders daily at 8am.", flush=True)

    # Run once at startup so a freshly deployed container catches up
    try:
        check_and_send_reminders()
    except Exception as e:
        print(f"[Scheduler] Startup check failed: {e}", flush=True)

    while True:
        now = datetime.now()
        # Sleep until next 8am
        next_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= next_8am:
            next_8am += timedelta(days=1)
        sleep_secs = (next_8am - now).total_seconds()
        time.sleep(sleep_secs)

        try:
            check_and_send_reminders()
        except Exception as e:
            print(f"[Scheduler] Reminder check failed: {e}", flush=True)


def start_scheduler():
    """Start the background scheduler thread. Call once from app startup."""
    t = threading.Thread(target=_scheduler_loop, daemon=True, name="reminder-scheduler")
    t.start()
