from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from db import get_db
from models import (
    Alert,
    AlertStatus,
    AuditEvent,
    AuditEventEntry,
    Priority,
)

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditListResponse(BaseModel):
    items: List[AuditEventEntry]
    total: int


@router.get("", response_model=AuditListResponse)
def list_audit_events(
    db: Session = Depends(get_db),
    priority: Optional[str] = Query(
        None,
        description="Optional priority filter, e.g. 'HIGH' or 'HIGH,MEDIUM'.",
    ),
    status: Optional[str] = Query(
        None,
        description="Optional alert status filter, e.g. 'OPEN' or 'OPEN,ESCALATED'.",
    ),
    event_type: Optional[str] = Query(
        None,
        description="Optional event type filter, e.g. 'RUN_COMPLETED,ALERT_REVIEWED'.",
    ),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> AuditListResponse:
    query = db.query(AuditEvent)

    # Join to alerts only when needed for filters.
    join_alerts = bool(priority or status)
    if join_alerts:
        query = query.join(Alert, AuditEvent.alert_id == Alert.id)

    conditions = []

    if priority:
        raw_values = {p.strip().upper() for p in priority.split(",") if p.strip()}
        priority_enums = [Priority(v) for v in raw_values if v in Priority.__members__]
        if priority_enums:
            conditions.append(Alert.priority.in_(priority_enums))

    if status:
        raw_status = {s.strip().upper() for s in status.split(",") if s.strip()}
        status_enums = [AlertStatus(v) for v in raw_status if v in AlertStatus.__members__]
        if status_enums:
            conditions.append(Alert.status.in_(status_enums))

    if event_type:
        raw_types = {e.strip().upper() for e in event_type.split(",") if e.strip()}
        if raw_types:
            conditions.append(AuditEvent.event_type.in_(raw_types))

    if from_date:
        conditions.append(AuditEvent.created_at >= from_date)
    if to_date:
        conditions.append(AuditEvent.created_at <= to_date)

    if conditions:
        query = query.filter(and_(*conditions))

    total = query.count()

    events: List[AuditEvent] = (
        query.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit).all()
    )

    items: List[AuditEventEntry] = [
        AuditEventEntry(
            id=e.id,
            alert_id=e.alert_id,
            run_id=e.run_id,
            event_type=e.event_type,
            actor=e.actor,
            details=e.details,
            created_at=e.created_at,
        )
        for e in events
    ]

    return AuditListResponse(items=items, total=total)

