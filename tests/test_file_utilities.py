from pathlib import Path

from core_utilities import file_utilities


def _write_source(path: Path, content: str, mtime: int) -> None:
    path.write_text(content, encoding="utf-8")
    path.touch()
    path.chmod(0o644)
    import os

    os.utime(path, (mtime, mtime))


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


def test_get_latest_file_returns_newest_match(tmp_path, monkeypatch):
    first = tmp_path / "report-1.txt"
    second = tmp_path / "report-2.txt"
    ignored = tmp_path / "notes.md"

    _write_source(first, "alpha", 1_700_000_000)
    _write_source(second, "beta", 1_700_000_100)
    _write_source(ignored, "gamma", 1_700_000_200)
    timestamps = {
        first.as_posix(): 1.0,
        second.as_posix(): 2.0,
    }

    monkeypatch.setattr(
        file_utilities.os.path,
        "getctime",
        lambda path: timestamps[Path(path).as_posix()],
    )

    latest = file_utilities.get_latest_file(
        tmp_path.as_posix(), r"report-\d+\.txt"
    )

    assert Path(latest) == second


def test_select_venv_finds_python_interpreter(tmp_path):
    activate = tmp_path / ".venv" / "bin" / "activate"
    activate.parent.mkdir(parents=True)
    activate.write_text("", encoding="utf-8")

    result = file_utilities.select_venv(tmp_path.as_posix())

    assert Path(result[0]) == activate
    assert result[1] == "python"
