"""
Seed script for Apex Human product catalogue.
Run: python -m scripts.seed_products
"""

import asyncio
import uuid
from app.dependencies import engine, async_session
from app.models.product import ProductCategory, Product

CATEGORIES = [
    {
        "name": "Apparel - Upper Body",
        "description": "Premium corporate upper body wear",
        "sort_order": 1,
        "products": [
            {"name": "Classic Polo Shirt", "sku": "APX-POL-001", "gsm_range": "220-260", "base_price": 450, "min_order_qty": 50, "lead_time_days": 21,
             "available_sizes": ["XS", "S", "M", "L", "XL", "XXL"], "available_colors": ["White", "Navy", "Black", "Crimson", "Grey"],
             "available_customizations": ["Embroidery", "Screen Print", "Sublimation", "Woven Label"]},
            {"name": "Round Neck T-Shirt", "sku": "APX-TEE-001", "gsm_range": "180-220", "base_price": 320, "min_order_qty": 100, "lead_time_days": 14,
             "available_sizes": ["XS", "S", "M", "L", "XL", "XXL"], "available_colors": ["White", "Black", "Navy", "Grey", "Olive", "Maroon"],
             "available_customizations": ["Screen Print", "DTG Print", "Sublimation", "Heat Transfer"]},
            {"name": "Corporate Jacket", "sku": "APX-JKT-001", "gsm_range": "280-320", "base_price": 1200, "min_order_qty": 30, "lead_time_days": 28,
             "available_sizes": ["S", "M", "L", "XL", "XXL"], "available_colors": ["Black", "Navy", "Charcoal"],
             "available_customizations": ["Embroidery", "Woven Label", "Metal Badge"]},
            {"name": "Hoodie", "sku": "APX-HOD-001", "gsm_range": "300-380", "base_price": 850, "min_order_qty": 30, "lead_time_days": 21,
             "available_sizes": ["S", "M", "L", "XL", "XXL"], "available_colors": ["Black", "Grey", "Navy", "Olive"],
             "available_customizations": ["Embroidery", "Screen Print", "DTG Print"]},
            {"name": "Formal Shirt", "sku": "APX-FSH-001", "gsm_range": "120-160", "base_price": 680, "min_order_qty": 50, "lead_time_days": 21,
             "available_sizes": ["S", "M", "L", "XL", "XXL"], "available_colors": ["White", "Light Blue", "Pink", "Grey"],
             "available_customizations": ["Embroidery", "Monogram", "Woven Label"]},
            {"name": "Vest / Sleeveless", "sku": "APX-VST-001", "gsm_range": "180-220", "base_price": 280, "min_order_qty": 100, "lead_time_days": 14,
             "available_sizes": ["S", "M", "L", "XL", "XXL"], "available_colors": ["Black", "White", "Grey", "Navy"],
             "available_customizations": ["Screen Print", "Sublimation"]},
        ],
    },
    {
        "name": "Apparel - Lower Body",
        "description": "Premium corporate lower body wear",
        "sort_order": 2,
        "products": [
            {"name": "Cargo Trousers", "sku": "APX-CRG-001", "gsm_range": "240-300", "base_price": 780, "min_order_qty": 30, "lead_time_days": 21,
             "available_sizes": ["28", "30", "32", "34", "36", "38", "40"], "available_colors": ["Khaki", "Olive", "Black", "Navy"],
             "available_customizations": ["Embroidery", "Woven Label"]},
            {"name": "Track Pants / Joggers", "sku": "APX-JOG-001", "gsm_range": "280-340", "base_price": 550, "min_order_qty": 50, "lead_time_days": 14,
             "available_sizes": ["S", "M", "L", "XL", "XXL"], "available_colors": ["Black", "Grey", "Navy"],
             "available_customizations": ["Embroidery", "Screen Print"]},
            {"name": "Shorts", "sku": "APX-SHT-001", "gsm_range": "200-240", "base_price": 380, "min_order_qty": 50, "lead_time_days": 14,
             "available_sizes": ["S", "M", "L", "XL", "XXL"], "available_colors": ["Black", "Grey", "Navy", "Khaki"],
             "available_customizations": ["Embroidery", "Screen Print"]},
        ],
    },
    {
        "name": "Gifting & Merchandise",
        "description": "Corporate gifts, awards, and branded merchandise",
        "sort_order": 3,
        "products": [
            {"name": "Commemorative Coin", "sku": "APX-CON-001", "base_price": 350, "min_order_qty": 100, "lead_time_days": 28,
             "available_customizations": ["Engraving", "Enamel Fill", "Gold Plating", "Silver Plating"]},
            {"name": "Stainless Steel Bottle", "sku": "APX-BTL-001", "base_price": 480, "min_order_qty": 50, "lead_time_days": 14,
             "available_colors": ["Silver", "Black", "White", "Crimson"],
             "available_customizations": ["Laser Engraving", "UV Print", "Screen Print"]},
            {"name": "Ceramic Mug", "sku": "APX-MUG-001", "base_price": 220, "min_order_qty": 100, "lead_time_days": 10,
             "available_colors": ["White", "Black"],
             "available_customizations": ["Sublimation", "UV Print"]},
            {"name": "Metal Keychain", "sku": "APX-KEY-001", "base_price": 120, "min_order_qty": 200, "lead_time_days": 14,
             "available_customizations": ["Engraving", "Enamel Fill", "Casting"]},
            {"name": "Desk Organizer", "sku": "APX-DSK-001", "base_price": 680, "min_order_qty": 30, "lead_time_days": 21,
             "available_colors": ["Walnut", "Black", "Natural"],
             "available_customizations": ["Laser Engraving", "Metal Plate"]},
            {"name": "Award Trophy", "sku": "APX-TRP-001", "base_price": 1500, "min_order_qty": 10, "lead_time_days": 28,
             "available_customizations": ["Engraving", "Crystal", "Wood Base", "Metal Plate"]},
        ],
    },
    {
        "name": "Accessories",
        "description": "Caps, bags, socks, lanyards, and other accessories",
        "sort_order": 4,
        "products": [
            {"name": "Baseball Cap", "sku": "APX-CAP-001", "base_price": 280, "min_order_qty": 100, "lead_time_days": 14,
             "available_sizes": ["One Size"], "available_colors": ["Black", "White", "Navy", "Grey", "Crimson"],
             "available_customizations": ["Embroidery", "Screen Print", "Woven Patch"]},
            {"name": "Corporate Socks", "sku": "APX-SOK-001", "base_price": 150, "min_order_qty": 200, "lead_time_days": 21,
             "available_sizes": ["Free Size", "S-M", "L-XL"], "available_colors": ["Black", "White", "Navy", "Grey"],
             "available_customizations": ["Knitted Pattern", "Sublimation"]},
            {"name": "Lanyard with ID Holder", "sku": "APX-LNY-001", "base_price": 85, "min_order_qty": 200, "lead_time_days": 10,
             "available_colors": ["Black", "Navy", "Red", "White", "Custom"],
             "available_customizations": ["Sublimation Print", "Woven", "Dye Sublimation"]},
            {"name": "Laptop Backpack", "sku": "APX-BAG-001", "base_price": 950, "min_order_qty": 30, "lead_time_days": 21,
             "available_colors": ["Black", "Grey", "Navy"],
             "available_customizations": ["Embroidery", "Rubber Patch", "Metal Badge"]},
            {"name": "Tote Bag", "sku": "APX-TOT-001", "gsm_range": "280-340", "base_price": 320, "min_order_qty": 100, "lead_time_days": 14,
             "available_colors": ["Natural", "Black", "White", "Navy"],
             "available_customizations": ["Screen Print", "Embroidery"]},
            {"name": "Wristband", "sku": "APX-WRB-001", "base_price": 45, "min_order_qty": 500, "lead_time_days": 10,
             "available_colors": ["Custom"],
             "available_customizations": ["Embossed", "Debossed", "Printed", "Silicone"]},
        ],
    },
]


async def seed():
    total_products = 0
    async with async_session() as db:
        for cat_data in CATEGORIES:
            products_data = cat_data["products"]
            category = ProductCategory(
                name=cat_data["name"],
                description=cat_data.get("description", ""),
                sort_order=cat_data.get("sort_order", 0),
            )
            db.add(category)
            await db.flush()

            for prod_data in products_data:
                product = Product(
                    category_id=category.id,
                    available_sizes=prod_data.get("available_sizes", []),
                    available_colors=prod_data.get("available_colors", []),
                    available_customizations=prod_data.get("available_customizations", []),
                    name=prod_data["name"],
                    sku=prod_data.get("sku"),
                    description=prod_data.get("description", ""),
                    gsm_range=prod_data.get("gsm_range"),
                    base_price=prod_data.get("base_price"),
                    min_order_qty=prod_data.get("min_order_qty", 50),
                    lead_time_days=prod_data.get("lead_time_days"),
                )
                db.add(product)
                total_products += 1

        await db.commit()
        print(f"Seeded {total_products} products across {len(CATEGORIES)} categories")


if __name__ == "__main__":
    asyncio.run(seed())
