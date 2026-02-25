from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, conint, field_validator
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class Priority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    REVIEWED = "REVIEWED"
    ESCALATED = "ESCALATED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class AuditEventType(str, Enum):
    RUN_STARTED = "RUN_STARTED"
    RUN_COMPLETED = "RUN_COMPLETED"
    ALERT_CREATED = "ALERT_CREATED"
    ALERT_REVIEWED = "ALERT_REVIEWED"
    ALERT_ESCALATED = "ALERT_ESCALATED"
    ALERT_FALSE_POSITIVE = "ALERT_FALSE_POSITIVE"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    segment: Mapped[str] = mapped_column(String, nullable=False)
    risk_profile: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    portfolios: Mapped[List["Portfolio"]] = relationship(
        "Portfolio", back_populates="client", cascade="all, delete-orphan"
    )


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    total_value: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    target_equity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    target_fixed_income_pct: Mapped[float] = mapped_column(Float, nullable=False)
    target_cash_pct: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    client: Mapped[Client] = relationship("Client", back_populates="portfolios")
    positions: Mapped[List["Position"]] = relationship(
        "Position", back_populates="portfolio", cascade="all, delete-orphan"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="portfolio", cascade="all, delete-orphan"
    )


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    asset_class: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)

    portfolio: Mapped[Portfolio] = relationship("Portfolio", back_populates="positions")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    alerts_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider_used: Mapped[str] = mapped_column(String, nullable=False)

    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="run")
    audit_events: Mapped[List["AuditEvent"]] = relationship(
        "AuditEvent", back_populates="run"
    )


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"), nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    priority: Mapped[Priority] = mapped_column(SAEnum(Priority), nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning_bullets: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    suggested_next_step: Mapped[str] = mapped_column(String, nullable=False)
    decision_trace_steps: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)
    change_detection: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, nullable=False)

    status: Mapped[AlertStatus] = mapped_column(
        SAEnum(AlertStatus), default=AlertStatus.OPEN, nullable=False, index=True
    )

    concentration_score: Mapped[float] = mapped_column(Float, nullable=False)
    drift_score: Mapped[float] = mapped_column(Float, nullable=False)
    volatility_proxy: Mapped[float] = mapped_column(Float, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)

    run: Mapped[Run] = relationship("Run", back_populates="alerts")
    portfolio: Mapped[Portfolio] = relationship("Portfolio", back_populates="alerts")
    client: Mapped[Client] = relationship("Client")
    audit_events: Mapped[List["AuditEvent"]] = relationship(
        "AuditEvent", back_populates="alert"
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("alerts.id"), nullable=True, index=True
    )
    run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("runs.id"), nullable=True, index=True
    )
    event_type: Mapped[AuditEventType] = mapped_column(
        SAEnum(AuditEventType), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String, nullable=False, default="operator_demo")
    details: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    alert: Mapped[Optional[Alert]] = relationship("Alert", back_populates="audit_events")
    run: Mapped[Optional[Run]] = relationship("Run", back_populates="audit_events")


# ---------- Pydantic Schemas ----------


class DecisionTraceStep(BaseModel):
    step: str
    detail: str


class ChangeDetectionItem(BaseModel):
    metric: str
    from_value: str = Field(alias="from")
    to_value: str = Field(alias="to")

    class Config:
        populate_by_name = True


class AIOutput(BaseModel):
    priority: Priority
    confidence: conint(ge=0, le=100)  # type: ignore[valid-type]
    event_title: str
    summary: str
    reasoning_bullets: List[str]
    human_review_required: bool
    suggested_next_step: str
    decision_trace_steps: List[DecisionTraceStep]
    change_detection: List[ChangeDetectionItem]

    @field_validator("suggested_next_step")
    @classmethod
    def enforce_operational_language(cls, v: str) -> str:
        banned = ["buy", "sell", "rebalance", "rebalance to", "%"]
        lower = v.lower()
        if any(word in lower for word in banned):
            # Soft guardrail: in a real system we'd reject, here we sanitize.
            return "Review alignment with client plan and risk profile based on detected changes."
        return v


class ClientSummary(BaseModel):
    id: int
    name: str
    email: str
    segment: str
    risk_profile: str


class PortfolioSummary(BaseModel):
    id: int
    name: str
    total_value: float
    target_equity_pct: float
    target_fixed_income_pct: float
    target_cash_pct: float


class AlertSummary(BaseModel):
    id: int
    created_at: datetime
    priority: Priority
    confidence: int
    event_title: str
    status: AlertStatus
    client: ClientSummary
    portfolio: PortfolioSummary


class AlertDetail(BaseModel):
    id: int
    created_at: datetime
    priority: Priority
    confidence: int
    event_title: str
    summary: str
    reasoning_bullets: List[str]
    human_review_required: bool
    suggested_next_step: str
    decision_trace_steps: List[DecisionTraceStep]
    change_detection: List[ChangeDetectionItem]
    status: AlertStatus
    concentration_score: float
    drift_score: float
    volatility_proxy: float
    risk_score: float
    client: ClientSummary
    portfolio: PortfolioSummary


class RunSummary(BaseModel):
    run_id: int
    provider_used: str
    created_alerts_count: int
    priority_counts: Dict[Priority, int]
    top_alerts: List[AlertSummary]


class AuditEventEntry(BaseModel):
    id: int
    alert_id: Optional[int]
    run_id: Optional[int]
    event_type: AuditEventType
    actor: str
    details: Dict[str, Any]
    created_at: datetime


class MonitoringUniverseSummary(BaseModel):
    total_clients: int
    total_portfolios: int
    alerts_by_priority: Dict[Priority, int]
    alerts_by_status: Dict[AlertStatus, int]
    total_runs: int
    average_alerts_per_run: float
    percent_alerts_human_review_required: float

