"""Verify that stock and order data persist across storage restarts (SQLite mode)."""

from product_catalog_service import SQLiteStorage
from order_service import SQLiteOrderStorage


def test_product_stock_persists_across_restart(tmp_path):
    db_path = str(tmp_path / "products.db")

    storage = SQLiteStorage(db_path)
    storage.seed_data()

    products = storage.get_all_products()
    assert len(products) >= 6

    target = next(p for p in products if p["stock"] > 0)
    initial_stock = target["stock"]

    success, new_stock = storage.update_stock(target["id"], 1)
    assert success is True
    assert new_stock == initial_stock - 1

    # Simulate a restart by creating a fresh storage instance on the same DB file
    restarted = SQLiteStorage(db_path)
    persisted = restarted.get_product(target["id"])
    assert persisted is not None
    assert persisted["stock"] == initial_stock - 1


def test_order_persists_across_restart(tmp_path):
    db_path = str(tmp_path / "orders.db")

    storage = SQLiteOrderStorage(db_path)
    order = {
        "order_id": "order-123",
        "timestamp": "2024-01-01T00:00:00Z",
        "items": [
            {
                "product_id": "p1",
                "quantity": 2,
                "product_name": "Widget",
                "unit_price": 9.99,
            }
        ],
        "total": 19.98,
    }
    assert storage.save_order(order) is True

    restarted = SQLiteOrderStorage(db_path)
    orders = restarted.get_all_orders()

    assert len(orders) == 1
    assert orders[0]["order_id"] == "order-123"
    assert orders[0]["total"] == 19.98
    assert orders[0]["items"][0]["product_name"] == "Widget"
