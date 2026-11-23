"""
Order Service - gRPC microservice for managing orders.

This service provides order management functionality including:
- Creating orders with stock validation
- Listing all historical orders

Storage: Supports both SQLite and in-memory modes (in-memory by default)
Port: 50052
"""

import grpc
from concurrent import futures
import uuid
import sqlite3
import logging
import sys
from typing import Dict, Optional, List
from datetime import datetime
import threading

# Import generated protobuf code
try:
    import order_pb2
    import order_pb2_grpc
    import product_pb2
    import product_pb2_grpc
except ImportError:
    print("ERROR: Protocol Buffer files not found. Please compile .proto files first:")
    print("  python -m grpc_tools.protoc -I./protos --python_out=. --grpc_python_out=. protos/order.proto")
    print("  python -m grpc_tools.protoc -I./protos --python_out=. --grpc_python_out=. protos/product.proto")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [OrderService] [%(levelname)s] [%(funcName)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)


class OrderStorage:
    """Abstract storage interface for orders."""
    
    def save_order(self, order: Dict) -> bool:
        """Save an order. Returns True on success."""
        raise NotImplementedError
    
    def get_all_orders(self) -> List[Dict]:
        """Return all orders."""
        raise NotImplementedError


class InMemoryOrderStorage(OrderStorage):
    """In-memory list storage for orders."""
    
    def __init__(self):
        self.orders: List[Dict] = []
        self.lock = threading.Lock()
        logger.info("Initialized in-memory order storage")
    
    def save_order(self, order: Dict) -> bool:
        with self.lock:
            self.orders.append(order)
            return True
    
    def get_all_orders(self) -> List[Dict]:
        with self.lock:
            return list(self.orders)


class SQLiteOrderStorage(OrderStorage):
    """SQLite database storage for orders."""
    
    def __init__(self, db_path: str = 'orders.db'):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._initialize_db()
        logger.info(f"Initialized SQLite order storage at {db_path}")
    
    def _initialize_db(self):
        """Create orders and order_items tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                timestamp TEXT,
                total REAL
            )
        ''')
        
        # Create order_items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                product_id TEXT,
                quantity INTEGER,
                product_name TEXT,
                unit_price REAL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_order(self, order: Dict) -> bool:
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Insert order
                cursor.execute(
                    'INSERT INTO orders (order_id, timestamp, total) VALUES (?, ?, ?)',
                    (order['order_id'], order['timestamp'], order['total'])
                )
                
                # Insert order items
                for item in order['items']:
                    cursor.execute(
                        '''INSERT INTO order_items 
                           (order_id, product_id, quantity, product_name, unit_price) 
                           VALUES (?, ?, ?, ?, ?)''',
                        (order['order_id'], item['product_id'], item['quantity'], 
                         item['product_name'], item['unit_price'])
                    )
                
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                logger.error(f"Failed to save order: {e}")
                return False
    
    def get_all_orders(self) -> List[Dict]:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all orders
            cursor.execute('SELECT * FROM orders ORDER BY timestamp DESC')
            order_rows = cursor.fetchall()
            
            orders = []
            for order_row in order_rows:
                order = {
                    'order_id': order_row['order_id'],
                    'timestamp': order_row['timestamp'],
                    'total': order_row['total'],
                    'items': []
                }
                
                # Get items for this order
                cursor.execute(
                    'SELECT * FROM order_items WHERE order_id = ?',
                    (order_row['order_id'],)
                )
                item_rows = cursor.fetchall()
                
                for item_row in item_rows:
                    order['items'].append({
                        'product_id': item_row['product_id'],
                        'quantity': item_row['quantity'],
                        'product_name': item_row['product_name'],
                        'unit_price': item_row['unit_price']
                    })
                
                orders.append(order)
            
            conn.close()
            return orders


class OrderServiceServicer(order_pb2_grpc.OrderServiceServicer):
    """gRPC servicer implementation for Order Service."""
    
    def __init__(self, storage: OrderStorage, product_catalog_address: str = 'localhost:50051'):
        self.storage = storage
        
        # Create gRPC channel and stub to Product Catalog Service
        # Configure keepalive options for connection stability
        options = [
            ('grpc.keepalive_time_ms', 30000),
            ('grpc.keepalive_timeout_ms', 10000),
        ]
        self.product_channel = grpc.insecure_channel(product_catalog_address, options=options)
        self.product_stub = product_pb2_grpc.ProductCatalogServiceStub(self.product_channel)
        
        logger.info(f"OrderServiceServicer initialized with Product Catalog at {product_catalog_address}")
    
    def CreateOrder(self, request, context):
        """
        Create a new order with stock validation.
        
        Validates request, checks product availability and stock levels,
        and returns appropriate errors for validation or stock issues.
        """
        logger.info(f"Order creation attempt with {len(request.items)} items")
        
        # Validate request: 1-100 items
        if len(request.items) == 0:
            logger.warning("Order creation failed: empty item list")
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Order must contain at least one item")
        
        if len(request.items) > 100:
            logger.warning(f"Order creation failed: too many items ({len(request.items)})")
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Order cannot contain more than 100 items")
        
        # Validate quantities: 1-1000 per item
        for item in request.items:
            if item.quantity < 1 or item.quantity > 1000:
                logger.warning(f"Order creation failed: invalid quantity {item.quantity} for product {item.product_id}")
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT, 
                    f"Quantity must be between 1 and 1000 (got {item.quantity} for product {item.product_id})"
                )
        
        # Collect product details and validate stock availability
        product_details = []
        insufficient_stock_products = []
        
        for item in request.items:
            try:
                # Call Product Catalog's GetProduct with 5-second timeout
                product_request = product_pb2.ProductRequest(product_id=item.product_id)
                product = self.product_stub.GetProduct(product_request, timeout=5.0)
                
                # Validate stock availability
                if product.stock < item.quantity:
                    insufficient_stock_products.append(item.product_id)
                    logger.warning(
                        f"Insufficient stock for product {item.product_id}: "
                        f"requested={item.quantity}, available={product.stock}"
                    )
                
                # Collect product name and price
                product_details.append({
                    'product_id': item.product_id,
                    'quantity': item.quantity,
                    'product_name': product.name,
                    'unit_price': product.price
                })
                
            except grpc.RpcError as e:
                # Handle gRPC errors from Product Catalog Service
                if e.code() == grpc.StatusCode.NOT_FOUND:
                    logger.error(f"Product not found: {item.product_id}")
                    context.abort(
                        grpc.StatusCode.NOT_FOUND,
                        f"Product {item.product_id} does not exist"
                    )
                elif e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                    logger.error(f"Timeout calling GetProduct for {item.product_id}: {e.details()}")
                    context.abort(
                        grpc.StatusCode.UNAVAILABLE,
                        "Product Catalog service timed out"
                    )
                elif e.code() == grpc.StatusCode.UNAVAILABLE:
                    logger.error(f"Product Catalog service unavailable: {e.details()}")
                    context.abort(
                        grpc.StatusCode.UNAVAILABLE,
                        "Product Catalog service is unavailable"
                    )
                else:
                    logger.error(f"gRPC error calling GetProduct for {item.product_id}: {e.code()} - {e.details()}")
                    context.abort(
                        grpc.StatusCode.UNAVAILABLE,
                        f"Error communicating with Product Catalog service: {e.details()}"
                    )
        
        # Return error if any items have insufficient stock
        if insufficient_stock_products:
            logger.warning(f"Order creation failed: insufficient stock for products {insufficient_stock_products}")
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                f"Insufficient stock for products: {', '.join(insufficient_stock_products)}"
            )
        
        # All validations passed - decrement stock for all items
        for detail in product_details:
            try:
                # Call Product Catalog's UpdateStock with 5-second timeout
                stock_update_request = product_pb2.StockUpdateRequest(
                    product_id=detail['product_id'],
                    decrement=detail['quantity']
                )
                stock_response = self.product_stub.UpdateStock(stock_update_request, timeout=5.0)
                
                if not stock_response.success:
                    # Stock update failed - abort order
                    logger.error(
                        f"Stock update failed for product {detail['product_id']}: "
                        f"UpdateStock returned success=False"
                    )
                    context.abort(
                        grpc.StatusCode.FAILED_PRECONDITION,
                        f"Failed to update stock for product {detail['product_id']}"
                    )
                
                logger.info(
                    f"Stock updated successfully for product {detail['product_id']}: "
                    f"quantity={detail['quantity']}, new_stock={stock_response.new_stock}"
                )
                
            except grpc.RpcError as e:
                # Handle gRPC errors from Product Catalog Service
                if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
                    logger.error(
                        f"Stock update failed for product {detail['product_id']}: "
                        f"insufficient stock (this should not happen after validation)"
                    )
                    context.abort(
                        grpc.StatusCode.FAILED_PRECONDITION,
                        f"Failed to update stock for product {detail['product_id']}: {e.details()}"
                    )
                elif e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                    logger.error(f"Timeout calling UpdateStock for {detail['product_id']}: {e.details()}")
                    context.abort(
                        grpc.StatusCode.UNAVAILABLE,
                        "Product Catalog service timed out during stock update"
                    )
                elif e.code() == grpc.StatusCode.UNAVAILABLE:
                    logger.error(f"Product Catalog service unavailable during UpdateStock: {e.details()}")
                    context.abort(
                        grpc.StatusCode.UNAVAILABLE,
                        "Product Catalog service is unavailable"
                    )
                else:
                    logger.error(
                        f"gRPC error calling UpdateStock for {detail['product_id']}: "
                        f"{e.code()} - {e.details()}"
                    )
                    context.abort(
                        grpc.StatusCode.UNAVAILABLE,
                        f"Error communicating with Product Catalog service: {e.details()}"
                    )
        
        # Generate UUID v4 order ID and ISO 8601 timestamp
        order_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + 'Z'
        
        # Calculate total
        total = sum(detail['quantity'] * detail['unit_price'] for detail in product_details)
        
        # Create order dictionary
        order = {
            'order_id': order_id,
            'timestamp': timestamp,
            'items': product_details,
            'total': total
        }
        
        # Store order
        if not self.storage.save_order(order):
            logger.error(f"Failed to persist order {order_id}")
            context.abort(
                grpc.StatusCode.INTERNAL,
                "Failed to save order to storage"
            )
        
        logger.info(
            f"Order created successfully: order_id={order_id}, "
            f"item_count={len(product_details)}, total={total:.2f}"
        )
        
        # Return success response
        response = order_pb2.OrderResponse()
        response.order_id = order_id
        response.timestamp = timestamp
        response.success = True
        response.message = "Order created successfully"
        return response
    
    def ListOrders(self, request, context):
        """
        List all historical orders with line items and totals.
        
        Returns OrderList message containing all orders from storage.
        """
        logger.info("Listing all orders")
        
        try:
            # Get all orders from storage
            orders_data = self.storage.get_all_orders()
            
            # Convert to protobuf format
            order_list = order_pb2.OrderList()
            
            for order_data in orders_data:
                order = order_list.orders.add()
                order.order_id = order_data['order_id']
                order.timestamp = order_data['timestamp']
                order.total = order_data['total']
                
                # Add line items
                for item_data in order_data['items']:
                    item = order.items.add()
                    item.product_id = item_data['product_id']
                    item.quantity = item_data['quantity']
                    item.product_name = item_data['product_name']
                    item.unit_price = item_data['unit_price']
            
            logger.info(f"Returning {len(orders_data)} orders")
            return order_list
            
        except Exception as e:
            logger.error(f"Failed to list orders: {e}")
            context.abort(
                grpc.StatusCode.INTERNAL,
                f"Failed to retrieve orders: {str(e)}"
            )
    
    def close(self):
        """Close the gRPC channel to Product Catalog Service."""
        if self.product_channel:
            self.product_channel.close()
            logger.info("Closed Product Catalog gRPC channel")


def serve(storage_mode: str = 'memory'):
    """Start the gRPC server."""
    # Initialize storage
    if storage_mode == 'sqlite':
        storage = SQLiteOrderStorage()
    else:
        storage = InMemoryOrderStorage()
    
    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = OrderServiceServicer(storage)
    order_pb2_grpc.add_OrderServiceServicer_to_server(servicer, server)
    
    port = '50052'
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    
    logger.info(f"Order Service started on port {port} (storage_mode={storage_mode})")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        servicer.close()
        server.stop(0)


if __name__ == '__main__':
    # Use in-memory storage by default
    storage_mode = 'memory'
    
    # Allow switching to SQLite via command line argument
    if len(sys.argv) > 1 and sys.argv[1] == '--sqlite':
        storage_mode = 'sqlite'
    
    serve(storage_mode)
