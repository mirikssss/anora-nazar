"""Схемы входа и выхода API модуля."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SignerRole = Literal["helper", "mahalla_banker", "veterinary"]


class HelperOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    district: str
    mahalla: str


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inn: str
    name: str
    category: str
    district: str
    registered_on: date
    account: str


class ActIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: str = Field(min_length=1, max_length=32)
    signer_id: str = Field(min_length=1, max_length=64)
    signer_role: SignerRole
    signed_on: date
    invoice_amount: int = Field(gt=0)


class ActOut(BaseModel):
    act_id: str
    application_id: str
    signer_id: str
    signer_role: str
    signed_on: date
    invoice_amount: int
    created_at: datetime
