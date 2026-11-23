"""
Unit tests for ListProducts RPC method.

Tests Requirements: 1.3, 1.4, 1.5
"""

import grpc
import product_pb2
import product_pb2_grpc
from product_catalog_service import ProductCatalogServicer, InMemoryStorage, SQLiteStorage
import tempfile
import os


def test_list_products_returns_all_products():
    """
    Test that ListProducts returns all products in the catalog.
    Requirements: 1.3, 1.4
    """
    # Setup
    storage = InMemoryStorage()
    storage.seed_data()
    servicer = ProductCatalogServicer(storage)
    
    # Create a mock context
    class MockContext:
        def abort(self, code, details):
            raise grpc.RpcError(f"{code}: {details}")
    
    context = MockContext()
    request = product_pb2.Empty()
    
    # Execute
    response = servicer.ListProducts(request, context)
    
    # Verify
    assert isinstance(response, product_pb2.ProductList)
    assert len(response.products) >= 6, "Should return at least 6 products"
    
    # Verify all products have required fields
    for product in response.products:
        assert product.id, "Product should have an ID"
        assert product.name, "Product should have a name"
        assert product.description is not None, "Product should have a description"
        assert product.price > 0, "Product should have a positive price"
        assert product.stock >= 0, "Product should have non-negative stock"
        assert product.image_url, "Product should have an image URL"
    
    print(f"✓ test_list_products_returns_all_products passed: {len(response.products)} products returned")


def test_list_products_empty_catalog():
    """
    Test that ListProducts returns an empty list when catalog is empty.
    Requirements: 1.5
    """
    # Setup - create storage without seeding
    storage = InMemoryStorage()
    servicer = ProductCatalogServicer(storage)
    
    class MockContext:
        def abort(self, code, details):
            raise grpc.RpcError(f"{code}: {details}")
    
    context = MockContext()
    request = product_pb2.Empty()
    
    # Execute
    response = servicer.ListProducts(request, context)
    
    # Verify
    assert isinstance(response, product_pb2.ProductList)
    assert len(response.products) == 0, "Should return empty list for empty catalog"
    
    print("✓ test_list_products_empty_catalog passed: empty list returned")


def test_list_products_with_sqlite_storage():
    """
    Test that ListProducts works correctly with SQLite storage.
    Requirements: 1.3, 1.4
    """
    # Setup - create temporary SQLite database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        storage = SQLiteStorage(temp_db.name)
        storage.seed_data()
        servicer = ProductCatalogServicer(storage)
        
        class MockContext:
            def abort(self, code, details):
                raise grpc.RpcError(f"{code}: {details}")
        
        context = MockContext()
        request = product_pb2.Empty()
        
        # Execute
        response = servicer.ListProducts(request, context)
        
        # Verify
        assert isinstance(response, product_pb2.ProductList)
        assert len(response.products) >= 6, "Should return at least 6 products from SQLite"
        
        print(f"✓ test_list_products_with_sqlite_storage passed: {len(response.products)} products returned")
    
    finally:
        # Cleanup
        if os.path.exists(temp_db.name):
            os.remove(temp_db.name)


def test_list_products_data_integrity():
    """
    Test that ListProducts returns products with correct data values.
    Requirements: 1.4
    """
    # Setup
    storage = InMemoryStorage()
    storage.seed_data()
    servicer = ProductCatalogServicer(storage)
    
    class MockContext:
        def abort(self, code, details):
            raise grpc.RpcError(f"{code}: {details}")
    
    context = MockContext()
    request = product_pb2.Empty()
    
    # Execute
    response = servicer.ListProducts(request, context)
    
    # Verify data requirements from Requirement 10
    stock_zero_count = sum(1 for p in response.products if p.stock == 0)
    stock_low_count = sum(1 for p in response.products if 1 <= p.stock <= 50)
    stock_high_count = sum(1 for p in response.products if p.stock > 50)
    
    assert stock_zero_count >= 2, "Should have at least 2 products with stock=0"
    assert stock_low_count >= 2, "Should have at least 2 products with stock 1-50"
    assert stock_high_count >= 2, "Should have at least 2 products with stock >50"
    
    # Verify price ranges
    for product in response.products:
        assert 0.01 <= product.price <= 999999.99, f"Price {product.price} out of valid range"
        assert 0 <= product.stock <= 999999, f"Stock {product.stock} out of valid range"
        assert len(product.name) <= 200, f"Product name too long: {len(product.name)} chars"
        assert len(product.description) <= 1000, f"Product description too long: {len(product.description)} chars"
        assert len(product.image_url) <= 500, f"Image URL too long: {len(product.image_url)} chars"
    
    print(f"✓ test_list_products_data_integrity passed: stock distribution and data ranges validated")


if __name__ == '__main__':
    print("=== Running ListProducts Unit Tests ===\n")
    
    test_list_products_returns_all_products()
    test_list_products_empty_catalog()
    test_list_products_with_sqlite_storage()
    test_list_products_data_integrity()
    
    print("\n=== All ListProducts tests passed ===")
