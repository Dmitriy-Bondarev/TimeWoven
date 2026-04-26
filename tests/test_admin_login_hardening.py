import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "password!123456")
    monkeypatch.setenv("ADMIN_LOGIN_RATE_LIMIT", "10")
    monkeypatch.setenv("ADMIN_LOGIN_RATE_WINDOW_SECONDS", "900")
    monkeypatch.setenv("ADMIN_SESSION_IDLE_TIMEOUT_MINUTES", "120")

    from app.main import app
    from app import security as security_mod

    security_mod._clear_admin_login_rate_limiter_for_tests()
    return TestClient(app)


def test_admin_login_success_sets_cookie(client: TestClient):
    resp = client.post(
        "/admin/login",
        data={"username": "admin", "password": "password!123456", "next": "/admin/people"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers.get("location") == "/admin/people"
    set_cookie = resp.headers.get("set-cookie", "")
    assert "tw_admin_session=" in set_cookie


def test_admin_login_rate_limit_blocks_after_n_attempts(client: TestClient):
    for _ in range(10):
        r = client.post(
            "/admin/login",
            data={"username": "admin", "password": "wrong", "next": "/admin"},
            follow_redirects=False,
        )
        assert r.status_code == 200

    r = client.post(
        "/admin/login",
        data={"username": "admin", "password": "password!123456", "next": "/admin"},
        follow_redirects=False,
    )
    assert r.status_code == 429
    assert "Too many login attempts" in r.text


def test_admin_idle_timeout_redirects_and_clears_cookie(client: TestClient, monkeypatch):
    monkeypatch.setenv("ADMIN_SESSION_IDLE_TIMEOUT_MINUTES", "1")

    from app.security import make_admin_token

    issued_at = int(time.time()) - 120
    cookie_value = make_admin_token(issued_at=issued_at)
    client.cookies.set("tw_admin_session", cookie_value, path="/")

    r = client.get("/admin/people", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers.get("location", "").startswith("/admin/login")
    set_cookie = r.headers.get("set-cookie", "")
    assert "tw_admin_session=" in set_cookie
