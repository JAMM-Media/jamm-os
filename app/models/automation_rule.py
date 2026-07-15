# app/models/automation_rule.py

from uuid import UUID, uuid4
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.core.enums import TriggerEvent, AutomationExecutionStatus


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    firm_id: Mapped[UUID] = mapped_column(ForeignKey("firms.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)
    is_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    trigger_event: Mapped[TriggerEvent] = mapped_column(
        sa.Enum(TriggerEvent, native_enum=False), nullable=False, index=True
    )
    trigger_conditions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    actions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    default_actions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Set when the rule is created from a catalog preset; never cleared
    # afterward, including when the rule is customized. Null means pure custom.
    preset_key: Mapped[str | None] = mapped_column(nullable=True, index=True)
    is_customized: Mapped[bool] = mapped_column(default=False, nullable=False)
    execution_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_executed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    firm: Mapped["Firm"] = relationship("Firm", back_populates="automation_rules")
    execution_logs: Mapped[list["AutomationExecutionLog"]] = relationship(
        "AutomationExecutionLog", back_populates="rule", cascade="all, delete-orphan"
    )


class AutomationExecutionLog(Base):
    __tablename__ = "automation_execution_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    firm_id: Mapped[UUID] = mapped_column(ForeignKey("firms.id"), nullable=False, index=True)
    rule_id: Mapped[UUID] = mapped_column(
        ForeignKey("automation_rules.id"), nullable=False, index=True
    )
    trigger_event: Mapped[TriggerEvent] = mapped_column(
        sa.Enum(TriggerEvent, native_enum=False), nullable=False
    )
    trigger_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[AutomationExecutionStatus] = mapped_column(
        sa.Enum(AutomationExecutionStatus, native_enum=False), nullable=False
    )
    actions_executed: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), nullable=False
    )

    rule: Mapped["AutomationRule"] = relationship("AutomationRule", back_populates="execution_logs")
