from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import ItemStatus, QuantityEventType, UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginResponse(BaseModel):
    api_key: str
    user: UserRead


class UserRoleUpdate(BaseModel):
    role: UserRole


class ItemBase(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=120)
    details: str | None = None
    quantity: int = Field(default=0, ge=0)
    reorder_threshold: int = Field(default=10, ge=0, le=100000)
    unit_cost: float = Field(default=0.0, ge=0.0)
    status: ItemStatus | None = None


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=120)
    details: str | None = None
    quantity: int | None = Field(default=None, ge=0)
    reorder_threshold: int | None = Field(default=None, ge=0, le=100000)
    unit_cost: float | None = Field(default=None, ge=0.0)
    status: ItemStatus | None = None


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    category: str
    details: str | None
    quantity: int
    reorder_threshold: int
    unit_cost: float
    status: ItemStatus
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class ItemListResponse(BaseModel):
    items: list[ItemRead]
    total: int
    page: int
    page_size: int


class QuantityAdjustmentRequest(BaseModel):
    event_type: QuantityEventType
    quantity_delta: int
    note: str | None = Field(default=None, max_length=500)

    @field_validator("quantity_delta")
    @classmethod
    def quantity_delta_non_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("quantity_delta must not be 0")
        return value


class ItemStatusUpdateRequest(BaseModel):
    status: ItemStatus
    note: str | None = Field(default=None, max_length=500)


class BulkStatusUpdateRequest(BaseModel):
    item_ids: list[int] = Field(min_length=1, max_length=300)
    status: ItemStatus
    note: str | None = Field(default=None, max_length=500)


class BulkStatusUpdateResponse(BaseModel):
    updated_count: int
    status: ItemStatus
    item_ids: list[int]


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int | None
    action: str
    before_state: str | None
    after_state: str | None
    note: str | None
    actor_user_id: int | None
    created_at: datetime


class CategorySummary(BaseModel):
    category: str
    count: int


class DashboardSummary(BaseModel):
    total_items: int
    active_items: int
    low_stock_alerts: int
    total_quantity: int
    total_inventory_value: float
    items_by_category: list[CategorySummary]
    recent_activity: list[AuditLogRead]


class ReorderSuggestion(BaseModel):
    item_id: int
    sku: str
    name: str
    status: ItemStatus
    current_quantity: int
    reorder_threshold: int
    recommended_order_qty: int
    reason: str


class ReorderSuggestionResponse(BaseModel):
    source: str
    model: str | None
    suggestions: list[ReorderSuggestion]


class AnomalyAlert(BaseModel):
    item_id: int
    sku: str
    name: str
    severity: str
    quantity_delta: int
    explanation: str
    suggested_action: str
    created_at: datetime


class AnomalyAlertResponse(BaseModel):
    source: str
    model: str | None
    alerts: list[AnomalyAlert]


class NaturalLanguageSearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=300)


class NaturalLanguageSearchResponse(BaseModel):
    source: str
    model: str | None
    parsed_filters: dict[str, str | int | None]
    items: list[ItemRead]
