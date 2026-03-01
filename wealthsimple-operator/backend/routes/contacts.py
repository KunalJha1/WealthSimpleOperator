from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from db import get_db
from models import Alert, AlertStatus, Client, ContactScheduleEntry, ContactScheduleResponse, MeetingNote, Priority

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("/schedule", response_model=ContactScheduleResponse)
def get_contact_schedule(db: Session = Depends(get_db)) -> ContactScheduleResponse:
    """
    Get contact schedule grouped by urgency for all clients.

    Urgency calculated as:
    - OVERDUE: HIGH alert AND no contact in > 5 days
    - DUE_SOON: MEDIUM alert AND no contact in > 10 days
    - UPCOMING: LOW alert AND no contact in > 21 days
    """
    # Bulk load all clients with active alerts (avoid N+1)
    from sqlalchemy import func, desc

    # Get all clients that have open/escalated alerts
    clients_with_alerts = (
        db.query(Client)
        .join(Alert, Client.id == Alert.client_id)
        .filter(Alert.status.in_([AlertStatus.OPEN, AlertStatus.ESCALATED]))
        .distinct()
        .all()
    )

    # Bulk load all alerts for these clients
    client_ids = [c.id for c in clients_with_alerts]
    alerts_by_client = {}
    if client_ids:
        alerts = (
            db.query(Alert)
            .filter(
                Alert.client_id.in_(client_ids),
                Alert.status.in_([AlertStatus.OPEN, AlertStatus.ESCALATED])
            )
            .all()
        )
        for alert in alerts:
            if alert.client_id not in alerts_by_client:
                alerts_by_client[alert.client_id] = []
            alerts_by_client[alert.client_id].append(alert)

    # Bulk load latest meeting notes
    latest_notes_subquery = (
        db.query(
            MeetingNote.client_id,
            func.max(MeetingNote.meeting_date).label("latest_date")
        )
        .filter(MeetingNote.client_id.in_(client_ids))
        .group_by(MeetingNote.client_id)
        .subquery()
    )

    latest_notes = (
        db.query(MeetingNote)
        .join(latest_notes_subquery,
              (MeetingNote.client_id == latest_notes_subquery.c.client_id) &
              (MeetingNote.meeting_date == latest_notes_subquery.c.latest_date))
        .all()
    )
    notes_by_client = {note.client_id: note for note in latest_notes}

    entries: List[ContactScheduleEntry] = []

    for client in clients_with_alerts:
        open_alerts = alerts_by_client.get(client.id, [])

        if not open_alerts:
            continue  # Skip if no active alerts

        # Get highest priority alert
        priority_order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
        highest_priority = min(
            (alert.priority for alert in open_alerts),
            key=lambda p: priority_order.get(p, 3),
            default=Priority.LOW
        )

        # Get latest meeting note
        latest_meeting_note = notes_by_client.get(client.id)

        # Calculate days since contact
        if latest_meeting_note:
            days_since_contact = (datetime.utcnow() - latest_meeting_note.meeting_date).days
        else:
            days_since_contact = 999  # Very old, no contact

        # Determine urgency
        if highest_priority == Priority.HIGH and days_since_contact > 5:
            urgency = "OVERDUE"
        elif highest_priority == Priority.MEDIUM and days_since_contact > 10:
            urgency = "DUE_SOON"
        elif highest_priority == Priority.LOW and days_since_contact > 21:
            urgency = "UPCOMING"
        else:
            urgency = "UPCOMING"  # Default to upcoming

        # Suggested action and channel based on priority
        if highest_priority == Priority.HIGH:
            suggested_action = "Review alert details and discuss portfolio rebalancing strategy"
            suggested_channel = "phone"
        elif highest_priority == Priority.MEDIUM:
            suggested_action = "Schedule call to discuss risk profile alignment"
            suggested_channel = "email_then_call"
        else:
            suggested_action = "Quarterly check-in on portfolio performance"
            suggested_channel = "email"

        entry = ContactScheduleEntry(
            client_id=client.id,
            client_name=client.name,
            email=client.email,
            segment=client.segment,
            urgency=urgency,
            alert_count=len(open_alerts),
            highest_priority=highest_priority.value,
            days_since_contact=days_since_contact,
            suggested_action=suggested_action,
            suggested_channel=suggested_channel
        )
        entries.append(entry)

    # Sort by urgency priority, then by days_since_contact (desc)
    urgency_order = {"OVERDUE": 0, "DUE_SOON": 1, "UPCOMING": 2}
    entries.sort(
        key=lambda e: (urgency_order.get(e.urgency, 3), -e.days_since_contact)
    )

    # Count by urgency
    overdue_count = sum(1 for e in entries if e.urgency == "OVERDUE")
    due_soon_count = sum(1 for e in entries if e.urgency == "DUE_SOON")
    upcoming_count = sum(1 for e in entries if e.urgency == "UPCOMING")

    return ContactScheduleResponse(
        entries=entries,
        overdue_count=overdue_count,
        due_soon_count=due_soon_count,
        upcoming_count=upcoming_count
    )
