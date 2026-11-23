"""
Test SQLite storage mode for Product Catalog Service.
"""

import grpc
import product_pb2
import product_pb2_grpc
import os

def test_sqlite_storage():
    """Test SQLite storage functionality."""
    
    # Remove old database if it exists
    db_path = 'product_catalog.db'
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed old database: {db_path}")
    
    print("\nNote: To test SQLite mode, start the service with:")
    print("  python product_catalog_service.py --sqlite")
    print("\nThis test assumes the service is running in SQLite mode.")
    print("\n=== Testing SQLite Storage ===\n")
    
    # Create a channel to the service
    channel = grpc.insecure_channel('localhost:50051')
    stub = product_pb2_grpc.ProductCatalogServiceStub(channel)
    
    # Test: ListProducts
    print("Test: ListProducts")
    try:
        response = stub.ListProducts(product_pb2.Empty(), timeout=5)
        print(f"✓ ListProducts returned {len(response.products)} products")
        
        if response.products:
            first_product_id = response.products[0].id
            print(f"  - First product: {response.products[0].name} (ID: {first_product_id})")
    except grpc.RpcError as e:
        print(f"✗ ListProducts failed: {e.code()} - {e.details()}")
        channel.close()
        return
    
    print("\n=== Test completed ===")
    print(f"\nTo verify persistence, restart the service and run this test again.")
    print(f"The database file should be at: {os.path.abspath(db_path)}")
    
    channel.close()

if __name__ == '__main__':
    test_sqlite_storage()
