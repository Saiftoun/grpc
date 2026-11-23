# E-Commerce Microservices

A microservices-based e-commerce application built with Python gRPC backend services, FastAPI HTTP gateway, and modern HTML/Tailwind CSS frontend.

## Overview

This system consists of:
- **Product Catalog Service**: gRPC microservice managing product data and inventory (port 50051)
- **Order Service**: gRPC microservice handling order creation and history (port 50052)
- **Web Gateway**: FastAPI HTTP server bridging browser requests to gRPC services (port 8000)
- **Frontend**: Responsive web interface using HTML, Tailwind CSS, and vanilla JavaScript

## Prerequisites

- Python 3.9 or later
- pip (Python package manager)

## Setup

### 1. Install Dependencies

Install all required Python packages:

```bash
pip install -r requirements.txt
```

This installs:
- `grpcio>=1.48.0` - gRPC framework
- `grpcio-tools>=1.48.0` - Protocol Buffer compiler
- `fastapi>=0.95.0` - Web framework for HTTP gateway
- `uvicorn>=0.20.0` - ASGI server
- `jinja2>=3.1.0` - Template engine
- `protobuf>=4.21.0` - Protocol Buffer runtime
- `httpx>=0.24.0` - HTTP client used by the gateway tests

### 2. Compile Protocol Buffers

Compile the `.proto` files to generate Python code:

**Option A: Using the compilation script (recommended)**

```bash
python compile_protos.py
```

**Option B: Using grpc_tools.protoc directly**

```bash
python -m grpc_tools.protoc -I./protos --python_out=. --grpc_python_out=. protos/product.proto protos/order.proto
```

This generates:
- `product_pb2.py` - Product message classes
- `product_pb2_grpc.py` - Product service stub and servicer
- `order_pb2.py` - Order message classes
- `order_pb2_grpc.py` - Order service stub and servicer

## Running the Services

The application requires three services to run simultaneously. Open three separate terminal windows:

### Terminal 1: Product Catalog Service

```bash
python product_catalog_service.py
```

Expected output:
```
Product Catalog Service listening on port 50051...
Seeded 6 products
```

### Terminal 2: Order Service

```bash
python order_service.py
```

Expected output:
```
Order Service listening on port 50052...
Connected to Product Catalog Service at localhost:50051
```

### Terminal 3: Web Gateway

```bash
python gateway/main.py
```

Expected output:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Accessing the Application

Once all three services are running:

- **Storefront**: http://localhost:8000
  - Browse products, add items to cart, place orders
  
- **Order History**: http://localhost:8000/orders
  - View all previously placed orders

## Project Structure

```
ecommerce-microservices/
├── protos/                          # Protocol Buffer definitions
│   ├── product.proto                # Product Catalog Service contract
│   └── order.proto                  # Order Service contract
├── gateway/                         # Web Gateway (FastAPI)
│   ├── main.py                      # FastAPI application
│   └── templates/                   # Jinja2 HTML templates
│       ├── index.html               # Storefront page
│       └── orders.html              # Order history page
├── product_catalog_service.py       # Product Catalog gRPC service
├── order_service.py                 # Order gRPC service
├── product_pb2.py                   # Generated: Product messages
├── product_pb2_grpc.py              # Generated: Product service
├── order_pb2.py                     # Generated: Order messages
├── order_pb2_grpc.py                # Generated: Order service
├── compile_protos.py                # Protocol Buffer compilation script
├── requirements.txt                 # Python dependencies
└── README.md                        # This file
```

## Storage Options

By default, services use **in-memory storage** (data is lost on restart). To enable persistence:

- **Product Catalog**: Data stored in `product_catalog.db` (SQLite)
- **Order Service**: Data stored in `orders.db` (SQLite)

Storage mode can be configured in the service files.

## Development Notes

- **No Docker Required**: All services run directly with Python for local development
- **Port Configuration**: Service ports are hardcoded (50051, 50052, 8000)
- **Sample Data**: Product Catalog Service automatically seeds 6+ sample products on first startup
- **Error Handling**: Frontend displays user-friendly error messages for service unavailability and stock issues

## Testing

Run the backend and gateway unit tests:

```bash
pytest
```

The suite covers the Product Catalog Service, Order Service, and the FastAPI
gateway endpoints (gRPC stubs are mocked, so no services need to be running).

## Troubleshooting

**Services won't start**:
- Ensure ports 50051, 50052, and 8000 are not in use
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Verify Protocol Buffers are compiled: `python compile_protos.py`

**"Module not found" errors**:
- Re-run: `pip install -r requirements.txt`
- Ensure you're in the project root directory

**Frontend can't connect to services**:
- Verify all three services are running
- Check terminal outputs for error messages
- Ensure no firewall is blocking localhost connections

## Architecture

```
┌─────────────┐
│ Web Browser │
└──────┬──────┘
       │ HTTP/JSON
       ↓
┌─────────────────┐
│  Web Gateway    │ :8000
│    (FastAPI)    │
└────┬───────┬────┘
     │       │ gRPC
     │       │
     ↓       ↓
┌─────────┐ ┌──────────┐
│ Product │ │  Order   │
│ Catalog │←│  Service │
│ Service │ │          │
└─────────┘ └──────────┘
   :50051      :50052
```

## License

This project is provided as-is for educational and development purposes.
