from fastapi import HTTPException, status

def create_client(db: Session, client_in: ClientCreate) -> Client:
    if client_in.email:
        existing = (
            db.query(Client)
            .filter(Client.email == client_in.email)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Client with this email already exists"
            )

    db_client = Client(**client_in.model_dump())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client
