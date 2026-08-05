# app/core/dashboard_widgets.py
#
# Code-level registry of all dashboard widget types available at launch.
# This is not a database table. It defines what widgets exist, what sizes
# they support, and what role is required to use them.

from typing import Any

WIDGET_REGISTRY: list[dict[str, Any]] = [
    {
        "type_key": "revenue_this_month",
        "display_name": "Revenue This Month",
        "category": "overview",
        "allowed_sizes": ["small"],
        "config_schema": [],
        "role_requirement": "manager_or_above",
    },
    {
        "type_key": "outstanding_ar",
        "display_name": "Outstanding AR",
        "category": "overview",
        "allowed_sizes": ["small"],
        "config_schema": [],
        "role_requirement": "manager_or_above",
    },
    {
        "type_key": "unbilled_wip_stat",
        "display_name": "Unbilled WIP (Total)",
        "category": "overview",
        "allowed_sizes": ["small"],
        "config_schema": [],
        "role_requirement": "manager_or_above",
    },
    {
        "type_key": "overdue_engagements_count",
        "display_name": "Overdue Engagements (Count)",
        "category": "overview",
        "allowed_sizes": ["small"],
        "config_schema": [],
        "role_requirement": "manager_or_above",
    },
    {
        "type_key": "work_in_progress",
        "display_name": "Work in Progress",
        "category": "billing",
        "allowed_sizes": ["medium", "large"],
        "config_schema": [],
        "role_requirement": "manager_or_above",
    },
    {
        "type_key": "upcoming_deadlines",
        "display_name": "Upcoming Deadlines",
        "category": "calendar",
        "allowed_sizes": ["medium", "large"],
        "config_schema": [],
        "role_requirement": "manager_or_above",
    },
    {
        "type_key": "staff_utilization",
        "display_name": "Staff Utilization",
        "category": "staff",
        "allowed_sizes": ["medium"],
        "config_schema": [],
        "role_requirement": "manager_or_above",
    },
    {
        "type_key": "overdue_engagements_table",
        "display_name": "Overdue Engagements",
        "category": "engagements",
        "allowed_sizes": ["medium", "large"],
        "config_schema": [],
        "role_requirement": "manager_or_above",
    },
    {
        "type_key": "awaiting_signature",
        "display_name": "Awaiting Signature",
        "category": "documents",
        "allowed_sizes": ["medium", "large"],
        "config_schema": [],
        "role_requirement": "manager_or_above",
    },
]

# Quick lookup by type_key
WIDGET_BY_TYPE_KEY: dict[str, dict[str, Any]] = {
    w["type_key"]: w for w in WIDGET_REGISTRY
}
