import uuid
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel


# --- Quote Item ---

class QuoteItemCreate(BaseModel):
    product_id: Optional[uuid.UUID] = None
    product_name: str
    description: str = ""
    quantity: int
    unit_price: float
    size_breakdown: dict = {}
    color: Optional[str] = None
    gsm: Optional[int] = None
    customization_type: Optional[str] = None
    customization_details: str = ""


class QuoteItemResponse(BaseModel):
    id: uuid.UUID
    quote_id: uuid.UUID
    product_id: Optional[uuid.UUID]
    product_name: str
    description: str
    quantity: int
    unit_price: float
    total_price: float
    size_breakdown: dict
    color: Optional[str]
    gsm: Optional[int]
    customization_type: Optional[str]
    customization_details: str

    model_config = {"from_attributes": True}


# --- Quote ---

class QuoteCreate(BaseModel):
    client_id: uuid.UUID
    valid_from: date
    valid_until: date
    payment_terms: Optional[str] = None
    delivery_terms: Optional[str] = None
    notes: str = ""
    terms_and_conditions: str = ""
    gst_rate: float = 18.0
    discount_percent: float = 0
    created_by: Optional[uuid.UUID] = None
    line_items: list[QuoteItemCreate] = []


class QuoteUpdate(BaseModel):
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    payment_terms: Optional[str] = None
    delivery_terms: Optional[str] = None
    notes: Optional[str] = None
    terms_and_conditions: Optional[str] = None
    gst_rate: Optional[float] = None
    discount_percent: Optional[float] = None


class QuoteResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    quote_number: str
    status: str
    subtotal: float
    gst_rate: float
    gst_amount: float
    discount_percent: float
    discount_amount: float
    total_amount: float
    currency: str
    valid_from: date
    valid_until: date
    payment_terms: Optional[str]
    delivery_terms: Optional[str]
    notes: str
    terms_and_conditions: str
    converted_to_order_id: Optional[uuid.UUID]
    sent_at: Optional[datetime]
    viewed_at: Optional[datetime]
    accepted_at: Optional[datetime]
    created_by: Optional[uuid.UUID]
    extra_data: dict
    created_at: datetime
    updated_at: datetime
    line_items: list[QuoteItemResponse] = []

    model_config = {"from_attributes": True}


class QuoteStatusUpdate(BaseModel):
    status: str


class QuoteToOrderConversion(BaseModel):
    shipping_address: Optional[str] = None
    billing_address: Optional[str] = None
    expected_delivery_date: Optional[date] = None
    priority: str = "normal"
    assigned_to: Optional[uuid.UUID] = None
    notes: str = ""
