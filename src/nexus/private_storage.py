"""Conservative paths and owner-only POSIX database files."""

import os
from pathlib import Path


def checked_path(value: Path) -> Path:
    path = value.expanduser().absolute()
    if any(candidate.is_symlink() for candidate in (path, *path.parents)):
        raise ValueError("Private database paths must not contain a symlink")
    if path.exists() and path.is_file() and path.stat().st_nlink > 1:
        raise ValueError("Private database paths must not use hard links")
    return path


def prepare_database(value: Path, *, exclusive: bool = False) -> Path:
    path = checked_path(value)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    except FileExistsError:
        if exclusive:
            raise
        if not path.is_file():
            raise ValueError("Private database path must be a file") from None
    else:
        os.close(descriptor)
    if os.name != "nt":
        path.chmod(0o600)
    return path
