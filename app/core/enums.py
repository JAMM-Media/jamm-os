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

    # Individual tax
    tax_return_1040nr = "tax_return_1040nr"

    # Business and entity tax
    tax_return_990 = "tax_return_990"
    tax_return_709 = "tax_return_709"
    amended_return_business = "amended_return_business"

    # Payroll and information reporting
    payroll_tax_940 = "payroll_tax_940"
    payroll_processing = "payroll_processing"
    information_returns_1099_w2 = "information_returns_1099_w2"

    # Sales tax
    sales_use_tax = "sales_use_tax"

    # Foreign reporting
    fbar_international = "fbar_international"

    # Bookkeeping and accounting
    bookkeeping_cleanup = "bookkeeping_cleanup"
    accounting_system_setup = "accounting_system_setup"

    # Financial statements
    financial_statement_compilation = "financial_statement_compilation"
    financial_statement_review = "financial_statement_review"
    financial_statement_audit = "financial_statement_audit"
    agreed_upon_procedures = "agreed_upon_procedures"

    # Advisory and representation
    fractional_cfo = "fractional_cfo"
    entity_formation = "entity_formation"
    irs_notice_resolution = "irs_notice_resolution"
    tax_resolution = "tax_resolution"

    # Specialty
    rd_tax_credit_study = "rd_tax_credit_study"
    nonprofit_formation_exemption = "nonprofit_formation_exemption"
    benefit_plan_5500 = "benefit_plan_5500"
    business_valuation = "business_valuation"
    business_personal_property_tax = "business_personal_property_tax"
    cost_segregation_study = "cost_segregation_study"
    transaction_advisory = "transaction_advisory"


# The CANONICAL display name for every EngagementType member: the formal,
# form-number-bearing string ("Individual Tax Return (Form 1040)").
# This is the single backend source of truth for these names and every member
# must have an entry, enforced by tests/test_engagement_type_canon.py.
#
# NOT the same thing as LEAD_FACING_LABELS below, which is the optional
# plain-English override a lead sees on the public intake form. This map was
# called "lead-facing" before August 18, 2026, when the two audiences were
# still the same one. They are not any more: this map is the complete, formal
# canon, and that one is the sparse, friendly override that falls back here.
ENGAGEMENT_TYPE_LABELS: dict[EngagementType, str] = {
    EngagementType.tax_return_1040: "Individual Tax Return (Form 1040)",
    EngagementType.tax_return_1040nr: "Nonresident Individual Tax Return (Form 1040-NR)",
    EngagementType.amended_return_1040x: "Amended Individual Return (Form 1040-X)",
    EngagementType.extension_4868: "Individual Extension (Form 4868)",
    EngagementType.tax_return_1120: "C Corporation Tax Return (Form 1120)",
    EngagementType.tax_return_1120s: "S Corporation Tax Return (Form 1120-S)",
    EngagementType.tax_return_1065: "Partnership Tax Return (Form 1065)",
    EngagementType.tax_return_990: "Nonprofit Tax Return (Form 990)",
    EngagementType.tax_return_1041: "Trust and Estate Income Tax Return (Form 1041)",
    EngagementType.tax_return_706: "Estate Tax Return (Form 706)",
    EngagementType.tax_return_709: "Gift Tax Return (Form 709)",
    EngagementType.amended_return_business: "Amended Business Return",
    EngagementType.extension_7004: "Business Extension (Form 7004)",
    EngagementType.extension_8868: "Exempt Organization Extension (Form 8868)",
    EngagementType.payroll_tax_941: "Quarterly Payroll Tax Filing (Form 941)",
    EngagementType.payroll_tax_940: "Annual FUTA Filing (Form 940)",
    EngagementType.payroll_processing: "Payroll Processing",
    EngagementType.information_returns_1099_w2: "1099 and W-2 Preparation",
    EngagementType.sales_use_tax: "Sales and Use Tax Filing",
    EngagementType.fbar_international: "FBAR and International Reporting",
    EngagementType.bookkeeping_monthly: "Monthly Bookkeeping",
    EngagementType.bookkeeping_quarterly: "Quarterly Bookkeeping",
    EngagementType.bookkeeping_cleanup: "Bookkeeping Cleanup and Catch-Up",
    EngagementType.accounting_system_setup: "Accounting System Setup and Migration",
    EngagementType.financial_statement_compilation: "Financial Statement Compilation",
    EngagementType.financial_statement_review: "Financial Statement Review",
    EngagementType.financial_statement_audit: "Financial Statement Audit",
    EngagementType.agreed_upon_procedures: "Agreed-Upon Procedures",
    EngagementType.tax_planning_advisory: "Tax Planning and Advisory",
    EngagementType.fractional_cfo: "Fractional CFO Services",
    EngagementType.entity_formation: "Entity Formation and New Business Setup",
    EngagementType.irs_notice_resolution: "IRS Notice Resolution",
    EngagementType.tax_resolution: "Tax Resolution",
    EngagementType.audit_representation: "Audit Representation",
    EngagementType.rd_tax_credit_study: "R&D Tax Credit Study",
    EngagementType.nonprofit_formation_exemption: "Nonprofit Formation and Exemption Application",
    EngagementType.benefit_plan_5500: "Employee Benefit Plan Filing (Form 5500)",
    EngagementType.business_valuation: "Business Valuation",
    EngagementType.business_personal_property_tax: "Business Personal Property Tax Filing",
    EngagementType.cost_segregation_study: "Cost Segregation Study",
    EngagementType.transaction_advisory: "Transaction Advisory",
    EngagementType.other_advisory: "Other Advisory",
    EngagementType.custom: "Custom Engagement",
}


class ServiceCategory(str, Enum):
    """The broad service bucket an engagement type belongs to.

    Presentation only. This is how the public intake form groups the services a
    firm offers into sections a lead can scan; it carries no pricing meaning, no
    deadline meaning, and nothing downstream branches on it.

    Ruled by Andrew on August 18, 2026 to be exactly these three values. It is a
    plain Python enum and NOT a database enum, because the map that uses it
    (ENGAGEMENT_TYPE_CATEGORIES below) is system-shared content living in code
    rather than a column. tests/test_engagement_type_presentation.py is what
    enforces that no value outside this enum reaches the payload, which is the
    job a sa.Enum column would otherwise have done.
    """

    tax = "tax"
    bookkeeping = "bookkeeping"
    advisory = "advisory"


# The plain-English name a LEAD sees for an engagement type, overriding the
# formal ENGAGEMENT_TYPE_LABELS canon above.
#
# DELIBERATELY SPARSE, AND DELIBERATELY EMPTY TODAY. A member absent from this
# map is not an error and never will be: it falls back to its
# ENGAGEMENT_TYPE_LABELS entry, which every member is guaranteed to have. That
# is why there is NO completeness test here and why one must never be added.
# ENGAGEMENT_TYPE_LABELS has one because absence there IS a gap; absence here is
# the designed default.
#
# THIS IS THE HALF OF THE RULE THAT DID NOT CHANGE. Both presentation maps
# shipped empty and unguarded on August 18, 2026 under one shared rule. That
# rule SPLIT the same day, when the intake structure contract made category a
# routing field: ENGAGEMENT_TYPE_CATEGORIES above is now complete and has a
# completeness test, and this map still has neither. The difference is not
# importance, it is the fallback. A missing entry here degrades to a formal
# label a lead can still read and act on. A missing entry there produced a
# service no lead could reach. One is a cosmetic gap, the other was a dead end,
# so they get opposite rules. Adding a completeness test here would encode the
# retired shared rule and start failing on a state that is deliberate.
#
# Content is authored in the catalog content session. Filling this map changes
# what the public intake payload SAYS and never what shape it has, so Ben can
# build against the contract before a single entry exists.
LEAD_FACING_LABELS: dict[EngagementType, str] = {}


# The broad bucket each engagement type is grouped under on the intake form.
#
# COMPLETE, AND REQUIRED TO STAY COMPLETE. Every EngagementType member must have
# an entry, enforced by tests/test_engagement_type_presentation.py.
#
# THIS MAP DID NOT ALWAYS CARRY THAT RULE, AND THE REASON IT DOES NOW IS THE
# WHOLE POINT. It shipped deliberately empty on August 18, 2026, alongside
# LEAD_FACING_LABELS below, on the reasoning that absence is a harmless default
# both maps could share. Then docs/Public_Intake_Form_Structure_Contract_v1.md
# landed and made category a ROUTING field: Step 1 of the intake form offers
# three fixed answers (Tax / Bookkeeping / Advisory) and Step 2 shows only the
# firm's active engagement types IN THE CHOSEN CATEGORY. There is no flat list
# anywhere in that spine.
#
# So absence stopped being harmless for THIS map. A type with no entry here
# belongs to none of the three Step 1 buckets and is unreachable through the
# funnel: the lead cannot get to it, the firm cannot sell it, and NOTHING GOES
# RED, because an uncategorized service is a valid payload and a dead form is
# not an exception. That is why this map is complete and guarded and the one
# below is neither. The two rules diverged on purpose, on August 18, 2026, and
# the divergence is the fallback: a missing label falls back to a string that
# always exists, and a missing category falls back to nothing at all.
#
# System-shared content by nature. A 1040 is a tax service for every firm that
# will ever exist, which is exactly why this lives in code beside the enum
# rather than on a firm-scoped column where each firm would re-author it and
# two firms could disagree.
#
# ASSIGNED BY THE LEAD'S MENTAL MODEL, NOT THE FIRM'S. The question each row
# answers is which of the three Step 1 buttons a LEAD would press to find this
# service, which is not always where a firm would file it internally. Ruled by
# Andrew on August 18, 2026, with these deliberate calls worth knowing about
# before anything is moved:
#
#   Tax planning is TAX, not advisory, even though the work is advisory and the
#   label says so. A lead thinking "I want to pay less tax" presses Tax.
#
#   All four payroll services are BOOKKEEPING, including the three that are
#   genuinely tax filings (941, 940, 1099 and W-2). A lead's word is "payroll"
#   and splitting the cluster across two buttons would hide half of it from
#   whoever only looked under one.
#
#   The assurance ladder (compilation, review, audit, agreed-upon procedures)
#   is ADVISORY because there is no assurance bucket to put it in. The four
#   stay together so a lead comparing rigor and price can see them side by
#   side. If a fourth bucket is ever added, this is the group that wants it,
#   and the Step 1 spine is locked, so that is a conversation first.
#
#   Audit Representation is TAX (IRS controversy) and has nothing to do with
#   Financial Statement Audit in advisory. The name collision is a Step 2 copy
#   hazard, not a category error.
ENGAGEMENT_TYPE_CATEGORIES: dict[EngagementType, ServiceCategory] = {
    # Tax: returns, extensions, other filings, IRS controversy, tax-benefit
    # studies, and planning.
    EngagementType.tax_return_1040: ServiceCategory.tax,
    EngagementType.tax_return_1040nr: ServiceCategory.tax,
    EngagementType.tax_return_1120: ServiceCategory.tax,
    EngagementType.tax_return_1120s: ServiceCategory.tax,
    EngagementType.tax_return_1065: ServiceCategory.tax,
    EngagementType.tax_return_990: ServiceCategory.tax,
    EngagementType.tax_return_1041: ServiceCategory.tax,
    EngagementType.tax_return_706: ServiceCategory.tax,
    EngagementType.tax_return_709: ServiceCategory.tax,
    EngagementType.amended_return_1040x: ServiceCategory.tax,
    EngagementType.amended_return_business: ServiceCategory.tax,
    EngagementType.extension_4868: ServiceCategory.tax,
    EngagementType.extension_7004: ServiceCategory.tax,
    EngagementType.extension_8868: ServiceCategory.tax,
    EngagementType.sales_use_tax: ServiceCategory.tax,
    EngagementType.fbar_international: ServiceCategory.tax,
    EngagementType.business_personal_property_tax: ServiceCategory.tax,
    EngagementType.benefit_plan_5500: ServiceCategory.tax,
    EngagementType.irs_notice_resolution: ServiceCategory.tax,
    EngagementType.tax_resolution: ServiceCategory.tax,
    # IRS controversy. Unrelated to Financial Statement Audit below.
    EngagementType.audit_representation: ServiceCategory.tax,
    EngagementType.rd_tax_credit_study: ServiceCategory.tax,
    EngagementType.cost_segregation_study: ServiceCategory.tax,
    # Advisory work, filed under Tax because that is the word the lead uses.
    EngagementType.tax_planning_advisory: ServiceCategory.tax,

    # Bookkeeping: the books, the systems that hold them, and payroll. The
    # three payroll filings sit here rather than under Tax so the whole payroll
    # cluster answers to one button.
    EngagementType.bookkeeping_monthly: ServiceCategory.bookkeeping,
    EngagementType.bookkeeping_quarterly: ServiceCategory.bookkeeping,
    EngagementType.bookkeeping_cleanup: ServiceCategory.bookkeeping,
    EngagementType.accounting_system_setup: ServiceCategory.bookkeeping,
    EngagementType.payroll_processing: ServiceCategory.bookkeeping,
    EngagementType.payroll_tax_941: ServiceCategory.bookkeeping,
    EngagementType.payroll_tax_940: ServiceCategory.bookkeeping,
    EngagementType.information_returns_1099_w2: ServiceCategory.bookkeeping,

    # Advisory: the assurance ladder, plus everything sold as a project or a
    # relationship rather than as a filing.
    EngagementType.financial_statement_compilation: ServiceCategory.advisory,
    EngagementType.financial_statement_review: ServiceCategory.advisory,
    EngagementType.financial_statement_audit: ServiceCategory.advisory,
    EngagementType.agreed_upon_procedures: ServiceCategory.advisory,
    EngagementType.fractional_cfo: ServiceCategory.advisory,
    EngagementType.entity_formation: ServiceCategory.advisory,
    EngagementType.nonprofit_formation_exemption: ServiceCategory.advisory,
    EngagementType.business_valuation: ServiceCategory.advisory,
    EngagementType.transaction_advisory: ServiceCategory.advisory,
    # The two catch-alls. They overlap with the intake form's own escape
    # answers ("Not sure yet" at Step 1, "None of these quite fits" at Step 2),
    # so whether they should be selectable at Step 2 at all is a live question
    # for the form, not for this map. They are categorized because an
    # uncategorized type is unreachable, which would decide that question by
    # accident.
    EngagementType.other_advisory: ServiceCategory.advisory,
    EngagementType.custom: ServiceCategory.advisory,
}


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
    lead_replied = "lead_replied"
    nurture_hold_for_approval = "nurture_hold_for_approval"
    # PROPOSED NAME -- pending Andrew's sign-off before any live firm is on this
    # (event names freeze once a firm goes live; this fires the hot lead alert).
    lead_hot_alert = "lead_hot_alert"
    # PROPOSED NAME -- pending Andrew's sign-off.
    # Fires when an enrollment reaches a dead_end step; triggers the firm-owner
    # take-over notification per Contract section 6.7.
    nurture_dead_end_reached = "nurture_dead_end_reached"


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
    lead_replied = "lead_replied"
    lead_hot_alert = "lead_hot_alert"
    nurture_dead_end_reached = "nurture_dead_end_reached"


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


class StepType(str, Enum):
    """One node in a nurture sequence's step graph."""
    trigger = "trigger"
    email = "email"
    wait_fixed = "wait_fixed"
    wait_until_event = "wait_until_event"
    branch = "branch"
    action = "action"
    goal = "goal"
    won = "won"
    dead_end = "dead_end"


class EnrollmentStatus(str, Enum):
    """Where an enrollment stands. active is the only status still being walked forward by the engine."""
    active = "active"
    unsubscribed = "unsubscribed"
    converted = "converted"
    removed_by_staff = "removed_by_staff"
    completed_dead_end = "completed_dead_end"
    completed_won = "completed_won"
    paused_reply = "paused_reply"
    held_for_approval = "held_for_approval"


class BookingStatus(str, Enum):
    """Status of a scheduled meeting with a lead.

    Values correspond to the candidate event names in section 9.1:
    lead.call_booked, lead.call_held, lead.call_no_show, lead.call_rescheduled.
    canceled is implied by the rebook and recovery flow described in section 7.2.
    """
    scheduled = "scheduled"
    completed = "completed"
    no_show = "no_show"
    canceled = "canceled"
    rescheduled = "rescheduled"


class MeetingLocationType(str, Enum):
    """How a staff member receives meeting participants.

    video  -- a permanent personal video room URL (Zoom, Meet, Teams).
    phone  -- a phone number.
    office -- a physical office address.

    Stored native_enum=False per standing rules.
    """
    video = "video"
    phone = "phone"
    office = "office"


class PricingMode(str, Enum):
    """
    How a firm's price for one service is served to a lead.

    fixed          -> runs full automation; the computed number is the price.
    starting_at    -> the same math, but proposals read "starting at".
    quote_required -> serves no number at all and routes intake to the firm
                      owner. Any unpriced path lands here too, by the
                      universal quote law.
    """
    fixed = "fixed"
    starting_at = "starting_at"
    quote_required = "quote_required"


class DimensionKind(str, Enum):
    """
    The shape of the answer a complexity dimension collects.

    boolean       -> yes or no.
    numeric_range -> a number bucketed into firm-defined tiers; the only kind
                     that carries units.
    categorical   -> one choice from a system-owned vocabulary; the only kind
                     that carries options.
    """
    boolean = "boolean"
    numeric_range = "numeric_range"
    categorical = "categorical"


class DimensionRole(str, Enum):
    """
    What a firm is using a configured dimension for.

    priced        -> the answer moves the price.
    informational -> the answer is collected and shown but never priced.
    guard         -> the answer is compared against a threshold that routes
                     the lead out of automation; requires a guard_threshold.
    """
    priced = "priced"
    informational = "informational"
    guard = "guard"


class SurfaceKind(str, Enum):
    """
    Which curated surface a surface_items row belongs to.

    briefing    -> the Morning Briefing: entity-level urgency, ranked daily,
                   capped, and stable for the day.
    observatory -> the Observatory: firm-level standing significance, which
                   persists for weeks until resolved or dismissed.

    The column is explicit so the frontend never infers placement from
    severity. A finding that is both urgent and significant produces two
    rows, one per surface.

    Copy vocabulary lives in the frontend, never here: briefing rows are
    "items" and observatory rows are "material signals". Code identifiers
    stay neutral.
    """
    briefing = "briefing"
    observatory = "observatory"


class DismissalReason(str, Enum):
    """
    Why an owner dismissed a surface item. Required on both surfaces.

    not_relevant    -> the item does not apply. Never resurfaces.
    already_handling -> the owner is on it. Starts a suppression window and
                       the item resurfaces at expiry if still unresolved.
    was_wrong       -> the item was factually wrong. Never resurfaces, and
                       the row is flagged for later human review.

    v1 records these and does nothing automatic with them. The response
    rules (tightening on not_relevant, human review for was_wrong) are design
    law for later sessions.
    """
    not_relevant = "not_relevant"
    already_handling = "already_handling"
    was_wrong = "was_wrong"
