from pydantic import BaseModel
from typing import Generic, TypeVar, List
from pydantic.generics import GenericModel

T = TypeVar("T")

class PaginatedResponse(GenericModel, Generic[T]):
    total: int
    limit: int
    offset: int
    items: List[T]
