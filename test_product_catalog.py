"""
Simple test script to verify Product Catalog Service functionality.
"""

import grpc
import product_pb2
import product_pb2_grpc

def test_product_catalog():
    """Test all Product Catalog Service methods."""
    
    # Create a channel to the service
    channel = grpc.insecure_channel('localhost:50051')
    stub = product_pb2_grpc.ProductCatalogServiceStub(channel)
    
    print("=== Testing Product Catalog Service ===\n")
    
    # Test 1: ListProducts
    print("Test 1: ListProducts")
    try:
        response = stub.ListProducts(product_pb2.Empty(), timeout=5)
        print(f"✓ ListProducts returned {len(response.products)} products")
        
        # Verify data seeding requirements
        stock_zero = sum(1 for p in response.products if p.stock == 0)
        stock_low = sum(1 for p in response.products if 1 <= p.stock <= 50)
        stock_high = sum(1 for p in response.products if p.stock > 50)
        
        print(f"  - Products with stock=0: {stock_zero}")
        print(f"  - Products with stock 1-50: {stock_low}")
        print(f"  - Products with stock >50: {stock_high}")
        
        assert len(response.products) >= 6, "Should have at least 6 products"
        assert stock_zero >= 2, "Should have at least 2 products with stock=0"
        assert stock_low >= 2, "Should have at least 2 products with stock 1-50"
        assert stock_high >= 2, "Should have at least 2 products with stock >50"
        
        # Save first product ID for later tests
        if response.products:
            first_product_id = response.products[0].id
            first_product_stock = response.products[0].stock
            print(f"  - First product: {response.products[0].name} (ID: {first_product_id}, Stock: {first_product_stock})")
    except grpc.RpcError as e:
        print(f"✗ ListProducts failed: {e.code()} - {e.details()}")
        channel.close()
        return
    
    print()
    
    # Test 2: GetProduct with valid ID
    print("Test 2: GetProduct with valid ID")
    try:
        request = product_pb2.ProductRequest(product_id=first_product_id)
        response = stub.GetProduct(request, timeout=5)
        print(f"✓ GetProduct returned: {response.name}")
        assert response.id == first_product_id
    except grpc.RpcError as e:
        print(f"✗ GetProduct failed: {e.code()} - {e.details()}")
    
    print()
    
    # Test 3: GetProduct with invalid ID
    print("Test 3: GetProduct with invalid ID")
    try:
        request = product_pb2.ProductRequest(product_id="invalid-id-123")
        response = stub.GetProduct(request, timeout=5)
        print(f"✗ GetProduct should have returned NOT_FOUND error")
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            print(f"✓ GetProduct correctly returned NOT_FOUND: {e.details()}")
        else:
            print(f"✗ GetProduct returned unexpected error: {e.code()} - {e.details()}")
    
    print()
    
    # Test 4: UpdateStock with valid decrement (find a product with stock > 0)
    print("Test 4: UpdateStock with valid decrement")
    
    # Get products list again to find one with stock > 0
    response = stub.ListProducts(product_pb2.Empty(), timeout=5)
    product_with_stock = None
    for p in response.products:
        if p.stock > 0:
            product_with_stock = p
            break
    
    if product_with_stock:
        try:
            request = product_pb2.StockUpdateRequest(
                product_id=product_with_stock.id,
                decrement=1
            )
            response = stub.UpdateStock(request, timeout=5)
            print(f"✓ UpdateStock succeeded: new_stock={response.new_stock}")
            assert response.success == True
            assert response.new_stock == product_with_stock.stock - 1
        except grpc.RpcError as e:
            print(f"✗ UpdateStock failed: {e.code()} - {e.details()}")
    else:
        print("⊘ Skipped: No products with stock > 0")
    
    print()
    
    # Test 5: UpdateStock with excessive decrement
    print("Test 5: UpdateStock with excessive decrement (should fail)")
    if product_with_stock:
        try:
            request = product_pb2.StockUpdateRequest(
                product_id=product_with_stock.id,
                decrement=99999
            )
            response = stub.UpdateStock(request, timeout=5)
            print(f"✗ UpdateStock should have returned FAILED_PRECONDITION error")
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
                print(f"✓ UpdateStock correctly returned FAILED_PRECONDITION: {e.details()}")
            else:
                print(f"✗ UpdateStock returned unexpected error: {e.code()} - {e.details()}")
    else:
        print("⊘ Skipped: No products with stock > 0")
    
    print()
    
    # Test 6: UpdateStock with invalid product ID
    print("Test 6: UpdateStock with invalid product ID")
    try:
        request = product_pb2.StockUpdateRequest(
            product_id="invalid-id-456",
            decrement=1
        )
        response = stub.UpdateStock(request, timeout=5)
        print(f"✗ UpdateStock should have returned NOT_FOUND error")
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            print(f"✓ UpdateStock correctly returned NOT_FOUND: {e.details()}")
        else:
            print(f"✗ UpdateStock returned unexpected error: {e.code()} - {e.details()}")
    
    print()
    
    # Test 7: Verify stock persistence
    print("Test 7: Verify stock was updated")
    if product_with_stock:
        try:
            request = product_pb2.ProductRequest(product_id=product_with_stock.id)
            response = stub.GetProduct(request, timeout=5)
            expected_stock = product_with_stock.stock - 1
            if response.stock == expected_stock:
                print(f"✓ Stock persisted correctly: {response.stock} (expected {expected_stock})")
            else:
                print(f"✗ Stock not persisted: {response.stock} (expected {expected_stock})")
        except grpc.RpcError as e:
            print(f"✗ GetProduct failed: {e.code()} - {e.details()}")
    
    print()
    print("=== All tests completed ===")
    
    channel.close()

if __name__ == '__main__':
    test_product_catalog()
