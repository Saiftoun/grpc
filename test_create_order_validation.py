"""
Test suite for CreateOrder RPC method validation (Task 4.2)

Tests request validation, stock validation, and error handling
for the Order Service CreateOrder method.
"""

import grpc
import pytest
import uuid
from unittest.mock import Mock, MagicMock, patch
import order_pb2
import order_pb2_grpc
import product_pb2
import product_pb2_grpc
from order_service import OrderServiceServicer, InMemoryOrderStorage


@pytest.fixture
def mock_product_stub():
    """Create a mock Product Catalog stub."""
    stub = Mock()
    stub.GetProduct = Mock()
    return stub


@pytest.fixture
def order_servicer(mock_product_stub):
    """Create an OrderServiceServicer with mocked product stub."""
    storage = InMemoryOrderStorage()
    servicer = OrderServiceServicer(storage)
    servicer.product_stub = mock_product_stub
    return servicer


@pytest.fixture
def mock_context():
    """Create a mock gRPC context."""
    context = Mock()
    context.abort = Mock(side_effect=grpc.RpcError)
    return context


class TestRequestValidation:
    """Test request validation rules."""
    
    def test_empty_item_list_returns_invalid_argument(self, order_servicer, mock_context):
        """Test that empty item list returns INVALID_ARGUMENT error."""
        request = order_pb2.OrderRequest(items=[])
        
        with pytest.raises(grpc.RpcError):
            order_servicer.CreateOrder(request, mock_context)
        
        mock_context.abort.assert_called_once()
        args = mock_context.abort.call_args[0]
        assert args[0] == grpc.StatusCode.INVALID_ARGUMENT
        assert "at least one item" in args[1].lower()
    
    def test_more_than_100_items_returns_invalid_argument(self, order_servicer, mock_context):
        """Test that >100 items returns INVALID_ARGUMENT error."""
        # Create 101 items
        items = [
            order_pb2.LineItem(product_id=f"prod-{i}", quantity=1)
            for i in range(101)
        ]
        request = order_pb2.OrderRequest(items=items)
        
        with pytest.raises(grpc.RpcError):
            order_servicer.CreateOrder(request, mock_context)
        
        mock_context.abort.assert_called_once()
        args = mock_context.abort.call_args[0]
        assert args[0] == grpc.StatusCode.INVALID_ARGUMENT
        assert "100 items" in args[1].lower()
    
    def test_quantity_less_than_1_returns_invalid_argument(self, order_servicer, mock_context):
        """Test that quantity < 1 returns INVALID_ARGUMENT error."""
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=0)
        ])
        
        with pytest.raises(grpc.RpcError):
            order_servicer.CreateOrder(request, mock_context)
        
        mock_context.abort.assert_called_once()
        args = mock_context.abort.call_args[0]
        assert args[0] == grpc.StatusCode.INVALID_ARGUMENT
        assert "1 and 1000" in args[1]
    
    def test_quantity_greater_than_1000_returns_invalid_argument(self, order_servicer, mock_context):
        """Test that quantity > 1000 returns INVALID_ARGUMENT error."""
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=1001)
        ])
        
        with pytest.raises(grpc.RpcError):
            order_servicer.CreateOrder(request, mock_context)
        
        mock_context.abort.assert_called_once()
        args = mock_context.abort.call_args[0]
        assert args[0] == grpc.StatusCode.INVALID_ARGUMENT
        assert "1 and 1000" in args[1]
    
    def test_valid_1_to_100_items_passes_validation(self, order_servicer, mock_product_stub, mock_context):
        """Test that 1-100 items with valid quantities passes initial validation."""
        # Mock product responses with sufficient stock
        mock_product_stub.GetProduct.return_value = product_pb2.Product(
            id="prod-1",
            name="Test Product",
            price=10.0,
            stock=100
        )
        
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=5)
        ])
        
        # Should not abort during validation, will return placeholder response
        response = order_servicer.CreateOrder(request, mock_context)
        
        # Validation passed (no abort called)
        mock_context.abort.assert_not_called()


class TestStockValidation:
    """Test stock validation with Product Catalog Service."""
    
    def test_calls_get_product_for_each_item(self, order_servicer, mock_product_stub, mock_context):
        """Test that GetProduct is called for each line item."""
        mock_product_stub.GetProduct.return_value = product_pb2.Product(
            id="prod-1",
            name="Test Product",
            price=10.0,
            stock=100
        )
        
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=5),
            order_pb2.LineItem(product_id="prod-2", quantity=3)
        ])
        
        order_servicer.CreateOrder(request, mock_context)
        
        assert mock_product_stub.GetProduct.call_count == 2
    
    def test_get_product_called_with_5_second_timeout(self, order_servicer, mock_product_stub, mock_context):
        """Test that GetProduct is called with 5-second timeout."""
        mock_product_stub.GetProduct.return_value = product_pb2.Product(
            id="prod-1",
            name="Test Product",
            price=10.0,
            stock=100
        )
        
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=5)
        ])
        
        order_servicer.CreateOrder(request, mock_context)
        
        # Check timeout parameter
        call_kwargs = mock_product_stub.GetProduct.call_args[1]
        assert call_kwargs['timeout'] == 5.0
    
    def test_insufficient_stock_returns_failed_precondition(self, order_servicer, mock_product_stub, mock_context):
        """Test that insufficient stock returns FAILED_PRECONDITION error."""
        mock_product_stub.GetProduct.return_value = product_pb2.Product(
            id="prod-1",
            name="Test Product",
            price=10.0,
            stock=3  # Less than requested quantity
        )
        
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=5)
        ])
        
        with pytest.raises(grpc.RpcError):
            order_servicer.CreateOrder(request, mock_context)
        
        mock_context.abort.assert_called_once()
        args = mock_context.abort.call_args[0]
        assert args[0] == grpc.StatusCode.FAILED_PRECONDITION
        assert "insufficient stock" in args[1].lower()
        assert "prod-1" in args[1]
    
    def test_multiple_items_insufficient_stock_lists_all_products(self, order_servicer, mock_product_stub, mock_context):
        """Test that FAILED_PRECONDITION lists all products with insufficient stock."""
        def mock_get_product(request, timeout):
            if request.product_id == "prod-1":
                return product_pb2.Product(id="prod-1", name="Product 1", price=10.0, stock=2)
            elif request.product_id == "prod-2":
                return product_pb2.Product(id="prod-2", name="Product 2", price=20.0, stock=100)
            elif request.product_id == "prod-3":
                return product_pb2.Product(id="prod-3", name="Product 3", price=30.0, stock=1)
        
        mock_product_stub.GetProduct.side_effect = mock_get_product
        
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=5),
            order_pb2.LineItem(product_id="prod-2", quantity=10),
            order_pb2.LineItem(product_id="prod-3", quantity=3)
        ])
        
        with pytest.raises(grpc.RpcError):
            order_servicer.CreateOrder(request, mock_context)
        
        args = mock_context.abort.call_args[0]
        assert args[0] == grpc.StatusCode.FAILED_PRECONDITION
        # Both prod-1 and prod-3 should be listed
        assert "prod-1" in args[1]
        assert "prod-3" in args[1]
    
    def test_sufficient_stock_passes_validation(self, order_servicer, mock_product_stub, mock_context):
        """Test that sufficient stock passes validation."""
        mock_product_stub.GetProduct.return_value = product_pb2.Product(
            id="prod-1",
            name="Test Product",
            price=10.0,
            stock=100
        )
        
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=50)
        ])
        
        response = order_servicer.CreateOrder(request, mock_context)
        
        # Should not abort
        mock_context.abort.assert_not_called()


class TestErrorHandling:
    """Test error handling for Product Catalog Service communication."""
    
    def test_product_not_found_returns_not_found(self, order_servicer, mock_product_stub, mock_context):
        """Test that non-existent product returns NOT_FOUND error."""
        # Mock NOT_FOUND error from Product Catalog
        error = grpc.RpcError()
        error.code = lambda: grpc.StatusCode.NOT_FOUND
        error.details = lambda: "Product not found"
        mock_product_stub.GetProduct.side_effect = error
        
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="nonexistent", quantity=1)
        ])
        
        with pytest.raises(grpc.RpcError):
            order_servicer.CreateOrder(request, mock_context)
        
        mock_context.abort.assert_called_once()
        args = mock_context.abort.call_args[0]
        assert args[0] == grpc.StatusCode.NOT_FOUND
        assert "nonexistent" in args[1]
    
    def test_product_catalog_timeout_returns_unavailable(self, order_servicer, mock_product_stub, mock_context):
        """Test that Product Catalog timeout returns UNAVAILABLE error."""
        # Mock DEADLINE_EXCEEDED error
        error = grpc.RpcError()
        error.code = lambda: grpc.StatusCode.DEADLINE_EXCEEDED
        error.details = lambda: "Deadline exceeded"
        mock_product_stub.GetProduct.side_effect = error
        
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=1)
        ])
        
        with pytest.raises(grpc.RpcError):
            order_servicer.CreateOrder(request, mock_context)
        
        mock_context.abort.assert_called_once()
        args = mock_context.abort.call_args[0]
        assert args[0] == grpc.StatusCode.UNAVAILABLE
        assert "timed out" in args[1].lower()
    
    def test_product_catalog_unreachable_returns_unavailable(self, order_servicer, mock_product_stub, mock_context):
        """Test that Product Catalog unreachable returns UNAVAILABLE error."""
        # Mock UNAVAILABLE error
        error = grpc.RpcError()
        error.code = lambda: grpc.StatusCode.UNAVAILABLE
        error.details = lambda: "Service unavailable"
        mock_product_stub.GetProduct.side_effect = error
        
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=1)
        ])
        
        with pytest.raises(grpc.RpcError):
            order_servicer.CreateOrder(request, mock_context)
        
        mock_context.abort.assert_called_once()
        args = mock_context.abort.call_args[0]
        assert args[0] == grpc.StatusCode.UNAVAILABLE
        assert "unavailable" in args[1].lower()


class TestLogging:
    """Test logging for order creation attempts and errors."""
    
    @patch('order_service.logger')
    def test_logs_order_creation_attempt(self, mock_logger, order_servicer, mock_product_stub, mock_context):
        """Test that order creation attempts are logged."""
        mock_product_stub.GetProduct.return_value = product_pb2.Product(
            id="prod-1",
            name="Test Product",
            price=10.0,
            stock=100
        )
        
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=5),
            order_pb2.LineItem(product_id="prod-2", quantity=3)
        ])
        
        order_servicer.CreateOrder(request, mock_context)
        
        # Check that info log was called with item count
        mock_logger.info.assert_called()
        log_message = mock_logger.info.call_args[0][0]
        assert "2 items" in log_message
    
    @patch('order_service.logger')
    def test_logs_validation_errors(self, mock_logger, order_servicer, mock_context):
        """Test that validation errors are logged."""
        request = order_pb2.OrderRequest(items=[])
        
        with pytest.raises(grpc.RpcError):
            order_servicer.CreateOrder(request, mock_context)
        
        # Check warning log was called
        mock_logger.warning.assert_called()
        log_message = mock_logger.warning.call_args[0][0]
        assert "empty item list" in log_message.lower()
    
    @patch('order_service.logger')
    def test_logs_insufficient_stock(self, mock_logger, order_servicer, mock_product_stub, mock_context):
        """Test that insufficient stock errors are logged."""
        mock_product_stub.GetProduct.return_value = product_pb2.Product(
            id="prod-1",
            name="Test Product",
            price=10.0,
            stock=3
        )
        
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=5)
        ])
        
        with pytest.raises(grpc.RpcError):
            order_servicer.CreateOrder(request, mock_context)
        
        # Check warning log was called with stock details
        mock_logger.warning.assert_called()
        log_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
        assert any("insufficient stock" in log.lower() and "prod-1" in log for log in log_calls)
    
    @patch('order_service.logger')
    def test_logs_grpc_communication_errors(self, mock_logger, order_servicer, mock_product_stub, mock_context):
        """Test that gRPC communication errors are logged."""
        error = grpc.RpcError()
        error.code = lambda: grpc.StatusCode.UNAVAILABLE
        error.details = lambda: "Connection refused"
        mock_product_stub.GetProduct.side_effect = error
        
        request = order_pb2.OrderRequest(items=[
            order_pb2.LineItem(product_id="prod-1", quantity=1)
        ])
        
        with pytest.raises(grpc.RpcError):
            order_servicer.CreateOrder(request, mock_context)
        
        # Check error log was called
        mock_logger.error.assert_called()
        log_message = mock_logger.error.call_args[0][0]
        assert "unavailable" in log_message.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
