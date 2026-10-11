"""Offline backup/restore-to-new-location. Never overwrite or delete existing user data."""

import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from nexus.cli import PrivateArgumentParser
from nexus.integrity import inspect_integrity
from nexus.private_storage import checked_database_path, prepare_database


def copy_database(source: Path, destination: Path) -> None:
    source = checked_database_path(source)
    if not source.is_file():
        raise FileNotFoundError("Source database does not exist")
    destination = prepare_database(destination, exclusive=True)
    created = destination.stat(follow_symlinks=False)
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as reader:
            reader.execute("BEGIN")
            if not inspect_integrity(reader)["ok"]:
                raise ValueError("Source database failed stored-record integrity check")
            checked_database_path(destination)
            with closing(sqlite3.connect(destination)) as writer:
                reader.backup(writer)
                if not inspect_integrity(writer)["ok"]:
                    raise ValueError("Copied database failed stored-record integrity check")
    except Exception:
        # Only the new file created by this invocation can be removed on failure.
        if destination.exists() and not destination.is_symlink() and not destination.is_junction():
            current = destination.stat(follow_symlinks=False)
            if (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino):
                destination.unlink()
        raise


def main() -> None:
    parser = PrivateArgumentParser(description="Copy a Nexus database to a new private path")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        copy_database(args.source, args.destination)
    except (OSError, ValueError, sqlite3.Error):
        print("Database copy refused or failed. No existing destination was overwritten.",
              file=sys.stderr)
        raise SystemExit(1) from None
    print("Database copy verified. Existing data was not overwritten.")


if __name__ == "__main__":
    main()
