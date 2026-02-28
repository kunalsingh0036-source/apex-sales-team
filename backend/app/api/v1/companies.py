import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.models.lead import Company
from app.schemas.lead import CompanyCreate, CompanyUpdate, CompanyResponse
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[CompanyResponse])
async def list_companies(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    industry: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Company)
    count_query = select(func.count()).select_from(Company)

    if industry:
        query = query.where(Company.industry == industry)
        count_query = count_query.where(Company.industry == industry)
    if search:
        search_filter = Company.name.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * per_page
    query = query.order_by(Company.created_at.desc()).offset(offset).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[CompanyResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.post("", response_model=CompanyResponse, status_code=201)
async def create_company(data: CompanyCreate, db: AsyncSession = Depends(get_db)):
    company = Company(**data.model_dump())
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return CompanyResponse.model_validate(company)


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyResponse.model_validate(company)


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: uuid.UUID,
    data: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(company, key, value)

    await db.commit()
    await db.refresh(company)
    return CompanyResponse.model_validate(company)


@router.delete("/{company_id}")
async def delete_company(company_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    await db.delete(company)
    await db.commit()
    return {"message": "Company deleted", "success": True}
