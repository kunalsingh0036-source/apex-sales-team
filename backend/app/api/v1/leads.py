import uuid
import io
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select, func, or_, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
import pandas as pd
from app.dependencies import get_db
from app.models.lead import Company, Lead
from app.models.activity import Activity
from app.schemas.lead import (
    LeadCreate, LeadUpdate, LeadResponse, LeadStageUpdate, LeadFilter,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[LeadResponse])
async def list_leads(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    stage: str | None = None,
    industry: str | None = None,
    seniority: str | None = None,
    department: str | None = None,
    min_score: int | None = None,
    source: str | None = None,
    has_email: bool | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Lead).options(selectinload(Lead.company))
    count_query = select(func.count()).select_from(Lead)

    if stage:
        query = query.where(Lead.stage == stage)
        count_query = count_query.where(Lead.stage == stage)
    if seniority:
        query = query.where(Lead.seniority == seniority)
        count_query = count_query.where(Lead.seniority == seniority)
    if department:
        query = query.where(Lead.department == department)
        count_query = count_query.where(Lead.department == department)
    if min_score is not None:
        query = query.where(Lead.lead_score >= min_score)
        count_query = count_query.where(Lead.lead_score >= min_score)
    if source:
        query = query.where(Lead.source == source)
        count_query = count_query.where(Lead.source == source)
    if has_email is True:
        query = query.where(Lead.email.isnot(None), Lead.email != "")
        count_query = count_query.where(Lead.email.isnot(None), Lead.email != "")
    elif has_email is False:
        query = query.where(or_(Lead.email.is_(None), Lead.email == ""))
        count_query = count_query.where(or_(Lead.email.is_(None), Lead.email == ""))
    if industry:
        query = query.join(Company).where(Company.industry == industry)
        count_query = count_query.join(Company).where(Company.industry == industry)
    if search:
        search_filter = or_(
            Lead.first_name.ilike(f"%{search}%"),
            Lead.last_name.ilike(f"%{search}%"),
            Lead.email.ilike(f"%{search}%"),
            Lead.job_title.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * per_page
    query = query.order_by(Lead.lead_score.desc(), Lead.created_at.desc())
    query = query.offset(offset).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[LeadResponse.model_validate(lead) for lead in items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.post("", response_model=LeadResponse, status_code=201)
async def create_lead(data: LeadCreate, db: AsyncSession = Depends(get_db)):
    lead = Lead(**data.model_dump())
    db.add(lead)
    await db.commit()
    await db.refresh(lead)

    # Load company relationship
    if lead.company_id:
        await db.refresh(lead, ["company"])

    # Log activity
    activity = Activity(
        lead_id=lead.id,
        type="lead_created",
        description=f"Lead {lead.full_name} created from source: {lead.source}",
    )
    db.add(activity)
    await db.commit()

    return LeadResponse.model_validate(lead)


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Lead).options(selectinload(Lead.company)).where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return LeadResponse.model_validate(lead)


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    data: LeadUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Lead).options(selectinload(Lead.company)).where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    update_data = data.model_dump(exclude_unset=True)
    old_stage = lead.stage

    for key, value in update_data.items():
        setattr(lead, key, value)

    # Log stage change
    if "stage" in update_data and update_data["stage"] != old_stage:
        activity = Activity(
            lead_id=lead.id,
            type="stage_changed",
            description=f"Stage changed from {old_stage} to {update_data['stage']}",
            extra_data={"old_stage": old_stage, "new_stage": update_data["stage"]},
        )
        db.add(activity)

    await db.commit()
    await db.refresh(lead)
    return LeadResponse.model_validate(lead)


@router.delete("/{lead_id}")
async def delete_lead(lead_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from app.models.activity import Activity
    from app.models.message import Message
    from app.models.sequence import CampaignEnrollment

    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Delete related records to avoid foreign key constraints
    await db.execute(delete(Activity).where(Activity.lead_id == lead_id))
    await db.execute(delete(Message).where(Message.lead_id == lead_id))
    await db.execute(delete(CampaignEnrollment).where(CampaignEnrollment.lead_id == lead_id))
    await db.delete(lead)
    await db.commit()
    return {"message": "Lead deleted", "success": True}


@router.put("/{lead_id}/stage", response_model=LeadResponse)
async def update_lead_stage(
    lead_id: uuid.UUID,
    data: LeadStageUpdate,
    db: AsyncSession = Depends(get_db),
):
    valid_stages = [
        "prospect", "contacted", "engaged", "qualified",
        "proposal_sent", "negotiation", "won", "lost", "nurture",
    ]
    if data.stage not in valid_stages:
        raise HTTPException(
            status_code=400, detail=f"Invalid stage. Must be one of: {valid_stages}"
        )

    result = await db.execute(
        select(Lead).options(selectinload(Lead.company)).where(Lead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    old_stage = lead.stage
    lead.stage = data.stage

    activity = Activity(
        lead_id=lead.id,
        type="stage_changed",
        description=f"Stage changed from {old_stage} to {data.stage}",
        extra_data={"old_stage": old_stage, "new_stage": data.stage},
    )
    db.add(activity)
    await db.commit()
    await db.refresh(lead)
    return LeadResponse.model_validate(lead)


@router.get("/{lead_id}/timeline")
async def get_lead_timeline(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    # Verify lead exists
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Lead not found")

    activities = await db.execute(
        select(Activity)
        .where(Activity.lead_id == lead_id)
        .order_by(Activity.created_at.desc())
        .limit(100)
    )
    items = activities.scalars().all()
    return [
        {
            "id": str(a.id),
            "type": a.type,
            "channel": a.channel,
            "description": a.description,
            "metadata": a.extra_data,
            "created_at": a.created_at.isoformat(),
        }
        for a in items
    ]


@router.post("/bulk-import")
async def bulk_import_leads(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Import leads from CSV or Excel file.

    Expected columns: first_name, last_name, email, phone, job_title,
    department, seniority, company_name, industry, city, state, source
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    content = await file.read()

    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        elif file.filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        else:
            raise HTTPException(
                status_code=400, detail="File must be CSV or Excel (.xlsx/.xls)"
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    # Normalize column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    required = ["first_name", "last_name", "job_title"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {missing}. Required: {required}",
        )

    created_count = 0
    skipped_count = 0
    errors = []

    for idx, row in df.iterrows():
        try:
            # Handle company — find or create
            company = None
            company_name = row.get("company_name") or row.get("company")
            if pd.notna(company_name) and company_name:
                industry = row.get("industry", "Other")
                if pd.isna(industry):
                    industry = "Other"

                result = await db.execute(
                    select(Company).where(Company.name == str(company_name))
                )
                company = result.scalar_one_or_none()

                if not company:
                    company = Company(
                        name=str(company_name),
                        industry=str(industry),
                        domain=str(row.get("domain", "")) if pd.notna(row.get("domain")) else None,
                    )
                    db.add(company)
                    await db.flush()

            # Check for duplicate by email
            email = row.get("email")
            if pd.notna(email) and email:
                existing = await db.execute(
                    select(Lead).where(Lead.email == str(email))
                )
                if existing.scalar_one_or_none():
                    skipped_count += 1
                    continue

            lead = Lead(
                first_name=str(row["first_name"]),
                last_name=str(row["last_name"]),
                email=str(email) if pd.notna(email) else None,
                phone=str(row.get("phone", "")) if pd.notna(row.get("phone")) else None,
                whatsapp_number=str(row.get("whatsapp", "")) if pd.notna(row.get("whatsapp")) else None,
                linkedin_url=str(row.get("linkedin_url", "")) if pd.notna(row.get("linkedin_url")) else None,
                job_title=str(row["job_title"]),
                department=str(row.get("department", "")) if pd.notna(row.get("department")) else None,
                seniority=str(row.get("seniority", "")) if pd.notna(row.get("seniority")) else None,
                city=str(row.get("city", "")) if pd.notna(row.get("city")) else None,
                state=str(row.get("state", "")) if pd.notna(row.get("state")) else None,
                country=str(row.get("country", "India")) if pd.notna(row.get("country")) else "India",
                source=str(row.get("source", "csv_import")) if pd.notna(row.get("source")) else "csv_import",
                company_id=company.id if company else None,
            )
            db.add(lead)
            created_count += 1

        except Exception as e:
            errors.append({"row": idx + 2, "error": str(e)})

    await db.commit()

    return {
        "success": True,
        "created": created_count,
        "skipped_duplicates": skipped_count,
        "errors": errors[:20],  # Cap error reporting
        "total_rows": len(df),
    }
