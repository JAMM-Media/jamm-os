# app/schemas/finding.py

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from app.core.enums import FindingLifecycleState, GateBar, GateStatus, SubjectType


class FindingBase(BaseModel):
    firm_id: Optional[UUID] = None
    technique: str
    subject_type: SubjectType
    subject_key: str
    metric_key: Optional[str] = None
    gate_bar: GateBar

    @field_validator("metric_key")
    @classmethod
    def _subject_key_matches_metric_key_for_metric_subjects(
        cls, metric_key: Optional[str], info: ValidationInfo
    ) -> Optional[str]:
        subject_type = info.data.get("subject_type")
        subject_key = info.data.get("subject_key")
        if subject_type == SubjectType.metric and subject_key != metric_key:
            raise ValueError(
                "subject_key must equal metric_key when subject_type is metric"
            )
        return metric_key


class FindingCreate(FindingBase):
    statistics: dict = {}
    data_sufficiency: dict = {}


class FindingUpdate(BaseModel):
    statistics: Optional[dict] = None
    data_sufficiency: Optional[dict] = None
    confidence_tier: Optional[int] = None
    gate_status: Optional[GateStatus] = None
    failure_reason: Optional[str] = None
    severity_base_weight: Optional[Decimal] = None
    severity_modifiers: Optional[dict] = None
    severity_score: Optional[Decimal] = None
    lifecycle_state: Optional[FindingLifecycleState] = None
    gate_passed_at: Optional[datetime] = None
    gate_failed_at: Optional[datetime] = None
    last_recheck_at: Optional[datetime] = None
    surfaced_at: Optional[datetime] = None
    displaced_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    eligible_surfaces: Optional[list] = None
    composite_id: Optional[UUID] = None


class FindingOut(FindingBase):
    id: UUID
    statistics: dict
    data_sufficiency: dict
    confidence_tier: Optional[int] = None
    gate_status: GateStatus
    failure_reason: Optional[str] = None
    severity_base_weight: Optional[Decimal] = None
    severity_modifiers: dict
    severity_score: Optional[Decimal] = None
    lifecycle_state: Optional[FindingLifecycleState] = None
    gate_passed_at: Optional[datetime] = None
    gate_failed_at: Optional[datetime] = None
    last_recheck_at: Optional[datetime] = None
    surfaced_at: Optional[datetime] = None
    displaced_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    eligible_surfaces: list
    composite_id: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
