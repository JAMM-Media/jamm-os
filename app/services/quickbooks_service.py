# app/services/quickbooks_service.py

import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crud import integration as crud_integration
from app.models.integration import Integration
from app.models.client import Client
from app.services.behavioral_log import log_event
from app.services.token_encryption import decrypt_token

logger = logging.getLogger(__name__)

INTUIT_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QB_SCOPES = "com.intuit.quickbooks.accounting"
QB_PROVIDER = "quickbooks"


class QuickBooksService:

    def get_authorization_url(self, firm_id: UUID) -> str:
        """Build and return the Intuit OAuth2 authorization URL."""
        settings = get_settings()
        state = str(firm_id)
        params = {
            "client_id": settings.QUICKBOOKS_CLIENT_ID,
            "response_type": "code",
            "scope": QB_SCOPES,
            "redirect_uri": settings.QUICKBOOKS_REDIRECT_URI,
            "state": state,
        }
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://appcenter.intuit.com/connect/oauth2?{query_string}"

    def handle_callback(
        self,
        code: str,
        realm_id: str,
        state: str,
        db: Session,
    ) -> Integration:
        """
        Exchange the authorization code for tokens and store them encrypted.
        state encodes the firm_id.
        """
        settings = get_settings()
        try:
            firm_id = UUID(state)
        except (ValueError, AttributeError) as e:
            logger.error("Invalid state parameter: %s", type(e).__name__)
            raise ValueError("Invalid state parameter") from e

        integration = crud_integration.get_integration(db, firm_id=firm_id, provider=QB_PROVIDER)
        if not integration:
            integration = crud_integration.create_integration(db, firm_id=firm_id, provider=QB_PROVIDER)

        try:
            resp = requests.post(
                INTUIT_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.QUICKBOOKS_REDIRECT_URI,
                },
                auth=(settings.QUICKBOOKS_CLIENT_ID, settings.QUICKBOOKS_CLIENT_SECRET),
                timeout=15,
            )
            resp.raise_for_status()
            token_data = resp.json()

            access_token = token_data["access_token"]
            refresh_token = token_data["refresh_token"]
            expires_in = int(token_data.get("expires_in", 3600))
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            integration = crud_integration.update_integration_tokens(
                db,
                integration,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scopes=QB_SCOPES,
                external_account_id=realm_id,
            )
            return integration

        except Exception as e:
            logger.error("QuickBooks callback failed: %s", type(e).__name__)
            crud_integration.update_integration_status(
                db, integration, status="error", error_message=str(e)
            )
            raise

    def refresh_tokens_if_needed(
        self,
        integration: Integration,
        db: Session,
    ) -> Integration:
        """Refresh tokens if they expire within 5 minutes."""
        settings = get_settings()
        if integration.token_expires_at is None:
            return integration

        expires_at = integration.token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        time_until_expiry = expires_at - datetime.now(timezone.utc)
        if time_until_expiry > timedelta(minutes=5):
            return integration

        try:
            current_refresh_token = decrypt_token(integration.encrypted_refresh_token)
            resp = requests.post(
                INTUIT_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": current_refresh_token,
                },
                auth=(settings.QUICKBOOKS_CLIENT_ID, settings.QUICKBOOKS_CLIENT_SECRET),
                timeout=15,
            )
            resp.raise_for_status()
            token_data = resp.json()

            access_token = token_data["access_token"]
            refresh_token = token_data["refresh_token"]
            expires_in = int(token_data.get("expires_in", 3600))
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            return crud_integration.update_integration_tokens(
                db,
                integration,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scopes=integration.scopes,
                external_account_id=integration.external_account_id,
            )
        except Exception as e:
            logger.error("QuickBooks token refresh failed: %s", type(e).__name__)
            crud_integration.update_integration_status(
                db, integration, status="error", error_message=str(e)
            )
            raise

    def get_access_token(self, integration: Integration, db: Session) -> str:
        """Refresh if needed, then decrypt and return the access token."""
        integration = self.refresh_tokens_if_needed(integration, db)
        return decrypt_token(integration.encrypted_access_token)

    def _get_headers(self, integration: Integration, db: Session) -> dict:
        """Return Authorization headers with a fresh access token."""
        token = self.get_access_token(integration, db)
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def _get_base_url(self) -> str:
        settings = get_settings()
        if settings.QUICKBOOKS_ENVIRONMENT == "sandbox":
            return "https://sandbox-quickbooks.api.intuit.com"
        return "https://quickbooks.api.intuit.com"

    def import_clients_from_quickbooks(
        self, integration: Integration, db: Session, firm_id: UUID
    ) -> dict:
        """
        Fetch all QB customers and create/update matching Client records.
        Returns {"imported": n, "updated": n, "skipped": n}.
        """
        realm_id = integration.external_account_id
        base_url = self._get_base_url()
        url = (
            f"{base_url}/v3/company/{realm_id}/query"
            "?query=SELECT * FROM Customer&minorversion=65"
        )
        headers = self._get_headers(integration, db)

        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        customers = (
            data.get("QueryResponse", {}).get("Customer", [])
        )

        imported = 0
        updated = 0
        skipped = 0

        for customer in customers:
            qb_id = str(customer.get("Id", ""))
            display_name = customer.get("DisplayName", "")
            email_obj = customer.get("PrimaryEmailAddr")
            email = email_obj.get("Address") if email_obj else None
            is_active = customer.get("Active", True)

            # Look for existing client by quickbooks_customer_id first, then email
            existing = None

            if qb_id:
                stmt = select(Client).where(
                    Client.firm_id == firm_id,
                    Client.quickbooks_customer_id == qb_id,
                )
                existing = db.execute(stmt).scalar_one_or_none()

            if existing is None and email:
                stmt = select(Client).where(
                    Client.firm_id == firm_id,
                    Client.email == email,
                )
                existing = db.execute(stmt).scalar_one_or_none()

            if existing is not None:
                # Only fill in quickbooks_customer_id if not already set
                if existing.quickbooks_customer_id is None and qb_id:
                    existing.quickbooks_customer_id = qb_id
                    db.commit()
                    updated += 1
                    log_event(
                        firm_id=firm_id,
                        event_type="client.qbo_synced",
                        entity_type="client",
                        entity_id=existing.id,
                        actor_type="system",
                        actor_id=None,
                        metadata={
                            "sync_direction": "import",
                            "fields_updated": ["quickbooks_customer_id"],
                            "conflicts_resolved": 0,
                        }
                    )
                else:
                    skipped += 1
            else:
                new_client = Client(
                    firm_id=firm_id,
                    name=display_name,
                    email=email,
                    quickbooks_customer_id=qb_id,
                    is_active=is_active,
                )
                db.add(new_client)
                db.commit()
                imported += 1
                log_event(
                    firm_id=firm_id,
                    event_type="client.qbo_synced",
                    entity_type="client",
                    entity_id=new_client.id,
                    actor_type="system",
                    actor_id=None,
                    metadata={
                        "sync_direction": "import",
                        "fields_updated": ["name", "email", "quickbooks_customer_id", "is_active"],
                        "conflicts_resolved": 0,
                    }
                )

        integration.last_synced_at = datetime.now(timezone.utc)
        db.commit()

        return {"imported": imported, "updated": updated, "skipped": skipped}

    def get_import_preview(
        self, integration: "Integration", db: Session, firm_id: UUID
    ) -> list[dict]:
        """
        Returns QB customers that do NOT yet exist as JAMM PX clients
        for this firm. Used by the onboarding import wizard to show
        a checkbox list of importable customers.

        Matches by quickbooks_customer_id first, then email.
        Returns a list of dicts with QB customer data — not Client objects.
        """
        from sqlalchemy import select as sa_select
        from app.models.client import Client

        realm_id = integration.external_account_id
        base_url = self._get_base_url()
        url = (
            f"{base_url}/v3/company/{realm_id}/query"
            "?query=SELECT * FROM Customer&minorversion=65"
        )
        headers = self._get_headers(integration, db)

        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        customers = resp.json().get("QueryResponse", {}).get("Customer", [])

        # Fetch existing QB IDs and emails for this firm
        existing_qb_ids = set(
            row[0]
            for row in db.execute(
                sa_select(Client.quickbooks_customer_id).where(
                    Client.firm_id == firm_id,
                    Client.quickbooks_customer_id.isnot(None),
                )
            ).all()
        )
        existing_emails = set(
            row[0].lower()
            for row in db.execute(
                sa_select(Client.email).where(
                    Client.firm_id == firm_id,
                    Client.email.isnot(None),
                )
            ).all()
            if row[0]
        )

        preview = []
        for customer in customers:
            qb_id = str(customer.get("Id", ""))
            display_name = customer.get("DisplayName", "")
            email_obj = customer.get("PrimaryEmailAddr")
            email = email_obj.get("Address") if email_obj else None

            # Skip if already imported
            if qb_id in existing_qb_ids:
                continue
            if email and email.lower() in existing_emails:
                continue

            preview.append({
                "quickbooks_customer_id": qb_id,
                "name": display_name,
                "email": email,
                "is_active": customer.get("Active", True),
            })

        return preview

    def import_selected_clients(
        self,
        integration: "Integration",
        db: Session,
        firm_id: UUID,
        quickbooks_customer_ids: list[str],
    ) -> dict:
        """
        Import a specific subset of QB customers as JAMM PX clients.
        Only creates clients whose quickbooks_customer_id is in the
        provided list. Skips any that already exist.

        Returns {imported: N, skipped: N}.
        """
        from sqlalchemy import select as sa_select
        from app.models.client import Client

        realm_id = integration.external_account_id
        base_url = self._get_base_url()
        url = (
            f"{base_url}/v3/company/{realm_id}/query"
            "?query=SELECT * FROM Customer&minorversion=65"
        )
        headers = self._get_headers(integration, db)

        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        customers = resp.json().get("QueryResponse", {}).get("Customer", [])

        # Filter to only requested IDs
        requested = set(quickbooks_customer_ids)
        target_customers = [
            c for c in customers
            if str(c.get("Id", "")) in requested
        ]

        imported = 0
        skipped = 0

        for customer in target_customers:
            qb_id = str(customer.get("Id", ""))
            display_name = customer.get("DisplayName", "")
            email_obj = customer.get("PrimaryEmailAddr")
            email = email_obj.get("Address") if email_obj else None

            # Check if already exists
            existing = db.execute(
                sa_select(Client).where(
                    Client.firm_id == firm_id,
                    Client.quickbooks_customer_id == qb_id,
                )
            ).scalars().first()

            if existing:
                skipped += 1
                continue

            if email:
                existing_by_email = db.execute(
                    sa_select(Client).where(
                        Client.firm_id == firm_id,
                        Client.email == email,
                    )
                ).scalars().first()
                if existing_by_email:
                    # Link QB ID to existing client
                    existing_by_email.quickbooks_customer_id = qb_id
                    db.commit()
                    skipped += 1
                    continue

            new_client = Client(
                firm_id=firm_id,
                name=display_name,
                email=email,
                quickbooks_customer_id=qb_id,
                is_active=customer.get("Active", True),
            )
            db.add(new_client)
            db.commit()
            imported += 1

        return {"imported": imported, "skipped": skipped}

    def export_client_to_quickbooks(
        self, integration: Integration, db: Session, client: Client
    ) -> str:
        """
        Create a QB customer for a JAMM PX client.
        If the client already has quickbooks_customer_id, skip and return it.
        Returns the quickbooks_customer_id string.
        """
        if client.quickbooks_customer_id:
            return client.quickbooks_customer_id

        realm_id = integration.external_account_id
        base_url = self._get_base_url()
        url = f"{base_url}/v3/company/{realm_id}/customer?minorversion=65"
        headers = self._get_headers(integration, db)

        body: dict = {"DisplayName": client.name}
        if client.email:
            body["PrimaryEmailAddr"] = {"Address": client.email}

        resp = requests.post(url, json=body, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        qb_customer_id = str(data["Customer"]["Id"])
        client.quickbooks_customer_id = qb_customer_id
        db.commit()

        return qb_customer_id

    def sync_clients(
        self, integration: Integration, db: Session, firm_id: UUID
    ) -> dict:
        """
        Import QB customers into JAMM PX, then export unlinked JAMM PX clients to QB.
        Returns {"imported": n, "updated": n, "skipped": n, "exported": n}.
        """
        result = self.import_clients_from_quickbooks(integration, db, firm_id)

        # Fetch clients with no quickbooks_customer_id
        stmt = select(Client).where(
            Client.firm_id == firm_id,
            Client.quickbooks_customer_id.is_(None),
        )
        unlinked_clients = list(db.execute(stmt).scalars().all())

        exported = 0
        for client in unlinked_clients:
            self.export_client_to_quickbooks(integration, db, client)
            exported += 1
            log_event(
                firm_id=firm_id,
                event_type="client.qbo_synced",
                entity_type="client",
                entity_id=client.id,
                actor_type="system",
                actor_id=None,
                metadata={
                    "sync_direction": "export",
                    "fields_updated": ["quickbooks_customer_id"],
                    "conflicts_resolved": 0,
                }
            )

        result["exported"] = exported
        return result
