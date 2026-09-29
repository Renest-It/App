"""The API is login-only: every route requires a token except the /health liveness check."""

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app

# The ONLY routes allowed without a token. Adding to this list is a deliberate decision.
PUBLIC_PATHS = {"/health"}


def _requires_login(dependant) -> bool:
    """True if get_current_user appears anywhere in the route's dependency tree."""
    return any(
        dep.call is get_current_user or _requires_login(dep) for dep in dependant.dependencies
    )


def test_every_route_except_health_requires_login():
    # Walks the real app, so a new route added without protection fails here (and in CI).
    unprotected = [
        f"{sorted(route.methods)} {route.path}"
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path not in PUBLIC_PATHS
        and not _requires_login(route.dependant)
    ]
    assert unprotected == []


def test_public_paths_really_are_public():
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path in PUBLIC_PATHS:
            assert not _requires_login(route.dependant), route.path


def test_health_is_public():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.requires_db
@pytest.mark.parametrize("path", ["/listings", "/categories", "/health/db"])
def test_data_routes_reject_anonymous_requests(path):
    r = TestClient(app).get(path)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
    assert r.json()["code"] == "invalid_token"


@pytest.mark.requires_db
def test_data_routes_work_with_a_token(make_token):
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {make_token()}"}

    listings = client.get("/listings", headers=headers)
    assert listings.status_code == 200 and isinstance(listings.json(), list)

    categories = client.get("/categories", headers=headers)
    assert categories.status_code == 200
    assert len(categories.json()) > 0  # seeded by the categories migration

    health_db = client.get("/health/db", headers=headers)
    assert health_db.status_code == 200 and health_db.json() == {"status": "ok"}
