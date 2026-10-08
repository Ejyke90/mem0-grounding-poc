"""Ingestion adapters: transform raw data from sources into Mem0 memories.

In production, these would connect to real APIs (IMAP, Graph API, Webex, Slack).
For this PoC, they demonstrate the ingestion pattern with mock data.
"""

from src.agent.memory_store import get_memory


def ingest_email(user_id: str, subject: str, sender: str, body: str, date: str) -> dict:
    """Ingest an email into Mem0 as a user memory."""
    mem = get_memory()
    content = f"Email from {sender} on {date}: Subject: {subject}. {body}"
    result = mem.add(
        [{"role": "user", "content": content}],
        user_id=user_id,
        metadata={
            "source": "email",
            "para_category": "resource",
            "sender": sender,
            "date": date,
        },
    )
    return {"source": "email", "subject": subject, "result": str(result)}


def ingest_calendar_event(
    user_id: str, title: str, start: str, end: str, attendees: list[str], location: str = ""
) -> dict:
    """Ingest a calendar event into Mem0 as a user memory."""
    mem = get_memory()
    attendee_str = ", ".join(attendees) if attendees else "no attendees listed"
    loc_str = f" at {location}" if location else ""
    content = (
        f"Calendar event: {title} from {start} to {end}{loc_str}. "
        f"Attendees: {attendee_str}."
    )
    result = mem.add(
        [{"role": "user", "content": content}],
        user_id=user_id,
        metadata={
            "source": "calendar",
            "para_category": "project",
            "event_title": title,
            "start": start,
        },
    )
    return {"source": "calendar", "title": title, "result": str(result)}


def ingest_slack_message(
    user_id: str, channel: str, sender: str, text: str, timestamp: str
) -> dict:
    """Ingest a Slack message into Mem0 as a user memory."""
    mem = get_memory()
    content = f"Slack message in #{channel} from {sender} ({timestamp}): {text}"
    result = mem.add(
        [{"role": "user", "content": content}],
        user_id=user_id,
        metadata={
            "source": "slack",
            "para_category": "resource",
            "channel": channel,
            "sender": sender,
        },
    )
    return {"source": "slack", "channel": channel, "result": str(result)}


def ingest_webex_message(
    user_id: str, space: str, sender: str, text: str, timestamp: str
) -> dict:
    """Ingest a Webex message into Mem0 as a user memory."""
    mem = get_memory()
    content = f"Webex message in '{space}' from {sender} ({timestamp}): {text}"
    result = mem.add(
        [{"role": "user", "content": content}],
        user_id=user_id,
        metadata={
            "source": "webex",
            "para_category": "resource",
            "space": space,
            "sender": sender,
        },
    )
    return {"source": "webex", "space": space, "result": str(result)}
