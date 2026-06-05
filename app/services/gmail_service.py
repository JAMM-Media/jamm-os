# app/services/gmail_service.py

import logging
import threading
from datetime import datetime, timezone
from uuid import UUID

import requests as http_requests
from google_auth_oauthlib.flow import Flow
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crud import integration as crud_integration
from app.models.integration import Integration
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event
from app.services.token_encryption import encrypt_token

logger = logging.getLogger(__name__)

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.metadata",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]
GMAIL_PROVIDER = "gmail"


class GmailService:

    def _build_flow(self) -> Flow:
        settings = get_settings()
        return Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                }
            },
            scopes=GMAIL_SCOPES,
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
        )

    def get_authorization_url(self, firm_id: UUID) -> str:
        flow = self._build_flow()
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            state=str(firm_id),
            include_granted_scopes="true",
        )
        return authorization_url

    def handle_callback(self, code: str, state: str, db: Session) -> Integration:
        try:
            firm_id = UUID(state)
        except (ValueError, AttributeError) as e:
            logger.error("Invalid state parameter: %s", type(e).__name__)
            raise ValueError("Invalid state parameter") from e

        integration = crud_integration.get_integration(db, firm_id=firm_id, provider=GMAIL_PROVIDER)
        if not integration:
            integration = crud_integration.create_integration(db, firm_id=firm_id, provider=GMAIL_PROVIDER)

        try:
            flow = self._build_flow()
            flow.fetch_token(code=code)
            credentials = flow.credentials

            resp = http_requests.get(
                "https://www.googleapis.com/oauth2/v1/userinfo",
                headers={"Authorization": f"Bearer {credentials.token}"},
                timeout=10,
            )
            resp.raise_for_status()
            email = resp.json().get("email")

            scopes_string = (
                " ".join(credentials.scopes) if credentials.scopes else " ".join(GMAIL_SCOPES)
            )

            expiry = None
            if credentials.expiry:
                expiry = credentials.expiry.replace(tzinfo=timezone.utc)

            integration.encrypted_access_token = encrypt_token(credentials.token)
            if credentials.refresh_token:
                integration.encrypted_refresh_token = encrypt_token(credentials.refresh_token)
            integration.token_expires_at = expiry
            integration.scopes = scopes_string
            integration.external_account_id = email
            integration.status = "connected"
            integration.connected_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(integration)

            integration_id = integration.id
            threading.Thread(
                target=log_event,
                kwargs={
                    "event_type": "integration.connected",
                    "firm_id": firm_id,
                    "entity_type": "integration",
                    "entity_id": integration_id,
                    "metadata": {"provider": GMAIL_PROVIDER, "scopes": scopes_string},
                },
                daemon=True,
            ).start()

            write_audit_log(
                db=db,
                firm_id=firm_id,
                action="integration.connected",
                actor_type="system",
                entity_type="integration",
                entity_id=integration.id,
                metadata={"provider": GMAIL_PROVIDER},
            )

            return integration

        except Exception as e:
            logger.error("Gmail callback failed: %s", type(e).__name__)
            crud_integration.update_integration_status(
                db, integration, status="error", error_message=str(e)
            )
            raise
