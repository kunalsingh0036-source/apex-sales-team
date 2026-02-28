from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = 1
    per_page: int = 50


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int
    total_pages: int


class MessageResponse(BaseModel):
    message: str
    success: bool = True
