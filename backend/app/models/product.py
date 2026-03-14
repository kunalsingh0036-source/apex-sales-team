import uuid
from typing import Optional
from sqlalchemy import String, Text, Integer, Boolean, Numeric, ForeignKey, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base, UUIDMixin, TimestampMixin


class ProductCategory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "product_categories"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_categories.id")
    )
    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    products: Mapped[list["Product"]] = relationship("Product", back_populates="category")
    children: Mapped[list["ProductCategory"]] = relationship("ProductCategory")


class Product(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_categories.id"),
        nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, default="")
    gsm_range: Mapped[Optional[str]] = mapped_column(String(50))
    available_sizes: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    available_colors: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    available_customizations: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    base_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    pricing_tiers: Mapped[dict] = mapped_column(JSONB, default=dict)
    min_order_qty: Mapped[int] = mapped_column(Integer, default=50)
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    image_urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    extra_data: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    category: Mapped["ProductCategory"] = relationship("ProductCategory", back_populates="products")
