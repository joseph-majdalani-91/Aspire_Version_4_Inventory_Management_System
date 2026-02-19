from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.auth import Principal, ensure_auth_config, require_roles, verify_password
from app.database import Base, engine, get_db
from app.models import (
    AuditLog,
    Item,
    ItemStatus,
    QuantityEvent,
    QuantityEventType,
    UserAccount,
    UserRole,
)
from app.schemas import (
    AnomalyAlertResponse,
    AuditLogRead,
    BulkStatusUpdateRequest,
    BulkStatusUpdateResponse,
    CategorySummary,
    DashboardSummary,
    ItemCreate,
    ItemListResponse,
    ItemRead,
    ItemStatusUpdateRequest,
    ItemUpdate,
    LoginRequest,
    LoginResponse,
    NaturalLanguageSearchRequest,
    NaturalLanguageSearchResponse,
    QuantityAdjustmentRequest,
    ReorderSuggestionResponse,
    UserRead,
    UserRoleUpdate,
)
from app.services.ai_features import (
    build_anomaly_alerts,
    build_reorder_suggestions,
    parse_natural_language_filters,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_auth_config()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Independent Inventory Management System",
    version="2.0.0",
    description="Inventory system with RBAC, search, audit trails, and AI-powered planning.",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def _item_snapshot(item: Item) -> dict[str, object]:
    return {
        "id": item.id,
        "sku": item.sku,
        "name": item.name,
        "category": item.category,
        "details": item.details,
        "quantity": item.quantity,
        "reorder_threshold": item.reorder_threshold,
        "unit_cost": item.unit_cost,
        "status": item.status.value,
        "is_deleted": item.is_deleted,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _serialize_item(item: Item) -> ItemRead:
    return ItemRead(
        id=item.id,
        sku=item.sku,
        name=item.name,
        category=item.category,
        details=item.details,
        quantity=item.quantity,
        reorder_threshold=item.reorder_threshold,
        unit_cost=item.unit_cost,
        status=item.status,
        is_deleted=item.is_deleted,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _derive_stock_status(item: Item, keep_ordered: bool = True) -> ItemStatus:
    if item.status == ItemStatus.DISCONTINUED:
        return ItemStatus.DISCONTINUED

    if keep_ordered and item.status == ItemStatus.ORDERED and item.quantity <= item.reorder_threshold:
        return ItemStatus.ORDERED

    if item.quantity <= item.reorder_threshold:
        return ItemStatus.LOW_STOCK

    return ItemStatus.IN_STOCK


def _get_item_or_404(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
    return item


def _create_audit_log(
    db: Session,
    actor_user_id: int | None,
    entity_type: str,
    entity_id: int | None,
    action: str,
    before_state: dict[str, object] | None = None,
    after_state: dict[str, object] | None = None,
    note: str | None = None,
) -> None:
    log = AuditLog(
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before_state=json.dumps(before_state) if before_state is not None else None,
        after_state=json.dumps(after_state) if after_state is not None else None,
        note=note,
    )
    db.add(log)


def _build_item_filter_query(
    q: str | None,
    category: str | None,
    status_filter: ItemStatus | None,
    min_qty: int | None,
    max_qty: int | None,
    include_deleted: bool,
) -> Select[tuple[Item]]:
    stmt = select(Item)

    if not include_deleted:
        stmt = stmt.where(Item.is_deleted.is_(False))

    if q:
        token = f"%{q.strip()}%"
        stmt = stmt.where(
            Item.name.ilike(token)
            | Item.sku.ilike(token)
            | Item.category.ilike(token)
            | Item.details.ilike(token)
        )

    if category:
        stmt = stmt.where(Item.category.ilike(category.strip()))

    if status_filter is not None:
        stmt = stmt.where(Item.status == status_filter)

    if min_qty is not None:
        stmt = stmt.where(Item.quantity >= min_qty)

    if max_qty is not None:
        stmt = stmt.where(Item.quantity <= max_qty)

    return stmt


def _apply_sort(stmt: Select[tuple[Item]], sort_by: str, sort_dir: str) -> Select[tuple[Item]]:
    sort_map = {
        "sku": Item.sku,
        "name": Item.name,
        "category": Item.category,
        "quantity": Item.quantity,
        "status": Item.status,
        "updated_at": Item.updated_at,
        "created_at": Item.created_at,
    }
    column = sort_map.get(sort_by, Item.updated_at)
    if sort_dir.lower() == "asc":
        return stmt.order_by(column.asc())
    return stmt.order_by(column.desc())


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.scalar(select(UserAccount).where(UserAccount.username == payload.username))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return LoginResponse(api_key=user.api_key, user=UserRead.model_validate(user))


@app.get("/api/me", response_model=UserRead)
def me(
    principal: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.VIEWER)),
    db: Session = Depends(get_db),
) -> UserRead:
    user = db.get(UserAccount, principal.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(user)


@app.get("/api/users", response_model=list[UserRead])
def list_users(
    _: Principal = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> list[UserRead]:
    users = db.scalars(select(UserAccount).order_by(UserAccount.username.asc())).all()
    return [UserRead.model_validate(user) for user in users]


@app.patch("/api/users/{user_id}/role", response_model=UserRead)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    principal: Principal = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> UserRead:
    user = db.get(UserAccount, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    before = {
        "id": user.id,
        "username": user.username,
        "role": user.role.value,
        "is_active": user.is_active,
    }
    user.role = payload.role
    user.updated_at = datetime.now(timezone.utc)

    db.add(user)
    _create_audit_log(
        db,
        actor_user_id=principal.user_id,
        entity_type="user",
        entity_id=user.id,
        action="USER_ROLE_UPDATE",
        before_state=before,
        after_state={"id": user.id, "username": user.username, "role": user.role.value},
        note=f"Role changed to {user.role.value}",
    )
    db.commit()
    db.refresh(user)
    return UserRead.model_validate(user)


@app.post("/api/items", response_model=ItemRead)
def create_item(
    payload: ItemCreate,
    principal: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
    db: Session = Depends(get_db),
) -> ItemRead:
    existing = db.scalar(select(Item).where(Item.sku == payload.sku))
    if existing:
        raise HTTPException(status_code=409, detail=f"SKU already exists: {payload.sku}")

    item = Item(
        sku=payload.sku,
        name=payload.name,
        category=payload.category,
        details=payload.details,
        quantity=payload.quantity,
        reorder_threshold=payload.reorder_threshold,
        unit_cost=payload.unit_cost,
        status=payload.status or ItemStatus.IN_STOCK,
        is_deleted=(payload.status == ItemStatus.DISCONTINUED),
        created_by_id=principal.user_id,
        updated_by_id=principal.user_id,
    )

    if payload.status is None:
        item.status = _derive_stock_status(item, keep_ordered=False)

    db.add(item)
    db.flush()

    _create_audit_log(
        db,
        actor_user_id=principal.user_id,
        entity_type="item",
        entity_id=item.id,
        action="ITEM_CREATE",
        before_state=None,
        after_state=_item_snapshot(item),
    )

    db.commit()
    db.refresh(item)
    return _serialize_item(item)


@app.get("/api/items", response_model=ItemListResponse)
def list_items(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status_filter: ItemStatus | None = Query(default=None, alias="status"),
    min_qty: int | None = Query(default=None, ge=0),
    max_qty: int | None = Query(default=None, ge=0),
    include_deleted: bool = Query(default=False),
    sort_by: str = Query(default="updated_at"),
    sort_dir: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    _: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.VIEWER)),
    db: Session = Depends(get_db),
) -> ItemListResponse:
    stmt = _build_item_filter_query(q, category, status_filter, min_qty, max_qty, include_deleted)
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)

    stmt = _apply_sort(stmt, sort_by=sort_by, sort_dir=sort_dir)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    items = db.scalars(stmt).all()
    return ItemListResponse(
        items=[_serialize_item(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@app.get("/api/items/search", response_model=ItemListResponse)
def search_items(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status_filter: ItemStatus | None = Query(default=None, alias="status"),
    min_qty: int | None = Query(default=None, ge=0),
    max_qty: int | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.VIEWER)),
    db: Session = Depends(get_db),
) -> ItemListResponse:
    return list_items(
        q=q,
        category=category,
        status_filter=status_filter,
        min_qty=min_qty,
        max_qty=max_qty,
        include_deleted=False,
        sort_by="updated_at",
        sort_dir="desc",
        page=page,
        page_size=page_size,
        _=principal,
        db=db,
    )


@app.get("/api/items/{item_id}", response_model=ItemRead)
def get_item(
    item_id: int,
    _: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.VIEWER)),
    db: Session = Depends(get_db),
) -> ItemRead:
    return _serialize_item(_get_item_or_404(db, item_id))


@app.put("/api/items/{item_id}", response_model=ItemRead)
def update_item(
    item_id: int,
    payload: ItemUpdate,
    principal: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
    db: Session = Depends(get_db),
) -> ItemRead:
    item = _get_item_or_404(db, item_id)
    if item.is_deleted:
        raise HTTPException(
            status_code=400,
            detail="Cannot edit a deleted item. Restore it by setting status to a non-discontinued value first.",
        )
    before = _item_snapshot(item)

    updates = payload.model_dump(exclude_unset=True)
    if "sku" in updates:
        sku_conflict = db.scalar(select(Item).where(Item.sku == updates["sku"], Item.id != item.id))
        if sku_conflict:
            raise HTTPException(status_code=409, detail=f"SKU already exists: {updates['sku']}")

    previous_qty = item.quantity
    explicit_status = "status" in updates and updates["status"] is not None

    for key, value in updates.items():
        setattr(item, key, value)

    if explicit_status:
        item.is_deleted = item.status == ItemStatus.DISCONTINUED
    else:
        item.status = _derive_stock_status(item)

    if item.quantity != previous_qty:
        delta = item.quantity - previous_qty
        quantity_event = QuantityEvent(
            item_id=item.id,
            event_type=QuantityEventType.ADJUSTMENT,
            quantity_before=previous_qty,
            quantity_delta=delta,
            quantity_after=item.quantity,
            note="Quantity changed through item update",
            actor_user_id=principal.user_id,
        )
        db.add(quantity_event)

    item.updated_by_id = principal.user_id
    item.updated_at = datetime.now(timezone.utc)

    db.add(item)
    _create_audit_log(
        db,
        actor_user_id=principal.user_id,
        entity_type="item",
        entity_id=item.id,
        action="ITEM_UPDATE",
        before_state=before,
        after_state=_item_snapshot(item),
    )

    db.commit()
    db.refresh(item)
    return _serialize_item(item)


@app.delete("/api/items/{item_id}")
def delete_item(
    item_id: int,
    principal: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = _get_item_or_404(db, item_id)
    if item.is_deleted:
        raise HTTPException(status_code=400, detail="Item already deleted")

    before = _item_snapshot(item)
    item.is_deleted = True
    item.status = ItemStatus.DISCONTINUED
    item.updated_by_id = principal.user_id
    item.updated_at = datetime.now(timezone.utc)

    db.add(item)
    _create_audit_log(
        db,
        actor_user_id=principal.user_id,
        entity_type="item",
        entity_id=item.id,
        action="ITEM_DELETE",
        before_state=before,
        after_state=_item_snapshot(item),
        note="Soft delete",
    )

    db.commit()
    return {"id": item.id, "is_deleted": True}


@app.patch("/api/items/{item_id}/status", response_model=ItemRead)
def update_item_status(
    item_id: int,
    payload: ItemStatusUpdateRequest,
    principal: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
    db: Session = Depends(get_db),
) -> ItemRead:
    item = _get_item_or_404(db, item_id)
    before = _item_snapshot(item)

    item.status = payload.status
    item.is_deleted = payload.status == ItemStatus.DISCONTINUED
    item.updated_by_id = principal.user_id
    item.updated_at = datetime.now(timezone.utc)

    db.add(item)
    _create_audit_log(
        db,
        actor_user_id=principal.user_id,
        entity_type="item",
        entity_id=item.id,
        action="ITEM_STATUS_UPDATE",
        before_state=before,
        after_state=_item_snapshot(item),
        note=payload.note,
    )

    db.commit()
    db.refresh(item)
    return _serialize_item(item)


@app.patch("/api/items/status/bulk", response_model=BulkStatusUpdateResponse)
def bulk_update_status(
    payload: BulkStatusUpdateRequest,
    principal: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
    db: Session = Depends(get_db),
) -> BulkStatusUpdateResponse:
    unique_ids = sorted(set(payload.item_ids))
    items = db.scalars(select(Item).where(Item.id.in_(unique_ids))).all()
    found_ids = {item.id for item in items}
    missing_ids = [item_id for item_id in unique_ids if item_id not in found_ids]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Items not found: {missing_ids}")

    for item in items:
        before = _item_snapshot(item)
        item.status = payload.status
        item.is_deleted = payload.status == ItemStatus.DISCONTINUED
        item.updated_by_id = principal.user_id
        item.updated_at = datetime.now(timezone.utc)
        db.add(item)
        _create_audit_log(
            db,
            actor_user_id=principal.user_id,
            entity_type="item",
            entity_id=item.id,
            action="ITEM_STATUS_BULK_UPDATE",
            before_state=before,
            after_state=_item_snapshot(item),
            note=payload.note,
        )

    db.commit()

    return BulkStatusUpdateResponse(updated_count=len(items), status=payload.status, item_ids=unique_ids)


@app.post("/api/items/{item_id}/quantity", response_model=ItemRead)
def adjust_quantity(
    item_id: int,
    payload: QuantityAdjustmentRequest,
    principal: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER)),
    db: Session = Depends(get_db),
) -> ItemRead:
    item = _get_item_or_404(db, item_id)
    if item.is_deleted:
        raise HTTPException(status_code=400, detail="Cannot adjust a deleted item")

    if payload.event_type == QuantityEventType.INBOUND and payload.quantity_delta < 0:
        raise HTTPException(status_code=422, detail="Inbound events require a positive quantity_delta")
    if payload.event_type == QuantityEventType.OUTBOUND and payload.quantity_delta > 0:
        raise HTTPException(status_code=422, detail="Outbound events require a negative quantity_delta")

    quantity_before = item.quantity
    quantity_after = quantity_before + payload.quantity_delta
    if quantity_after < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient quantity. Current: {quantity_before}, requested delta: {payload.quantity_delta}",
        )

    before_snapshot = _item_snapshot(item)
    item.quantity = quantity_after
    item.status = _derive_stock_status(item)
    item.updated_by_id = principal.user_id
    item.updated_at = datetime.now(timezone.utc)

    event = QuantityEvent(
        item_id=item.id,
        event_type=payload.event_type,
        quantity_before=quantity_before,
        quantity_delta=payload.quantity_delta,
        quantity_after=quantity_after,
        note=payload.note,
        actor_user_id=principal.user_id,
    )

    db.add(item)
    db.add(event)
    _create_audit_log(
        db,
        actor_user_id=principal.user_id,
        entity_type="item",
        entity_id=item.id,
        action="ITEM_QUANTITY_ADJUST",
        before_state=before_snapshot,
        after_state=_item_snapshot(item),
        note=payload.note,
    )

    db.commit()
    db.refresh(item)
    return _serialize_item(item)


@app.get("/api/audit", response_model=list[AuditLogRead])
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=500),
    _: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.VIEWER)),
    db: Session = Depends(get_db),
) -> list[AuditLogRead]:
    logs = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [AuditLogRead.model_validate(log) for log in logs]


@app.get("/api/dashboard", response_model=DashboardSummary)
def dashboard(
    _: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.VIEWER)),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    active_items = db.scalars(select(Item).where(Item.is_deleted.is_(False))).all()
    total_items = db.scalar(select(func.count()).select_from(Item)) or 0

    low_stock_alerts = sum(
        1
        for item in active_items
        if item.status in {ItemStatus.LOW_STOCK, ItemStatus.ORDERED} or item.quantity <= item.reorder_threshold
    )

    total_quantity = sum(item.quantity for item in active_items)
    total_inventory_value = round(sum(item.quantity * item.unit_cost for item in active_items), 2)

    category_rows = db.execute(
        select(Item.category, func.count(Item.id))
        .where(Item.is_deleted.is_(False))
        .group_by(Item.category)
        .order_by(func.count(Item.id).desc(), Item.category.asc())
    ).all()
    items_by_category = [CategorySummary(category=category, count=count) for category, count in category_rows]

    recent_activity = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(12)).all()

    return DashboardSummary(
        total_items=int(total_items),
        active_items=len(active_items),
        low_stock_alerts=low_stock_alerts,
        total_quantity=total_quantity,
        total_inventory_value=total_inventory_value,
        items_by_category=items_by_category,
        recent_activity=[AuditLogRead.model_validate(row) for row in recent_activity],
    )


@app.get("/api/ai/reorder-suggestions", response_model=ReorderSuggestionResponse)
def ai_reorder_suggestions(
    limit: int = Query(default=20, ge=1, le=100),
    _: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.VIEWER)),
    db: Session = Depends(get_db),
) -> ReorderSuggestionResponse:
    items = db.scalars(select(Item).where(Item.is_deleted.is_(False))).all()
    result = build_reorder_suggestions(items, limit=limit)

    return ReorderSuggestionResponse(
        source=str(result["source"]),
        model=result.get("model"),
        suggestions=list(result["suggestions"]),
    )


@app.get("/api/ai/anomaly-alerts", response_model=AnomalyAlertResponse)
def ai_anomaly_alerts(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
    _: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.VIEWER)),
    db: Session = Depends(get_db),
) -> AnomalyAlertResponse:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    events = db.scalars(select(QuantityEvent).where(QuantityEvent.created_at >= cutoff)).all()
    item_index = {item.id: item for item in db.scalars(select(Item)).all()}

    result = build_anomaly_alerts(events, item_index=item_index, limit=limit)
    return AnomalyAlertResponse(
        source=str(result["source"]),
        model=result.get("model"),
        alerts=list(result["alerts"]),
    )


@app.post("/api/ai/natural-language-search", response_model=NaturalLanguageSearchResponse)
def ai_natural_language_search(
    payload: NaturalLanguageSearchRequest,
    _: Principal = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.VIEWER)),
    db: Session = Depends(get_db),
) -> NaturalLanguageSearchResponse:
    parsed = parse_natural_language_filters(payload.query)

    status_raw = parsed.get("status")
    status_filter = ItemStatus(status_raw) if isinstance(status_raw, str) and status_raw else None

    min_qty = parsed.get("min_qty")
    max_qty = parsed.get("max_qty")
    stmt = _build_item_filter_query(
        q=str(parsed.get("q") or payload.query),
        category=str(parsed.get("category") or "") or None,
        status_filter=status_filter,
        min_qty=int(min_qty) if isinstance(min_qty, int) else None,
        max_qty=int(max_qty) if isinstance(max_qty, int) else None,
        include_deleted=False,
    )

    stmt = _apply_sort(
        stmt,
        sort_by=str(parsed.get("sort_by") or "updated_at"),
        sort_dir=str(parsed.get("sort_dir") or "desc"),
    )
    items = db.scalars(stmt.limit(100)).all()

    parsed_filters = {
        "q": str(parsed.get("q") or payload.query),
        "category": str(parsed.get("category")) if parsed.get("category") else None,
        "status": status_filter.value if status_filter else None,
        "min_qty": int(min_qty) if isinstance(min_qty, int) else None,
        "max_qty": int(max_qty) if isinstance(max_qty, int) else None,
    }

    return NaturalLanguageSearchResponse(
        source=str(parsed.get("source") or "fallback"),
        model=str(parsed.get("model")) if parsed.get("model") else None,
        parsed_filters=parsed_filters,
        items=[_serialize_item(item) for item in items],
    )
