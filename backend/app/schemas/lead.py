import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


# --- Company Schemas ---

class CompanyCreate(BaseModel):
    name: str
    domain: Optional[str] = None
    industry: str
    sub_industry: Optional[str] = None
    employee_count: Optional[str] = None
    headquarters: Optional[str] = None
    linkedin_url: Optional[str] = None
    website: Optional[str] = None
    annual_revenue: Optional[str] = None


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    industry: Optional[str] = None
    sub_industry: Optional[str] = None
    employee_count: Optional[str] = None
    headquarters: Optional[str] = None
    linkedin_url: Optional[str] = None
    website: Optional[str] = None
    annual_revenue: Optional[str] = None


class CompanyResponse(BaseModel):
    id: uuid.UUID
    name: str
    domain: Optional[str]
    industry: str
    sub_industry: Optional[str]
    employee_count: Optional[str]
    headquarters: Optional[str]
    linkedin_url: Optional[str]
    website: Optional[str]
    annual_revenue: Optional[str]
    enrichment_data: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Lead Schemas ---

class LeadCreate(BaseModel):
    company_id: Optional[uuid.UUID] = None
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    linkedin_url: Optional[str] = None
    instagram_handle: Optional[str] = None
    job_title: str
    department: Optional[str] = None
    seniority: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "India"
    source: str = "manual"
    tags: list[str] = []
    notes: str = ""


class LeadUpdate(BaseModel):
    company_id: Optional[uuid.UUID] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    whatsapp_number: Optional[str] = None
    linkedin_url: Optional[str] = None
    instagram_handle: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    seniority: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    stage: Optional[str] = None
    deal_value: Optional[float] = None
    lost_reason: Optional[str] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    consent_status: Optional[str] = None
    do_not_contact: Optional[bool] = None


class LeadResponse(BaseModel):
    id: uuid.UUID
    company_id: Optional[uuid.UUID]
    first_name: str
    last_name: str
    full_name: str
    email: Optional[str]
    email_verified: bool
    phone: Optional[str]
    whatsapp_number: Optional[str]
    linkedin_url: Optional[str]
    instagram_handle: Optional[str]
    job_title: str
    department: Optional[str]
    seniority: Optional[str]
    city: Optional[str]
    state: Optional[str]
    country: str
    source: str
    lead_score: int
    score_breakdown: dict
    stage: str
    deal_value: Optional[float]
    tags: list[str]
    notes: str
    consent_status: str
    do_not_contact: bool
    created_at: datetime
    updated_at: datetime
    company: Optional[CompanyResponse] = None

    model_config = {"from_attributes": True}


class LeadStageUpdate(BaseModel):
    stage: str


class LeadFilter(BaseModel):
    industry: Optional[str] = None
    stage: Optional[str] = None
    seniority: Optional[str] = None
    department: Optional[str] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    city: Optional[str] = None
    state: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[list[str]] = None
    search: Optional[str] = None
