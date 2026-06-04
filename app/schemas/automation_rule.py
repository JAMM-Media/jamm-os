# app/schemas/automation_rule.py

from uuid import UUID
from datetime import datetime
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.enums import TriggerEvent, AutomationActionType, ConditionOperator, AutomationExecutionStatus


class ConditionSchema(BaseModel):
    field: str
    operator: ConditionOperator
    value: Any = None


class ActionSchema(BaseModel):
    type: AutomationActionType
    config: Dict[str, Any] = {}
    order: int = 0


class AutomationRuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_enabled: bool = False
    trigger_event: TriggerEvent
    trigger_conditions: List[ConditionSchema] = []
    actions: List[ActionSchema] = []

    @field_validator("actions")
    @classmethod
    def actions_required_when_enabled(cls, v: List[ActionSchema], info) -> List[ActionSchema]:
        is_enabled = info.data.get("is_enabled", False)
        if is_enabled and len(v) == 0:
            raise ValueError("An enabled rule must have at least one action.")
        return v


class AutomationRuleCreate(AutomationRuleBase):
    pass


class AutomationRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    trigger_event: Optional[TriggerEvent] = None
    trigger_conditions: Optional[List[ConditionSchema]] = None
    actions: Optional[List[ActionSchema]] = None


class AutomationRuleOut(AutomationRuleBase):
    id: UUID
    firm_id: UUID
    execution_count: int
    last_executed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    default_actions: List[Any] = []
    model_config = ConfigDict(from_attributes=True)


class AutomationExecutionLogBase(BaseModel):
    rule_id: UUID
    trigger_event: TriggerEvent
    trigger_payload: Dict[str, Any]
    status: AutomationExecutionStatus
    actions_executed: List[Dict[str, Any]]
    error_message: Optional[str] = None


class AutomationExecutionLogOut(AutomationExecutionLogBase):
    id: UUID
    firm_id: UUID
    executed_at: datetime
    model_config = ConfigDict(from_attributes=True)
