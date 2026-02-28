import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.models.sequence import Sequence
from app.schemas.sequence import SequenceCreate, SequenceUpdate, SequenceResponse
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[SequenceResponse])
async def list_sequences(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    channel: str | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Sequence)
    count_query = select(func.count()).select_from(Sequence)

    if channel:
        query = query.where(Sequence.channel == channel)
        count_query = count_query.where(Sequence.channel == channel)
    if is_active is not None:
        query = query.where(Sequence.is_active == is_active)
        count_query = count_query.where(Sequence.is_active == is_active)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * per_page
    query = query.order_by(Sequence.created_at.desc()).offset(offset).limit(per_page)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[SequenceResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.post("", response_model=SequenceResponse, status_code=201)
async def create_sequence(data: SequenceCreate, db: AsyncSession = Depends(get_db)):
    sequence = Sequence(
        name=data.name,
        description=data.description,
        target_industry=data.target_industry,
        target_role=data.target_role,
        channel=data.channel,
        steps=[s.model_dump() for s in data.steps],
        settings=data.settings,
    )
    db.add(sequence)
    await db.commit()
    await db.refresh(sequence)
    return SequenceResponse.model_validate(sequence)


@router.get("/{sequence_id}", response_model=SequenceResponse)
async def get_sequence(sequence_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    sequence = result.scalar_one_or_none()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    return SequenceResponse.model_validate(sequence)


@router.put("/{sequence_id}", response_model=SequenceResponse)
async def update_sequence(
    sequence_id: uuid.UUID,
    data: SequenceUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    sequence = result.scalar_one_or_none()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")

    update_data = data.model_dump(exclude_unset=True)
    if "steps" in update_data and update_data["steps"] is not None:
        update_data["steps"] = [
            s.model_dump() if hasattr(s, "model_dump") else s
            for s in update_data["steps"]
        ]

    for key, value in update_data.items():
        setattr(sequence, key, value)

    await db.commit()
    await db.refresh(sequence)
    return SequenceResponse.model_validate(sequence)


@router.delete("/{sequence_id}")
async def delete_sequence(sequence_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    sequence = result.scalar_one_or_none()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")

    await db.delete(sequence)
    await db.commit()
    return {"message": "Sequence deleted", "success": True}


@router.post("/{sequence_id}/duplicate", response_model=SequenceResponse)
async def duplicate_sequence(
    sequence_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=404, detail="Sequence not found")

    clone = Sequence(
        name=f"{original.name} (Copy)",
        description=original.description,
        target_industry=original.target_industry,
        target_role=original.target_role,
        channel=original.channel,
        steps=original.steps,
        settings=original.settings,
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return SequenceResponse.model_validate(clone)
