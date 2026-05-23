# app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.anniversary_service import check_client_anniversaries, check_document_expiries
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.clients import router as clients_router
from app.api.engagements import router as engagements_router
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
from app.api.irs_authorizations import router as irs_authorizations_router
from app.api.extensions import router as extensions_router
from app.api.tax_organizers import router as tax_organizers_router
from app.api.transcript_requests import router as transcript_requests_router
from app.api.reports import router as reports_router
from app.api.dashboard import router as dashboard_router
from app.api.settings import router as settings_router
from app.api.engagement_templates import router as engagement_templates_router
from app.api.document_expiries import router as document_expiries_router
from app.api.qc_checklists import router as qc_checklists_router

from app.db.base_class import Base
from app.core.config import get_settings
from app.core.middleware import SecurityHeadersMiddleware
from app.core.rate_limit import limiter

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


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

if settings.env == "production":
    app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(firms_router)
app.include_router(users_router)
app.include_router(clients_router)
app.include_router(engagements_router)
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
app.include_router(irs_authorizations_router)
app.include_router(extensions_router)
app.include_router(tax_organizers_router)
app.include_router(transcript_requests_router)
app.include_router(reports_router)
app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
app.include_router(settings_router)
app.include_router(engagement_templates_router, prefix="/api/v1")
app.include_router(document_expiries_router)
app.include_router(qc_checklists_router)


@app.get("/")
def root():
    return {"message": "JAMM PX is running"}


@app.get("/api/health")
def health_check():
    return {"status": "ok"}