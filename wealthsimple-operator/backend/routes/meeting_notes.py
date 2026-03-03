from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ai.provider import get_provider
from db import get_db
from models import (
    AuditEvent,
    MeetingNote,
    MeetingNoteCreate,
    MeetingNoteView,
    TranscriptSummary,
    PreCallBriefResponse,
    Alert,
    Client,
)


router = APIRouter(prefix="/meeting-notes", tags=["meeting-notes"])


class MeetingNotesListResponse(BaseModel):
    items: List[MeetingNoteView]
    total: int


class MeetingNoteCreateRequest(BaseModel):
    client_id: int
    title: str
    meeting_date: str
    note_body: str
    meeting_type: str = "meeting"
    call_transcript: Optional[str] = None


class SummarizeTranscriptRequest(BaseModel):
    force_regenerate: bool = False


class SummarizeTranscriptResponse(BaseModel):
    note: MeetingNoteView
    message: str


@router.get("", response_model=MeetingNotesListResponse)
def list_meeting_notes(
    client_id: int = Query(..., description="Client ID to filter notes"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> MeetingNotesListResponse:
    """List meeting notes for a specific client."""
    query = db.query(MeetingNote).filter(MeetingNote.client_id == client_id)
    total = query.count()

    notes = (
        query.order_by(MeetingNote.meeting_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    items = [_note_to_view(note) for note in notes]
    return MeetingNotesListResponse(items=items, total=total)


@router.get("/{note_id}", response_model=MeetingNoteView)
def get_meeting_note(note_id: int, db: Session = Depends(get_db)) -> MeetingNoteView:
    """Get a specific meeting note by ID."""
    note: MeetingNote | None = db.query(MeetingNote).filter(MeetingNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Meeting note not found")
    return _note_to_view(note)


@router.post("", response_model=MeetingNoteView, status_code=201)
def create_meeting_note(
    payload: MeetingNoteCreateRequest,
    db: Session = Depends(get_db),
) -> MeetingNoteView:
    """Create a new meeting note."""
    from datetime import datetime as dt_class
    meeting_date = dt_class.fromisoformat(payload.meeting_date) if isinstance(payload.meeting_date, str) else payload.meeting_date

    note = MeetingNote(
        client_id=payload.client_id,
        title=payload.title,
        meeting_date=meeting_date,
        note_body=payload.note_body,
        meeting_type=payload.meeting_type,
        call_transcript=payload.call_transcript,
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    # Log audit event
    audit_event = AuditEvent(
        event_type="MEETING_NOTE_CREATED",
        actor="system",
        alert_id=None,
        run_id=None,
        details={
            "client_id": payload.client_id,
            "note_id": note.id,
            "title": payload.title,
            "meeting_type": payload.meeting_type,
            "has_transcript": bool(payload.call_transcript),
        }
    )
    db.add(audit_event)
    db.commit()

    return _note_to_view(note)


@router.post("/{note_id}/summarize", response_model=SummarizeTranscriptResponse)
def summarize_transcript(
    note_id: int,
    payload: SummarizeTranscriptRequest,
    db: Session = Depends(get_db),
) -> SummarizeTranscriptResponse:
    """Generate AI summary for a meeting note's transcript."""
    note: MeetingNote | None = db.query(MeetingNote).filter(MeetingNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Meeting note not found")

    if not note.call_transcript:
        raise HTTPException(status_code=400, detail="Meeting note has no transcript to summarize")

    if note.ai_summary and not payload.force_regenerate:
        raise HTTPException(
            status_code=409,
            detail="Meeting note already summarized. Use force_regenerate=true to regenerate."
        )

    # Get the AI provider and summarize
    provider = get_provider()
    client = note.client

    summary_result: TranscriptSummary = provider.summarize_transcript(
        transcript=note.call_transcript,
        context={
            "client_name": client.name,
            "risk_profile": client.risk_profile,
        }
    )

    # Update the note with the summary
    note.ai_summary = summary_result.summary_paragraph
    note.ai_action_items = summary_result.action_items
    note.ai_summarized_at = datetime.utcnow()
    note.ai_provider_used = getattr(provider, "name", "unknown")

    db.commit()
    db.refresh(note)

    # Log audit event
    audit_event = AuditEvent(
        event_type="MEETING_NOTE_SUMMARIZED",
        actor="system",
        alert_id=None,
        run_id=None,
        details={
            "client_id": note.client_id,
            "note_id": note.id,
            "ai_provider": note.ai_provider_used,
            "action_items_count": len(note.ai_action_items) if note.ai_action_items else 0,
        }
    )
    db.add(audit_event)
    db.commit()

    return SummarizeTranscriptResponse(
        note=_note_to_view(note),
        message=f"Transcript summarized using {note.ai_provider_used} provider."
    )


class PreCallBriefRequest(BaseModel):
    client_id: int


@router.post("/pre-call-brief", response_model=PreCallBriefResponse)
def generate_pre_call_brief(
    payload: PreCallBriefRequest,
    db: Session = Depends(get_db),
) -> PreCallBriefResponse:
    """Generate a pre-call brief with open alerts, last interaction, and outstanding action items."""
    client: Client | None = db.query(Client).filter(Client.id == payload.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Get open alerts for this client
    open_alerts = db.query(Alert).filter(
        Alert.client_id == payload.client_id,
        Alert.status == "OPEN"
    ).all()

    # Get the most recent meeting note
    last_note: MeetingNote | None = (
        db.query(MeetingNote)
        .filter(MeetingNote.client_id == payload.client_id)
        .order_by(MeetingNote.meeting_date.desc())
        .first()
    )

    # Collect outstanding action items from all notes
    all_notes = db.query(MeetingNote).filter(MeetingNote.client_id == payload.client_id).all()
    outstanding_action_items: List[str] = []
    for note in all_notes:
        if note.ai_action_items:
            for idx, item in enumerate(note.ai_action_items):
                is_completed = note.action_item_completions and note.action_item_completions[idx]
                if not is_completed:
                    outstanding_action_items.append(item)

    # Get client portfolio context (total AUM)
    total_aum = sum(p.total_value for p in client.portfolios) if client.portfolios else 0.0

    # Determine highest priority
    highest_priority = None
    if open_alerts:
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        highest_priority = min(open_alerts, key=lambda a: priority_order.get(a.priority.value, 3)).priority.value

    return PreCallBriefResponse(
        client_name=client.name,
        risk_profile=client.risk_profile,
        aum=total_aum,
        open_alert_count=len(open_alerts),
        highest_priority=highest_priority,
        last_note_title=last_note.title if last_note else None,
        last_note_date=last_note.meeting_date if last_note else None,
        last_note_summary=last_note.ai_summary if last_note else None,
        outstanding_action_items=outstanding_action_items,
    )


class UpdateActionItemRequest(BaseModel):
    index: int
    completed: bool


class UpdateActionItemResponse(BaseModel):
    note: MeetingNoteView
    message: str


@router.patch("/{note_id}/action-items", response_model=UpdateActionItemResponse)
def update_action_item(
    note_id: int,
    payload: UpdateActionItemRequest,
    db: Session = Depends(get_db),
) -> UpdateActionItemResponse:
    """Update completion status of an action item."""
    note: MeetingNote | None = db.query(MeetingNote).filter(MeetingNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Meeting note not found")

    if not note.ai_action_items or payload.index < 0 or payload.index >= len(note.ai_action_items):
        raise HTTPException(status_code=400, detail="Invalid action item index")

    # Initialize or update completions list
    if note.action_item_completions is None:
        note.action_item_completions = [False] * len(note.ai_action_items)

    note.action_item_completions[payload.index] = payload.completed
    db.commit()
    db.refresh(note)

    # Log audit event
    audit_event = AuditEvent(
        event_type="MEETING_NOTE_ACTION_ITEM_UPDATED",
        actor="system",
        alert_id=None,
        run_id=None,
        details={
            "client_id": note.client_id,
            "note_id": note.id,
            "action_item_index": payload.index,
            "completed": payload.completed,
        }
    )
    db.add(audit_event)
    db.commit()

    return UpdateActionItemResponse(
        note=_note_to_view(note),
        message=f"Action item {payload.index + 1} marked as {'complete' if payload.completed else 'incomplete'}"
    )


def _note_to_view(note: MeetingNote) -> MeetingNoteView:
    """Convert a MeetingNote ORM object to a Pydantic view."""
    return MeetingNoteView(
        id=note.id,
        client_id=note.client_id,
        title=note.title,
        meeting_date=note.meeting_date,
        note_body=note.note_body,
        meeting_type=note.meeting_type,
        call_transcript=note.call_transcript,
        ai_summary=note.ai_summary,
        ai_action_items=note.ai_action_items,
        action_item_completions=note.action_item_completions,
        ai_summarized_at=note.ai_summarized_at,
        ai_provider_used=note.ai_provider_used,
        created_at=note.created_at,
    )
