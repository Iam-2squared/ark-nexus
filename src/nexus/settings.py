"""Local-only configuration. Do not store imported private messages inside source control."""

import os
from pathlib import Path


def data_directory() -> Path:
    configured = os.environ.get("NEXUS_DATA_DIR")
    if configured:
        return Path(configured).expanduser().absolute()
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return (root / "ARK-Nexus").absolute()
    return (Path.home() / ".local" / "share" / "ark-nexus").absolute()


def database_path() -> Path:
    return data_directory() / "nexus.sqlite3"
