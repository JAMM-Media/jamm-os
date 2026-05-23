from app.models.irs_authorization import IrsAuthorization
from app.models.extension import Extension
# app/models/__init__.py
# Import order matters here: Firm must come first because every other
# model has a foreign key pointing to it. Python needs to see the Firm
# class definition before models that reference it.
from app.models.firm import Firm
from app.models.user import User
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.task import Task
from app.models.contact import Contact
from app.models.document import Document, DocumentAuditLog
from app.models.document_request import DocumentRequest
from app.models.checklist_template import ChecklistTemplate
from app.models.signature_envelope import SignatureEnvelope
from app.models.engagement_letter_template import EngagementLetterTemplate
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
from app.models.note import Note
from app.models.message import ClientMessage, ClientMessageRead
from app.models.firm_chat import Channel, FirmMessage, FirmMessageRead
from app.models.tax_organizer import TaxOrganizerTemplate, TaxOrganizer
from app.models.transcript_request import TranscriptRequest
from app.models.behavioral_event import BehavioralEvent
from app.models.engagement_template import EngagementTemplate