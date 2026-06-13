from types import SimpleNamespace

from google.auth.exceptions import GoogleAuthError

from core_utilities.errors import ExternalServiceError, UtilityOperationError
from web_utilities import google_services


def test_get_credentials_wraps_invalid_token_load(monkeypatch, tmp_path):
    token_json = tmp_path / "token.json"
    encrypted_token_json = tmp_path / "token.json.gpg"
    encrypted_token_json.write_bytes(b"encrypted")

    def fail_token_load(info, scopes):
        raise ValueError("invalid token")

    monkeypatch.setattr(
        google_services.Credentials,
        "from_authorized_user_info",
        fail_token_load,
    )
    monkeypatch.setattr(
        google_services, "read_encrypted_file", lambda path: b"{}"
    )

    try:
        google_services.get_credentials(str(token_json))
    except ExternalServiceError as e:
        message = str(e)
    else:
        raise AssertionError("Expected ExternalServiceError")

    assert message == (
        "Unable to load Google credentials from "
        f"{encrypted_token_json}: invalid token"
    )


def test_get_credentials_wraps_refresh_failure(monkeypatch, tmp_path):
    token_json = tmp_path / "token.json"
    encrypted_token_json = tmp_path / "token.json.gpg"
    encrypted_token_json.write_bytes(b"encrypted")

    class ExpiredCredentials:
        valid = False
        expired = True
        refresh_token = "refresh-token"

        def refresh(self, request):
            raise GoogleAuthError("refresh failed")

    monkeypatch.setattr(
        google_services.Credentials,
        "from_authorized_user_info",
        lambda info, scopes: ExpiredCredentials(),
    )
    monkeypatch.setattr(
        google_services, "read_encrypted_file", lambda path: b"{}"
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
        raise UtilityOperationError("disk full")

    monkeypatch.setattr(google_services.os.path, "isfile", lambda path: False)
    monkeypatch.setattr("builtins.input", lambda prompt: "client.json")
    monkeypatch.setattr(
        google_services.InstalledAppFlow,
        "from_client_secrets_file",
        lambda path, scopes: Flow(),
    )
    monkeypatch.setattr(
        google_services, "write_encrypted_file", fail_token_write
    )

    try:
        google_services.get_credentials(str(token_json), fingerprint="abc")
    except ExternalServiceError as e:
        message = str(e)
    else:
        raise AssertionError("Expected ExternalServiceError")

    assert message == (
        f"Unable to write Google credentials to {token_json}.gpg: disk full"
    )
    assert not token_json.exists()


def test_get_credentials_preserves_existing_token_on_write_failure(
    monkeypatch, tmp_path
):
    token_json = tmp_path / "token.json"
    encrypted_token_json = tmp_path / "token.json.gpg"
    encrypted_token_json.write_bytes(b"previous token")

    class ExpiredCredentials:
        valid = False
        expired = True
        refresh_token = "refresh-token"

        def refresh(self, request):
            self.valid = True

        def to_json(self):
            return "new token"

    def fail_token_write(*args, **kwargs):
        raise UtilityOperationError("disk full")

    monkeypatch.setattr(
        google_services.Credentials,
        "from_authorized_user_info",
        lambda info, scopes: ExpiredCredentials(),
    )
    monkeypatch.setattr(
        google_services, "read_encrypted_file", lambda path: b"{}"
    )
    monkeypatch.setattr(
        google_services, "write_encrypted_file", fail_token_write
    )

    try:
        google_services.get_credentials(str(token_json))
    except ExternalServiceError as e:
        message = str(e)
    else:
        raise AssertionError("Expected ExternalServiceError")

    assert message == (
        f"Unable to write Google credentials to {token_json}.gpg: disk full"
    )
    assert encrypted_token_json.read_bytes() == b"previous token"


def test_get_credentials_ignores_plaintext_token(monkeypatch, tmp_path):
    token_json = tmp_path / "token.json"
    token_json.write_text("{}", encoding="utf-8")
    write_calls = []

    class Flow:
        def run_local_server(self, port):
            return SimpleNamespace(valid=True, to_json=lambda: '{"new": true}')

    monkeypatch.setattr("builtins.input", lambda prompt: "client.json")
    monkeypatch.setattr(
        google_services.InstalledAppFlow,
        "from_client_secrets_file",
        lambda path, scopes: Flow(),
    )
    monkeypatch.setattr(
        google_services,
        "write_encrypted_file",
        lambda *args, **kwargs: write_calls.append((args, kwargs)),
    )

    google_services.get_credentials(str(token_json), fingerprint="abc")

    assert write_calls == [
        (
            (f"{token_json}.gpg", b'{"new": true}'),
            {"fingerprint": "abc"},
        )
    ]
    assert token_json.read_text(encoding="utf-8") == "{}"


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
        lambda credentials_path, fingerprint="": "credentials",
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


def test_get_calendar_resource_wraps_build_failure(monkeypatch):
    monkeypatch.setattr(
        google_services,
        "get_credentials",
        lambda credentials_path, fingerprint="": "credentials",
    )
    monkeypatch.setattr(
        google_services,
        "build",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("discovery failed")
        ),
    )

    try:
        google_services.get_calendar_resource(
            "/tmp/token.json", "", "Calendar", "Asia/Tokyo"
        )
    except ExternalServiceError as e:
        message = str(e)
    else:
        raise AssertionError("Expected ExternalServiceError")

    assert message == (
        "Unable to build Google Calendar resource for "
        "/tmp/token.json: discovery failed"
    )


def test_send_email_message_wraps_build_failure(monkeypatch):
    monkeypatch.setattr(
        google_services,
        "get_credentials",
        lambda credentials_path, fingerprint="": "credentials",
    )
    monkeypatch.setattr(
        google_services,
        "build",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("discovery failed")
        ),
    )

    try:
        google_services.send_email_message(
            "/tmp/token.json",
            "Subject",
            "from@example.com",
            "to@example.com",
            "content",
        )
    except ExternalServiceError as e:
        message = str(e)
    else:
        raise AssertionError("Expected ExternalServiceError")

    assert message == (
        "Unable to build Gmail resource for "
        "/tmp/token.json: discovery failed"
    )


def test_insert_calendar_event_ignores_duplicate_event_id(monkeypatch):
    class DuplicateEventError(Exception):
        def __init__(self):
            self.resp = SimpleNamespace(status=409)

    class Request:
        def execute(self):
            raise DuplicateEventError()

    class Events:
        def insert(self, calendarId, body):
            return Request()

    class Resource:
        def events(self):
            return Events()

    monkeypatch.setattr(google_services, "HttpError", DuplicateEventError)

    assert (
        google_services.insert_calendar_event(
            Resource(), "calendar", {"id": "event"}
        )
        is None
    )
