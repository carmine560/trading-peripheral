from types import SimpleNamespace

from google.auth.exceptions import GoogleAuthError

from core_utilities.errors import ExternalServiceError
from web_utilities import google_services


def test_get_credentials_wraps_invalid_token_load(monkeypatch, tmp_path):
    token_json = tmp_path / "token.json"
    token_json.write_text("bad json", encoding="utf-8")

    def fail_token_load(path, scopes):
        raise ValueError("invalid token")

    monkeypatch.setattr(
        google_services.Credentials,
        "from_authorized_user_file",
        fail_token_load,
    )

    try:
        google_services.get_credentials(str(token_json))
    except ExternalServiceError as e:
        message = str(e)
    else:
        raise AssertionError("Expected ExternalServiceError")

    assert message == (
        f"Unable to load Google credentials from {token_json}: invalid token"
    )


def test_get_credentials_wraps_refresh_failure(monkeypatch, tmp_path):
    token_json = tmp_path / "token.json"
    token_json.write_text("{}", encoding="utf-8")

    class ExpiredCredentials:
        valid = False
        expired = True
        refresh_token = "refresh-token"

        def refresh(self, request):
            raise GoogleAuthError("refresh failed")

    monkeypatch.setattr(
        google_services.Credentials,
        "from_authorized_user_file",
        lambda path, scopes: ExpiredCredentials(),
    )

    try:
        google_services.get_credentials(str(token_json))
    except ExternalServiceError as e:
        message = str(e)
    else:
        raise AssertionError("Expected ExternalServiceError")

    assert message == (
        "Unable to refresh Google credentials for "
        f"{token_json}: refresh failed"
    )


def test_get_credentials_wraps_token_write_failure(monkeypatch, tmp_path):
    token_json = tmp_path / "token.json"

    class Flow:
        def run_local_server(self, port):
            return SimpleNamespace(valid=True, to_json=lambda: "{}")

    def fail_token_write(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(google_services.os.path, "isfile", lambda path: False)
    monkeypatch.setattr("builtins.input", lambda prompt: "client.json")
    monkeypatch.setattr(
        google_services.InstalledAppFlow,
        "from_client_secrets_file",
        lambda path, scopes: Flow(),
    )
    monkeypatch.setattr("builtins.open", fail_token_write)

    try:
        google_services.get_credentials(str(token_json))
    except ExternalServiceError as e:
        message = str(e)
    else:
        raise AssertionError("Expected ExternalServiceError")

    assert message == (
        f"Unable to write Google credentials to {token_json}: disk full"
    )


def test_send_email_message_returns_false_without_required_fields(
    monkeypatch,
):
    def fail_build(*args, **kwargs):
        raise AssertionError("Gmail resource should not be built")

    monkeypatch.setattr(google_services, "build", fail_build)

    assert (
        google_services.send_email_message(
            "/tmp/token.json",
            "Subject",
            "",
            "to@example.com",
            "content",
        )
        is False
    )


def test_send_email_message_returns_true_after_send(monkeypatch):
    build_calls = []
    send_calls = []

    class Request:
        def execute(self):
            return {"id": "message-id"}

    class Messages:
        def send(self, userId, body):
            send_calls.append((userId, body))
            return Request()

    class Users:
        def messages(self):
            return Messages()

    class Resource:
        def users(self):
            return Users()

    monkeypatch.setattr(
        google_services,
        "get_credentials",
        lambda credentials_path: "credentials",
    )
    monkeypatch.setattr(
        google_services,
        "build",
        lambda *args, **kwargs: build_calls.append((args, kwargs))
        or Resource(),
    )

    sent = google_services.send_email_message(
        "/tmp/token.json",
        "Subject",
        "from@example.com",
        "to@example.com",
        "content",
    )

    assert sent is True
    assert build_calls == [(("gmail", "v1"), {"credentials": "credentials"})]
    assert send_calls[0][0] == "me"
    assert "raw" in send_calls[0][1]
