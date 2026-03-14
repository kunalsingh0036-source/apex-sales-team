import uuid
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel


# --- Order Item ---

class OrderItemCreate(BaseModel):
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


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
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
    extra_data: dict

    model_config = {"from_attributes": True}


# --- Order ---

class OrderCreate(BaseModel):
    client_id: uuid.UUID
    quote_id: Optional[uuid.UUID] = None
    expected_delivery_date: Optional[date] = None
    brief_received_date: Optional[date] = None
    shipping_address: Optional[str] = None
    billing_address: Optional[str] = None
    notes: str = ""
    priority: str = "normal"
    assigned_to: Optional[uuid.UUID] = None
    gst_rate: float = 18.0
    discount_percent: float = 0
    line_items: list[OrderItemCreate] = []


class OrderUpdate(BaseModel):
    expected_delivery_date: Optional[date] = None
    actual_delivery_date: Optional[date] = None
    brief_received_date: Optional[date] = None
    shipping_address: Optional[str] = None
    billing_address: Optional[str] = None
    notes: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[uuid.UUID] = None
    gst_rate: Optional[float] = None
    discount_percent: Optional[float] = None


class OrderResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    quote_id: Optional[uuid.UUID]
    order_number: str
    stage: str
    subtotal: float
    gst_rate: float
    gst_amount: float
    discount_percent: float
    discount_amount: float
    total_amount: float
    currency: str
    expected_delivery_date: Optional[date]
    actual_delivery_date: Optional[date]
    brief_received_date: Optional[date]
    shipping_address: Optional[str]
    billing_address: Optional[str]
    notes: str
    priority: str
    assigned_to: Optional[uuid.UUID]
    extra_data: dict
    created_at: datetime
    updated_at: datetime
    line_items: list[OrderItemResponse] = []

    model_config = {"from_attributes": True}


# --- Stage Change ---

class OrderStageChange(BaseModel):
    to_stage: str
    notes: str = ""
    changed_by: Optional[uuid.UUID] = None


class OrderStageLogResponse(BaseModel):
    id: uuid.UUID
    order_id: uuid.UUID
    from_stage: Optional[str]
    to_stage: str
    notes: str
    changed_by: Optional[uuid.UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Pipeline Summary ---

class PipelineStageSummary(BaseModel):
    stage: str
    count: int
    total_value: float


class PipelineSummary(BaseModel):
    stages: list[PipelineStageSummary]
    total_orders: int
    total_pipeline_value: float
