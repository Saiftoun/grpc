# Requirements Document

## Introduction

This document defines the requirements for an E-Commerce Microservices web application built with pure Python backend services communicating via gRPC, and a modern HTML + Tailwind CSS frontend. The system enables users to browse products, manage a shopping cart, place orders, and view order history through a clean, responsive web interface backed by independent microservices.

## Glossary

- **Product_Catalog_Service**: The gRPC microservice that manages product data including inventory, pricing, and product details
- **Order_Service**: The gRPC microservice that handles order creation, cart checkout, and order history
- **Web_Gateway**: The FastAPI-based HTTP server that acts as a bridge between browser requests and gRPC microservices
- **Storefront_Page**: The main HTML page displaying the product grid and shopping cart interface
- **Order_History_Page**: The HTML page displaying previously placed orders
- **Shopping_Cart**: The client-side data structure holding products selected for purchase
- **Product**: An entity with ID, name, description, price, stock quantity, and image URL
- **Order**: An entity containing order ID, timestamp, line items, and total amount
- **Stock_Level**: The available quantity of a product in inventory
- **Protocol_Buffer**: The `.proto` schema files defining gRPC service contracts and message structures
- **gRPC_Client_Stub**: The Python client object used to invoke remote gRPC service methods

## Requirements

### Requirement 1: Product Catalog Service

**User Story:** As a system administrator, I want a dedicated Product Catalog microservice, so that product data management is isolated and scalable.

#### Acceptance Criteria

1. THE Product_Catalog_Service SHALL listen on port 50051 for gRPC connections
2. THE Product_Catalog_Service SHALL store product data using SQLite or in-memory storage
3. THE Product_Catalog_Service SHALL expose a `ListProducts` gRPC method
4. WHEN `ListProducts` is called, THE Product_Catalog_Service SHALL return all products in the catalog
5. WHEN `ListProducts` is called and the catalog is empty, THE Product_Catalog_Service SHALL return an empty list
6. THE Product_Catalog_Service SHALL expose a `GetProduct` gRPC method
7. WHEN `GetProduct` is called with a valid product ID, THE Product_Catalog_Service SHALL return the product data for that ID
8. IF `GetProduct` is called with a non-existent product ID, THEN THE Product_Catalog_Service SHALL return a gRPC NOT_FOUND error
9. THE Product_Catalog_Service SHALL expose an `UpdateStock` gRPC method
10. WHEN `UpdateStock` is called with a valid product ID and a positive integer decrement amount, THE Product_Catalog_Service SHALL reduce the stock quantity by the specified amount
11. IF `UpdateStock` is called with a decrement amount that exceeds current stock quantity, THEN THE Product_Catalog_Service SHALL return a gRPC FAILED_PRECONDITION error and leave stock quantity unchanged
12. IF `UpdateStock` is called with a non-existent product ID, THEN THE Product_Catalog_Service SHALL return a gRPC NOT_FOUND error
13. WHEN a product's stock quantity is successfully updated, THE Product_Catalog_Service SHALL persist the new stock level

### Requirement 2: Order Service

**User Story:** As a customer, I want my orders to be processed reliably, so that my purchases are recorded and inventory is updated correctly.

#### Acceptance Criteria

1. THE Order_Service SHALL listen on port 50052 for gRPC connections
2. THE Order_Service SHALL expose a `CreateOrder` gRPC method
3. WHEN `CreateOrder` is called, THE Order_Service SHALL accept a list of 1 to 100 product IDs with quantities between 1 and 1000 per line item
4. IF `CreateOrder` is called with an empty product list, THEN THE Order_Service SHALL return a gRPC INVALID_ARGUMENT error
5. IF `CreateOrder` is called with more than 100 line items, THEN THE Order_Service SHALL return a gRPC INVALID_ARGUMENT error
6. WHEN an order is created, THE Order_Service SHALL communicate with the Product_Catalog_Service via gRPC within a 5-second timeout to verify product availability for all requested product IDs
7. WHEN an order is created AND all products are available, THE Order_Service SHALL communicate with the Product_Catalog_Service via gRPC within a 5-second timeout to decrement stock levels atomically for all line items
8. IF any stock decrement operation fails during order creation, THEN THE Order_Service SHALL abort the order and return a gRPC FAILED_PRECONDITION error without persisting the order
9. THE Order_Service SHALL expose a `ListOrders` gRPC method that returns all historical orders
10. THE Order_Service SHALL generate a unique order ID (UUID v4 format) and timestamp (ISO 8601 format) for each order
11. IF product stock is insufficient for any requested line item, THEN THE Order_Service SHALL return a gRPC FAILED_PRECONDITION error listing all affected product IDs
12. IF communication with Product_Catalog_Service times out, THEN THE Order_Service SHALL return a gRPC UNAVAILABLE error
13. THE Order_Service SHALL store order history using SQLite or in-memory storage

### Requirement 3: Protocol Buffer Definitions

**User Story:** As a developer, I want well-defined service contracts, so that microservices can communicate reliably with type safety.

#### Acceptance Criteria

1. THE system SHALL include a `protos/product.proto` file using proto3 syntax
2. THE `protos/product.proto` file SHALL define the Product_Catalog_Service with rpc methods ListProducts, GetProduct, and UpdateStock
3. THE system SHALL include a `protos/order.proto` file using proto3 syntax
4. THE `protos/order.proto` file SHALL define the Order_Service with rpc methods CreateOrder and ListOrders
5. THE Protocol_Buffer definitions SHALL include message types for Product, ProductList, Order, and OrderRequest
6. THE Protocol_Buffer definitions SHALL define a package name for each `.proto` file
7. THE system SHALL provide a shell command or Python script to compile `.proto` files using `grpc_tools.protoc`
8. WHEN the compilation command is executed, THE system SHALL generate Python code files (*_pb2.py and *_pb2_grpc.py) without compilation errors
9. IF the compilation command fails, THEN THE system SHALL output an error message indicating the cause of the failure
10. THE generated Python code SHALL be importable by both Product_Catalog_Service and Order_Service without import errors
11. THE generated Python code SHALL be importable by the Web_Gateway without import errors

### Requirement 4: Web Gateway HTTP-to-gRPC Bridge

**User Story:** As a frontend developer, I want an HTTP API gateway, so that I can interact with gRPC services using standard web requests.

#### Acceptance Criteria

1. THE Web_Gateway SHALL be built using FastAPI
2. THE Web_Gateway SHALL listen on port 8000 for HTTP connections
3. WHEN the Web_Gateway starts, THE Web_Gateway SHALL create gRPC_Client_Stub instances for both Product_Catalog_Service (localhost:50051) and Order_Service (localhost:50052)
4. THE Web_Gateway SHALL expose an HTTP GET endpoint `/api/products`
5. WHEN `/api/products` is called, THE Web_Gateway SHALL invoke the Product_Catalog_Service `ListProducts` method and return the response as a JSON array of product objects
6. THE Web_Gateway SHALL expose an HTTP POST endpoint `/api/orders`
7. WHEN `/api/orders` receives a POST request with a JSON body containing a list of product IDs and quantities, THE Web_Gateway SHALL invoke the Order_Service `CreateOrder` method
8. IF the POST request to `/api/orders` contains invalid JSON or missing required fields, THEN THE Web_Gateway SHALL return an HTTP 400 error with a JSON error message
9. THE Web_Gateway SHALL expose an HTTP GET endpoint `/api/orders`
10. WHEN `/api/orders` is called with a GET request, THE Web_Gateway SHALL invoke the Order_Service `ListOrders` method and return the response as a JSON array of order objects
11. IF a gRPC microservice is unavailable or times out, THEN THE Web_Gateway SHALL return an HTTP 503 error with a JSON error message indicating which service is unavailable
12. THE Web_Gateway SHALL use Jinja2 templates to serve HTML pages

### Requirement 5: Storefront User Interface

**User Story:** As a customer, I want a modern, responsive storefront, so that I can browse products and add them to my cart easily.

#### Acceptance Criteria

1. THE Storefront_Page SHALL display products in a grid layout with 1 column on screens below 640px width, 2 columns on screens 640px to 1023px width, and 3 or more columns on screens 1024px width and above
2. THE Storefront_Page SHALL use Tailwind CSS via CDN (version 3.0 or later) for styling
3. THE Storefront_Page SHALL display product cards
4. FOR ALL product cards, THE Storefront_Page SHALL display product name, description, price formatted to 2 decimal places, stock level as an integer, and image loaded from the image URL
5. THE Storefront_Page SHALL include a shopping cart component displayed as a slide-over panel or fixed sidebar
6. THE Storefront_Page SHALL use JavaScript `fetch` API to send a GET request to `/api/products`
7. WHEN the `/api/products` request completes successfully within 10 seconds, THE Storefront_Page SHALL render the returned products
8. IF the `/api/products` request fails or times out after 10 seconds, THEN THE Storefront_Page SHALL display an error message stating "Unable to load products. Please try again later."
9. WHEN a customer clicks an "Add to Cart" button, THE Storefront_Page SHALL add the selected product to the Shopping_Cart state with a quantity of 1 or increment the quantity by 1 if the product is already in the cart
10. WHEN a product is added to or updated in the Shopping_Cart, THE Storefront_Page SHALL update the cart display to show the product name, quantity, unit price, and line total for all items in the cart
11. THE Storefront_Page SHALL include a text input field or dropdown menu to filter or search products by category or name
12. IF a product's stock level is 0, THEN THE Storefront_Page SHALL display an "Out of Stock" badge and disable the "Add to Cart" button for that product
13. IF a customer attempts to add more than the available stock quantity to the cart, THEN THE Storefront_Page SHALL display a validation message stating "Only [stock quantity] available"

### Requirement 6: Order Checkout and Confirmation

**User Story:** As a customer, I want to complete checkout and see confirmation, so that I know my order was successfully placed.

#### Acceptance Criteria

1. THE Storefront_Page SHALL include a "Checkout" button in the Shopping_Cart component
2. IF the Shopping_Cart is empty, THEN THE Storefront_Page SHALL disable the "Checkout" button
3. WHEN a customer clicks "Checkout", THE Storefront_Page SHALL send a POST request to `/api/orders` with a JSON payload containing all product IDs and quantities from the Shopping_Cart
4. IF the POST request to `/api/orders` completes successfully within 15 seconds, THEN THE Web_Gateway SHALL return an HTTP 200 response with a JSON object containing the order ID and timestamp
5. WHEN an HTTP 200 response is received from `/api/orders`, THE Storefront_Page SHALL display a success message containing the order ID and clear the Shopping_Cart state
6. IF the POST request to `/api/orders` returns an HTTP 400 or 412 error with a message indicating insufficient stock, THEN THE Storefront_Page SHALL display an error message listing the product names that are out of stock
7. IF the POST request to `/api/orders` returns an HTTP 503 error, THEN THE Storefront_Page SHALL display the message "Service temporarily unavailable. Please try again later."
8. IF the POST request to `/api/orders` times out after 15 seconds, THEN THE Storefront_Page SHALL display the message "Request timed out. Please try again."
9. IF an order creation error occurs, THEN THE Storefront_Page SHALL preserve the Shopping_Cart state so the customer can retry
10. WHEN an order is successfully created, THE Storefront_Page SHALL remove all items from the Shopping_Cart

### Requirement 7: Order History Interface

**User Story:** As a customer, I want to view my past orders, so that I can track my purchase history.

#### Acceptance Criteria

1. THE Order_History_Page SHALL be served at the `/orders` route by the Web_Gateway
2. THE Order_History_Page SHALL use Tailwind CSS via CDN (version 3.0 or later) for styling
3. THE Order_History_Page SHALL use JavaScript `fetch` API to send a GET request to `/api/orders`
4. IF the GET request to `/api/orders` completes successfully within 30 seconds, THEN THE Order_History_Page SHALL render the returned orders
5. THE Order_History_Page SHALL display the order ID for each order
6. THE Order_History_Page SHALL display the timestamp in ISO 8601 format for each order
7. THE Order_History_Page SHALL display line items for each order, showing product name, quantity, and unit price for each line item
8. THE Order_History_Page SHALL display the total amount for each order, calculated as the sum of all line item totals (quantity × unit price)
9. IF the response from `/api/orders` contains zero orders, THEN THE Order_History_Page SHALL display the message "No orders yet"
10. IF the GET request to `/api/orders` returns an HTTP 503 error, THEN THE Order_History_Page SHALL display the message "Order service is currently unavailable. Please try again later."
11. IF the GET request to `/api/orders` times out after 30 seconds, THEN THE Order_History_Page SHALL display the message "Request timed out. Please try again."
12. IF the GET request to `/api/orders` returns an HTTP error other than 503, THEN THE Order_History_Page SHALL display the message "An error occurred while loading orders. Please try again."
13. IF the response from `/api/orders` contains invalid JSON or missing required fields, THEN THE Order_History_Page SHALL display the message "Failed to load order data. Please refresh the page."

### Requirement 8: Project Structure and Developer Experience

**User Story:** As a developer, I want a clean, simple project structure, so that I can quickly understand and run the application locally.

#### Acceptance Criteria

1. THE system SHALL include a `requirements.txt` file listing all Python dependencies with pinned or minimum version numbers
2. THE `requirements.txt` SHALL include `grpcio` (version 1.48.0 or later), `grpcio-tools` (version 1.48.0 or later), `fastapi` (version 0.95.0 or later), `uvicorn` (version 0.20.0 or later), `jinja2` (version 3.1.0 or later), and `protobuf` (version 4.21.0 or later)
3. THE system SHALL include a `README.md` file
4. THE `README.md` SHALL include a "Setup" section with commands to install dependencies from `requirements.txt`
5. THE `README.md` SHALL include a "Compile Protocol Buffers" section with the exact command to compile `.proto` files using `grpc_tools.protoc`
6. THE `README.md` SHALL include a "Running the Services" section with separate commands to start Product_Catalog_Service, Order_Service, and Web_Gateway
7. WHEN the commands in the `README.md` are executed in sequence, THE system SHALL start all services without errors
8. THE system SHALL organize code into directories with `protos/` for Protocol Buffer definitions and `gateway/` for Web Gateway code
9. THE system SHALL place Product_Catalog_Service and Order_Service files either at the project root or in a `services/` directory
10. THE system SHALL require no Docker, Kubernetes, or container orchestration tools for local development

### Requirement 9: Error Handling and Service Resilience

**User Story:** As a user, I want clear error messages when services fail, so that I understand what went wrong.

#### Acceptance Criteria

1. IF the Product_Catalog_Service is unreachable or offline, THEN THE Web_Gateway SHALL return an HTTP 503 response for `/api/products` within 10 seconds
2. IF the Order_Service is unreachable or offline, THEN THE Web_Gateway SHALL return an HTTP 503 response for `/api/orders` within 10 seconds
3. WHEN a gRPC call fails with a network error (gRPC UNAVAILABLE or DEADLINE_EXCEEDED), THE Web_Gateway SHALL log an error message containing the service name, method name, and error details
4. WHEN a gRPC call fails with a network error, THE Web_Gateway SHALL return an HTTP response with a JSON body containing a "message" field describing the error
5. IF the Storefront_Page receives an HTTP error response (4xx or 5xx) from any API endpoint, THEN THE Storefront_Page SHALL display the "message" field from the JSON response body, or a generic message if no "message" field is present
6. IF the Order_History_Page receives an HTTP error response (4xx or 5xx) from `/api/orders`, THEN THE Order_History_Page SHALL display the "message" field from the JSON response body, or a generic message if no "message" field is present
7. IF stock validation fails during order creation (gRPC FAILED_PRECONDITION error from Order_Service), THEN THE Web_Gateway SHALL return an HTTP 412 response with a JSON body containing a list of product IDs that are out of stock
8. IF the Web_Gateway receives a gRPC NOT_FOUND error, THEN THE Web_Gateway SHALL return an HTTP 404 response with a JSON error message

### Requirement 10: Data Initialization and Seeding

**User Story:** As a developer, I want pre-populated product data, so that I can test the application immediately without manual data entry.

#### Acceptance Criteria

1. WHEN the Product_Catalog_Service starts, THE Product_Catalog_Service SHALL initialize with sample product data
2. THE sample product data SHALL include exactly 6 or more products
3. THE sample product data SHALL include at least 2 products with stock quantity of 0, at least 2 products with stock quantity between 1 and 50, and at least 2 products with stock quantity greater than 50
4. THE sample product data SHALL include prices ranging from 0.01 to 999999.99
5. THE sample product data SHALL include product name (maximum 200 characters), description (maximum 1000 characters), price (0.01 to 999999.99), stock quantity (0 to 999999), and image URL (maximum 500 characters) for each product
6. IF the Product_Catalog_Service uses in-memory storage, THEN THE Product_Catalog_Service SHALL seed data on every startup
7. IF the Product_Catalog_Service uses SQLite storage AND the database contains zero products, THEN THE Product_Catalog_Service SHALL seed data
8. IF the Product_Catalog_Service uses SQLite storage AND the database contains one or more products, THEN THE Product_Catalog_Service SHALL NOT seed data
9. IF data seeding fails during startup, THEN THE Product_Catalog_Service SHALL log an error message indicating the seeding failure and continue startup without sample data
