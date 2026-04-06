import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TemplateCreate(BaseModel):
    name: str
    channel: str = "email"
    category: Optional[str] = None
    subject: Optional[str] = None
    body: str
    variables: list[str] = []
    tone: str = "authoritative_warm"
    industry_tags: list[str] = []
    role_tags: list[str] = []


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    channel: Optional[str] = None
    category: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    variables: Optional[list[str]] = None
    tone: Optional[str] = None
    industry_tags: Optional[list[str]] = None
    role_tags: Optional[list[str]] = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    channel: str
    category: Optional[str]
    subject: Optional[str]
    body: str
    variables: list[str]
    tone: str
    industry_tags: list[str]
    role_tags: list[str]
    performance: dict
    is_ai_generated: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    campaign_id: Optional[uuid.UUID]
    channel: str
    direction: str
    subject: Optional[str]
    body: str
    status: str
    classification: Optional[str]
    classification_confidence: Optional[float]
    ai_suggested_reply: Optional[str]
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    opened_at: Optional[datetime]
    replied_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    lead_id: uuid.UUID
    channel: str = "email"
    subject: Optional[str] = None
    body: str
    schedule_at: Optional[datetime] = None


class GenerateMessageRequest(BaseModel):
    lead_id: uuid.UUID
    channel: str = "email"
    message_type: str = "cold_intro"
    context: str = ""
    custom_instructions: str = ""


class ApproveBatchRequest(BaseModel):
    message_ids: list[uuid.UUID]


class RegenerateRequest(BaseModel):
    custom_instructions: str = ""
