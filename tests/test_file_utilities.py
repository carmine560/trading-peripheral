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
