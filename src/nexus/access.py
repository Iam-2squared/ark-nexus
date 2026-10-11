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
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        if os.name != "nt":
            path.chmod(0o600)
        with path.open(encoding="ascii") as reader:
            return valid_key(reader.read(257).strip())
    else:
        token = secrets.token_urlsafe(32)
        with os.fdopen(descriptor, "w", encoding="ascii") as writer:
            writer.write(token + "\n")
        return token
