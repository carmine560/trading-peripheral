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
