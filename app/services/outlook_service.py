# app/services/outlook_service.py

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import UUID

import msal
import requests as http_requests
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crud import integration as crud_integration
from app.models.integration import Integration
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event
from app.services.token_encryption import encrypt_token

logger = logging.getLogger(__name__)

OUTLOOK_SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/User.Read",
    "offline_access",
]
OUTLOOK_PROVIDER = "outlook"


class OutlookService:

    def get_authorization_url(self, firm_id: UUID) -> str:
        settings = get_settings()
        app = msal.ConfidentialClientApplication(
            client_id=settings.MICROSOFT_CLIENT_ID,
            client_credential=settings.MICROSOFT_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}",
        )
        result = app.get_authorization_request_url(
            scopes=OUTLOOK_SCOPES,
            state=str(firm_id),
            redirect_uri=settings.MICROSOFT_REDIRECT_URI,
        )
        return result

    def handle_callback(self, code: str, state: str, db: Session) -> Integration:
        try:
            firm_id = UUID(state)
        except (ValueError, AttributeError) as e:
            logger.error("Invalid state parameter: %s", type(e).__name__)
            raise ValueError("Invalid state parameter") from e

        integration = crud_integration.get_integration(db, firm_id=firm_id, provider=OUTLOOK_PROVIDER)
        if not integration:
            integration = crud_integration.create_integration(db, firm_id=firm_id, provider=OUTLOOK_PROVIDER)

        try:
            settings = get_settings()
            app = msal.ConfidentialClientApplication(
                client_id=settings.MICROSOFT_CLIENT_ID,
                client_credential=settings.MICROSOFT_CLIENT_SECRET,
                authority=f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}",
            )
            result = app.acquire_token_by_authorization_code(
                code=code,
                scopes=OUTLOOK_SCOPES,
                redirect_uri=settings.MICROSOFT_REDIRECT_URI,
            )

            if "error" in result:
                raise ValueError(result.get("error_description", result["error"]))

            access_token = result["access_token"]
            refresh_token = result.get("refresh_token")
            expires_in = result.get("expires_in", 3600)
            token_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            resp = http_requests.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            resp.raise_for_status()
            email = resp.json().get("mail") or resp.json().get("userPrincipalName")

            integration.encrypted_access_token = encrypt_token(access_token)
            if refresh_token:
                integration.encrypted_refresh_token = encrypt_token(refresh_token)
            integration.token_expires_at = token_expiry
            integration.scopes = " ".join(OUTLOOK_SCOPES)
            integration.external_account_id = email
            integration.status = "connected"
            integration.connected_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(integration)

            integration_id = integration.id
            scopes_string = " ".join(OUTLOOK_SCOPES)
            threading.Thread(
                target=log_event,
                kwargs={
                    "event_type": "integration.connected",
                    "firm_id": firm_id,
                    "entity_type": "integration",
                    "entity_id": integration_id,
                    "metadata": {"provider": OUTLOOK_PROVIDER, "scopes": scopes_string},
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
                metadata={"provider": OUTLOOK_PROVIDER},
            )

            return integration

        except Exception as e:
            logger.error("Outlook callback failed: %s", type(e).__name__)
            crud_integration.update_integration_status(
                db, integration, status="error", error_message=str(e)
            )
            raise
