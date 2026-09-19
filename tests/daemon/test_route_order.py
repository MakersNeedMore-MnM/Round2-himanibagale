"""Regression tests for daemon route ordering (backend.daemon.server).

FastAPI matches routes in registration order, so a catch-all
``app.mount("/", StaticFiles(...))`` defined BEFORE an API route shadows
it: requests fall into the mount (404 for a missing file) and the real
endpoint never runs.  The teaching endpoints were defined after the
mount, which silently broke diagram rendering on the dashboard —
the frontend's ``data.teachings || []`` fell back to an empty list.

These tests pin the contract: every API route must respond even when
the dashboard build is mounted.
"""

from __future__ import annotations

import backend.daemon.server as server


def test_teachings_endpoint_not_shadowed_by_static_mount(isolated_store):
    """GET /teachings must reach the API handler, not the static mount."""
    client = server.app.router.test_client() if hasattr(server.app.router, "test_client") else None
    from fastapi.testclient import TestClient

    with TestClient(server.app) as client:
        resp = client.get("/teachings?session=default")
        assert resp.status_code == 200, (
            "GET /teachings returned 404 — the catch-all static mount is "
            "shadowing the teaching endpoints. The mount must be registered "
            "AFTER every API route."
        )
        assert "teachings" in resp.json()


def test_all_api_routes_resolve(isolated_store):
    """Every declared API path must be reachable, not swallowed by the mount."""
    from fastapi.testclient import TestClient

    api_paths = [
        "/health",
        "/concepts?session=default",
        "/teachings?session=default",
        "/assessments?session=default",
        "/assessments/pending?session=default",
        "/assessments/progress?session=default",
        "/progress?session=default",
        "/modes",
    ]
    with TestClient(server.app) as client:
        for path in api_paths:
            resp = client.get(path)
            assert resp.status_code == 200, f"GET {path} -> {resp.status_code}"
