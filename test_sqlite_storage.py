"""Test SQLite storage mode for Product Catalog Service."""

from product_catalog_service import SQLiteStorage


def test_sqlite_storage(tmp_path):
    db_path = str(tmp_path / "product_catalog.db")
    storage = SQLiteStorage(db_path)

    # Empty database starts with no products
    assert storage.get_all_products() == []

    storage.seed_data()
    products = storage.get_all_products()
    assert len(products) >= 6

    # Seeding again must not duplicate rows when the DB already has data
    storage.seed_data()
    assert len(storage.get_all_products()) == len(products)

    target = next(p for p in products if p["stock"] > 0)
    initial_stock = target["stock"]

    success, new_stock = storage.update_stock(target["id"], 1)
    assert success is True
    assert new_stock == initial_stock - 1
    assert storage.get_product(target["id"])["stock"] == initial_stock - 1

    # Insufficient stock leaves the value unchanged
    success, unchanged = storage.update_stock(target["id"], initial_stock + 100)
    assert success is False
    assert unchanged == initial_stock - 1
    assert storage.get_product(target["id"])["stock"] == initial_stock - 1

    # Unknown product ID is reported as not found
    success, missing = storage.update_stock("does-not-exist", 1)
    assert success is False
    assert missing == -1
