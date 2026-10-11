"""Owner-local key material. Never expose it through HTTP or commit it."""

import os
import secrets
from pathlib import Path

from nexus.private_storage import checked_path


def valid_key(value: str) -> str:
    if not 32 <= len(value) <= 256 or not value.isascii():
        raise ValueError("Local access key must contain 32-256 ASCII token characters")
    if any(not (char.isalnum() or char in "-_") for char in value):
        raise ValueError("Invalid local access key characters")
    return value


def local_access_key(directory: Path) -> str:
    configured = os.environ.get("NEXUS_API_TOKEN")
    if configured is not None:
        return valid_key(configured)
    path = checked_path(directory / "nexus-access.key")
    # Windows reports EACCES, rather than EEXIST, when O_EXCL targets a directory.
    if path.exists() and not path.is_file():
        raise ValueError("Local access key path must be a file")
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        if not path.is_file():
            raise ValueError("Local access key path must be a file") from None
        try:
            with path.open("rb") as reader:
                raw = reader.read(259)
            if len(raw) > 258:
                raise ValueError
            if raw.endswith(b"\r\n"):
                raw = raw[:-2]
            elif raw.endswith(b"\n"):
                raw = raw[:-1]
            token = valid_key(raw.decode("ascii"))
        except (OSError, ValueError):
            raise ValueError("Invalid local access key file") from None
        if os.name != "nt":
            path.chmod(0o600)
        return token
    else:
        token = secrets.token_urlsafe(32)
        with os.fdopen(descriptor, "w", encoding="ascii") as writer:
            writer.write(token + "\n")
        return token
