# app/main.py

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.anniversary_service import check_client_anniversaries, check_document_expiries, check_credential_expiries
from app.services.recurring_engagement_service import spawn_recurring_engagements
from app.services.qbo_budget_service import run_budget_variance_checks
from app.services.gmail_signals_service import run_gmail_signals_for_all_firms
from app.services.outlook_signals_service import run_outlook_signals_for_all_firms
from app.services.esign_reminder_service import run_esign_auto_reminders, run_esign_escalation_check
from app.services.invoice_service import run_invoice_overdue_sweep
from app.services.findings_recheck import recheck_failed_findings
from app.services.deadline_scheduler import check_approaching_deadlines
from app.services.nurture_execution_service import run_nurture_tick
from app.services.metric_pipeline import run_nightly_metric_recompute
from app.services.irs_auth_service import check_expiring_authorizations
from app.core.scheduler_lock import try_acquire_scheduler_lock, release_scheduler_lock
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.clients import router as clients_router
from app.api.engagements import router as engagements_router
from app.api.engagement_members import router as engagement_members_router
from app.api.tasks import router as tasks_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.contacts import router as contacts_router
from app.api.firms import router as firms_router
from app.api.documents import router as documents_router
from app.api.document_requests import router as document_requests_router
from app.api.checklist_templates import router as checklist_templates_router
from app.api.esign import router as esign_router
from app.api.portal import router as portal_router
from app.api.invoices import router as invoices_router
from app.api.time_entries import router as time_entries_router
from app.api.stripe_connect import router as stripe_connect_router
from app.api.payments import router as payments_router
from app.api.automation_rules import router as automation_rules_router
from app.api.notifications import router as notifications_router
from app.api.notification_preferences import router as notification_preferences_router
from app.api.integrations import router as integrations_router
from app.api.admin_audit import router as admin_audit_router
from app.api.totp import router as totp_router
from app.api.retention import router as retention_router
from app.api.notes import router as notes_router
from app.api.messages import router as messages_router
from app.api.firm_chat import router as firm_chat_router
from app.api.concierge.route import router as concierge_router
from app.api.irs_authorizations import router as irs_authorizations_router
from app.api.extensions import router as extensions_router
from app.api.tax_organizers import router as tax_organizers_router
from app.api.transcript_requests import router as transcript_requests_router
from app.api.reports import router as reports_router
from app.api.dashboard import router as dashboard_router
from app.api.archive import router as archive_router
from app.api.peer_network import router as peer_network_router
from app.api.settings import router as settings_router
from app.api.engagement_templates import router as engagement_templates_router
from app.api.document_expiries import router as document_expiries_router
from app.api.qc_checklists import router as qc_checklists_router
from app.api.review_requests import router as review_requests_router
from app.api.ack_parser import router as ack_parser_router
from app.api.firm_export import router as firm_export_router
from app.api.migration import router as migration_router
from app.api.sending_domain import router as sending_domain_router
from app.api.portal_domain import router as portal_domain_router
from app.api.inbox import router as inbox_router
from app.api.calendar import router as calendar_router
from app.api.morning_briefing import router as morning_briefing_router
from app.api.staff_credentials import router as staff_credentials_router
from app.api.cpe_records import router as cpe_records_router
from app.api.intake import router as intake_router
from app.api.unsubscribe import router as unsubscribe_router
from app.api.webhooks.postmark_inbound import router as postmark_inbound_router
from app.api.availability_windows import router as availability_windows_router
from app.api.leads import router as leads_router
from app.api.referral_partners import router as referral_partners_router
from app.api.financial_intelligence import router as financial_intelligence_router
from app.api.pricing import router as pricing_router

from app.db.base_class import Base
from app.core.config import get_settings
from app.core.middleware import SecurityHeadersMiddleware
from app.core.context_middleware import RequestContextMiddleware
from app.core.rate_limit import limiter

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    acquired = try_acquire_scheduler_lock()

    if acquired:
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            check_client_anniversaries,
            trigger="cron",
            hour=8,
            minute=0,
            id="client_anniversary_check",
            replace_existing=True,
        )
        scheduler.add_job(
            check_document_expiries,
            trigger="cron",
            hour=8,
            minute=15,
            id="document_expiry_check",
            replace_existing=True,
        )
        scheduler.add_job(
            spawn_recurring_engagements,
            trigger="cron",
            hour=8,
            minute=30,
            id="recurring_engagement_spawn",
            replace_existing=True,
        )
        scheduler.add_job(
            run_budget_variance_checks,
            trigger="cron",
            hour=9,
            minute=0,
            id="qbo_budget_variance_check",
            replace_existing=True,
        )
        scheduler.add_job(
            run_gmail_signals_for_all_firms,
            "cron",
            hour=6,
            minute=0,
            id="gmail_signals_daily",
            replace_existing=True,
        )
        scheduler.add_job(
            run_outlook_signals_for_all_firms,
            "cron",
            hour=6,
            minute=15,
            id="outlook_signals_daily",
            replace_existing=True,
        )
        scheduler.add_job(
            check_credential_expiries,
            trigger="cron",
            hour=8,
            minute=35,
            id="credential_expiry_check",
            replace_existing=True,
        )
        scheduler.add_job(
            run_esign_auto_reminders,
            trigger="cron",
            hour=8,
            minute=45,
            id="esign_auto_reminders",
            replace_existing=True,
        )
        scheduler.add_job(
            run_esign_escalation_check,
            trigger="cron",
            hour=9,
            minute=15,
            id="esign_escalation_check",
            replace_existing=True,
        )
        # Scheduler invokes with no floors argument, so recheck_failed_findings
        # defaults to an empty floors_by_technique and every finding it touches
        # fails closed. Wiring a real floors source into this job is a BLOCKING
        # precondition of the first technique build, alongside the floor
        # registry design itself.
        scheduler.add_job(
            recheck_failed_findings,
            trigger="cron",
            day_of_week="sun",
            hour=5,
            minute=0,
            id="findings_weekly_recheck",
            replace_existing=True,
        )
        scheduler.add_job(
            run_invoice_overdue_sweep,
            trigger="cron",
            hour=7,
            minute=45,
            id="invoice_overdue_sweep",
            replace_existing=True,
        )
        # Runs before nightly_metric_recompute (4:00 AM) so deadline misses
        # are always recorded before the metrics job counts them, without
        # explicit dependency wiring between the two jobs.
        scheduler.add_job(
            check_approaching_deadlines,
            trigger="cron",
            hour=3,
            minute=30,
            id="deadline_miss_sweep",
            replace_existing=True,
        )
        scheduler.add_job(
            run_nightly_metric_recompute,
            trigger="cron",
            hour=4,
            minute=0,
            id="nightly_metric_recompute",
            replace_existing=True,
        )
        # 10:01 UTC. Hawaii-Aleutian is UTC-10 with no DST, so 10:00 UTC is
        # the moment the last US timezone rolls onto the server's calendar
        # date. That puts this at 12:01 am Hawaii, 3:01 am Pacific, 6:01 am
        # Eastern: outside working hours everywhere in the ICP, with the
        # warning waiting before anyone sits down.
        #
        # timezone is pinned explicitly because BackgroundScheduler()
        # otherwise resolves the zone through tzlocal from the host, and
        # nothing in this repo pins the droplet's TZ.
        #
        # This is a UX choice about when people get emailed, NOT where
        # correctness lives. The calendar safety is in
        # compute_expiry_cutoff_date, so running this sweep off schedule,
        # including through POST /irs-authorizations/run-expiry-check at four
        # in the morning, produces the same result.
        scheduler.add_job(
            check_expiring_authorizations,
            trigger="cron",
            hour=10,
            minute=1,
            timezone="UTC",
            id="irs_authorization_expiry_check",
            replace_existing=True,
        )
        # Runs every 15 minutes so no enrollment waits more than one quarter-hour
        # past its scheduled next_action_time. Shorter than hourly cron jobs here
        # because nurture latency is user-visible: a prospect receives an email
        # up to interval-length late. 15 minutes is the deliberate trade-off
        # between latency and DB load for a background tick that runs on every
        # active enrollment across all firms.
        scheduler.add_job(
            run_nurture_tick,
            trigger="cron",
            minute="*/15",
            id="nurture_execution_tick",
            replace_existing=True,
        )
        scheduler.start()

    try:
        yield
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
        if acquired:
            release_scheduler_lock()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "localhost",
        "127.0.0.1",
        "testserver",
        "jammpx.com",
        "*.jammpx.com",
    ],
)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(RequestContextMiddleware)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(firms_router)
app.include_router(users_router)
app.include_router(clients_router)
app.include_router(engagements_router)
app.include_router(engagement_members_router)
app.include_router(tasks_router)
app.include_router(contacts_router)
app.include_router(documents_router)
app.include_router(document_requests_router)
app.include_router(checklist_templates_router)
app.include_router(esign_router)
app.include_router(portal_router)
app.include_router(invoices_router, prefix="/invoices", tags=["invoices"])
app.include_router(time_entries_router, prefix="/time-entries", tags=["time-entries"])
app.include_router(stripe_connect_router, prefix="/stripe", tags=["stripe"])
# Payments router must be registered — webhook endpoint
# reads raw request body for Stripe HMAC validation
app.include_router(payments_router, prefix="/payments", tags=["payments"])
app.include_router(automation_rules_router)
app.include_router(notifications_router)
app.include_router(notification_preferences_router)
app.include_router(integrations_router)
app.include_router(admin_audit_router)
app.include_router(totp_router, prefix="/auth")
app.include_router(retention_router)
app.include_router(notes_router)
app.include_router(messages_router, tags=["Messages"])
app.include_router(firm_chat_router, tags=["Firm Chat"])
app.include_router(concierge_router)
app.include_router(irs_authorizations_router)
app.include_router(extensions_router)
app.include_router(tax_organizers_router)
app.include_router(transcript_requests_router)
app.include_router(reports_router)
app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
app.include_router(archive_router, prefix="/archive", tags=["archive"])
app.include_router(peer_network_router, prefix="/peer-network", tags=["Peer Network"])
app.include_router(settings_router)
app.include_router(engagement_templates_router, prefix="/api/v1")
app.include_router(document_expiries_router)
app.include_router(qc_checklists_router)
app.include_router(review_requests_router)
app.include_router(ack_parser_router, prefix="/api/v1/ack-parser", tags=["ACK Parser"])
app.include_router(firm_export_router, prefix="/api/v1", tags=["Firm Export"])
app.include_router(migration_router, prefix="/api/v1")
app.include_router(sending_domain_router, prefix="/api/v1")
app.include_router(portal_domain_router, prefix="/api/v1")
app.include_router(inbox_router, prefix="/api/v1")
app.include_router(calendar_router, prefix="/api/v1")
app.include_router(morning_briefing_router, prefix="/api/v1")
app.include_router(staff_credentials_router)
app.include_router(cpe_records_router)
app.include_router(postmark_inbound_router)
app.include_router(intake_router)
app.include_router(unsubscribe_router)
app.include_router(availability_windows_router)
app.include_router(leads_router)
app.include_router(referral_partners_router)
app.include_router(financial_intelligence_router)
app.include_router(pricing_router)


@app.get("/")
def root():
    return {"message": "JAMM PX is running"}


@app.get("/api/health")
def health_check():
    return {"status": "ok"}