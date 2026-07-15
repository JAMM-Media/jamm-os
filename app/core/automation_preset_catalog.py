# app/core/automation_preset_catalog.py
"""
Code-level catalog of automation presets, one entry per preset shipped in
app/services/automation_presets.py. introduced_at is the date each preset
was actually added to the codebase (per git history), not a single blanket
date -- the catalog grew in three batches, not all at once.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class AutomationPresetCatalogEntry:
    key: str
    display_name: str
    introduced_at: date


PRESET_CATALOG: list[AutomationPresetCatalogEntry] = [
    # Shipped 2026-05-03 -- initial JAMM PX build (commit aeb47761)
    AutomationPresetCatalogEntry("doc_request_reminder_3day", "Document Request Reminder (3-day)", date(2026, 5, 3)),
    AutomationPresetCatalogEntry("esign_reminder_2day", "E-Signature Reminder (2-day)", date(2026, 5, 3)),
    AutomationPresetCatalogEntry("overdue_task_alert_to_staff", "Overdue Task Alert to Staff", date(2026, 5, 3)),
    AutomationPresetCatalogEntry("auto_create_invoice_on_completion", "Auto-Create Invoice on Engagement Completion", date(2026, 5, 3)),
    AutomationPresetCatalogEntry("new_client_welcome_email", "New Client Welcome Email", date(2026, 5, 3)),
    AutomationPresetCatalogEntry("notify_staff_docs_complete", "Notify Staff When Documents Are Complete", date(2026, 5, 3)),
    AutomationPresetCatalogEntry("invoice_overdue_reminder", "Invoice Overdue Reminder", date(2026, 5, 3)),
    AutomationPresetCatalogEntry("recurring_engagement_kickoff", "Recurring Engagement Kickoff Notification", date(2026, 5, 3)),
    AutomationPresetCatalogEntry("season_1040_kickoff", "1040 Season Kickoff", date(2026, 5, 3)),
    AutomationPresetCatalogEntry("extension_filed_auto_notify", "Extension Filed Auto-Notify", date(2026, 5, 3)),
    AutomationPresetCatalogEntry("irs_authorization_expiry_warning", "IRS Authorization Expiry Warning", date(2026, 5, 3)),
    AutomationPresetCatalogEntry("invoice_overdue_escalating_sequence", "Invoice Overdue Escalating Sequence", date(2026, 5, 3)),
    AutomationPresetCatalogEntry("deadline_approaching_14day_alert", "Engagement Deadline Approaching — 14-day Alert", date(2026, 5, 3)),
    AutomationPresetCatalogEntry("return_completed_client_delivery_loop", "Return Completed: Client Delivery Loop", date(2026, 5, 3)),
    AutomationPresetCatalogEntry("new_client_full_onboarding_sequence", "New Client Full Onboarding Sequence", date(2026, 5, 3)),
    # Shipped 2026-06-05 (commit 2c99f0fd)
    AutomationPresetCatalogEntry("budget_variance_alert", "Budget Variance Alert", date(2026, 6, 5)),
    # Shipped 2026-06-06 (commit 994ad94b)
    AutomationPresetCatalogEntry("morning_briefing", "Morning Briefing", date(2026, 6, 6)),
]

PRESET_CATALOG_BY_KEY: dict[str, AutomationPresetCatalogEntry] = {
    entry.key: entry for entry in PRESET_CATALOG
}
