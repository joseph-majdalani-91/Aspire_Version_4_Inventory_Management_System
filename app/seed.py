from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import (
    AuditLog,
    Item,
    ItemStatus,
    QuantityEvent,
    QuantityEventType,
    UserAccount,
    UserRole,
)


DEMO_USERS = [
    {
        "username": "admin",
        "full_name": "Admin User",
        "role": UserRole.ADMIN,
        "password": "admin123",
        "api_key": "admin-demo-key",
    },
    {
        "username": "manager",
        "full_name": "Manager User",
        "role": UserRole.MANAGER,
        "password": "manager123",
        "api_key": "manager-demo-key",
    },
    {
        "username": "viewer",
        "full_name": "Viewer User",
        "role": UserRole.VIEWER,
        "password": "viewer123",
        "api_key": "viewer-demo-key",
    },
]


def run_seed() -> None:
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        db.execute(delete(AuditLog))
        db.execute(delete(QuantityEvent))
        db.execute(delete(Item))
        db.execute(delete(UserAccount))
        db.flush()

        users: list[UserAccount] = []
        for row in DEMO_USERS:
            users.append(
                UserAccount(
                    username=row["username"],
                    full_name=row["full_name"],
                    role=row["role"],
                    password_hash=hash_password(row["password"]),
                    api_key=row["api_key"],
                    is_active=True,
                )
            )

        db.add_all(users)
        db.flush()

        admin = next(user for user in users if user.role == UserRole.ADMIN)
        manager = next(user for user in users if user.role == UserRole.MANAGER)

        items = [
            Item(
                sku="ELEC-1001",
                name="27-inch Monitor",
                category="Electronics",
                details="QHD IPS office monitor",
                quantity=42,
                reorder_threshold=15,
                unit_cost=179.00,
                status=ItemStatus.IN_STOCK,
                created_by_id=manager.id,
                updated_by_id=manager.id,
            ),
            Item(
                sku="ELEC-1002",
                name="Wireless Keyboard",
                category="Electronics",
                details="Low-profile Bluetooth keyboard",
                quantity=9,
                reorder_threshold=12,
                unit_cost=39.50,
                status=ItemStatus.LOW_STOCK,
                created_by_id=manager.id,
                updated_by_id=manager.id,
            ),
            Item(
                sku="ELEC-1003",
                name="USB-C Dock",
                category="Electronics",
                details="Dual-display docking station",
                quantity=6,
                reorder_threshold=10,
                unit_cost=121.90,
                status=ItemStatus.ORDERED,
                created_by_id=manager.id,
                updated_by_id=manager.id,
            ),
            Item(
                sku="OFF-2001",
                name="Notebook Pack",
                category="Office Supplies",
                details="Pack of 5 ruled notebooks",
                quantity=120,
                reorder_threshold=40,
                unit_cost=6.20,
                status=ItemStatus.IN_STOCK,
                created_by_id=manager.id,
                updated_by_id=manager.id,
            ),
            Item(
                sku="OFF-2002",
                name="Ballpoint Pen Box",
                category="Office Supplies",
                details="Box of 50 blue pens",
                quantity=22,
                reorder_threshold=30,
                unit_cost=12.70,
                status=ItemStatus.LOW_STOCK,
                created_by_id=manager.id,
                updated_by_id=manager.id,
            ),
            Item(
                sku="OFF-2003",
                name="Printer Toner C13",
                category="Office Supplies",
                details="Laser toner cartridge C13",
                quantity=4,
                reorder_threshold=8,
                unit_cost=88.40,
                status=ItemStatus.ORDERED,
                created_by_id=manager.id,
                updated_by_id=manager.id,
            ),
            Item(
                sku="SAFE-3001",
                name="Safety Gloves",
                category="Safety",
                details="Cut-resistant gloves (pair)",
                quantity=85,
                reorder_threshold=35,
                unit_cost=3.60,
                status=ItemStatus.IN_STOCK,
                created_by_id=manager.id,
                updated_by_id=manager.id,
            ),
            Item(
                sku="SAFE-3002",
                name="Protective Goggles",
                category="Safety",
                details="Anti-fog protective eyewear",
                quantity=14,
                reorder_threshold=20,
                unit_cost=8.90,
                status=ItemStatus.LOW_STOCK,
                created_by_id=manager.id,
                updated_by_id=manager.id,
            ),
            Item(
                sku="SAFE-3003",
                name="High-Vis Vest",
                category="Safety",
                details="ANSI reflective vest",
                quantity=2,
                reorder_threshold=10,
                unit_cost=14.30,
                status=ItemStatus.ORDERED,
                created_by_id=manager.id,
                updated_by_id=manager.id,
            ),
            Item(
                sku="PKG-4001",
                name="Cardboard Carton",
                category="Packaging",
                details="Medium corrugated box",
                quantity=260,
                reorder_threshold=100,
                unit_cost=0.95,
                status=ItemStatus.IN_STOCK,
                created_by_id=manager.id,
                updated_by_id=manager.id,
            ),
            Item(
                sku="PKG-4002",
                name="Shipping Tape",
                category="Packaging",
                details="48mm transparent tape roll",
                quantity=18,
                reorder_threshold=25,
                unit_cost=1.80,
                status=ItemStatus.LOW_STOCK,
                created_by_id=manager.id,
                updated_by_id=manager.id,
            ),
            Item(
                sku="LEG-9001",
                name="Legacy Barcode Scanner",
                category="Electronics",
                details="Legacy device retired from catalog",
                quantity=0,
                reorder_threshold=0,
                unit_cost=95.00,
                status=ItemStatus.DISCONTINUED,
                is_deleted=True,
                created_by_id=admin.id,
                updated_by_id=admin.id,
            ),
        ]

        db.add_all(items)
        db.flush()

        now = datetime.now(timezone.utc)

        for item in items:
            created_at = now - timedelta(days=10)
            quantity_before = max(0, item.quantity - max(5, item.reorder_threshold // 2))
            quantity_delta = item.quantity - quantity_before

            db.add(
                QuantityEvent(
                    item_id=item.id,
                    event_type=QuantityEventType.ADJUSTMENT,
                    quantity_before=quantity_before,
                    quantity_delta=quantity_delta,
                    quantity_after=item.quantity,
                    note="Initial seeded quantity",
                    actor_user_id=manager.id,
                    created_at=created_at,
                )
            )

            db.add(
                AuditLog(
                    entity_type="item",
                    entity_id=item.id,
                    action="ITEM_CREATE",
                    before_state=None,
                    after_state=f'{{"sku":"{item.sku}","status":"{item.status.value}","quantity":{item.quantity}}}',
                    note="Seeded demo item",
                    actor_user_id=item.created_by_id,
                    created_at=created_at,
                )
            )

        # Add a few realistic recent movements for anomaly and activity panels.
        movement_rows = [
            ("ELEC-1002", QuantityEventType.OUTBOUND, -8, "Bulk laptop onboarding"),
            ("SAFE-3002", QuantityEventType.OUTBOUND, -11, "Site safety inspection issue"),
            ("PKG-4002", QuantityEventType.OUTBOUND, -10, "Large outbound shipment"),
            ("OFF-2003", QuantityEventType.INBOUND, 20, "Urgent toner replenishment"),
        ]

        sku_index = {item.sku: item for item in items}
        for idx, (sku, event_type, delta, note) in enumerate(movement_rows, start=1):
            item = sku_index[sku]
            before_qty = item.quantity
            after_qty = max(0, before_qty + delta)
            item.quantity = after_qty
            if item.status != ItemStatus.DISCONTINUED:
                if item.status != ItemStatus.ORDERED or after_qty > item.reorder_threshold:
                    item.status = ItemStatus.LOW_STOCK if after_qty <= item.reorder_threshold else ItemStatus.IN_STOCK
            item.updated_by_id = manager.id
            item.updated_at = now - timedelta(days=1, hours=idx)

            db.add(
                QuantityEvent(
                    item_id=item.id,
                    event_type=event_type,
                    quantity_before=before_qty,
                    quantity_delta=delta,
                    quantity_after=after_qty,
                    note=note,
                    actor_user_id=manager.id,
                    created_at=now - timedelta(days=1, hours=idx),
                )
            )
            db.add(
                AuditLog(
                    entity_type="item",
                    entity_id=item.id,
                    action="ITEM_QUANTITY_ADJUST",
                    before_state=f'{{"quantity":{before_qty},"status":"{item.status.value}"}}',
                    after_state=f'{{"quantity":{after_qty},"status":"{item.status.value}"}}',
                    note=note,
                    actor_user_id=manager.id,
                    created_at=now - timedelta(days=1, hours=idx),
                )
            )

        db.commit()


if __name__ == "__main__":
    run_seed()
    print("Seed complete. Users: admin/admin123, manager/manager123, viewer/viewer123")
