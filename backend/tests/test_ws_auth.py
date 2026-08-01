from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.ws import router
from app.auth.jwt import create_access_token
from app.database import get_db


class _Result:
    def __init__(self, user):
        self.user = user

    def scalar_one_or_none(self):
        return self.user


class _Session:
    def __init__(self, user=None):
        self.user = user
        self.execute_calls = 0

    async def execute(self, statement):
        self.execute_calls += 1
        return _Result(self.user)


def _build_client(user=None):
    app = FastAPI()
    app.include_router(router, prefix="/ws")
    session = _Session(user)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), session


def _ws_url(token=None):
    if token is None:
        return "/ws/monitor"
    return f"/ws/monitor?{urlencode({'token': token})}"


def _assert_rejected(client, url, expected_code):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(url):
            pass
    assert exc_info.value.code == expected_code


def test_websocket_rejects_missing_token_before_database_lookup():
    client, session = _build_client()

    with client:
        _assert_rejected(client, _ws_url(), 4001)

    assert session.execute_calls == 0


def test_websocket_rejects_invalid_token_before_database_lookup():
    client, session = _build_client()

    with client:
        _assert_rejected(client, _ws_url("not-a-jwt"), 4001)

    assert session.execute_calls == 0


def test_websocket_rejects_token_without_subject_before_database_lookup():
    client, session = _build_client()
    token = create_access_token({"role": "viewer"})

    with client:
        _assert_rejected(client, _ws_url(token), 4001)

    assert session.execute_calls == 0


def test_websocket_rejects_unknown_user():
    client, session = _build_client()
    token = create_access_token({"sub": "missing-user"})

    with client:
        _assert_rejected(client, _ws_url(token), 4001)

    assert session.execute_calls == 1


def test_websocket_rejects_inactive_user():
    user = SimpleNamespace(username="disabled", is_active=False)
    client, session = _build_client(user)
    token = create_access_token({"sub": user.username})

    with client:
        _assert_rejected(client, _ws_url(token), 4003)

    assert session.execute_calls == 1


def test_websocket_accepts_active_user_and_keeps_ping_pong():
    user = SimpleNamespace(username="operator", is_active=True)
    client, session = _build_client(user)
    token = create_access_token({"sub": user.username})

    with client:
        with client.websocket_connect(_ws_url(token)) as websocket:
            websocket.send_text("ping")
            assert websocket.receive_text() == "pong"

    assert session.execute_calls == 1
