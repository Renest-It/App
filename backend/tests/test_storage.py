"""app.storage's calls to Supabase Storage, with httpx replaced (tests never make network calls)."""

import httpx
import pytest

from app import storage

STORAGE = "https://test-project.supabase.co/storage/v1"
PATH = "listings/6f1c0000-0000-0000-0000-000000000000/0b9e0000-0000-0000-0000-000000000000.jpg"


def fake_response(method: str, status: int, json=None) -> httpx.Response:
    return httpx.Response(status, json=json, request=httpx.Request(method, STORAGE))


@pytest.fixture
def calls(monkeypatch):
    """Records each request and answers with whatever the test put in `calls.responses`."""

    class Calls(list):
        pass

    recorded = Calls()
    recorded.responses = {}

    def fake(method):
        def _send(url, *, headers, timeout):
            recorded.append((method, url, headers))
            answer = recorded.responses[method]
            if isinstance(answer, Exception):
                raise answer
            return answer

        return _send

    monkeypatch.setattr(httpx, "post", fake("POST"))
    monkeypatch.setattr(httpx, "head", fake("HEAD"))
    return recorded


def test_signed_upload_url_is_made_absolute(calls):
    calls.responses["POST"] = fake_response(
        "POST", 200, {"url": f"/object/upload/sign/listing-photos/{PATH}?token=abc"}
    )
    assert storage.create_signed_upload_url(PATH) == (
        f"{STORAGE}/object/upload/sign/listing-photos/{PATH}?token=abc"
    )
    [(method, url, headers)] = calls
    assert url == f"{STORAGE}/object/upload/sign/listing-photos/{PATH}"
    assert headers["Authorization"] == "Bearer test-service-role-key"


@pytest.mark.parametrize(
    "answer",
    [
        fake_response("POST", 500),
        fake_response("POST", 200, {"unexpected": "shape"}),
        httpx.ConnectError("offline"),
    ],
)
def test_signed_upload_url_failures_are_storage_unavailable(calls, answer):
    calls.responses["POST"] = answer
    with pytest.raises(storage.StorageUnavailable):
        storage.create_signed_upload_url(PATH)


@pytest.mark.parametrize("status, exists", [(200, True), (400, False), (404, False)])
def test_object_exists(calls, status, exists):
    calls.responses["HEAD"] = fake_response("HEAD", status)
    assert storage.object_exists(PATH) is exists
    [(method, url, headers)] = calls
    assert url == f"{STORAGE}/object/authenticated/listing-photos/{PATH}"
    assert headers["Authorization"] == "Bearer test-service-role-key"


@pytest.mark.parametrize("answer", [fake_response("HEAD", 500), httpx.ConnectError("offline")])
def test_object_exists_failures_are_storage_unavailable(calls, answer):
    calls.responses["HEAD"] = answer
    with pytest.raises(storage.StorageUnavailable):
        storage.object_exists(PATH)


def test_missing_service_role_key_is_storage_unavailable(calls, monkeypatch):
    monkeypatch.setattr(storage.settings, "supabase_service_role_key", "")
    with pytest.raises(storage.StorageUnavailable):
        storage.create_signed_upload_url(PATH)
    with pytest.raises(storage.StorageUnavailable):
        storage.object_exists(PATH)
    assert calls == []
