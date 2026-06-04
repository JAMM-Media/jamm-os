# app/crud/portal_session.py

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.portal_session import PortalSession
from app.schemas.portal_session import PortalSessionCreate


def create_session(db: Session, data: PortalSessionCreate) -> PortalSession:
    session = PortalSession(
        firm_id=data.firm_id,
        client_id=data.client_id,
        refresh_token_hash=data.refresh_token_hash,
        access_jti=data.access_jti,
        ip_address=data.ip_address,
        user_agent=data.user_agent,
        expires_at=data.expires_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_by_jti(
    db: Session,
    jti: str,
    firm_id: uuid.UUID,
) -> PortalSession | None:
    stmt = select(PortalSession).where(
        PortalSession.access_jti == jti,
        PortalSession.firm_id == firm_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_active_sessions_for_client(
    db: Session,
    client_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> list[PortalSession]:
    stmt = select(PortalSession).where(
        PortalSession.client_id == client_id,
        PortalSession.firm_id == firm_id,
        PortalSession.is_revoked.is_(False),
    )
    return list(db.execute(stmt).scalars().all())


def update_session_activity(db: Session, session: PortalSession) -> PortalSession:
    """Set last_active_at to now — called on every authenticated portal request."""
    session.last_active_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


def revoke_session(
    db: Session,
    session: PortalSession,
    revoked_by: str,
) -> PortalSession:
    session.is_revoked = True
    session.revoked_at = datetime.now(timezone.utc)
    session.revoked_by = revoked_by
    db.commit()
    db.refresh(session)
    return session


def revoke_all_client_sessions(
    db: Session,
    client_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> int:
    """Revoke all active sessions for a client. Returns count of sessions revoked."""
    now = datetime.now(timezone.utc)
    stmt = (
        update(PortalSession)
        .where(
            PortalSession.client_id == client_id,
            PortalSession.firm_id == firm_id,
            PortalSession.is_revoked.is_(False),
        )
        .values(is_revoked=True, revoked_at=now, revoked_by="firm_owner")
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount


def cleanup_expired_sessions(db: Session) -> int:
    """Mark all expired but not yet revoked sessions as revoked. Returns count updated."""
    now = datetime.now(timezone.utc)
    stmt = (
        update(PortalSession)
        .where(
            PortalSession.expires_at < now,
            PortalSession.is_revoked.is_(False),
        )
        .values(is_revoked=True, revoked_at=now, revoked_by="system")
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount
