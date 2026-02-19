from app.models import Item, ItemStatus
from app.main import _derive_stock_status


def test_status_derivation_low_stock() -> None:
    item = Item(
        sku="TEST",
        name="Test",
        category="Category",
        quantity=2,
        reorder_threshold=5,
        unit_cost=1.0,
        status=ItemStatus.IN_STOCK,
    )
    assert _derive_stock_status(item) == ItemStatus.LOW_STOCK
