"""API schemas shared by all routes: the error envelope and paginated lists."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

MAX_PAGE_SIZE = 100


class ErrorBody(BaseModel):
    code: str = Field(examples=["validation_error"])
    message: str
    details: Any | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Every error response has this shape, whatever went wrong."""

    error: ErrorBody


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=MAX_PAGE_SIZE)
    total: int = Field(ge=0)
    has_next: bool
