"""
Web Gateway - FastAPI HTTP-to-gRPC bridge.

Translates browser HTTP/JSON requests into gRPC calls to the Product Catalog
Service (localhost:50051) and Order Service (localhost:50052), and serves the
Jinja2 HTML pages for the storefront and order history.

Port: 8000
"""

import sys
import json
import logging
from pathlib import Path
from contextlib import asynccontextmanager

import grpc
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

# Ensure the project root is importable so the generated pb2 modules are found
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import product_pb2  # noqa: E402
import product_pb2_grpc  # noqa: E402
import order_pb2  # noqa: E402
import order_pb2_grpc  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [Gateway] [%(levelname)s] [%(funcName)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
)
logger = logging.getLogger(__name__)

PRODUCT_SERVICE_ADDRESS = 'localhost:50051'
ORDER_SERVICE_ADDRESS = 'localhost:50052'

PRODUCT_TIMEOUT = 10
CREATE_ORDER_TIMEOUT = 15
LIST_ORDERS_TIMEOUT = 30

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / 'templates'))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create gRPC channels/stubs on startup and close them on shutdown."""
    logger.info("Connecting to Product Catalog Service at %s", PRODUCT_SERVICE_ADDRESS)
    app.state.product_channel = grpc.insecure_channel(PRODUCT_SERVICE_ADDRESS)
    app.state.product_stub = product_pb2_grpc.ProductCatalogServiceStub(app.state.product_channel)

    logger.info("Connecting to Order Service at %s", ORDER_SERVICE_ADDRESS)
    app.state.order_channel = grpc.insecure_channel(ORDER_SERVICE_ADDRESS)
    app.state.order_stub = order_pb2_grpc.OrderServiceStub(app.state.order_channel)

    try:
        yield
    finally:
        logger.info("Closing gRPC channels")
        app.state.product_channel.close()
        app.state.order_channel.close()


app = FastAPI(title="E-Commerce Web Gateway", lifespan=lifespan)


def product_to_dict(product) -> dict:
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "stock": product.stock,
        "image_url": product.image_url,
    }


def order_to_dict(order) -> dict:
    return {
        "order_id": order.order_id,
        "timestamp": order.timestamp,
        "items": [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "product_name": item.product_name,
                "unit_price": item.unit_price,
            }
            for item in order.items
        ],
        "total": order.total,
    }


def error_response(status_code: int, message: str, **extra) -> JSONResponse:
    content = {"message": message}
    content.update(extra)
    return JSONResponse(status_code=status_code, content=content)


def grpc_error_response(e: grpc.RpcError, service_name: str, method: str) -> JSONResponse:
    """Translate a gRPC error into an HTTP JSON error response."""
    code = e.code() if hasattr(e, "code") else None
    details = e.details() if hasattr(e, "details") else str(e)
    logger.error(
        "gRPC error service=%s method=%s code=%s details=%s",
        service_name, method, code, details,
    )

    if code in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
        return error_response(503, f"{service_name} is unavailable")
    if code == grpc.StatusCode.NOT_FOUND:
        return error_response(404, "Resource not found")
    if code == grpc.StatusCode.INVALID_ARGUMENT:
        return error_response(400, details or "Invalid request")
    if code == grpc.StatusCode.FAILED_PRECONDITION:
        return error_response(412, details or "Precondition failed")
    return error_response(503, f"{service_name} is unavailable")


@app.get("/api/products")
def get_products(request: Request):
    """Return all products from the Product Catalog Service as JSON."""
    logger.info("GET /api/products")
    try:
        response = request.app.state.product_stub.ListProducts(
            product_pb2.Empty(), timeout=PRODUCT_TIMEOUT
        )
        products = [product_to_dict(p) for p in response.products]
        logger.info("GET /api/products returned %d products", len(products))
        return JSONResponse(status_code=200, content=products)
    except grpc.RpcError as e:
        return grpc_error_response(e, "Product Catalog Service", "ListProducts")


@app.post("/api/orders")
async def create_order(request: Request):
    """Create an order from a JSON body: {"items": [{"product_id", "quantity"}]}."""
    logger.info("POST /api/orders")

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        logger.warning("POST /api/orders: invalid JSON body")
        return error_response(400, "Invalid JSON body")

    if not isinstance(body, dict):
        return error_response(400, "Request body must be a JSON object")

    items = body.get("items")
    if not isinstance(items, list) or len(items) == 0:
        return error_response(400, "Field 'items' must be a non-empty array")

    line_items = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            return error_response(400, f"Item at index {index} must be an object")
        product_id = item.get("product_id")
        quantity = item.get("quantity")
        if not isinstance(product_id, str) or not product_id:
            return error_response(400, f"Item at index {index} is missing 'product_id'")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
            return error_response(400, f"Item at index {index} has an invalid 'quantity'")
        line_items.append(order_pb2.LineItem(product_id=product_id, quantity=quantity))

    order_request = order_pb2.OrderRequest(items=line_items)

    try:
        response = request.app.state.order_stub.CreateOrder(
            order_request, timeout=CREATE_ORDER_TIMEOUT
        )
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.FAILED_PRECONDITION:
            details = e.details() or ""
            out_of_stock = []
            marker = "products:"
            if marker in details:
                out_of_stock = [p.strip() for p in details.split(marker, 1)[1].split(",") if p.strip()]
            logger.error(
                "gRPC error service=Order Service method=CreateOrder code=%s details=%s",
                e.code(), details,
            )
            return error_response(412, "Insufficient stock", out_of_stock=out_of_stock)
        return grpc_error_response(e, "Order Service", "CreateOrder")

    logger.info("POST /api/orders created order_id=%s", response.order_id)
    return JSONResponse(
        status_code=200,
        content={
            "order_id": response.order_id,
            "timestamp": response.timestamp,
            "success": response.success,
            "message": response.message,
        },
    )


@app.get("/api/orders")
def get_orders(request: Request):
    """Return all historical orders from the Order Service as JSON."""
    logger.info("GET /api/orders")
    try:
        response = request.app.state.order_stub.ListOrders(
            order_pb2.Empty(), timeout=LIST_ORDERS_TIMEOUT
        )
        orders = [order_to_dict(o) for o in response.orders]
        logger.info("GET /api/orders returned %d orders", len(orders))
        return JSONResponse(status_code=200, content=orders)
    except grpc.RpcError as e:
        return grpc_error_response(e, "Order Service", "ListOrders")


@app.get("/")
def storefront(request: Request):
    """Render the storefront page."""
    return templates.TemplateResponse(request, "index.html")


@app.get("/orders")
def order_history(request: Request):
    """Render the order history page."""
    return templates.TemplateResponse(request, "orders.html")


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000)
