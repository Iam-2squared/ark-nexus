"""Conservative paths and owner-only POSIX database files."""

import os
import re
import stat
from pathlib import Path


class PrivateStorageError(ValueError):
    """A fixed, path-free boundary failure suitable for generic API handling."""


def configure_memory_temp(connection) -> None:
    """SQLite TEMP_STORE=0 ignores temp_store. Refuse that build, never disk-fallback.

    Journals/WAL/SHM remain adjacent to the private database; this setting is for
    TEMP tables, transient indices and sort materialization, not encryption.
    """
    options = {row[0] for row in connection.execute("PRAGMA compile_options")}
    builds = {option for option in options if option.startswith("TEMP_STORE=")}
    if len(builds) != 1 or not builds <= {"TEMP_STORE=1", "TEMP_STORE=2", "TEMP_STORE=3"}:
        raise PrivateStorageError("SQLite memory temporary storage is unavailable")
    connection.execute("PRAGMA temp_store=MEMORY")
    if connection.execute("PRAGMA temp_store").fetchone()[0] != 2:
        raise PrivateStorageError("SQLite memory temporary storage is unavailable")


def checked_path(value: Path) -> Path:
    path = value.expanduser().absolute()
    # One portable policy: Windows must not reinterpret a path as ADS/device/alias.
    names = (candidate.name for candidate in (path, *path.parents) if candidate.name)
    if any(re.search(r'[<>:"|?*\\\x00-\x1f]', name) or name.endswith((".", " "))
           or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³])(?:\..*)?", name)
           for name in names):
        raise PrivateStorageError("Private database paths must use portable file names")
    if path.drive.startswith("\\\\"):
        raise PrivateStorageError("Private database paths must use a local volume")
    if any(candidate.is_symlink() for candidate in (path, *path.parents)):
        raise PrivateStorageError("Private database paths must not contain a symlink")
    if any(candidate.is_junction() for candidate in (path, *path.parents)):
        raise PrivateStorageError("Private database paths must not contain a junction")
    if os.name == "nt" and any(
        candidate.exists() and candidate.stat(follow_symlinks=False).st_file_attributes
        & stat.FILE_ATTRIBUTE_REPARSE_POINT for candidate in (path, *path.parents)
    ):
        raise PrivateStorageError("Private database paths must not contain a reparse point")
    if path.exists() and path.is_file() and path.stat().st_nlink > 1:
        raise PrivateStorageError("Private database paths must not use hard links")
    return path


def checked_database_path(value: Path) -> Path:
    """SQLite can read/write these siblings even when its main file is safe."""
    path = checked_path(value)
    if path.parent.exists():
        if not path.parent.is_dir():
            raise PrivateStorageError("Private database parent must be a directory")
        if os.name != "nt":
            metadata = path.parent.stat()
            if metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
                raise PrivateStorageError("Private database directory must be owner-only")
    for candidate in (path, *(Path(str(path) + suffix)
                              for suffix in ("-journal", "-wal", "-shm"))):
        checked_path(candidate)
        if candidate.exists():
            if not candidate.is_file():
                raise PrivateStorageError("Private database files must be regular files")
            if os.name != "nt":
                metadata = candidate.stat()
                if metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
                    raise PrivateStorageError("Private database files must be owner-only")
    return path


def database_identity(value: Path) -> tuple[int, int, int, int]:
    """Bind an operation to one regular main file and its reviewed directory.

    This detects cooperative replacement between checkpoints, not an atomic
    defence against a privileged or same-user filesystem race. Sidecars remain
    checked separately because SQLite legitimately creates/removes them.
    """
    path = checked_database_path(value)
    try:
        file = path.stat(follow_symlinks=False)
        directory = path.parent.stat(follow_symlinks=False)
    except OSError:
        raise PrivateStorageError("Private database identity is unavailable") from None
    if not stat.S_ISREG(file.st_mode) or not stat.S_ISDIR(directory.st_mode):
        raise PrivateStorageError("Private database identity is unavailable")
    if any(type(identifier) is not int or identifier <= 0
           for identifier in (file.st_ino, directory.st_ino)):
        raise PrivateStorageError("Private database identity is unavailable")
    return file.st_dev, file.st_ino, directory.st_dev, directory.st_ino


def require_database_identity(value: Path, expected: tuple[int, int, int, int]) -> None:
    if database_identity(value) != expected:
        raise PrivateStorageError("Private database identity changed")


def prepare_database(value: Path, *, exclusive: bool = False) -> Path:
    path = checked_database_path(value)
    if exclusive and any(Path(str(path) + suffix).exists()
                         for suffix in ("-journal", "-wal", "-shm")):
        raise PrivateStorageError("New database destination must have no existing sidecars")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    checked_database_path(path)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR
                             | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        if exclusive:
            raise
        if not path.is_file():
            raise PrivateStorageError("Private database path must be a file") from None
    else:
        os.close(descriptor)
    if os.name != "nt":
        path.chmod(0o600)
    return path
