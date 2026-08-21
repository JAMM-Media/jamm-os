# app/models/folder.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Folder(Base):
    """
    A named container for client documents, created and managed by firm staff.

    Portal clients can view folders and upload into them but cannot create,
    rename, or delete folders. Folder structure is firm-controlled.

    parent_folder_id supports one optional level of nesting. Deleting a folder
    sets parent_folder_id to NULL on any child folders (they become top-level)
    and sets folder_id to NULL on any contained documents (they move to root).
    Both cascades are handled by the FK ondelete="SET NULL" at the DB level.
    No documents or child folders are ever deleted when a folder is removed.
    """

    __tablename__ = "folders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # One optional level of nesting. SET NULL so deleting a parent folder
    # does not delete its children -- they become top-level folders.
    parent_folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    firm: Mapped["Firm"] = relationship("Firm")
    client: Mapped["Client"] = relationship("Client")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="folder")
