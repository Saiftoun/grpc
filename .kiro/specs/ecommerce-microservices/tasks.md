# Implementation Plan: E-Commerce Microservices

## Overview

This implementation plan breaks down the E-Commerce Microservices system into discrete coding tasks. The system consists of two Python gRPC backend services (Product Catalog and Order Management), a FastAPI HTTP gateway, and HTML/Tailwind CSS frontend pages. Tasks are organized to build incrementally, starting with foundational Protocol Buffer definitions and service skeletons, then implementing core business logic, and finally wiring everything together with the web interface.

## Tasks

- [x] 1. Set up project structure and Protocol Buffer definitions
  - Create directory structure: `protos/`, `gateway/`, `gateway/templates/`
  - Create `protos/product.proto` with ProductCatalogService definition (ListProducts, GetProduct, UpdateStock methods)
  - Create `protos/order.proto` with OrderService definition (CreateOrder, ListOrders methods)
  - Create `requirements.txt` with dependencies: grpcio>=1.48.0, grpcio-tools>=1.48.0, fastapi>=0.95.0, uvicorn>=0.20.0, jinja2>=3.1.0, protobuf>=4.21.0
  - Create compilation script or document compilation command: `python -m grpc_tools.protoc -I./protos --python_out=. --grpc_python_out=. protos/product.proto protos/order.proto`
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 8.1, 8.2, 8.8_

- [x] 2. Implement Product Catalog Service core functionality
  - [x] 2.1 Create Product Catalog Service with storage initialization
    - Implement `product_catalog_service.py` with gRPC server setup on port 50051
    - Implement storage layer supporting both SQLite and in-memory modes (use in-memory by default)
    - Implement data seeding logic: 6+ products with varied stock levels (at least 2 with stock=0, 2 with 1-50, 2 with 50+)
    - Implement database schema for SQLite mode: `CREATE TABLE products (id TEXT PRIMARY KEY, name TEXT, description TEXT, price REAL, stock INTEGER, image_url TEXT)`
    - _Requirements: 1.1, 1.2, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8_

  - [x] 2.2 Implement ListProducts RPC method
    - Implement `ListProducts` method to query all products from storage
    - Return ProductList message with all products
    - Handle empty catalog case (return empty list)
    - _Requirements: 1.3, 1.4, 1.5_

  - [x] 2.3 Implement GetProduct RPC method
    - Implement `GetProduct` method to query product by ID
    - Return Product message for valid product ID
    - Return gRPC NOT_FOUND error for non-existent product ID
    - _Requirements: 1.6, 1.7, 1.8_

  - [x] 2.4 Implement UpdateStock RPC method with atomic operations
    - Implement `UpdateStock` method with product ID and decrement amount validation
    - Implement atomic stock update (check stock >= decrement, then subtract)
    - Return StockUpdateResponse with success status and new stock level
    - Return gRPC FAILED_PRECONDITION error if decrement exceeds stock
    - Return gRPC NOT_FOUND error for non-existent product ID
    - Persist updated stock level to storage
    - Add logging for all stock update operations (product ID, decrement, result)
    - _Requirements: 1.9, 1.10, 1.11, 1.12, 1.13_

  - [x]* 2.5 Write unit tests for Product Catalog Service
    - Test ListProducts returns seeded products
    - Test GetProduct with valid and invalid IDs
    - Test UpdateStock success, insufficient stock, and invalid ID cases
    - Test data seeding creates correct number of products with correct stock distribution
    - _Requirements: 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.11, 1.12_

- [x] 3. Checkpoint - Verify Product Catalog Service
  - Ensure all tests pass, manually start Product Catalog Service on port 50051, ask the user if questions arise.

- [x] 4. Implement Order Service core functionality
  - [x] 4.1 Create Order Service with gRPC client to Product Catalog
    - Implement `order_service.py` with gRPC server setup on port 50052
    - Implement storage layer supporting both SQLite and in-memory modes (use in-memory by default)
    - Create gRPC channel and stub to Product Catalog Service (localhost:50051) with keepalive options
    - Implement database schema for SQLite mode: `orders` table and `order_items` table
    - _Requirements: 2.1, 2.13_

  - [x] 4.2 Implement CreateOrder RPC method with stock validation
    - Implement request validation (1-100 items, quantities 1-1000 per item)
    - Return gRPC INVALID_ARGUMENT error for empty list or >100 items
    - For each line item, call Product Catalog's GetProduct with 5-second timeout
    - Collect product names and prices from GetProduct responses
    - Validate stock availability for all items (stock >= quantity)
    - Return gRPC FAILED_PRECONDITION error with list of product IDs if any item has insufficient stock
    - Return gRPC UNAVAILABLE error if Product Catalog times out or is unreachable
    - Return gRPC NOT_FOUND error if any product ID does not exist
    - Add logging for order creation attempts and gRPC communication errors
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.11, 2.12_

  - [x] 4.3 Implement stock decrement and order persistence in CreateOrder
    - After validation passes, call Product Catalog's UpdateStock for each item with 5-second timeout
    - If any UpdateStock call fails, abort order and return gRPC FAILED_PRECONDITION error without persisting
    - Generate UUID v4 order ID and ISO 8601 timestamp
    - Store order with line items (including product names and prices as snapshots) and total
    - Return OrderResponse with order ID, timestamp, and success status
    - Add logging for successful stock updates and order creation
    - _Requirements: 2.7, 2.8, 2.10_

  - [x] 4.4 Implement ListOrders RPC method
    - Implement `ListOrders` method to query all orders from storage
    - Return OrderList message with all historical orders including line items and totals
    - _Requirements: 2.9_

  - [x]* 4.5 Write unit tests for Order Service
    - Test CreateOrder with valid items (mock Product Catalog responses)
    - Test CreateOrder validation errors (empty items, >100 items, invalid quantities)
    - Test CreateOrder with insufficient stock (mock FAILED_PRECONDITION from Product Catalog)
    - Test CreateOrder with Product Catalog timeout (mock UNAVAILABLE)
    - Test CreateOrder with partial failure scenario (some UpdateStock calls succeed, then one fails)
    - Test ListOrders returns created orders
    - Test UUID and timestamp generation
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12_

- [x] 5. Checkpoint - Verify Order Service
  - Ensure all tests pass, manually start Order Service on port 50052 with Product Catalog running, ask the user if questions arise.

- [x] 6. Implement Web Gateway (FastAPI)
  - [x] 6.1 Create FastAPI application with gRPC client lifecycle management
    - Implement `gateway/main.py` with FastAPI app
    - Implement lifespan context manager to create gRPC channels and stubs on startup
    - Create channels to Product Catalog (localhost:50051) and Order Service (localhost:50052)
    - Close channels on shutdown
    - Configure app to listen on port 8000
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 6.2 Implement GET /api/products endpoint
    - Implement endpoint that calls Product Catalog's ListProducts with 10-second timeout
    - Convert protobuf Product messages to JSON array
    - Return HTTP 200 with JSON array on success
    - Translate gRPC UNAVAILABLE to HTTP 503 with error message
    - Add logging for requests and gRPC errors
    - _Requirements: 4.4, 4.5, 9.1, 9.3, 9.4_

  - [x] 6.3 Implement POST /api/orders endpoint
    - Implement endpoint that accepts JSON body with items array (product_id, quantity)
    - Validate JSON structure and return HTTP 400 for invalid/missing fields
    - Convert JSON to OrderRequest protobuf message
    - Call Order Service's CreateOrder with 15-second timeout
    - Return HTTP 200 with order ID and timestamp on success
    - Translate gRPC FAILED_PRECONDITION to HTTP 412 with out_of_stock product list
    - Translate gRPC UNAVAILABLE/DEADLINE_EXCEEDED to HTTP 503
    - Add logging for requests and gRPC errors
    - _Requirements: 4.6, 4.7, 4.8, 9.2, 9.3, 9.4, 9.7_

  - [x] 6.4 Implement GET /api/orders endpoint
    - Implement endpoint that calls Order Service's ListOrders with 30-second timeout
    - Convert protobuf Order messages to JSON array
    - Return HTTP 200 with JSON array on success
    - Translate gRPC UNAVAILABLE to HTTP 503 with error message
    - Translate gRPC NOT_FOUND to HTTP 404
    - Add logging for requests and gRPC errors
    - _Requirements: 4.9, 4.10, 9.3, 9.4, 9.8_

  - [x] 6.5 Set up Jinja2 template rendering for HTML routes
    - Configure Jinja2Templates with `gateway/templates/` directory
    - Implement GET / route to render `index.html` (storefront)
    - Implement GET /orders route to render `orders.html` (order history)
    - _Requirements: 4.11, 4.12, 7.1_

  - [x]* 6.6 Write unit tests for Web Gateway
    - Test /api/products with successful gRPC response returns 200
    - Test /api/products with gRPC UNAVAILABLE returns 503
    - Test /api/orders POST with valid request returns 200
    - Test /api/orders POST with invalid JSON returns 400
    - Test /api/orders POST with gRPC FAILED_PRECONDITION returns 412
    - Test /api/orders GET returns 200 with order array
    - Test error translation for all gRPC status codes
    - _Requirements: 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 9.1, 9.2, 9.7, 9.8_

- [x] 7. Checkpoint - Verify Web Gateway
  - Ensure all tests pass, manually start Web Gateway with both backend services running, test API endpoints, ask the user if questions arise.

- [x] 8. Implement Storefront frontend page
  - [x] 8.1 Create storefront HTML structure with Tailwind CSS
    - Create `gateway/templates/index.html`
    - Add Tailwind CSS 3.x CDN link in head
    - Implement responsive product grid (1 column <640px, 2 columns 640-1023px, 3+ columns ≥1024px)
    - Implement shopping cart component (slide-over panel or fixed sidebar)
    - Add search/filter input field for products
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.11_

  - [x] 8.2 Implement product loading and rendering JavaScript
    - Implement `loadProducts()` function using fetch API with 10-second timeout (AbortSignal)
    - Call GET /api/products on page load
    - Render product cards with name, description, price (2 decimals), stock, image, "Add to Cart" button
    - Display "Out of Stock" badge and disable button if stock = 0
    - Display error message "Unable to load products. Please try again later." on failure
    - _Requirements: 5.4, 5.6, 5.7, 5.8, 5.12_

  - [x] 8.3 Implement shopping cart state management
    - Implement cart object: `{ product_id: { product, quantity } }`
    - Implement `addToCart(product)` function that adds product or increments quantity
    - Validate quantity does not exceed available stock
    - Display validation message "Only [stock quantity] available" if limit reached
    - Update cart UI to show product name, quantity, unit price, and line total for all items
    - _Requirements: 5.9, 5.10, 5.13_

  - [x] 8.4 Implement checkout functionality
    - Add "Checkout" button in cart component
    - Disable "Checkout" button if cart is empty
    - Implement `checkout()` function using fetch API POST to /api/orders with 15-second timeout
    - Send JSON payload with items array (product_id, quantity)
    - On HTTP 200, display success message with order ID and clear cart
    - On HTTP 412, display error message listing out-of-stock product names
    - On HTTP 503, display "Service temporarily unavailable. Please try again later."
    - On timeout, display "Request timed out. Please try again."
    - Preserve cart state on error so customer can retry
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10_

  - [ ]* 8.5 Write unit tests for storefront JavaScript
    - Test addToCart increments quantity for existing products
    - Test addToCart respects stock limits
    - Test addToCart disabled for out-of-stock products
    - Test checkout sends correct payload format
    - Test checkout handles 200, 412, 503 responses
    - Test checkout handles timeout errors
    - Test loadProducts timeout after 10 seconds
    - _Requirements: 5.9, 5.10, 5.12, 5.13, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

- [x] 9. Implement Order History frontend page
  - [x] 9.1 Create order history HTML structure with Tailwind CSS
    - Create `gateway/templates/orders.html`
    - Add Tailwind CSS 3.x CDN link in head
    - Implement list/grid layout for orders
    - Add navigation link back to storefront
    - _Requirements: 7.1, 7.2_

  - [x] 9.2 Implement order loading and rendering JavaScript
    - Implement `loadOrders()` function using fetch API GET /api/orders with 30-second timeout
    - Render each order with order ID, timestamp (ISO 8601), line items table (product name, quantity, unit price), and total
    - Display "No orders yet" message if response contains zero orders
    - Display "Order service is currently unavailable. Please try again later." on HTTP 503
    - Display "Request timed out. Please try again." on timeout
    - Display "An error occurred while loading orders. Please try again." on other HTTP errors
    - Display "Failed to load order data. Please refresh the page." on JSON parse errors
    - _Requirements: 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 7.10, 7.11, 7.12, 7.13_

  - [ ]* 9.3 Write unit tests for order history JavaScript
    - Test loadOrders handles empty order list
    - Test loadOrders timeout after 30 seconds
    - Test loadOrders handles 503 error
    - Test loadOrders handles invalid JSON
    - _Requirements: 7.3, 7.9, 7.10, 7.11, 7.13_

- [x] 10. Create project documentation
  - [x] 10.1 Create comprehensive README.md
    - Add "Setup" section with `pip install -r requirements.txt` command
    - Add "Compile Protocol Buffers" section with exact protoc command
    - Add "Running the Services" section with separate commands for each service (Product Catalog, Order Service, Web Gateway)
    - Add "Project Structure" section showing directory organization
    - Add "Accessing the Application" section with URLs for storefront and order history
    - Verify commands execute without errors when followed in sequence
    - _Requirements: 8.3, 8.4, 8.5, 8.6, 8.7, 8.9_

- [x] 11. Final checkpoint and integration testing
  - Ensure all tests pass, ask the user if questions arise.

- [ ]* 12. End-to-end integration tests
  - [x]* 12.1 Test complete order flow
    - Start all three services
    - Call /api/products and verify seeded products returned
    - Submit order via /api/orders with valid items
    - Verify HTTP 200 response with order ID
    - Call /api/products again and verify stock decreased
    - Call /api/orders and verify order appears in history
    - Attempt order with quantity exceeding stock, verify HTTP 412 response
    - Verify stock unchanged after failed order
    - _Requirements: 1.3, 1.4, 1.10, 1.13, 2.6, 2.7, 2.9, 2.11, 4.5, 4.7, 9.7_

  - [x]* 12.2 Test service resilience
    - Stop Product Catalog Service
    - Call /api/products, verify HTTP 503 within 10 seconds
    - Call /api/orders POST, verify HTTP 503 within timeout
    - Restart Product Catalog Service
    - Verify services recover and requests succeed
    - _Requirements: 9.1, 9.2, 9.3_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- Each task references specific requirements from the requirements document for traceability
- Checkpoints ensure incremental validation and provide opportunities for user feedback
- The implementation uses Python throughout (gRPC services with grpcio, FastAPI gateway, vanilla JavaScript frontend)
- All services use in-memory storage by default for simplicity; SQLite persistence is supported but not required
- No Docker or Kubernetes required - all services run directly with Python for local development
- Testing tasks are marked optional but strongly recommended for production readiness
- Protocol Buffer compilation must be done before running services

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4"] },
    { "id": 3, "tasks": ["2.5", "4.1"] },
    { "id": 4, "tasks": ["4.2"] },
    { "id": 5, "tasks": ["4.3", "4.4"] },
    { "id": 6, "tasks": ["4.5", "6.1"] },
    { "id": 7, "tasks": ["6.2", "6.3", "6.4"] },
    { "id": 8, "tasks": ["6.5", "6.6"] },
    { "id": 9, "tasks": ["8.1", "9.1"] },
    { "id": 10, "tasks": ["8.2", "9.2"] },
    { "id": 11, "tasks": ["8.3"] },
    { "id": 12, "tasks": ["8.4", "8.5", "9.3"] },
    { "id": 13, "tasks": ["10.1"] },
    { "id": 14, "tasks": ["12.1", "12.2"] }
  ]
}
```
