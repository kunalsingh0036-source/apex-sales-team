import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# --- Product Category ---

class ProductCategoryCreate(BaseModel):
    name: str
    parent_id: Optional[uuid.UUID] = None
    description: str = ""
    sort_order: int = 0


class ProductCategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None


class ProductCategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: Optional[uuid.UUID]
    description: str
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Product ---

class ProductCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    category_id: uuid.UUID
    description: str = ""
    gsm_range: Optional[str] = None
    available_sizes: list[str] = []
    available_colors: list[str] = []
    available_customizations: list[str] = []
    base_price: Optional[float] = None
    pricing_tiers: dict = {}
    min_order_qty: int = 50
    lead_time_days: Optional[int] = None
    is_active: bool = True
    image_urls: list[str] = []


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    gsm_range: Optional[str] = None
    available_sizes: Optional[list[str]] = None
    available_colors: Optional[list[str]] = None
    available_customizations: Optional[list[str]] = None
    base_price: Optional[float] = None
    pricing_tiers: Optional[dict] = None
    min_order_qty: Optional[int] = None
    lead_time_days: Optional[int] = None
    is_active: Optional[bool] = None
    image_urls: Optional[list[str]] = None


class ProductResponse(BaseModel):
    id: uuid.UUID
    name: str
    sku: Optional[str]
    category_id: uuid.UUID
    description: str
    gsm_range: Optional[str]
    available_sizes: list[str]
    available_colors: list[str]
    available_customizations: list[str]
    base_price: Optional[float]
    pricing_tiers: dict
    min_order_qty: int
    lead_time_days: Optional[int]
    is_active: bool
    image_urls: list[str]
    extra_data: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
