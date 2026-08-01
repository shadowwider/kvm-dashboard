import json

from simulator.bridge import DashboardBridge


def test_cleanup_uses_scoped_session_endpoint_and_clears_local_ownership(monkeypatch):
    bridge = DashboardBridge()
    bridge.token = "test-token"
    bridge.session_id = "session-a"
    bridge.session_epoch = "epoch-a"
    calls = []

    monkeypatch.setattr(
        bridge,
        "_request",
        lambda method, path, payload: calls.append((method, path, payload)) or {
            "enabled": True,
            "ok": True,
        },
    )

    result = bridge.cleanup()

    assert result["ok"] is True
    assert calls == [
        (
            "DELETE",
            f"/simulator/runs/{bridge.run_id}/sessions/session-a",
            {"session_epoch": "epoch-a"},
        )
    ]
    assert bridge.session_id is None
    assert bridge.session_epoch is None


def test_cleanup_never_calls_dashboard_without_an_owned_session(monkeypatch):
    bridge = DashboardBridge()
    bridge.token = "test-token"
    called = []
    monkeypatch.setattr(bridge, "_request", lambda *args: called.append(args))

    result = bridge.cleanup()

    assert result == {"enabled": True, "ok": True, "detail": "no bridge session to clean"}
    assert called == []


def test_request_treats_empty_204_response_as_success(monkeypatch):
    bridge = DashboardBridge()
    bridge.token = "test-token"

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b""

    monkeypatch.setattr("simulator.bridge.request.urlopen", lambda *_args, **_kwargs: Response())

    assert bridge._request("DELETE", "/simulator/runs/test/sessions/test", {}) == {
        "enabled": True,
        "ok": True,
        "response": {},
    }


def test_heartbeat_uses_the_current_scoped_session(monkeypatch):
    bridge = DashboardBridge()
    bridge.token = "test-token"
    bridge.session_id = "session-a"
    bridge.session_epoch = "epoch-a"
    calls = []
    monkeypatch.setattr(bridge, "_request", lambda *args: calls.append(args) or {"enabled": True, "ok": True})

    assert bridge.heartbeat()["ok"] is True
    assert calls == [("POST", f"/simulator/runs/{bridge.run_id}/sessions/session-a/heartbeat", {"session_epoch": "epoch-a"})]
