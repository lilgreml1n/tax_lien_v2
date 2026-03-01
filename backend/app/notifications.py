"""
LienHunter Notification System
Sends email reminders + Google Calendar (.ics) invites via Gmail SMTP.

Credentials loaded from env:
  LIENHUNTER_GMAIL_ADDRESS
  LIENHUNTER_GMAIL_APP_PASSWORD
"""
import os
import smtplib
import uuid
from datetime import date, datetime, timedelta
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

GMAIL_ADDRESS  = os.getenv("LIENHUNTER_GMAIL_ADDRESS", "")
GMAIL_PASSWORD = os.getenv("LIENHUNTER_GMAIL_APP_PASSWORD", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# Who gets the reminders
DEFAULT_RECIPIENTS = ["davidcorbett@gmail.com"]


def _make_ics(county: str, state: str, event_date: date, event_type: str,
              url: str = None, notes: str = None) -> str:
    """Generate a minimal .ics calendar invite string."""
    uid = str(uuid.uuid4())
    now_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    date_str = event_date.strftime("%Y%m%d")
    next_day  = (event_date + timedelta(days=1)).strftime("%Y%m%d")

    summary = f"{county} County {state} Tax Lien {event_type.title()}"
    description = notes or f"Tax lien {event_type} for {county} County, {state}."
    if url:
        description += f"\\nAuction site: {url}"

    return "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//LienHunter//EN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now_str}",
        f"DTSTART;VALUE=DATE:{date_str}",
        f"DTEND;VALUE=DATE:{next_day}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
        "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    ])


def send_reminder(county: str, state: str, event_date: date,
                  event_type: str, days_until: int,
                  url: str = None, notes: str = None,
                  recipients: list = None) -> bool:
    """
    Send an email reminder with a .ics calendar attachment.
    Returns True on success, False on failure.
    """
    if not GMAIL_ADDRESS or not GMAIL_PASSWORD:
        print("[Notifications] LIENHUNTER_GMAIL_ADDRESS or LIENHUNTER_GMAIL_APP_PASSWORD not set", flush=True)
        return False

    recipients = recipients or DEFAULT_RECIPIENTS

    if days_until == 0:
        urgency = "TODAY"
    elif days_until == 1:
        urgency = "TOMORROW"
    else:
        urgency = f"in {days_until} days"

    subject = f"🏛️ LienHunter: {county} County {state} auction {urgency} ({event_date})"

    body_lines = [
        f"<h2>Tax Lien Auction Reminder</h2>",
        f"<p><strong>County:</strong> {county} County, {state}</p>",
        f"<p><strong>Date:</strong> {event_date.strftime('%A, %B %d, %Y')}</p>",
        f"<p><strong>Type:</strong> {event_type.title()}</p>",
    ]
    if url:
        body_lines.append(f'<p><strong>Auction site:</strong> <a href="{url}">{url}</a></p>')
    if notes:
        body_lines.append(f"<p><strong>Notes:</strong> {notes}</p>")
    body_lines += [
        "<hr>",
        "<p>A calendar invite is attached. Open the .ics file to add it to Google Calendar.</p>",
        "<p><em>— LienHunter v2</em></p>",
    ]

    msg = MIMEMultipart("mixed")
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText("\n".join(body_lines), "html"))

    # Attach .ics
    ics_content = _make_ics(county, state, event_date, event_type, url, notes)
    ics_part = MIMEBase("text", "calendar", method="REQUEST", name="invite.ics")
    ics_part.set_payload(ics_content.encode("utf-8"))
    encoders.encode_base64(ics_part)
    ics_part.add_header("Content-Disposition", "attachment", filename="invite.ics")
    msg.attach(ics_part)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, recipients, msg.as_string())
        print(f"[Notifications] Sent {days_until}-day reminder → {recipients} for {county} {event_date}", flush=True)
        return True
    except Exception as e:
        print(f"[Notifications] Failed to send email: {e}", flush=True)
        return False
