"""
Unit tests for ListOrders RPC method.

Tests that ListOrders correctly retrieves and returns all orders from storage.
"""

import pytest
import grpc
from unittest.mock import Mock, MagicMock

import order_pb2
import order_pb2_grpc
from order_service import OrderServiceServicer, InMemoryOrderStorage, SQLiteOrderStorage


class TestListOrdersMethod:
    """Test suite for ListOrders RPC method."""
    
    @pytest.fixture
    def mock_product_stub(self):
        """Create a mock Product Catalog stub."""
        return Mock()
    
    @pytest.fixture
    def order_storage(self):
        """Create in-memory order storage."""
        return InMemoryOrderStorage()
    
    @pytest.fixture
    def order_servicer(self, order_storage, mock_product_stub):
        """Create Order servicer with mocked Product Catalog."""
        servicer = OrderServiceServicer(order_storage, 'localhost:50051')
        servicer.product_stub = mock_product_stub
        return servicer
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock gRPC context."""
        return Mock()
    
    def test_list_orders_returns_empty_list_when_no_orders(self, order_servicer, mock_context):
        """Test that ListOrders returns empty list when no orders exist."""
        request = order_pb2.Empty()
        
        response = order_servicer.ListOrders(request, mock_context)
        
        assert isinstance(response, order_pb2.OrderList)
        assert len(response.orders) == 0
    
    def test_list_orders_returns_all_orders(self, order_servicer, mock_context):
        """Test that ListOrders returns all orders from storage."""
        # Add some test orders to storage
        test_orders = [
            {
                'order_id': '123e4567-e89b-12d3-a456-426614174000',
                'timestamp': '2024-01-15T10:30:00Z',
                'total': 150.50,
                'items': [
                    {
                        'product_id': 'prod-1',
                        'quantity': 2,
                        'product_name': 'Laptop',
                        'unit_price': 75.25
                    }
                ]
            },
            {
                'order_id': '123e4567-e89b-12d3-a456-426614174001',
                'timestamp': '2024-01-15T11:00:00Z',
                'total': 50.00,
                'items': [
                    {
                        'product_id': 'prod-2',
                        'quantity': 1,
                        'product_name': 'Mouse',
                        'unit_price': 25.00
                    },
                    {
                        'product_id': 'prod-3',
                        'quantity': 1,
                        'product_name': 'Keyboard',
                        'unit_price': 25.00
                    }
                ]
            }
        ]
        
        for order in test_orders:
            order_servicer.storage.save_order(order)
        
        # Call ListOrders
        request = order_pb2.Empty()
        response = order_servicer.ListOrders(request, mock_context)
        
        # Verify response
        assert isinstance(response, order_pb2.OrderList)
        assert len(response.orders) == 2
        
        # Verify first order
        order1 = response.orders[0]
        assert order1.order_id == '123e4567-e89b-12d3-a456-426614174000'
        assert order1.timestamp == '2024-01-15T10:30:00Z'
        assert order1.total == 150.50
        assert len(order1.items) == 1
        assert order1.items[0].product_id == 'prod-1'
        assert order1.items[0].quantity == 2
        assert order1.items[0].product_name == 'Laptop'
        assert order1.items[0].unit_price == 75.25
        
        # Verify second order
        order2 = response.orders[1]
        assert order2.order_id == '123e4567-e89b-12d3-a456-426614174001'
        assert order2.timestamp == '2024-01-15T11:00:00Z'
        assert order2.total == 50.00
        assert len(order2.items) == 2
        assert order2.items[0].product_id == 'prod-2'
        assert order2.items[0].quantity == 1
        assert order2.items[0].product_name == 'Mouse'
        assert order2.items[1].product_id == 'prod-3'
        assert order2.items[1].quantity == 1
        assert order2.items[1].product_name == 'Keyboard'
    
    def test_list_orders_with_sqlite_storage(self, mock_product_stub, mock_context):
        """Test that ListOrders works with SQLite storage."""
        import tempfile
        import os
        
        # Create temporary database
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        try:
            # Create servicer with SQLite storage
            storage = SQLiteOrderStorage(db_path)
            servicer = OrderServiceServicer(storage, 'localhost:50051')
            servicer.product_stub = mock_product_stub
            
            # Add a test order
            test_order = {
                'order_id': '123e4567-e89b-12d3-a456-426614174000',
                'timestamp': '2024-01-15T10:30:00Z',
                'total': 100.00,
                'items': [
                    {
                        'product_id': 'prod-1',
                        'quantity': 1,
                        'product_name': 'Test Product',
                        'unit_price': 100.00
                    }
                ]
            }
            storage.save_order(test_order)
            
            # Call ListOrders
            request = order_pb2.Empty()
            response = servicer.ListOrders(request, mock_context)
            
            # Verify response
            assert isinstance(response, order_pb2.OrderList)
            assert len(response.orders) == 1
            assert response.orders[0].order_id == '123e4567-e89b-12d3-a456-426614174000'
            assert response.orders[0].total == 100.00
            assert len(response.orders[0].items) == 1
            
        finally:
            # Clean up
            if os.path.exists(db_path):
                os.remove(db_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
