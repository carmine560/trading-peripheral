import io
import os
import subprocess
import tarfile
from pathlib import Path

from core_utilities import file_utilities
from core_utilities.errors import UtilityOperationError


def _write_source(path: Path, content: str, mtime: int) -> None:
    path.write_text(content, encoding="utf-8")
    path.touch()
    path.chmod(0o644)
    os.utime(path, (mtime, mtime))


def _build_snapshot_data(root_name: str, filename: str, content: str) -> bytes:
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w:xz") as tar:
        root_info = tarfile.TarInfo(root_name)
        root_info.type = tarfile.DIRTYPE
        root_info.mode = 0o755
        tar.addfile(root_info)

        data = content.encode()
        file_info = tarfile.TarInfo(f"{root_name}/{filename}")
        file_info.size = len(data)
        tar.addfile(file_info, io.BytesIO(data))

    return tar_stream.getvalue()


def _patch_gpg_decrypt(monkeypatch, data: bytes) -> None:
    def run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout=data, stderr=b"")

    monkeypatch.setattr(file_utilities.subprocess, "run", run)


def test_backup_file_skips_unchanged_content(tmp_path):
    source = tmp_path / "watchlists.json"
    backup_directory = tmp_path / "backups"

    _write_source(source, "alpha", 1_700_000_000)
    file_utilities.backup_file(source.as_posix(), backup_directory.as_posix())

    _write_source(source, "alpha", 1_700_000_100)
    file_utilities.backup_file(source.as_posix(), backup_directory.as_posix())

    backups = sorted(backup_directory.iterdir())
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "alpha"


def test_backup_file_prunes_old_backups(tmp_path):
    source = tmp_path / "orders.csv"
    backup_directory = tmp_path / "backups"

    for index, content in enumerate(("alpha", "beta", "gamma")):
        _write_source(source, content, 1_700_000_000 + index)
        file_utilities.backup_file(
            source.as_posix(),
            backup_directory.as_posix(),
            number_of_backups=2,
        )

    backups = sorted(backup_directory.iterdir())
    assert len(backups) == 2
    assert [path.read_text(encoding="utf-8") for path in backups] == [
        "beta",
        "gamma",
    ]


def test_select_venv_finds_python_interpreter(tmp_path):
    activate = tmp_path / ".venv" / "bin" / "activate"
    activate.parent.mkdir(parents=True)
    activate.write_text("", encoding="utf-8")

    result = file_utilities.select_venv(tmp_path.as_posix())

    assert Path(result[0]) == activate
    assert result[1] == "python"


def test_archive_encrypt_directory_raises_on_gpg_failure(
    tmp_path, monkeypatch
):
    source = tmp_path / "settings"
    output_directory = tmp_path / "backups"
    source.mkdir()
    output_directory.mkdir()

    def run(args, **kwargs):
        return subprocess.CompletedProcess(
            args, 2, stdout=b"", stderr=b"no public key"
        )

    monkeypatch.setattr(file_utilities.subprocess, "run", run)

    try:
        file_utilities.archive_encrypt_directory(
            source.as_posix(), output_directory.as_posix()
        )
    except UtilityOperationError as e:
        message = str(e)
    else:
        raise AssertionError("Expected UtilityOperationError")

    assert message == "GPG encryption failed: no public key"


def test_decrypt_extract_file_raises_on_empty_gpg_data(tmp_path, monkeypatch):
    source = tmp_path / "snapshot.tar.xz.gpg"
    output_directory = tmp_path / "restore"
    source.write_bytes(b"encrypted")
    output_directory.mkdir()

    def run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(file_utilities.subprocess, "run", run)

    try:
        file_utilities.decrypt_extract_file(
            source.as_posix(), output_directory.as_posix()
        )
    except UtilityOperationError as e:
        message = str(e)
    else:
        raise AssertionError("Expected UtilityOperationError")

    assert message == "GPG decryption returned no file data."


def test_decrypt_extract_file_replaces_directory_atomically(
    tmp_path, monkeypatch
):
    source = tmp_path / "snapshot.tar.xz.gpg"
    output_directory = tmp_path / "restore"
    root = output_directory / "settings"
    source.write_bytes(b"encrypted")
    root.mkdir(parents=True)
    (root / "portfolio.json").write_text("old", encoding="utf-8")
    _patch_gpg_decrypt(
        monkeypatch,
        _build_snapshot_data("settings", "portfolio.json", "new"),
    )

    file_utilities.decrypt_extract_file(
        source.as_posix(), output_directory.as_posix()
    )

    assert (root / "portfolio.json").read_text(encoding="utf-8") == "new"
    assert not (output_directory / "settings.bak").exists()
    assert not (output_directory / "settings.tmp").exists()


def test_decrypt_extract_file_rejects_existing_backup_path(
    tmp_path, monkeypatch
):
    source = tmp_path / "snapshot.tar.xz.gpg"
    output_directory = tmp_path / "restore"
    root = output_directory / "settings"
    backup = output_directory / "settings.bak"
    source.write_bytes(b"encrypted")
    root.mkdir(parents=True)
    backup.mkdir()
    (root / "portfolio.json").write_text("old", encoding="utf-8")
    (backup / "portfolio.json").write_text("backup", encoding="utf-8")
    _patch_gpg_decrypt(
        monkeypatch,
        _build_snapshot_data("settings", "portfolio.json", "new"),
    )

    try:
        file_utilities.decrypt_extract_file(
            source.as_posix(), output_directory.as_posix()
        )
    except FileExistsError as e:
        message = str(e)
    else:
        raise AssertionError("Expected FileExistsError")

    assert message.startswith("The ")
    assert message.endswith("settings.bak path exists.")
    assert (root / "portfolio.json").read_text(encoding="utf-8") == "old"
    assert (backup / "portfolio.json").read_text(encoding="utf-8") == "backup"


def test_decrypt_extract_file_keeps_root_after_temp_extract_failure(
    tmp_path, monkeypatch
):
    source = tmp_path / "snapshot.tar.xz.gpg"
    output_directory = tmp_path / "restore"
    root = output_directory / "settings"
    source.write_bytes(b"encrypted")
    root.mkdir(parents=True)
    (root / "portfolio.json").write_text("old", encoding="utf-8")
    _patch_gpg_decrypt(
        monkeypatch,
        _build_snapshot_data("settings", "portfolio.json", "new"),
    )
    extract = file_utilities.tarfile.TarFile.extract

    def fail_file_extract(
        tar,
        member,
        path="",
        set_attrs=True,
        *,
        numeric_owner=False,
    ):
        if member.name.endswith("portfolio.json"):
            raise OSError("extract failed")
        return extract(
            tar,
            member,
            path=path,
            set_attrs=set_attrs,
            numeric_owner=numeric_owner,
        )

    monkeypatch.setattr(
        file_utilities.tarfile.TarFile,
        "extract",
        fail_file_extract,
    )

    try:
        file_utilities.decrypt_extract_file(
            source.as_posix(), output_directory.as_posix()
        )
    except OSError as e:
        message = str(e)
    else:
        raise AssertionError("Expected OSError")

    assert message == "extract failed"
    assert (root / "portfolio.json").read_text(encoding="utf-8") == "old"
    assert not (output_directory / "settings.bak").exists()
    assert not (output_directory / "settings.tmp").exists()


def test_decrypt_extract_file_restores_backup_after_final_move_failure(
    tmp_path, monkeypatch
):
    source = tmp_path / "snapshot.tar.xz.gpg"
    output_directory = tmp_path / "restore"
    root = output_directory / "settings"
    temporary_root = output_directory / "settings.tmp" / "settings"
    source.write_bytes(b"encrypted")
    root.mkdir(parents=True)
    (root / "portfolio.json").write_text("old", encoding="utf-8")
    _patch_gpg_decrypt(
        monkeypatch,
        _build_snapshot_data("settings", "portfolio.json", "new"),
    )
    rename = file_utilities.os.rename

    def fail_final_move(source_path, destination_path):
        is_final_move = (
            Path(source_path) == temporary_root
            and Path(destination_path) == root
        )
        if is_final_move:
            raise OSError("final move failed")
        rename(source_path, destination_path)

    monkeypatch.setattr(file_utilities.os, "rename", fail_final_move)

    try:
        file_utilities.decrypt_extract_file(
            source.as_posix(), output_directory.as_posix()
        )
    except OSError as e:
        message = str(e)
    else:
        raise AssertionError("Expected OSError")

    assert message == "final move failed"
    assert (root / "portfolio.json").read_text(encoding="utf-8") == "old"
    assert not (output_directory / "settings.bak").exists()
    assert not (output_directory / "settings.tmp").exists()
