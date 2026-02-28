import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.models.message import MessageTemplate
from app.schemas.message import TemplateCreate, TemplateUpdate, TemplateResponse
from app.schemas.common import PaginatedResponse
from app.services.ai_engine import ai_engine

router = APIRouter()


@router.get("", response_model=PaginatedResponse[TemplateResponse])
async def list_templates(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    channel: str | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(MessageTemplate)
    count_query = select(func.count()).select_from(MessageTemplate)

    if channel:
        query = query.where(MessageTemplate.channel == channel)
        count_query = count_query.where(MessageTemplate.channel == channel)
    if category:
        query = query.where(MessageTemplate.category == category)
        count_query = count_query.where(MessageTemplate.category == category)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * per_page
    query = query.order_by(MessageTemplate.created_at.desc()).offset(offset).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[TemplateResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.post("", response_model=TemplateResponse, status_code=201)
async def create_template(data: TemplateCreate, db: AsyncSession = Depends(get_db)):
    template = MessageTemplate(**data.model_dump())
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return TemplateResponse.model_validate(template)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MessageTemplate).where(MessageTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateResponse.model_validate(template)


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    data: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MessageTemplate).where(MessageTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(template, key, value)

    await db.commit()
    await db.refresh(template)
    return TemplateResponse.model_validate(template)


@router.delete("/{template_id}")
async def delete_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MessageTemplate).where(MessageTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    await db.delete(template)
    await db.commit()
    return {"message": "Template deleted", "success": True}


@router.post("/generate", response_model=TemplateResponse)
async def ai_generate_template(
    channel: str = "email",
    message_type: str = "cold_intro",
    industry: str = "Technology & SaaS",
    role: str = "Procurement Manager",
    db: AsyncSession = Depends(get_db),
):
    """Use Claude to generate a message template in Apex brand voice."""
    result = await ai_engine.generate_outreach_message(
        lead_name="{{first_name}} {{last_name}}",
        lead_title="{{job_title}}",
        lead_company="{{company_name}}",
        lead_industry=industry,
        channel=channel,
        message_type=message_type,
    )

    template = MessageTemplate(
        name=f"AI: {message_type} - {industry} ({channel})",
        channel=channel,
        category=message_type,
        subject=result.get("subject"),
        body=result.get("body", ""),
        variables=["first_name", "last_name", "job_title", "company_name"],
        industry_tags=[industry],
        role_tags=[role],
        is_ai_generated=True,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return TemplateResponse.model_validate(template)
