# migrations/env.py

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from app.db.base_class import Base
from app.core.config import get_settings

# Import all models so Alembic can see them and generate correct migrations
from app.models import user, engagement, task, client, contact
from app.models import firm, document, document_request, checklist_template, signature_envelope, engagement_letter_template
from app.models.portal_session import PortalSession
from app.models.portal_notification import PortalNotification
from app.models.invoice import Invoice
from app.models.time_entry import TimeEntry
from app.models.stripe_connection import StripeConnection
from app.models.automation_rule import AutomationRule, AutomationExecutionLog
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.integration import Integration
from app.models.audit_log import AuditLog
from app.models.retention import DataRetentionPolicy
from app.models.message import ClientMessage, ClientMessageRead
from app.models.firm_chat import Channel, ChannelMember, FirmMessage, FirmMessageRead
from app.models.irs_authorization import IrsAuthorization
from app.models.extension import Extension
from app.models.tax_organizer import TaxOrganizerTemplate, TaxOrganizer
from app.models.transcript_request import TranscriptRequest
from app.models.behavioral_event import BehavioralEvent
from app.models.document_expiry import DocumentExpiry
from app.models.qc_checklist import (
    QcChecklistTemplate, QcChecklistItem
)
from app.models.recurring_engagement_log import RecurringEngagementLog
from app.models.concierge_question_log import ConciergeQuestionLog
from app.models.concierge_notification import ConciergeNotification

settings = get_settings()

config = context.config

# Override sqlalchemy.url from settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is what autogenerate compares against
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()