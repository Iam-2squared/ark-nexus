"""Offline backup/restore-to-new-location. Never overwrite or delete existing user data."""

import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from nexus.cli import PrivateArgumentParser
from nexus.integrity import inspect_integrity
from nexus.private_storage import (
    checked_database_path,
    configure_memory_temp,
    database_identity,
    prepare_database,
    require_database_identity,
)


def copy_database(source: Path, destination: Path) -> None:
    source = checked_database_path(source)
    if not source.is_file():
        raise FileNotFoundError("Source database does not exist")
    source_identity = database_identity(source)
    destination = prepare_database(destination, exclusive=True)
    destination_identity = database_identity(destination)
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as reader:
            require_database_identity(source, source_identity)
            configure_memory_temp(reader)
            reader.execute("BEGIN")
            if not inspect_integrity(reader)["ok"]:
                raise ValueError("Source database failed stored-record integrity check")
            checked_database_path(destination)
            with closing(sqlite3.connect(destination.as_uri() + "?mode=rw", uri=True)) as writer:
                require_database_identity(source, source_identity)
                require_database_identity(destination, destination_identity)
                configure_memory_temp(writer)
                reader.backup(writer)
                require_database_identity(source, source_identity)
                require_database_identity(destination, destination_identity)
                writer.execute("BEGIN")
                if not inspect_integrity(writer)["ok"]:
                    raise ValueError("Copied database failed stored-record integrity check")
    except BaseException:
        # Remove only this operation's still-private, unchanged new identity.
        # A replacement, moved parent or newly shared hardlink is retained.
        # Cleanup failure must not replace the original interruption/error.
        try:
            if database_identity(destination) == destination_identity:
                destination.unlink()
        except (OSError, ValueError):
            pass
        raise


def main() -> None:
    parser = PrivateArgumentParser(description="Copy a Nexus database to a new private path")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        copy_database(args.source, args.destination)
    except (OSError, ValueError, sqlite3.Error, KeyboardInterrupt):
        print("Database copy refused or failed. No existing destination was overwritten.",
              file=sys.stderr)
        raise SystemExit(1) from None
    print("Database copy verified. Existing data was not overwritten.")


if __name__ == "__main__":
    main()
