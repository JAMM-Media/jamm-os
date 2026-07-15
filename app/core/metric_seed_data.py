# app/core/metric_seed_data.py

"""
Single source of truth for the locked Session 0 metric_registry seed rows.
Shared by the seeding migration and its tests so the two can never drift
apart from each other. Full Tier-1 registry authoring happens in a later
session; this is the skeleton plus the locked core.
"""

# (key, display_name, unit, better_direction, benchmark_eligible, tier, window_type)
# window_type added July 2026: automation_utilization is a rolling_snapshot
# (share of presets ever fired), every other row is a weekly_summary.
SEED_METRICS = [
    ("engagement_velocity", "Engagement Velocity", "days", "lower", True, 1, "weekly_summary"),
    ("deadline_adherence_original", "Deadline Adherence - Beat Original", "percent", "higher", True, 1, "weekly_summary"),
    ("deadline_adherence_extended", "Deadline Adherence - Beat Extended", "percent", "higher", True, 1, "weekly_summary"),
    ("deadline_adherence_operative", "Deadline Adherence - Beat Operative", "percent", "higher", True, 1, "weekly_summary"),
    ("document_collection_speed", "Document Collection Speed", "days", "lower", True, 1, "weekly_summary"),
    ("invoice_payment_time", "Invoice Payment Time", "days", "lower", True, 1, "weekly_summary"),
    ("portal_utilization_documents", "Portal Utilization - Document Items", "percent", "higher", True, 1, "weekly_summary"),
    ("portal_utilization_invoices", "Portal Utilization - Invoice Payments", "percent", "higher", True, 1, "weekly_summary"),
    ("portal_utilization_todos", "Portal Utilization - Todos", "percent", "higher", True, 1, "weekly_summary"),
    ("portal_utilization_esign", "Portal Utilization - E-signatures", "percent", "higher", True, 1, "weekly_summary"),
    ("automation_utilization", "Automation Utilization", "percent", "higher", True, 1, "rolling_snapshot"),
]
