# app/core/enums.py

from enum import Enum


class UserRole(str, Enum):
    """
    The roles that exist in JAMM PX.

    firm_owner  → Full access to everything in their firm.
                  Can change firm settings, billing, add/remove staff.
    manager     → Access to all client/engagement data.
                  Cannot change firm settings or billing.
    staff       → Access to assigned engagements and tasks only.
                  Cannot see engagements they are not assigned to.
    client_portal_user → Client-facing role. Can only see their own data
                         through the client portal. Completely isolated
                         from the staff-facing side of the app.
    system_admin → JAMM PX internal use only. Cross-firm access for support.
                   Never assigned to a real firm's users.

    NOTE: The old "admin" role has been renamed to "firm_owner" to match
    accounting industry language and the master instructions domain model.
    The old "client" role has been renamed to "client_portal_user" to be
    explicit about what this role can and cannot access.
    """

    firm_owner = "firm_owner"
    manager = "manager"
    staff = "staff"
    client_portal_user = "client_portal_user"
    system_admin = "system_admin"


class EngagementStatus(str, Enum):
    """Valid status values for an Engagement."""
    draft = "draft"
    active = "active"
    in_review = "in_review"
    completed = "completed"
    acknowledged = "acknowledged"
    archived = "archived"


class EngagementType(str, Enum):
    """
    Tax-firm-specific engagement types.
    Stored as VARCHAR in the DB (native_enum=False).
    Each type maps to an IRS filing deadline in app/core/tax_deadlines.py.
    """
    tax_return_1040 = "tax_return_1040"
    tax_return_1120 = "tax_return_1120"
    tax_return_1120s = "tax_return_1120s"
    tax_return_1065 = "tax_return_1065"
    tax_return_1041 = "tax_return_1041"
    tax_return_706 = "tax_return_706"
    amended_return_1040x = "amended_return_1040x"
    extension_4868 = "extension_4868"
    extension_7004 = "extension_7004"
    extension_8868 = "extension_8868"
    payroll_tax_941 = "payroll_tax_941"
    tax_planning_advisory = "tax_planning_advisory"
    bookkeeping_monthly = "bookkeeping_monthly"
    bookkeeping_quarterly = "bookkeeping_quarterly"
    audit_representation = "audit_representation"
    other_advisory = "other_advisory"
    custom = "custom"


class TaskStatus(str, Enum):
    """Valid status values for a Task."""
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class InvoiceStatus(str, Enum):
    draft = "draft"
    sent = "sent"
    paid = "paid"
    overdue = "overdue"
    void = "void"
    partial = "partial"
    refunded = "refunded"


class InvoiceDeliveryMethod(str, Enum):
    email = "email"
    portal = "portal"
    both = "both"


class StripeConnectionStatus(str, Enum):
    connected = "connected"
    disconnected = "disconnected"
    error = "error"


class TriggerEvent(str, Enum):
    engagement_created = "engagement.created"
    engagement_status_changed = "engagement.status_changed"
    engagement_completed = "engagement.completed"
    engagement_overdue = "engagement.overdue"
    engagement_recurrence_created = "engagement.recurrence_created"
    doc_request_created = "doc_request.created"
    doc_request_item_uploaded = "doc_request.item_uploaded"
    doc_request_completed = "doc_request.completed"
    doc_request_reminder_sent = "doc_request.reminder_sent"
    esign_sent = "esign.sent"
    esign_signed = "esign.signed"
    esign_declined = "esign.declined"
    esign_expired = "esign.expired"
    esign_reminder_sent = "esign.reminder_sent"
    invoice_created = "invoice.created"
    invoice_sent = "invoice.sent"
    invoice_paid = "invoice.paid"
    invoice_overdue = "invoice.overdue"
    time_entry_created = "time_entry.created"
    task_assigned = "task.assigned"
    task_reassigned = "task.reassigned"
    client_created = "client.created"
    intake_form_submitted = "intake_form.submitted"
    engagement_deadline_approaching = "engagement.deadline_approaching"
    irs_authorization_signed = "irs_authorization.signed"
    irs_authorization_expired = "irs_authorization.expired"
    irs_authorization_expiry_approaching = "irs_authorization.expiry_approaching"
    extension_filed = "extension.filed"
    extension_deadline_approaching = "extension.deadline_approaching"
    qbo_budget_variance = "qbo.budget_variance"
    morning_briefing = "morning_briefing"


class AutomationActionType(str, Enum):
    send_email = "send_email"
    send_notification = "send_notification"
    create_task = "create_task"
    assign_task = "assign_task"
    update_engagement_status = "update_engagement_status"
    create_document_request = "create_document_request"
    send_document_request_reminder = "send_document_request_reminder"
    create_invoice = "create_invoice"
    add_internal_note = "add_internal_note"
    webhook_post = "webhook_post"
    send_irs_auth_reminder = "send_irs_auth_reminder"
    morning_briefing = "morning_briefing"


class ConditionOperator(str, Enum):
    equals = "equals"
    not_equals = "not_equals"
    contains = "contains"
    greater_than = "greater_than"
    less_than = "less_than"
    is_empty = "is_empty"
    is_not_empty = "is_not_empty"


class AutomationExecutionStatus(str, Enum):
    success = "success"
    failed = "failed"
    partial = "partial"
    skipped = "skipped"


class RecipientType(str, Enum):
    staff = "staff"
    client = "client"


class NotificationType(str, Enum):
    task_assigned = "task_assigned"
    doc_request_ready = "doc_request_ready"
    esign_needed = "esign_needed"
    payment_due = "payment_due"
    system = "system"
    deadline_alert = "deadline_alert"
    irs_auth_expiry = "irs_auth_expiry"
    irs_auth_missing = "irs_auth_missing"
    extension_deadline = "extension_deadline"
    client_anniversary = "client_anniversary"
    document_expiry_alert = "document_expiry_alert"
    peer_network_mention = "peer_network_mention"


class NotificationChannel(str, Enum):
    in_app = "in_app"
    email = "email"
    both = "both"
    none = "none"


class StaffAuthPolicy(str, Enum):
    PASSWORD_ONLY = "password_only"
    MAGIC_LINK_ONLY = "magic_link_only"
    EITHER = "either"


class NotificationEventType(str, Enum):
    task_assigned = "task_assigned"
    doc_request_ready = "doc_request_ready"
    esign_needed = "esign_needed"
    payment_due = "payment_due"
    system = "system"
    deadline_alert = "deadline_alert"
    irs_auth_expiry = "irs_auth_expiry"
    irs_auth_missing = "irs_auth_missing"
    extension_deadline = "extension_deadline"
    client_anniversary = "client_anniversary"
    document_expiry_alert = "document_expiry_alert"


class CredentialType(str, Enum):
    cpa_license = "cpa_license"
    ea_enrollment = "ea_enrollment"
    ptin = "ptin"
    state_license = "state_license"
    other = "other"


class CPEStatus(str, Enum):
    in_progress = "in_progress"
    complete = "complete"
    overdue = "overdue"


class ReferralSource(str, Enum):
    """How a client found the firm. Captured at intake for acquisition reporting."""
    client_referral = "client_referral"
    professional_referral = "professional_referral"
    returning_client = "returning_client"
    google_search = "google_search"
    search_ads = "search_ads"
    social_ads = "social_ads"
    social_media = "social_media"
    website = "website"
    association_or_community = "association_or_community"
    walk_in = "walk_in"
    cold_outreach = "cold_outreach"
    purchased_book = "purchased_book"
    other = "other"
    unknown = "unknown"


class BetterDirection(str, Enum):
    """Which direction of a metric's value counts as improvement."""
    lower = "lower"
    higher = "higher"


class MetricWindowType(str, Enum):
    """How a metric's value is computed relative to time."""
    weekly_summary = "weekly_summary"
    rolling_snapshot = "rolling_snapshot"


class MetricRunStatus(str, Enum):
    """Status of one nightly metric computation run."""
    running = "running"
    succeeded = "succeeded"
    partial = "partial"
    failed = "failed"


class SubjectType(str, Enum):
    """What kind of thing a finding is about."""
    metric = "metric"
    entity = "entity"
    pattern = "pattern"


class GateBar(str, Enum):
    """Which confidence bar a finding is judged against."""
    firm_facing = "firm_facing"
    internal = "internal"


class GateStatus(str, Enum):
    """Where a finding sits in the confidence gate's judgment cycle."""
    pending = "pending"
    passed = "passed"
    failed = "failed"


class FindingLifecycleState(str, Enum):
    """
    Lifecycle of a finding after it has passed the confidence gate.
    Null until the gate passes; set to indexed on pass.
    """
    indexed = "indexed"
    surfaced = "surfaced"
    displaced = "displaced"
    resolved = "resolved"
    dismissed = "dismissed"
    archived = "archived"


EFILEABLE_ENGAGEMENT_TYPES = {
    "tax_return_1040",
    "tax_return_1120",
    "tax_return_1120s",
    "tax_return_1065",
    "tax_return_990",
    "tax_return_941",
    "tax_return_940",
    "tax_return_720",
    "tax_return_2290",
    "tax_return_706",
    "tax_return_709",
}

class LeadStage(str, Enum):
    """A lead's position in the acquisition pipeline. Ordered but skippable -- a walk-in ready to sign can jump straight to proposal."""
    identified = "identified"
    contacted = "contacted"
    call_booked = "call_booked"
    proposal = "proposal"
    won = "won"
    lost = "lost"


class LeadLostReason(str, Enum):
    """Captured at the transition to lost. unqualified is filtered-on-purpose and never counts against conversion metrics -- that distinction is sacred, per the build contract."""
    unqualified = "unqualified"
    unresponsive = "unresponsive"
    chose_competitor = "chose_competitor"
    price = "price"
    timing = "timing"
    other = "other"


class SourcePlatform(str, Enum):
    """Layer 2 attribution: the where. Auto-derived from utm_source when a lead arrives through a tracked link; manual picker is the fallback for leads with no link behind them. For cold_outreach leads (see ReferralSource), this same field carries the mechanism instead of a platform."""
    facebook = "facebook"
    instagram = "instagram"
    tiktok = "tiktok"
    linkedin = "linkedin"
    youtube = "youtube"
    x = "x"
    google = "google"
    bing = "bing"
    nextdoor = "nextdoor"
    email = "email"
    phone = "phone"
    dm = "dm"
    direct_mail = "direct_mail"
    other = "other"


class LeadProvenance(str, Enum):
    """How we know this lead's attribution. Precedence is substitution, never blending: crm_lead beats firm_entered beats client_reported. Lower tiers fill blanks only and never overwrite higher tiers."""
    crm_lead = "crm_lead"
    firm_entered = "firm_entered"
    client_reported = "client_reported"
