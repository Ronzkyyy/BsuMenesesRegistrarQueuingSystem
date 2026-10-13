"""
Document catalog models - the documents offered under Request Documents
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# Fee bounds shared by create/update: pesos, two decimal places, 0 = free.
_FEE = dict(ge=0, le=100000, max_digits=8, decimal_places=2)


class DocumentBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    short_name: str = Field(..., min_length=1, max_length=30)
    requirements: Optional[str] = Field(default=None, max_length=500)
    processing_time: Optional[str] = Field(default=None, max_length=50)
    fee: Optional[Decimal] = Field(default=None, **_FEE)

    @field_validator("requirements", "processing_time")
    @classmethod
    def blank_to_none(cls, v):
        # An emptied optional text box means "nothing listed", not "".
        return v or None


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    short_name: Optional[str] = Field(default=None, min_length=1, max_length=30)
    requirements: Optional[str] = Field(default=None, max_length=500)
    processing_time: Optional[str] = Field(default=None, max_length=50)
    fee: Optional[Decimal] = Field(default=None, **_FEE)
    is_active: Optional[bool] = None

    @field_validator("name", "short_name", "is_active")
    @classmethod
    def reject_explicit_null(cls, v):
        if v is None:
            raise ValueError("This field cannot be set to null")
        return v

    @field_validator("requirements", "processing_time")
    @classmethod
    def blank_to_none(cls, v):
        return v or None


class DocumentOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_ids: List[int] = Field(..., min_length=1, max_length=200)

    @field_validator("document_ids")
    @classmethod
    def positive_ids(cls, v):
        if any(i <= 0 for i in v):
            raise ValueError("Document ids must be positive")
        return v


class DocumentPublic(BaseModel):
    """What the kiosk and booking form need - no flags or timestamps."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    short_name: str
    requirements: Optional[str] = None
    processing_time: Optional[str] = None
    fee: Optional[Decimal] = None


class Document(DocumentPublic):
    display_order: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class RequestedDocument(BaseModel):
    """One document on a ticket/appointment, as snapshotted at request time."""
    model_config = ConfigDict(from_attributes=True)

    document_id: int
    name: str
    short_name: str
    fee: Optional[Decimal] = None


def fee_total(documents) -> Optional[Decimal]:
    """Sum of the listed fees, or None when no requested document lists one."""
    fees = [d.fee for d in documents if d.fee is not None]
    return sum(fees, Decimal("0")) if fees else None
