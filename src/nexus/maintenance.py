"""Offline backup/restore-to-new-location. Never overwrite or delete existing user data."""

import argparse
import sqlite3
from pathlib import Path

from nexus.private_storage import checked_path, prepare_database


def copy_database(source: Path, destination: Path) -> None:
    source = checked_path(source)
    if not source.is_file():
        raise FileNotFoundError("Source database does not exist")
    destination = prepare_database(destination, exclusive=True)
    try:
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as reader:
            if reader.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Source database failed SQLite integrity check")
            with sqlite3.connect(destination) as writer:
                reader.backup(writer)
                if writer.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("Copied database failed SQLite integrity check")
    except Exception:
        # Only the new file created by this invocation can be removed on failure.
        destination.unlink()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy a Nexus database to a new private path")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    copy_database(args.source, args.destination)
    print("Database copy verified. Existing data was not overwritten.")


if __name__ == "__main__":
    main()
