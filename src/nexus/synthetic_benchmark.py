"""Opt-in parser/store benchmark in a NEW checkout-local synthetic directory only.

This measures conditions and results, not a retroactively invented performance gate.
The summary contains no message text, source identifiers, credentials, or paths.
"""

import hashlib
import json
import os
import platform
import sqlite3
import sys
import time
import tracemalloc
import uuid
from pathlib import Path

from nexus import __version__
from nexus.cli import PrivateArgumentParser
from nexus.importers import MAX_MESSAGES, PARSER_VERSION, load_synthetic
from nexus.maintenance import copy_database
from nexus.private_storage import checked_path
from nexus.store import Store

_CHECKOUT_ROOT = Path(__file__).absolute().parents[2]
DEFAULT_STAGES = (1_000, 10_000, 50_000)
_RECORD_TABLES = ("source_instances", "conversations", "messages", "message_search",
                  "projects", "import_batches", "source_events", "audit_log", "schema_migrations")


class BenchmarkProblem(ValueError):
    """A fixed diagnostic; never repeat private argument values."""


def _require(condition):
    if not condition:
        raise BenchmarkProblem("Synthetic benchmark checks failed")


def _fixture(message_count):
    return {
        "nexus_fixture": "synthetic-v1", "provider": "chatgpt", "conversations": [
            {"id": f"synthetic-benchmark-c{first // 250}",
             "title": f"Synthetic benchmark {first // 250}", "messages": [
                 {"id": f"synthetic-benchmark-m{i}", "role": "user",
                  "text": f"benchmark 日本語 token{i:05d} 100% x_y"}
                 for i in range(first, min(first + 250, message_count))
             ]} for first in range(0, message_count, 250)
        ],
    }


def _measure(operation):
    started = time.perf_counter()
    result = operation()
    return result, round(time.perf_counter() - started, 6)


def _records_digest(store):
    """Compare full logical records internally; never put records/hashes into the summary."""
    digest = hashlib.sha256()
    with store.connect() as db:
        db.execute("BEGIN")
        for table in _RECORD_TABLES:
            digest.update(table.encode("ascii"))
            for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid"):
                digest.update(json.dumps(tuple(row), ensure_ascii=False).encode("utf-8"))
                digest.update(b"\n")
    return digest.digest()


def _stage(root, message_count):
    started = time.perf_counter()
    tracemalloc.start()
    try:
        blob = json.dumps(_fixture(message_count), ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8")
        records, parser_seconds = _measure(lambda: load_synthetic(blob, "chatgpt"))
        store = Store(root / f"stage-{message_count}" / "nexus.sqlite3")

        def import_data():
            return store.import_conversations(
                provider="chatgpt", account_alias="synthetic-benchmark",
                import_hash=hashlib.sha256(blob).hexdigest(), parser_version=PARSER_VERSION,
                conversations=records,
            )

        first, import_seconds = _measure(import_data)
        second, reimport_seconds = _measure(import_data)
        _require(first["counts"]["messages_inserted"] == message_count)
        _require(second["counts"]["messages_inserted"] == 0)
        _require(second["counts"]["messages_duplicates"] == message_count)
        _require(first["source_id"] == second["source_id"])
        search_seconds = {}
        search_counts = {}
        for kind, query, expected in (
            ("unicode_all_matches", "日本語", message_count),
            ("unique_term", f"token{message_count - 1:05d}", 1),
            ("literal_percent", "100%", message_count),
        ):
            page, duration = _measure(lambda: store.search_page(query, None, None))
            _require(page["total"] == expected)
            _require(len(page["items"]) == min(expected, 100))
            search_seconds[kind] = duration
            search_counts[kind] = page["total"]
        end_page, end_page_seconds = _measure(
            lambda: store.search_page("日本語", None, None, offset=message_count)
        )
        _require(end_page["total"] == message_count and end_page["items"] == [])
        _require(end_page["next_offset"] is None)
        integrity, integrity_seconds = _measure(store.integrity_report)
        _require(integrity["ok"])
        before = _records_digest(store)
        destination = root / f"restored-{message_count}" / "nexus.sqlite3"
        _, backup_seconds = _measure(lambda: copy_database(store.path, destination))
        restored = Store(destination)
        _require(restored.integrity_report()["ok"])
        _require(before == _records_digest(restored))
        _require(restored.overview()["counts"] == store.overview()["counts"])
        with store.connect() as db:
            temp_store = db.execute("PRAGMA temp_store").fetchone()[0]
        _, peak = tracemalloc.get_traced_memory()
        return {
            "messages": message_count, "conversations": len(records),
            "fixture_bytes": len(blob), "parser_version": PARSER_VERSION,
            "sqlite_temp_store": temp_store,
            "seconds": {"normalize": parser_seconds, "import": import_seconds,
                        "reimport": reimport_seconds, "search": search_seconds,
                        "end_page": end_page_seconds, "integrity": integrity_seconds,
                        "backup": backup_seconds,
                        "stage_total": round(time.perf_counter() - started, 6)},
            "import_messages_per_second": round(
                message_count / max(import_seconds, 0.000001), 2),
            "tracked_python_peak_bytes": peak,
            "checks": {"messages_inserted": first["counts"]["messages_inserted"],
                       "reimport_inserted": second["counts"]["messages_inserted"],
                       "reimport_duplicates": second["counts"]["messages_duplicates"],
                       "search_totals": search_counts, "end_page_empty": True,
                       "integrity_ok": True, "backup_records_equal": True,
                       "backup_counts_equal": True},
        }
    finally:
        tracemalloc.stop()


def run_benchmark(root: Path, stages=DEFAULT_STAGES):
    """Refuse existing destinations and all paths outside this checkout's tmp subtree."""
    stages = tuple(stages)
    if (not stages or len(stages) > 6
            or any(type(count) is not int or not 1 <= count <= MAX_MESSAGES for count in stages)
            or len(set(stages)) != len(stages)):
        raise BenchmarkProblem("Invalid synthetic benchmark stages")
    if tracemalloc.is_tracing():
        raise BenchmarkProblem("A separate benchmark process is required")
    if ".." in Path(root).parts:
        raise BenchmarkProblem("Synthetic benchmark requires a new checkout-local directory")
    root = checked_path(root)
    allowed = checked_path(_CHECKOUT_ROOT / "tmp")
    if root == allowed or not root.is_relative_to(allowed):
        raise BenchmarkProblem("Synthetic benchmark requires a new checkout-local directory")
    if root.exists():
        raise BenchmarkProblem("Synthetic benchmark destination already exists")
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    report = {
        "schema_version": 1, "data_kind": "synthetic", "coverage": "synthetic_only",
        "result": "synthetic_checks_passed", "performance_targets": None,
        "conditions": {"nexus_version": __version__, "python_version": platform.python_version(),
                       "python_implementation": platform.python_implementation(),
                       "sqlite_version": sqlite3.sqlite_version, "os": platform.system(),
                       "architecture": platform.machine(), "logical_cpu_count": os.cpu_count(),
                       "entrypoint": "synthetic_parser_and_store",
                       "memory_measure": "tracemalloc_python_allocations_only",
                       "full_process_rss_measured": False,
                       "timing_clock": "perf_counter_wall_seconds",
                       "search_page_limit": 100, "messages_per_conversation": 250,
                       "samples_per_operation": 1,
                       "external_ai_connections": 0, "paid_api_calls": 0},
        "stages": [_stage(root, count) for count in stages],
    }
    checked_path(root)
    descriptor = os.open(root / "report.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=True, indent=2)
        output.write("\n")
    return report


def main():
    parser = PrivateArgumentParser(description="Benchmark only new checkout-local synthetic data")
    parser.add_argument("--root", type=Path,
                        help="New directory under this checkout's tmp; existing paths are refused")
    parser.add_argument("--stages", nargs="+", type=int, default=DEFAULT_STAGES,
                        help="Message counts (1..50000); default: 1000 10000 50000")
    args = parser.parse_args()
    root = args.root or _CHECKOUT_ROOT / "tmp" / "synthetic-benchmark" / uuid.uuid4().hex
    try:
        run_benchmark(root, args.stages)
    except (OSError, ValueError, sqlite3.Error, KeyboardInterrupt):
        print("Synthetic benchmark refused or failed. No existing data was overwritten.",
              file=sys.stderr)
        raise SystemExit(1) from None
    print("Synthetic benchmark checks passed. The new directory contains report.json.")


if __name__ == "__main__":
    main()
