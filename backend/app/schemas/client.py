import uuid
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, EmailStr


# --- Client ---

class ClientCreate(BaseModel):
    company_id: uuid.UUID
    lead_id: Optional[uuid.UUID] = None
    primary_contact_name: str
    primary_contact_email: Optional[EmailStr] = None
    primary_contact_phone: Optional[str] = None
    primary_contact_title: Optional[str] = None
    ama_tier: Optional[str] = None
    ama_commitment: Optional[float] = None
    ama_start_date: Optional[date] = None
    ama_end_date: Optional[date] = None
    status: str = "active"
    billing_address: Optional[str] = None
    shipping_address: Optional[str] = None
    gst_number: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: str = ""
    tags: list[str] = []


class ClientUpdate(BaseModel):
    primary_contact_name: Optional[str] = None
    primary_contact_email: Optional[EmailStr] = None
    primary_contact_phone: Optional[str] = None
    primary_contact_title: Optional[str] = None
    ama_tier: Optional[str] = None
    ama_commitment: Optional[float] = None
    ama_start_date: Optional[date] = None
    ama_end_date: Optional[date] = None
    status: Optional[str] = None
    billing_address: Optional[str] = None
    shipping_address: Optional[str] = None
    gst_number: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[list[str]] = None


class ClientResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    lead_id: Optional[uuid.UUID]
    primary_contact_name: str
    primary_contact_email: Optional[str]
    primary_contact_phone: Optional[str]
    primary_contact_title: Optional[str]
    ama_tier: Optional[str]
    ama_commitment: Optional[float]
    ama_start_date: Optional[date]
    ama_end_date: Optional[date]
    status: str
    billing_address: Optional[str]
    shipping_address: Optional[str]
    gst_number: Optional[str]
    payment_terms: Optional[str]
    notes: str
    tags: list[str]
    extra_data: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeadToClientConversion(BaseModel):
    lead_id: uuid.UUID
    ama_tier: Optional[str] = None
    ama_commitment: Optional[float] = None
    billing_address: Optional[str] = None
    shipping_address: Optional[str] = None
    gst_number: Optional[str] = None
    payment_terms: Optional[str] = None


# --- Client Contact ---

class ClientContactCreate(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    is_primary: bool = False
    notes: str = ""


class ClientContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    is_primary: Optional[bool] = None
    notes: Optional[str] = None


class ClientContactResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    name: str
    email: Optional[str]
    phone: Optional[str]
    title: Optional[str]
    department: Optional[str]
    is_primary: bool
    notes: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Brand Asset ---

class BrandAssetCreate(BaseModel):
    asset_type: str
    name: str
    value: Optional[str] = None
    file_url: Optional[str] = None
    notes: str = ""


class BrandAssetResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    asset_type: str
    name: str
    value: Optional[str]
    file_url: Optional[str]
    notes: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Interaction ---

class InteractionCreate(BaseModel):
    type: str
    subject: str
    description: str = ""
    interaction_date: datetime
    performed_by: Optional[uuid.UUID] = None
    follow_up_date: Optional[date] = None


class InteractionResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    type: str
    subject: str
    description: str
    interaction_date: datetime
    performed_by: Optional[uuid.UUID]
    follow_up_date: Optional[date]
    extra_data: dict
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Sample Kit ---

class SampleKitCreate(BaseModel):
    client_id: Optional[uuid.UUID] = None
    lead_id: Optional[uuid.UUID] = None
    recipient_name: str
    recipient_company: Optional[str] = None
    kit_name: str
    contents: list = []
    status: str = "preparing"
    sent_date: Optional[date] = None
    follow_up_date: Optional[date] = None
    tracking_number: Optional[str] = None


class SampleKitUpdate(BaseModel):
    status: Optional[str] = None
    sent_date: Optional[date] = None
    delivered_date: Optional[date] = None
    follow_up_date: Optional[date] = None
    tracking_number: Optional[str] = None
    feedback: Optional[str] = None
    conversion_status: Optional[str] = None


class SampleKitResponse(BaseModel):
    id: uuid.UUID
    client_id: Optional[uuid.UUID]
    lead_id: Optional[uuid.UUID]
    recipient_name: str
    recipient_company: Optional[str]
    kit_name: str
    contents: list
    status: str
    sent_date: Optional[date]
    delivered_date: Optional[date]
    follow_up_date: Optional[date]
    tracking_number: Optional[str]
    feedback: str
    conversion_status: Optional[str]
    extra_data: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
