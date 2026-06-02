# app/crud/client.py

from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID

from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate


def get_client_for_firm(db: Session, client_id: UUID, firm_id: UUID) -> Client | None:
    """
    Fetch a client by ID, but ONLY if it belongs to the specified firm.
    This is the correct way to fetch a client — always use this, never get_client alone.
    If a client with this ID exists but belongs to a different firm, this returns None.
    That means the API returns 404, not 403 — we don't even confirm the record exists.
    Returning 404 instead of 403 is intentional: it prevents an attacker from probing
    which IDs exist across firms.
    """
    stmt = select(Client).where(
        Client.id == client_id,
        Client.firm_id == firm_id,
    )
    return db.execute(stmt).scalars().first()


def get_client(db: Session, client_id: UUID) -> Client | None:
    """
    Fetch a client by ID without firm scoping.
    Only use this in internal contexts where tenant isolation is handled elsewhere.
    For all API endpoints, use get_client_for_firm instead.
    """
    return db.query(Client).filter(Client.id == client_id).first()


def get_clients(db: Session):
    return db.query(Client)


def create_client(db: Session, client_in: ClientCreate, firm_id: UUID) -> Client:
    """
    firm_id is passed explicitly from the tenant dependency — never from user input.
    This is why ClientCreate schema does NOT include a firm_id field.
    """
    data = client_in.model_dump()
    client = Client(**data, firm_id=firm_id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def update_client(db: Session, client: Client, client_in: ClientUpdate) -> Client:
    for key, value in client_in.model_dump(exclude_unset=True).items():
        setattr(client, key, value)
    db.commit()
    db.refresh(client)
    return client


def delete_client(db: Session, client: Client):
    db.delete(client)
    db.commit()