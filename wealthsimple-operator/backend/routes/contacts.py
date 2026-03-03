from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from db import get_db
from models import Alert, AlertStatus, Client, ContactScheduleEntry, ContactScheduleResponse, MeetingNote, MeetingNoteType, Priority, FollowUpDraft, FollowUpDraftStatus, AuditEvent
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

    # Generate call script using AI
    provider = get_provider()

    if not open_alerts:
        alert_context = "routine quarterly check-in on portfolio performance and alignment"
        talking_points = ["Portfolio performance review", "Goal alignment check", "Market outlook discussion"]
    else:
        # Build detailed alert context for call script
        alert_details = []
        talking_points = []
        for alert in open_alerts[:3]:
            main_reason = alert.reasoning_bullets[0] if alert.reasoning_bullets else "Portfolio review needed"
            alert_details.append(f"[{alert.priority}] {main_reason}")
            talking_points.append(f"{alert.priority} Priority: {main_reason}")

        alert_context = "\n- ".join(alert_details)

    script = f"""CALL OPENING (Friendly, Professional):
"Hi {client.name}, thanks so much for taking my call. I'm reaching out because we've completed our latest portfolio review, and I wanted to walk through some important observations with you. Do you have about 20 minutes to chat?"

[Wait for confirmation]

BRIDGE TO AGENDA:
"Great! Here's what I'd like to cover today: First, I'll walk through what our analysis revealed, then we can discuss what it means for your portfolio, and finally we'll explore if any adjustments make sense for your situation."

DETAILED DISCUSSION POINTS:
• Portfolio Analysis Findings: {alert_context}
• Market Context: "Given current market conditions, I think it's important we discuss how your allocation is positioned."
• Risk Assessment: "Let's revisit your comfort level with your current risk profile."
• Actionable Options: "I've identified a few potential strategies we could explore."

KEY QUESTIONS TO ASK:
1. "Have there been any significant changes in your financial situation or goals since we last spoke?"
2. "How are you feeling about the current market environment?"
3. "Is your portfolio still aligned with how you wanted to be invested?"
4. "What are your thoughts on the adjustments I'm suggesting?"

DISCUSSION FLOW:
1. Present the portfolio findings in context
2. Connect findings to client's stated goals and risk tolerance
3. Discuss potential solutions (don't push, explore together)
4. Confirm next steps and timeline
5. Set expectations for follow-up

HANDLING OBJECTIONS:
• If concerned about market timing: "That's a valid point. What we focus on is keeping your portfolio aligned with your goals, not predicting market moves."
• If wants to wait: "I understand. Let's schedule a follow-up to revisit this in [2-3 weeks]."
• If asks about fees: "Your investment in making adjustments is [X]. Let's discuss if the potential benefit justifies that cost."

CLOSING:
"Thanks so much for discussing this with me. Here's what we'll do next: I'll send you a detailed email with our analysis and recommendations. Take a few days to review it, and then we can reconnect to finalize any decisions. Does that work for you?"

[Confirm timing and set next meeting]

POST-CALL:
Send follow-up email with summary, recommendations, and clear next steps."""

    return CallScriptDraft(
        client_id=client_id,
        client_name=client.name,
        script=script,
        key_talking_points=talking_points,
        provider=provider.__class__.__name__
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

    if not open_alerts:
        # Fallback if no alerts
        subject = f"Quarterly Portfolio Check-in"
        body = f"""Hi {client.name},

I hope this message finds you well. As part of our ongoing commitment to managing your wealth effectively, I wanted to reach out for a brief check-in on your portfolio.

During our last review, we discussed your investment goals and risk tolerance. I'd like to ensure your current allocation continues to align with your objectives and market conditions.

This is an excellent opportunity to:
• Review your current portfolio performance and positioning
• Discuss any changes in your financial situation or goals
• Explore optimization opportunities within your investment strategy
• Address any questions or concerns you may have

I'd welcome the chance to connect with you soon. Please let me know what times work best for a brief call this week or next.

Best regards,
Your Wealth Advisor"""
        key_points = ["Routine portfolio review", "Alignment check", "Market positioning"]
    else:
        # Build detailed alert context
        alert_details = []
        for alert in open_alerts[:3]:
            priority_label = f"[{alert.priority}]"
            main_reason = alert.reasoning_bullets[0] if alert.reasoning_bullets else "Portfolio adjustment recommended"
            additional_reasons = alert.reasoning_bullets[1:3] if len(alert.reasoning_bullets) > 1 else []

            detail = f"{priority_label} {main_reason}"
            if additional_reasons:
                detail += "\n    - " + "\n    - ".join(additional_reasons)
            alert_details.append(detail)

        alert_context = "\n".join(alert_details)

        # Generate more comprehensive email with context
        subject = f"Important Portfolio Review - {client.name}"

        body = f"""Hi {client.name},

I hope you're doing well. I wanted to reach out because our recent portfolio analysis has identified some important items that would benefit from our discussion.

**Current Portfolio Situation:**

Based on our comprehensive review of your holdings, allocation, and market positioning, we've identified the following considerations:

{alert_context}

**Why This Matters:**

Your portfolio's current composition is an important factor in your long-term financial success. Market conditions, your life circumstances, and your financial goals can all influence whether adjustments might be beneficial. Our role is to ensure your portfolio remains optimized for your situation.

**What I Recommend We Discuss:**

During our call, I'd like to walk through:
1. A detailed analysis of what's driving these observations
2. How your current allocation aligns with your long-term objectives
3. Potential adjustments that could better position your portfolio
4. Any tax-efficient strategies we should consider
5. A timeline and action plan moving forward

**Next Steps:**

I'd value the opportunity to connect with you soon to discuss these points in detail. Our conversation will help ensure your portfolio continues to work effectively toward your goals.

Could you share a few times that work best for you this week or early next week? I'm flexible and happy to work around your schedule. A 30-minute call should give us plenty of time to cover the essentials.

I look forward to connecting with you.

Best regards,
Your Wealth Advisor"""

        key_points = [
            f"{alert.priority}: {alert.reasoning_bullets[0] if alert.reasoning_bullets else 'Action recommended'}"
            for alert in open_alerts[:3]
        ]

    return EmailDraft(
        client_id=client_id,
        client_name=client.name,
        subject=subject,
        body=body,
        key_points=key_points,
        provider=get_provider().__class__.__name__
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
