"""
Verify that stock updates persist across service restarts (SQLite mode only).
"""

import grpc
import product_pb2
import product_pb2_grpc

def test_persistence():
    """Check if stock updates are persisted."""
    
    channel = grpc.insecure_channel('localhost:50051')
    stub = product_pb2_grpc.ProductCatalogServiceStub(channel)
    
    print("=== Testing Data Persistence ===\n")
    
    # Get all products
    response = stub.ListProducts(product_pb2.Empty(), timeout=5)
    
    # Look for the product with stock=24 (from previous test)
    for product in response.products:
        if product.name == "Laptop Stand":
            print(f"Found: {product.name}")
            print(f"  Stock: {product.stock}")
            if product.stock == 24:
                print(f"  ✓ Stock persisted correctly (was updated from 25 to 24)")
            else:
                print(f"  ✗ Stock not persisted (expected 24, got {product.stock})")
            break
    
    channel.close()

if __name__ == '__main__':
    test_persistence()
