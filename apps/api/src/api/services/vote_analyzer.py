from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from shared_schemas.vote import MeetingSuggestion, VoteTally


def compute_tally(
    votes: list,
    options: list,
) -> list[VoteTally]:
    """Compute vote counts per option."""
    option_map: dict[UUID, dict] = {}
    for opt in options:
        option_map[opt.id] = {
            "option_id": opt.id,
            "option_label": opt.label,
            "count": 0,
            "voters": [],
        }

    for vote in votes:
        entry = option_map.get(vote.option_id)
        if entry:
            entry["count"] += 1
            entry["voters"].append(vote.voter_name)

    total = len(votes) if votes else 1  # avoid division by zero

    result = []
    for opt in options:
        entry = option_map[opt.id]
        result.append(
            VoteTally(
                option_id=entry["option_id"],
                option_label=entry["option_label"],
                count=entry["count"],
                percentage=round(entry["count"] / total * 100, 1) if votes else 0,
                voters=entry["voters"],
            )
        )
    return result


def detect_split(tally: list[VoteTally], threshold: float = 0.5) -> bool:
    """Return True if no option has a majority (>threshold)."""
    if not tally:
        return False
    for item in tally:
        if item.percentage > threshold * 100:
            return False
    return True


def _next_business_day(from_date: datetime) -> datetime:
    """Get next business day (Mon-Fri)."""
    d = from_date + timedelta(days=1)
    while d.weekday() >= 5:  # Saturday=5, Sunday=6
        d += timedelta(days=1)
    return d.replace(hour=10, minute=0, second=0, microsecond=0)


def generate_ics(question: str, tally: list[VoteTally]) -> str:
    """Generate ICS calendar event string."""
    now = datetime.utcnow()
    start = _next_business_day(now)
    end = start + timedelta(minutes=30)

    tally_lines = []
    for t in tally:
        tally_lines.append(f"  - {t.option_label}: {t.count} votes ({t.percentage}%)")
    tally_text = "\\n".join(tally_lines)

    description = (
        f"Vote Split Resolution Meeting\\n\\n"
        f"Question: {question}\\n\\n"
        f"Current Results:\\n{tally_text}\\n\\n"
        f"Please discuss and reach consensus."
    )

    uid = f"{start.strftime('%Y%m%dT%H%M%S')}-vote-split@thirdy"
    dtstart = start.strftime("%Y%m%dT%H%M%SZ")
    dtend = end.strftime("%Y%m%dT%H%M%SZ")
    dtstamp = now.strftime("%Y%m%dT%H%M%SZ")

    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Thirdy//Vote Split//EN\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{dtstamp}\r\n"
        f"DTSTART:{dtstart}\r\n"
        f"DTEND:{dtend}\r\n"
        f"SUMMARY:Vote Split Resolution: {question[:80]}\r\n"
        f"DESCRIPTION:{description}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


def generate_meeting_suggestion(
    question: str,
    tally: list[VoteTally],
) -> MeetingSuggestion:
    """Generate a meeting suggestion with ICS content."""
    tally_lines = []
    for t in tally:
        tally_lines.append(f"- {t.option_label}: {t.count} votes ({t.percentage}%)")
    tally_text = "\n".join(tally_lines)

    subject = f"Vote Split Resolution: {question[:80]}"
    description = (
        f"The vote on the following question resulted in a split:\n\n"
        f"Question: {question}\n\n"
        f"Results:\n{tally_text}\n\n"
        f"A meeting is suggested to discuss and reach consensus."
    )

    return MeetingSuggestion(
        subject=subject,
        description=description,
        ics_content=generate_ics(question, tally),
    )
