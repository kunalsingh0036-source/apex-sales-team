import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db
from app.models.client import Client, ClientContact, BrandAsset, Interaction, SampleKit
from app.schemas.client import (
    ClientCreate, ClientUpdate, ClientResponse,
    LeadToClientConversion,
    ClientContactCreate, ClientContactUpdate, ClientContactResponse,
    BrandAssetCreate, BrandAssetResponse,
    InteractionCreate, InteractionResponse,
    SampleKitCreate, SampleKitUpdate, SampleKitResponse,
)
from app.schemas.common import PaginatedResponse
from app.services.client_service import ClientService

router = APIRouter()
client_service = ClientService()


# --- Clients CRUD ---

@router.get("", response_model=PaginatedResponse[ClientResponse])
async def list_clients(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    status: str | None = None,
    ama_tier: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    clients, total = await client_service.list_clients(
        db, status=status, ama_tier=ama_tier, search=search,
        page=page, per_page=per_page,
    )
    return PaginatedResponse(
        items=clients, total=total, page=page, per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(data: ClientCreate, db: AsyncSession = Depends(get_db)):
    client = Client(**data.model_dump())
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client


@router.post("/convert-lead", response_model=ClientResponse, status_code=201)
async def convert_lead_to_client(
    data: LeadToClientConversion, db: AsyncSession = Depends(get_db),
):
    try:
        client = await client_service.convert_lead_to_client(db, data)
        await db.commit()
        await db.refresh(client)
        return client
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    client = await client_service.get_client(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: uuid.UUID, data: ClientUpdate, db: AsyncSession = Depends(get_db),
):
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(client, key, value)
    await db.commit()
    await db.refresh(client)
    return client


@router.get("/{client_id}/revenue", response_model=dict)
async def get_client_revenue(
    client_id: uuid.UUID, db: AsyncSession = Depends(get_db),
):
    client = await db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return await client_service.get_client_revenue_summary(db, client_id)


# --- Client Contacts ---

@router.get("/{client_id}/contacts", response_model=list[ClientContactResponse])
async def list_contacts(client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ClientContact).where(ClientContact.client_id == client_id)
    )
    return list(result.scalars().all())


@router.post("/{client_id}/contacts", response_model=ClientContactResponse, status_code=201)
async def create_contact(
    client_id: uuid.UUID, data: ClientContactCreate, db: AsyncSession = Depends(get_db),
):
    contact = ClientContact(client_id=client_id, **data.model_dump())
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.patch("/{client_id}/contacts/{contact_id}", response_model=ClientContactResponse)
async def update_contact(
    client_id: uuid.UUID, contact_id: uuid.UUID,
    data: ClientContactUpdate, db: AsyncSession = Depends(get_db),
):
    contact = await db.get(ClientContact, contact_id)
    if not contact or contact.client_id != client_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(contact, key, value)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.delete("/{client_id}/contacts/{contact_id}", status_code=204)
async def delete_contact(
    client_id: uuid.UUID, contact_id: uuid.UUID, db: AsyncSession = Depends(get_db),
):
    contact = await db.get(ClientContact, contact_id)
    if not contact or contact.client_id != client_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    await db.delete(contact)
    await db.commit()


# --- Brand Assets ---

@router.get("/{client_id}/brand-assets", response_model=list[BrandAssetResponse])
async def list_brand_assets(client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BrandAsset).where(BrandAsset.client_id == client_id)
    )
    return list(result.scalars().all())


@router.post("/{client_id}/brand-assets", response_model=BrandAssetResponse, status_code=201)
async def create_brand_asset(
    client_id: uuid.UUID, data: BrandAssetCreate, db: AsyncSession = Depends(get_db),
):
    asset = BrandAsset(client_id=client_id, **data.model_dump())
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


@router.delete("/{client_id}/brand-assets/{asset_id}", status_code=204)
async def delete_brand_asset(
    client_id: uuid.UUID, asset_id: uuid.UUID, db: AsyncSession = Depends(get_db),
):
    asset = await db.get(BrandAsset, asset_id)
    if not asset or asset.client_id != client_id:
        raise HTTPException(status_code=404, detail="Brand asset not found")
    await db.delete(asset)
    await db.commit()


# --- Interactions ---

@router.get("/{client_id}/interactions", response_model=list[InteractionResponse])
async def list_interactions(client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Interaction)
        .where(Interaction.client_id == client_id)
        .order_by(Interaction.interaction_date.desc())
    )
    return list(result.scalars().all())


@router.post("/{client_id}/interactions", response_model=InteractionResponse, status_code=201)
async def create_interaction(
    client_id: uuid.UUID, data: InteractionCreate, db: AsyncSession = Depends(get_db),
):
    interaction = Interaction(client_id=client_id, **data.model_dump())
    db.add(interaction)
    await db.commit()
    await db.refresh(interaction)
    return interaction


# --- Sample Kits ---

@router.get("/{client_id}/sample-kits", response_model=list[SampleKitResponse])
async def list_sample_kits(client_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SampleKit).where(SampleKit.client_id == client_id)
    )
    return list(result.scalars().all())


@router.post("/{client_id}/sample-kits", response_model=SampleKitResponse, status_code=201)
async def create_sample_kit(
    client_id: uuid.UUID, data: SampleKitCreate, db: AsyncSession = Depends(get_db),
):
    kit = SampleKit(client_id=client_id, **data.model_dump(exclude={"client_id"}))
    db.add(kit)
    await db.commit()
    await db.refresh(kit)
    return kit


@router.patch("/{client_id}/sample-kits/{kit_id}", response_model=SampleKitResponse)
async def update_sample_kit(
    client_id: uuid.UUID, kit_id: uuid.UUID,
    data: SampleKitUpdate, db: AsyncSession = Depends(get_db),
):
    kit = await db.get(SampleKit, kit_id)
    if not kit or kit.client_id != client_id:
        raise HTTPException(status_code=404, detail="Sample kit not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(kit, key, value)
    await db.commit()
    await db.refresh(kit)
    return kit
