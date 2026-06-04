# app/models/concierge_question_log.py

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import Boolean, DateTime, Index, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ConciergeQuestionLog(Base):
    __tablename__ = "concierge_question_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("firms.id", ondelete="CASCADE"), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    low_confidence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_concierge_question_log_firm_id", "firm_id"),
        Index("ix_concierge_question_log_low_confidence", "low_confidence"),
    )
