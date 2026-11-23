"""
Product Catalog Service - gRPC microservice for managing product data.

This service provides product catalog functionality including:
- Listing all products
- Retrieving individual products by ID
- Updating stock levels atomically

Storage: Supports both SQLite and in-memory modes (in-memory by default)
Port: 50051
"""

import grpc
from concurrent import futures
import uuid
import sqlite3
import logging
import sys
from typing import Dict, Optional, List
import threading

# Import generated protobuf code
try:
    import product_pb2
    import product_pb2_grpc
except ImportError:
    print("ERROR: Protocol Buffer files not found. Please compile .proto files first:")
    print("  python -m grpc_tools.protoc -I./protos --python_out=. --grpc_python_out=. protos/product.proto")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [ProductCatalog] [%(levelname)s] [%(funcName)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)


class ProductStorage:
    """Abstract storage interface for products."""
    
    def get_all_products(self) -> List[Dict]:
        """Return all products."""
        raise NotImplementedError
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        """Return product by ID or None if not found."""
        raise NotImplementedError
    
    def update_stock(self, product_id: str, decrement: int) -> tuple[bool, int]:
        """
        Atomically update stock level.
        Returns (success, new_stock_level).
        """
        raise NotImplementedError
    
    def seed_data(self):
        """Initialize storage with sample products."""
        raise NotImplementedError


class InMemoryStorage(ProductStorage):
    """In-memory dictionary storage for products."""
    
    def __init__(self):
        self.products: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        logger.info("Initialized in-memory storage")
    
    def get_all_products(self) -> List[Dict]:
        with self.lock:
            return list(self.products.values())
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        with self.lock:
            return self.products.get(product_id)
    
    def update_stock(self, product_id: str, decrement: int) -> tuple[bool, int]:
        with self.lock:
            if product_id not in self.products:
                return False, -1
            
            current_stock = self.products[product_id]['stock']
            if current_stock < decrement:
                logger.warning(f"Stock update failed: insufficient stock product_id={product_id} current={current_stock} requested={decrement}")
                return False, current_stock
            
            new_stock = current_stock - decrement
            self.products[product_id]['stock'] = new_stock
            logger.info(f"Stock updated product_id={product_id} decrement={decrement} new_stock={new_stock}")
            return True, new_stock
    
    def seed_data(self):
        """Seed with 6+ products with varied stock levels."""
        sample_products = [
            {
                'id': str(uuid.uuid4()),
                'name': 'Wireless Headphones',
                'description': 'Premium noise-cancelling wireless headphones with 30-hour battery life',
                'price': 199.99,
                'stock': 0,
                'image_url': 'https://via.placeholder.com/300x300?text=Headphones'
            },
            {
                'id': str(uuid.uuid4()),
                'name': 'Smart Watch',
                'description': 'Fitness tracking smart watch with heart rate monitor and GPS',
                'price': 299.50,
                'stock': 0,
                'image_url': 'https://via.placeholder.com/300x300?text=Smart+Watch'
            },
            {
                'id': str(uuid.uuid4()),
                'name': 'Laptop Stand',
                'description': 'Ergonomic aluminum laptop stand with adjustable height',
                'price': 49.99,
                'stock': 25,
                'image_url': 'https://via.placeholder.com/300x300?text=Laptop+Stand'
            },
            {
                'id': str(uuid.uuid4()),
                'name': 'USB-C Hub',
                'description': '7-in-1 USB-C hub with HDMI, USB 3.0, and SD card reader',
                'price': 39.99,
                'stock': 15,
                'image_url': 'https://via.placeholder.com/300x300?text=USB-C+Hub'
            },
            {
                'id': str(uuid.uuid4()),
                'name': 'Mechanical Keyboard',
                'description': 'RGB mechanical keyboard with cherry MX switches',
                'price': 149.00,
                'stock': 75,
                'image_url': 'https://via.placeholder.com/300x300?text=Keyboard'
            },
            {
                'id': str(uuid.uuid4()),
                'name': 'Wireless Mouse',
                'description': 'Ergonomic wireless mouse with precision tracking',
                'price': 59.99,
                'stock': 120,
                'image_url': 'https://via.placeholder.com/300x300?text=Mouse'
            },
        ]
        
        with self.lock:
            for product in sample_products:
                self.products[product['id']] = product
        
        logger.info(f"Seeded {len(sample_products)} products")


class SQLiteStorage(ProductStorage):
    """SQLite database storage for products."""
    
    def __init__(self, db_path: str = 'product_catalog.db'):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._initialize_db()
        logger.info(f"Initialized SQLite storage at {db_path}")
    
    def _initialize_db(self):
        """Create products table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                price REAL,
                stock INTEGER,
                image_url TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def get_all_products(self) -> List[Dict]:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM products')
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
    
    def get_product(self, product_id: str) -> Optional[Dict]:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
    
    def update_stock(self, product_id: str, decrement: int) -> tuple[bool, int]:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check current stock
            cursor.execute('SELECT stock FROM products WHERE id = ?', (product_id,))
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return False, -1
            
            current_stock = row[0]
            if current_stock < decrement:
                logger.warning(f"Stock update failed: insufficient stock product_id={product_id} current={current_stock} requested={decrement}")
                conn.close()
                return False, current_stock
            
            # Update stock
            new_stock = current_stock - decrement
            cursor.execute('UPDATE products SET stock = ? WHERE id = ?', (new_stock, product_id))
            conn.commit()
            conn.close()
            
            logger.info(f"Stock updated product_id={product_id} decrement={decrement} new_stock={new_stock}")
            return True, new_stock
    
    def seed_data(self):
        """Seed database with sample products if empty."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if database is empty
            cursor.execute('SELECT COUNT(*) FROM products')
            count = cursor.fetchone()[0]
            
            if count > 0:
                logger.info(f"Database already contains {count} products, skipping seeding")
                conn.close()
                return
            
            # Seed data
            sample_products = [
                (str(uuid.uuid4()), 'Wireless Headphones', 'Premium noise-cancelling wireless headphones with 30-hour battery life', 199.99, 0, 'https://via.placeholder.com/300x300?text=Headphones'),
                (str(uuid.uuid4()), 'Smart Watch', 'Fitness tracking smart watch with heart rate monitor and GPS', 299.50, 0, 'https://via.placeholder.com/300x300?text=Smart+Watch'),
                (str(uuid.uuid4()), 'Laptop Stand', 'Ergonomic aluminum laptop stand with adjustable height', 49.99, 25, 'https://via.placeholder.com/300x300?text=Laptop+Stand'),
                (str(uuid.uuid4()), 'USB-C Hub', '7-in-1 USB-C hub with HDMI, USB 3.0, and SD card reader', 39.99, 15, 'https://via.placeholder.com/300x300?text=USB-C+Hub'),
                (str(uuid.uuid4()), 'Mechanical Keyboard', 'RGB mechanical keyboard with cherry MX switches', 149.00, 75, 'https://via.placeholder.com/300x300?text=Keyboard'),
                (str(uuid.uuid4()), 'Wireless Mouse', 'Ergonomic wireless mouse with precision tracking', 59.99, 120, 'https://via.placeholder.com/300x300?text=Mouse'),
            ]
            
            cursor.executemany(
                'INSERT INTO products (id, name, description, price, stock, image_url) VALUES (?, ?, ?, ?, ?, ?)',
                sample_products
            )
            conn.commit()
            conn.close()
            
            logger.info(f"Seeded {len(sample_products)} products")


class ProductCatalogServicer(product_pb2_grpc.ProductCatalogServiceServicer):
    """gRPC servicer implementation for Product Catalog."""
    
    def __init__(self, storage: ProductStorage):
        self.storage = storage
        logger.info("ProductCatalogServicer initialized")
    
    def ListProducts(self, request, context):
        """List all products in catalog."""
        try:
            products = self.storage.get_all_products()
            product_list = product_pb2.ProductList()
            
            for p in products:
                product = product_list.products.add()
                product.id = p['id']
                product.name = p['name']
                product.description = p['description']
                product.price = p['price']
                product.stock = p['stock']
                product.image_url = p['image_url']
            
            logger.info(f"ListProducts returned {len(products)} products")
            return product_list
        
        except Exception as e:
            logger.error(f"ListProducts error: {e}")
            context.abort(grpc.StatusCode.INTERNAL, f"Internal error: {str(e)}")
    
    def GetProduct(self, request, context):
        """Get a single product by ID."""
        product_id = request.product_id
        p = self.storage.get_product(product_id)
        
        if not p:
            logger.warning(f"GetProduct: product not found product_id={product_id}")
            context.abort(grpc.StatusCode.NOT_FOUND, "Product not found")
        
        product = product_pb2.Product()
        product.id = p['id']
        product.name = p['name']
        product.description = p['description']
        product.price = p['price']
        product.stock = p['stock']
        product.image_url = p['image_url']
        
        logger.info(f"GetProduct returned product_id={product_id}")
        return product
    
    def UpdateStock(self, request, context):
        """Update stock level for a product."""
        product_id = request.product_id
        decrement = request.decrement
        
        # Validate decrement
        if decrement < 0:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Decrement must be non-negative")
        
        # Check if product exists
        product = self.storage.get_product(product_id)
        if not product:
            logger.warning(f"UpdateStock: product not found product_id={product_id}")
            context.abort(grpc.StatusCode.NOT_FOUND, "Product not found")
        
        # Attempt stock update
        success, new_stock = self.storage.update_stock(product_id, decrement)
        
        if not success:
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Insufficient stock")
        
        response = product_pb2.StockUpdateResponse()
        response.success = True
        response.new_stock = new_stock
        
        return response


def serve(storage_mode: str = 'memory'):
    """Start the gRPC server."""
    # Initialize storage
    if storage_mode == 'sqlite':
        storage = SQLiteStorage()
    else:
        storage = InMemoryStorage()
    
    # Seed data
    try:
        storage.seed_data()
    except Exception as e:
        logger.error(f"Data seeding failed: {e}")
    
    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    product_pb2_grpc.add_ProductCatalogServiceServicer_to_server(
        ProductCatalogServicer(storage), server
    )
    
    port = '50051'
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    
    logger.info(f"Product Catalog Service started on port {port} (storage_mode={storage_mode})")
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.stop(0)


if __name__ == '__main__':
    # Use in-memory storage by default
    storage_mode = 'memory'
    
    # Allow switching to SQLite via command line argument
    if len(sys.argv) > 1 and sys.argv[1] == '--sqlite':
        storage_mode = 'sqlite'
    
    serve(storage_mode)
