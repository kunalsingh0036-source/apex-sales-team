import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SequenceStepSchema(BaseModel):
    step_number: int
    type: str  # email, linkedin, whatsapp, instagram, wait
    delay_days: int = 0
    template_id: Optional[str] = None
    subject_variants: list[str] = []
    body_variants: list[str] = []
    send_window: Optional[dict] = None  # {"start": "10:00", "end": "11:30"}
    exit_on_reply: bool = True
    channel: str = "email"


class SequenceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    target_industry: Optional[str] = None
    target_role: Optional[str] = None
    channel: str = "email"
    steps: list[SequenceStepSchema]
    settings: dict = {}


class SequenceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_industry: Optional[str] = None
    target_role: Optional[str] = None
    channel: Optional[str] = None
    is_active: Optional[bool] = None
    steps: Optional[list[SequenceStepSchema]] = None
    settings: Optional[dict] = None


class SequenceResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    target_industry: Optional[str]
    target_role: Optional[str]
    channel: str
    is_active: bool
    steps: list[dict]
    settings: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignCreate(BaseModel):
    name: str
    sequence_id: uuid.UUID
    target_filter: dict = {}


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    target_filter: Optional[dict] = None


class CampaignResponse(BaseModel):
    id: uuid.UUID
    name: str
    sequence_id: uuid.UUID
    status: str
    target_filter: dict
    total_leads: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    sequence: Optional[SequenceResponse] = None

    model_config = {"from_attributes": True}


class EnrollmentLeadSummary(BaseModel):
    id: uuid.UUID
    lead_code: str = ""
    full_name: str
    email: Optional[str] = None
    job_title: str
    company_name: Optional[str] = None
    lead_score: int = 0
    stage: str = "prospect"

    model_config = {"from_attributes": True}


class EnrollmentResponse(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    lead_id: uuid.UUID
    sequence_id: uuid.UUID
    current_step: int
    status: str
    enrolled_at: datetime
    last_step_at: Optional[datetime]
    next_step_at: Optional[datetime]
    lead: Optional[EnrollmentLeadSummary] = None

    model_config = {"from_attributes": True}


class EnrollLeadsRequest(BaseModel):
    lead_ids: list[uuid.UUID]
