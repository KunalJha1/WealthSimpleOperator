from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from db import get_db
from models import Alert, AlertStatus, Client, ContactScheduleEntry, ContactScheduleResponse, MeetingNote, MeetingNoteType, Portfolio, Priority, FollowUpDraft, FollowUpDraftStatus, AuditEvent
from ai.provider import get_provider

router = APIRouter(prefix="/contacts", tags=["contacts"])


# Pydantic schemas
class CallScriptDraft(BaseModel):
    client_id: int
    client_name: str
    script: str
    key_talking_points: List[str]
    provider: str


class EmailDraft(BaseModel):
    client_id: int
    client_name: str
    subject: str
    body: str
    key_points: List[str]
    provider: str


class ActivityLogEntry(BaseModel):
    client_id: int
    client_name: str
    title: str
    summary: str
    meeting_date: datetime


class DraftApprovalRequest(BaseModel):
    client_id: int
    actor: str = "advisor"
    notes: Optional[str] = None


class ApprovalResponse(BaseModel):
    success: bool
    message: str
    meeting_note_id: Optional[int] = None


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


@router.post("/generate-call-script", response_model=CallScriptDraft)
def generate_call_script(client_id: int, db: Session = Depends(get_db)) -> CallScriptDraft:
    """Generate AI call script draft for advisor approval."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get latest open alerts
    open_alerts = (
        db.query(Alert)
        .filter(
            Alert.client_id == client_id,
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.ESCALATED])
        )
        .order_by(Alert.priority)
        .all()
    )

    # Get latest meeting note for days_since_contact
    latest_meeting_note = (
        db.query(MeetingNote)
        .filter(MeetingNote.client_id == client_id)
        .order_by(MeetingNote.meeting_date.desc())
        .first()
    )

    if latest_meeting_note:
        days_since_contact = (datetime.utcnow() - latest_meeting_note.meeting_date).days
    else:
        days_since_contact = 999

    # Get primary portfolio AUM
    primary_portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.client_id == client_id)
        .order_by(Portfolio.total_value.desc())
        .first()
    )
    portfolio_aum = primary_portfolio.total_value if primary_portfolio else 0.0

    # Build alert summaries for context
    alert_summaries = []
    for alert in open_alerts[:3]:
        main_reason = alert.reasoning_bullets[0] if alert.reasoning_bullets else "Portfolio review needed"
        alert_summaries.append(f"[{alert.priority}] {main_reason}")

    # Build call context for provider
    call_context = {
        "client_name": client.name,
        "segment": client.segment,
        "risk_profile": client.risk_profile,
        "aum": portfolio_aum,
        "days_since_contact": days_since_contact,
        "alert_summaries": alert_summaries,
    }

    # Generate call script using AI provider
    provider = get_provider()
    content = provider.generate_call_script(call_context)

    return CallScriptDraft(
        client_id=client_id,
        client_name=client.name,
        script=content.script,
        key_talking_points=content.key_talking_points,
        provider=provider.name
    )


@router.post("/generate-email-draft", response_model=EmailDraft)
def generate_email_draft(client_id: int, db: Session = Depends(get_db)) -> EmailDraft:
    """Generate AI email draft for advisor approval."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get latest open alerts
    open_alerts = (
        db.query(Alert)
        .filter(
            Alert.client_id == client_id,
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.ESCALATED])
        )
        .order_by(Alert.priority)
        .all()
    )

    # Get latest meeting note for days_since_contact
    latest_meeting_note = (
        db.query(MeetingNote)
        .filter(MeetingNote.client_id == client_id)
        .order_by(MeetingNote.meeting_date.desc())
        .first()
    )

    if latest_meeting_note:
        days_since_contact = (datetime.utcnow() - latest_meeting_note.meeting_date).days
    else:
        days_since_contact = 999

    # Build alert summaries for context
    alert_summaries = []
    for alert in open_alerts[:3]:
        main_reason = alert.reasoning_bullets[0] if alert.reasoning_bullets else "Portfolio adjustment recommended"
        alert_summaries.append(f"[{alert.priority}] {main_reason}")

    # Build email context for provider
    email_context = {
        "client_name": client.name,
        "segment": client.segment,
        "risk_profile": client.risk_profile,
        "days_since_contact": days_since_contact,
        "alert_summaries": alert_summaries,
    }

    # Generate email draft using AI provider
    provider = get_provider()
    content = provider.generate_email_draft(email_context)

    return EmailDraft(
        client_id=client_id,
        client_name=client.name,
        subject=content.subject,
        body=content.body,
        key_points=content.key_points,
        provider=provider.name
    )


@router.post("/approve-call-scheduled", response_model=ApprovalResponse)
def approve_call_scheduled(req: DraftApprovalRequest, db: Session = Depends(get_db)) -> ApprovalResponse:
    """Advisor approves and schedules call - creates meeting note."""
    client = db.query(Client).filter(Client.id == req.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Create meeting note for call
    meeting_note = MeetingNote(
        client_id=req.client_id,
        title=f"Scheduled Call - {datetime.utcnow().strftime('%B %d, %Y')}",
        meeting_date=datetime.utcnow(),
        note_body="Call scheduled for portfolio review discussion.",
        meeting_type=MeetingNoteType.CALL
    )
    db.add(meeting_note)

    # Log audit event
    audit_event = AuditEvent(
        event_type="contact_action",
        actor=req.actor,
        details={
            "action": "call_scheduled",
            "client_id": req.client_id,
            "client_name": client.name
        }
    )
    db.add(audit_event)

    db.commit()

    return ApprovalResponse(
        success=True,
        message=f"Call scheduled with {client.name}",
        meeting_note_id=meeting_note.id
    )


@router.post("/approve-email-sent", response_model=ApprovalResponse)
def approve_email_sent(req: DraftApprovalRequest, db: Session = Depends(get_db)) -> ApprovalResponse:
    """Advisor approves and sends email - creates follow-up draft record."""
    client = db.query(Client).filter(Client.id == req.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Create meeting note for email
    meeting_note = MeetingNote(
        client_id=req.client_id,
        title=f"Email Sent - {datetime.utcnow().strftime('%B %d, %Y')}",
        meeting_date=datetime.utcnow(),
        note_body="Outreach email sent to client.",
        meeting_type=MeetingNoteType.EMAIL
    )
    db.add(meeting_note)

    # Log audit event
    audit_event = AuditEvent(
        event_type="contact_action",
        actor=req.actor,
        details={
            "action": "email_sent",
            "client_id": req.client_id,
            "client_name": client.name
        }
    )
    db.add(audit_event)

    db.commit()

    return ApprovalResponse(
        success=True,
        message=f"Email sent to {client.name}",
        meeting_note_id=meeting_note.id
    )


@router.post("/approve-activity-logged", response_model=ApprovalResponse)
def approve_activity_logged(req: DraftApprovalRequest, db: Session = Depends(get_db)) -> ApprovalResponse:
    """Advisor logs activity - creates meeting note record."""
    client = db.query(Client).filter(Client.id == req.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Create meeting note for activity
    note_body = req.notes or "Contact activity recorded."
    meeting_note = MeetingNote(
        client_id=req.client_id,
        title=f"Activity Logged - {datetime.utcnow().strftime('%B %d, %Y')}",
        meeting_date=datetime.utcnow(),
        note_body=note_body,
        meeting_type=MeetingNoteType.NOTE
    )
    db.add(meeting_note)

    # Log audit event
    audit_event = AuditEvent(
        event_type="contact_action",
        actor=req.actor,
        details={
            "action": "activity_logged",
            "client_id": req.client_id,
            "client_name": client.name
        }
    )
    db.add(audit_event)

    db.commit()

    return ApprovalResponse(
        success=True,
        message=f"Activity logged for {client.name}",
        meeting_note_id=meeting_note.id
    )
