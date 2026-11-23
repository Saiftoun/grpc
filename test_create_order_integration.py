"""
Integration test for CreateOrder RPC method (Task 4.2)

Tests CreateOrder with actual Product Catalog Service to verify
real gRPC communication, stock validation, and error handling.
"""

import grpc
import pytest
import time
import threading
import order_pb2
import order_pb2_grpc
import product_pb2
import product_pb2_grpc
from order_service import OrderServiceServicer, InMemoryOrderStorage
from product_catalog_service import ProductCatalogServicer, InMemoryStorage
from concurrent import futures


@pytest.fixture(scope='module')
def product_catalog_server():
    """Start a Product Catalog Service on port 50061 (test port)."""
    # Create server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
    
    # Create servicer with in-memory storage
    storage = InMemoryStorage()
    servicer = ProductCatalogServicer(storage)
    
    # Seed with test products
    storage.products = {
        'prod-high-stock': {
            'id': 'prod-high-stock',
            'name': 'High Stock Product',
            'description': 'Product with plenty of stock',
            'price': 29.99,
            'stock': 1000,
            'image_url': 'https://example.com/high-stock.jpg'
        },
        'prod-low-stock': {
            'id': 'prod-low-stock',
            'name': 'Low Stock Product',
            'description': 'Product with limited stock',
            'price': 49.99,
            'stock': 5,
            'image_url': 'https://example.com/low-stock.jpg'
        },
        'prod-no-stock': {
            'id': 'prod-no-stock',
            'name': 'Out of Stock Product',
            'description': 'Product with no stock',
            'price': 19.99,
            'stock': 0,
            'image_url': 'https://example.com/no-stock.jpg'
        }
    }
    
    # Add servicer to server
    product_pb2_grpc.add_ProductCatalogServiceServicer_to_server(servicer, server)
    server.add_insecure_port('[::]:50061')
    
    # Start server in background thread
    server.start()
    
    # Wait for server to be ready
    time.sleep(0.5)
    
    yield server
    
    # Teardown: stop server
    server.stop(0)


@pytest.fixture
def order_servicer(product_catalog_server):
    """Create Order Service connected to test Product Catalog."""
    storage = InMemoryOrderStorage()
    servicer = OrderServiceServicer(storage, product_catalog_address='localhost:50061')
    return servicer


@pytest.fixture
def grpc_context():
    """Create a real gRPC servicer context."""
    class TestContext:
        def abort(self, code, details):
            error = grpc.RpcError()
            error._code = code
            error._details = details
            raise error
    
    return TestContext()


class TestIntegrationValidation:
    """Integration tests for request validation."""
    
    def test_empty_item_list(self, order_servicer, grpc_context):
        """Test empty item list returns INVALID_ARGUMENT."""
        request = order_pb2.OrderRequest(items=[])
        
        with pytest.raises(grpc.RpcError) as exc_info:
            order_servicer.CreateOrder(request, grpc_context)
        
        assert exc_info.value._code == grpc.StatusCode.INVALID_ARGUMENT
        assert "at least one item" in exc_info.value._details.lower()
    
    def test_more_than_100_items(self, order_servicer, grpc_context):
        """Test >100 items returns INVALID_ARGUMENT."""
        items = [
            order_pb2.LineItem(product_id=f"prod-{i}", quantity=1)
            for i in range(101)
        ]
        request = order_pb2.OrderRequest(items=items)
        
        with pytest.raises(grpc.RpcError) as exc_info:
            order_servicer.CreateOrder(request, grpc_context)
        
        assert exc_info.value._code == grpc.StatusCode.INVALID_ARGUMENT
        assert "100 items" in exc_info.value._details.lower()
    
    def test_quantity_out_of_range(self, order_servicer, grpc_context):
        """Test quantity outside 1-1000 range returns INVALID_ARGUMENT."""
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=1001)
        ])
        
        with pytest.raises(grpc.RpcError) as exc_info:
            order_servicer.CreateOrder(request, grpc_context)
        
        assert exc_info.value._code == grpc.StatusCode.INVALID_ARGUMENT


class TestIntegrationStockValidation:
    """Integration tests for stock validation with real Product Catalog."""
    
    def test_sufficient_stock_passes_validation(self, order_servicer, grpc_context):
        """Test order with sufficient stock passes validation."""
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-high-stock", quantity=10)
        ])
        
        response = order_servicer.CreateOrder(request, grpc_context)
        
        # Should not raise, returns placeholder response
        assert response is not None
    
    def test_insufficient_stock_returns_failed_precondition(self, order_servicer, grpc_context):
        """Test order with insufficient stock returns FAILED_PRECONDITION."""
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-low-stock", quantity=10)
        ])
        
        with pytest.raises(grpc.RpcError) as exc_info:
            order_servicer.CreateOrder(request, grpc_context)
        
        assert exc_info.value._code == grpc.StatusCode.FAILED_PRECONDITION
        assert "insufficient stock" in exc_info.value._details.lower()
        assert "prod-low-stock" in exc_info.value._details
    
    def test_zero_stock_returns_failed_precondition(self, order_servicer, grpc_context):
        """Test order for out-of-stock product returns FAILED_PRECONDITION."""
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-no-stock", quantity=1)
        ])
        
        with pytest.raises(grpc.RpcError) as exc_info:
            order_servicer.CreateOrder(request, grpc_context)
        
        assert exc_info.value._code == grpc.StatusCode.FAILED_PRECONDITION
        assert "prod-no-stock" in exc_info.value._details
    
    def test_multiple_items_mixed_stock(self, order_servicer, grpc_context):
        """Test order with multiple items, some insufficient stock."""
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-high-stock", quantity=10),
            order_pb2.LineItem(product_id="prod-low-stock", quantity=10),  # Insufficient
            order_pb2.LineItem(product_id="prod-no-stock", quantity=1)     # Insufficient
        ])
        
        with pytest.raises(grpc.RpcError) as exc_info:
            order_servicer.CreateOrder(request, grpc_context)
        
        assert exc_info.value._code == grpc.StatusCode.FAILED_PRECONDITION
        # Should list both products with insufficient stock
        assert "prod-low-stock" in exc_info.value._details
        assert "prod-no-stock" in exc_info.value._details
    
    def test_product_not_found_returns_not_found(self, order_servicer, grpc_context):
        """Test order for non-existent product returns NOT_FOUND."""
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="nonexistent-product", quantity=1)
        ])
        
        with pytest.raises(grpc.RpcError) as exc_info:
            order_servicer.CreateOrder(request, grpc_context)
        
        assert exc_info.value._code == grpc.StatusCode.NOT_FOUND
        assert "nonexistent-product" in exc_info.value._details


class TestIntegrationTimeout:
    """Integration tests for timeout handling."""
    
    def test_product_catalog_unavailable(self, grpc_context):
        """Test order service handles unavailable Product Catalog."""
        # Create order servicer pointing to non-existent port
        storage = InMemoryOrderStorage()
        servicer = OrderServiceServicer(storage, product_catalog_address='localhost:59999')
        
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=1)
        ])
        
        with pytest.raises(grpc.RpcError) as exc_info:
            servicer.CreateOrder(request, grpc_context)
        
        assert exc_info.value._code == grpc.StatusCode.UNAVAILABLE
        
        # Cleanup
        servicer.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
