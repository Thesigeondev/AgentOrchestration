from fastapi.testclient import TestClient

from src.api import routes
from src.api.server import create_app
from src.api.trace_query import TraceQueryService


def authorized_client():
    return TestClient(create_app()), {"Authorization": "Bearer test-token"}


def nested_filter(depth):
    value = {"field": "trace_id", "eq": "trace-1"}
    for _ in range(depth):
        value = {"and": [value]}
    return value


def test_authorized_valid_trace_query_succeeds():
    def lookup(**kwargs):
        return [{"trace_id": "trace-1", "tenant_id": kwargs["tenant_id"]}]

    original_service = routes.trace_query_service
    service = TraceQueryService(lookup=lookup)
    routes.trace_query_service = service
    client, headers = authorized_client()

    try:
        response = client.post(
            "/api/v2/traces/query",
            headers=headers,
            json={
                "tenant_id": "tenant-a",
                "filters": {"field": "status", "eq": "ok"},
            },
        )
    finally:
        routes.trace_query_service = original_service

    assert response.status_code == 200
    assert response.json() == {
        "traces": [{"trace_id": "trace-1", "tenant_id": "tenant-a"}],
        "count": 1,
    }
    assert service.success_count == 1


def test_trace_query_requires_authorization():
    client = TestClient(create_app())

    response = client.post(
        "/api/v2/traces/query",
        json={"tenant_id": "tenant-a", "filters": {}},
    )

    assert response.status_code == 401


def test_nested_trace_filter_depth_returns_deterministic_4xx():
    client, headers = authorized_client()

    response = client.post(
        "/api/v2/traces/query",
        headers=headers,
        json={"tenant_id": "tenant-a", "filters": nested_filter(10)},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Trace filter depth exceeds maximum of 8"
    }


def test_trace_query_rejects_non_object_filters():
    client, headers = authorized_client()

    response = client.post(
        "/api/v2/traces/query",
        headers=headers,
        json={"tenant_id": "tenant-a", "filters": ["status", "ok"]},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "filters must be an object"}


def test_trace_query_requires_tenant_id():
    client, headers = authorized_client()

    response = client.post(
        "/api/v2/traces/query",
        headers=headers,
        json={"filters": {"field": "status", "eq": "ok"}},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "tenant_id is required"}


def test_nested_trace_filter_depth_fails_before_lookup_or_success():
    calls = []
    original_service = routes.trace_query_service
    service = TraceQueryService(
        lookup=lambda **kwargs: calls.append(kwargs),
        max_filter_depth=2,
    )
    routes.trace_query_service = service

    try:
        client, headers = authorized_client()
        response = client.post(
            "/api/v2/traces/query",
            headers=headers,
            json={"tenant_id": "tenant-a", "filters": nested_filter(3)},
        )
    finally:
        routes.trace_query_service = original_service

    assert response.status_code == 400
    assert calls == []
    assert service.success_count == 0
