"""Unit tests for the FastAPI Web Gateway.

These tests mock the gRPC stubs stored on ``app.state`` so no backend
services are required.
"""

from unittest.mock import MagicMock

import grpc
import pytest
from fastapi.testclient import TestClient

from gateway.main import app
import order_pb2
import product_pb2


class FakeRpcError(grpc.RpcError):
    def __init__(self, code, details=""):
        self._code = code
        self._details = details

    def code(self):
        return self._code

    def details(self):
        return self._details


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_get_products_success(client):
    product_list = product_pb2.ProductList()
    p = product_list.products.add()
    p.id = "p1"
    p.name = "Widget"
    p.description = "A widget"
    p.price = 9.99
    p.stock = 5
    p.image_url = "http://img"

    app.state.product_stub = MagicMock()
    app.state.product_stub.ListProducts.return_value = product_list

    response = client.get("/api/products")

    assert response.status_code == 200
    assert response.json() == [{
        "id": "p1",
        "name": "Widget",
        "description": "A widget",
        "price": 9.99,
        "stock": 5,
        "image_url": "http://img",
    }]


def test_get_products_unavailable(client):
    app.state.product_stub = MagicMock()
    app.state.product_stub.ListProducts.side_effect = FakeRpcError(
        grpc.StatusCode.UNAVAILABLE, "connection refused"
    )

    response = client.get("/api/products")

    assert response.status_code == 503
    assert "message" in response.json()


def test_create_order_success(client):
    app.state.order_stub = MagicMock()
    app.state.order_stub.CreateOrder.return_value = order_pb2.OrderResponse(
        order_id="order-1",
        timestamp="2024-01-01T00:00:00Z",
        success=True,
        message="Order created successfully",
    )

    response = client.post("/api/orders", json={"items": [{"product_id": "p1", "quantity": 2}]})

    assert response.status_code == 200
    body = response.json()
    assert body["order_id"] == "order-1"
    assert body["timestamp"] == "2024-01-01T00:00:00Z"

    sent_request = app.state.order_stub.CreateOrder.call_args[0][0]
    assert sent_request.items[0].product_id == "p1"
    assert sent_request.items[0].quantity == 2


def test_create_order_invalid_json(client):
    response = client.post(
        "/api/orders",
        content="{not valid json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert "message" in response.json()


def test_create_order_missing_fields(client):
    response = client.post("/api/orders", json={"items": []})

    assert response.status_code == 400


def test_create_order_failed_precondition(client):
    app.state.order_stub = MagicMock()
    app.state.order_stub.CreateOrder.side_effect = FakeRpcError(
        grpc.StatusCode.FAILED_PRECONDITION,
        "Insufficient stock for products: p1, p2",
    )

    response = client.post(
        "/api/orders",
        json={"items": [{"product_id": "p1", "quantity": 999}]},
    )

    assert response.status_code == 412
    body = response.json()
    assert body["out_of_stock"] == ["p1", "p2"]


def test_get_orders_success(client):
    order_list = order_pb2.OrderList()
    order = order_list.orders.add()
    order.order_id = "order-1"
    order.timestamp = "2024-01-01T00:00:00Z"
    order.total = 19.98
    item = order.items.add()
    item.product_id = "p1"
    item.quantity = 2
    item.product_name = "Widget"
    item.unit_price = 9.99

    app.state.order_stub = MagicMock()
    app.state.order_stub.ListOrders.return_value = order_list

    response = client.get("/api/orders")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["order_id"] == "order-1"
    assert body[0]["total"] == 19.98
    assert body[0]["items"][0]["product_name"] == "Widget"


def test_get_orders_not_found(client):
    app.state.order_stub = MagicMock()
    app.state.order_stub.ListOrders.side_effect = FakeRpcError(
        grpc.StatusCode.NOT_FOUND, "not found"
    )

    response = client.get("/api/orders")

    assert response.status_code == 404
