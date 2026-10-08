"""Seed script: populates Mem0 with realistic mock data from all four sources.

Run this before testing the agent to give it personal context to retrieve.
Usage: python -m src.ingestion.seed
"""

from src.ingestion.adapters import (
    ingest_email,
    ingest_calendar_event,
    ingest_slack_message,
    ingest_webex_message,
)

USER_ID = "demo-user"


def seed_emails():
    """Seed sample emails."""
    emails = [
        {
            "subject": "Q4 Budget Review - Action Items",
            "sender": "sarah.chen@company.com",
            "body": (
                "Hi, following up on our budget meeting. The Q4 allocation for the "
                "Safe School project is $45,000. Please submit your department estimates "
                "by October 15th. I've attached the template."
            ),
            "date": "2026-10-02",
        },
        {
            "subject": "Re: Vendor Selection for IoT Gate Devices",
            "sender": "james.okafor@company.com",
            "body": (
                "I've narrowed it down to two vendors: SecureGate Pro ($1,200/unit) "
                "and SmartAccess ($950/unit). SecureGate has better APIs but SmartAccess "
                "has a longer warranty. Let's discuss in Thursday's standup."
            ),
            "date": "2026-10-03",
        },
        {
            "subject": "Team Offsite - Save the Date",
            "sender": "hr@company.com",
            "body": (
                "Our annual team offsite is scheduled for November 15-17 at the "
                "Lagos Continental Hotel. Please confirm your attendance by October 20th."
            ),
            "date": "2026-10-04",
        },
    ]
    results = []
    for e in emails:
        r = ingest_email(USER_ID, **e)
        results.append(r)
        print(f"  Ingested email: {e['subject']}")
    return results


def seed_calendar():
    """Seed sample calendar events."""
    events = [
        {
            "title": "Q4 Budget Review",
            "start": "2026-10-10T10:00",
            "end": "2026-10-10T11:30",
            "attendees": ["sarah.chen@company.com", "james.okafor@company.com"],
            "location": "Conference Room B",
        },
        {
            "title": "Safe School Sprint Planning",
            "start": "2026-10-07T14:00",
            "end": "2026-10-07T15:00",
            "attendees": [
                "dev-team@company.com",
                "product@company.com",
            ],
            "location": "Zoom",
        },
        {
            "title": "1:1 with Sarah (Manager)",
            "start": "2026-10-08T09:00",
            "end": "2026-10-08T09:30",
            "attendees": ["sarah.chen@company.com"],
        },
        {
            "title": "IoT Vendor Demo - SecureGate",
            "start": "2026-10-11T15:00",
            "end": "2026-10-11T16:00",
            "attendees": ["james.okafor@company.com", "vendor@securegate.io"],
            "location": "Webex",
        },
    ]
    results = []
    for e in events:
        r = ingest_calendar_event(USER_ID, **e)
        results.append(r)
        print(f"  Ingested calendar: {e['title']}")
    return results


def seed_slack():
    """Seed sample Slack messages."""
    messages = [
        {
            "channel": "safe-school-dev",
            "sender": "james.okafor",
            "text": (
                "FYI the QR attendance feature is passing all tests now. "
                "Ready for staging deployment whenever you give the go-ahead."
            ),
            "timestamp": "2026-10-04T11:23",
        },
        {
            "channel": "general",
            "sender": "sarah.chen",
            "text": (
                "Reminder: department budget estimates are due October 15. "
                "No extensions this quarter."
            ),
            "timestamp": "2026-10-03T16:45",
        },
        {
            "channel": "safe-school-dev",
            "sender": "ada.nwosu",
            "text": (
                "Found a bug in the pickup pass token validation. "
                "Tokens are not expiring after 10 minutes. Looking into it."
            ),
            "timestamp": "2026-10-05T09:12",
        },
    ]
    results = []
    for m in messages:
        r = ingest_slack_message(USER_ID, **m)
        results.append(r)
        print(f"  Ingested Slack: #{m['channel']} from {m['sender']}")
    return results


def seed_webex():
    """Seed sample Webex messages."""
    messages = [
        {
            "space": "KudEgOwo Platform",
            "sender": "james.okafor",
            "text": (
                "The gate device heartbeat threshold is set to 5 minutes. "
                "If we go lower, we'll get too many false OFFLINE alerts."
            ),
            "timestamp": "2026-10-04T14:30",
        },
        {
            "space": "Leadership Sync",
            "sender": "sarah.chen",
            "text": (
                "Compliance audit is scheduled for November 1st. "
                "All six pillars need to be documented by then."
            ),
            "timestamp": "2026-10-05T10:00",
        },
    ]
    results = []
    for m in messages:
        r = ingest_webex_message(USER_ID, **m)
        results.append(r)
        print(f"  Ingested Webex: '{m['space']}' from {m['sender']}")
    return results


def seed_all():
    """Run all seeders."""
    print("Seeding Mem0 with mock personal context data...\n")

    print("Emails:")
    seed_emails()

    print("\nCalendar events:")
    seed_calendar()

    print("\nSlack messages:")
    seed_slack()

    print("\nWebex messages:")
    seed_webex()

    print("\nSeeding complete. The agent now has personal context to retrieve.")


if __name__ == "__main__":
    seed_all()
