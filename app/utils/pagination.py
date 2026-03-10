# app/utils/pagination.py

from sqlalchemy.orm import Query
from typing import Any


def paginate(query: Query, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    total = query.count()
    items = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }


def apply_sorting(query: Query, model, order_by: str | None = None, desc: bool = False) -> Query:
    if not order_by:
        return query  # No sorting applied

    column = getattr(model, order_by, None)
    if not column:
        return query  # Invalid column name, skip sorting

    return query.order_by(column.desc() if desc else column.asc())
