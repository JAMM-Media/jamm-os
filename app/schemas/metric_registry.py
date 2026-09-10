# app/schemas/metric_registry.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.enums import (
    BetterDirection,
    MetricEntityType,
    MetricPillar,
    MetricWindowType,
)


def clean_synonyms(values: Optional[list[str]]) -> Optional[list[str]]:
    """Strip whitespace, drop empties, refuse case-insensitive duplicates.

    Shared by the base and update schemas so the two can never disagree.
    Synonyms are search vocabulary only, so the rule is about tidiness, not
    integrity: "Speed" and "speed" would match the same search and one of
    them is a mistake.
    """
    if values is None:
        return None
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        if not value:
            continue
        folded = value.casefold()
        if folded in seen:
            raise ValueError(
                f"Synonyms must be unique. '{value}' appears more than once "
                "(letter case does not make two synonyms different)."
            )
        seen.add(folded)
        cleaned.append(value)
    return cleaned


class MetricRegistryBase(BaseModel):
    key: str
    display_name: str
    description: Optional[str] = None
    unit: str
    better_direction: BetterDirection
    benchmark_eligible: bool = False
    window_type: MetricWindowType
    tier: int = 1
    is_active: bool = True

    # Display curation fields (Sep 10, 2026). NULL means not yet authored.
    pillar: Optional[MetricPillar] = None
    entity_type: Optional[MetricEntityType] = None
    attention_weight: Optional[int] = None
    synonyms: list[str] = []

    @field_validator("synonyms")
    @classmethod
    def _validate_synonyms(cls, values: list[str]) -> list[str]:
        return clean_synonyms(values) or []


class MetricRegistryCreate(MetricRegistryBase):
    pass


class MetricRegistryUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    better_direction: Optional[BetterDirection] = None
    benchmark_eligible: Optional[bool] = None
    window_type: Optional[MetricWindowType] = None
    tier: Optional[int] = None
    is_active: Optional[bool] = None

    pillar: Optional[MetricPillar] = None
    entity_type: Optional[MetricEntityType] = None
    attention_weight: Optional[int] = None
    synonyms: Optional[list[str]] = None

    @field_validator("synonyms")
    @classmethod
    def _validate_synonyms(cls, values: Optional[list[str]]) -> Optional[list[str]]:
        return clean_synonyms(values)


class MetricRegistryOut(MetricRegistryBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
