"""Bounded comparisons of the unchanged synthetic 10k pytest gate.

Only child processes install an optional count observer. Evidence is deliberately
not a repair, a provider-format qualification, or proof that the historic anomaly
has disappeared. Failed synthetic databases are retained in a new ignored root.
"""

import ast
import hashlib
import json
import os
import platform
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import uuid
from contextlib import closing
from pathlib import Path
from urllib.parse import unquote, urlsplit

from nexus.cli import PrivateArgumentParser
from nexus.forensic_lifecycle import BOUNDARY_PHASES, pytest_lifecycle, validate_lifecycle
from nexus.machine_check import REPOSITORY, workspace_metadata
from nexus.private_storage import checked_database_path, checked_path

CHECKOUT_ROOT = Path(__file__).absolute().parents[2]
FROZEN_FUNCTION = "test_10000_message_reimport_and_complete_pagination"
FROZEN_FILE = "tests/test_megabatch_integrity.py"
FROZEN_NODE = FROZEN_FILE + "::" + FROZEN_FUNCTION
RELATED_FILES = (
    FROZEN_FILE, "tests/test_next_database_integrity.py", "tests/test_data_management.py",
    "tests/test_integrity.py", "tests/test_store.py", "tests/test_search_regression.py",
    "tests/test_concurrency.py",
)
SCOPES = {"single", "related", "full"}
TABLES = ("source_instances", "conversations", "messages", "import_batches",
          "message_search", "source_events", "audit_log", "schema_migrations")
CORE_TABLES = set(TABLES) - {"schema_migrations"}
PHASES = {"opened", "begin_before", "begin_after", "commit_before", "commit_after",
          "rollback_before", "rollback_after", "close_before", "close_reopened", "final"}
PHASES |= BOUNDARY_PHASES
MAX_CONNECTIONS = 512
MAX_CHECKPOINTS = 4096
MAX_REPORT_BYTES = 8 * 1024 * 1024


class ForensicsProblem(ValueError):
    """A fixed diagnostic; never include argument, SQL or exception values."""


def _require(condition, code="Synthetic forensic checks failed"):
    if not condition:
        raise ForensicsProblem(code)


def _runtime():
    import _sqlite3

    return {
        "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
        "os": platform.system() if platform.system() in {"Linux", "Windows", "Darwin"}
        else "Other",
        "sqlite_module": "builtin" if _sqlite3.__spec__.origin == "built-in" else "extension",
        "connection_runtime": "current_python_sqlite3",
    }


def _identity(path):
    """File IDs remain internal; only equality classifications enter evidence."""
    checked_database_path(path)
    file = path.stat(follow_symlinks=False)
    directory = path.parent.stat(follow_symlinks=False)
    _require(file.st_ino > 0 and directory.st_ino > 0,
             "Synthetic database identity unavailable")
    return file.st_dev, file.st_ino, directory.st_dev, directory.st_ino


def _snapshot(connection):
    # Calling the base execute avoids observing our own queries as workload SQL.
    def query(sql):
        return sqlite3.Connection.execute(connection, sql)

    existing = {row[0] for row in query("SELECT name FROM sqlite_master WHERE type IN "
                                     "('table','view')")}
    present = [table for table in TABLES if table in existing]
    counts = {table: None for table in TABLES}
    if present:
        # One SELECT observes all row counts in one SQLite statement snapshot.
        row = query("SELECT " + ",".join("(SELECT count(*) FROM " + table + ")"
                                        for table in present)).fetchone()
        counts.update(zip(present, row, strict=True))
    journal = query("PRAGMA journal_mode").fetchone()[0]
    return {
        "counts": counts,
        "foreign_key_errors": sum(1 for _ in query("PRAGMA foreign_key_check")),
        "foreign_keys_enabled": query("PRAGMA foreign_keys").fetchone()[0] == 1,
        "temp_store": query("PRAGMA temp_store").fetchone()[0],
        "journal_mode": journal if journal in {"delete", "wal", "truncate", "persist",
                                               "memory", "off"} else "unknown",
        "in_transaction": connection.in_transaction,
        "total_changes": connection.total_changes,
    }


def _database_path(value, uri=False):
    if not isinstance(value, (str, os.PathLike)):
        return None
    value = os.fspath(value)
    if not isinstance(value, str) or value == ":memory:":
        return None
    if uri and value.startswith("file:"):
        parsed = urlsplit(value)
        if parsed.netloc not in {"", "localhost"}:
            return None
        value = unquote(parsed.path)
        if os.name == "nt" and re.match(r"^/[A-Za-z]:/", value):
            value = value[1:]
    return Path(value).absolute()


class CountObserver:
    """Child-local observer, never installed into Nexus production code.

    Authorizer counts are preparations, not assertions that a DELETE executed.
    The callback always permits the same operation; it records no SQL or values.
    Explicit factories supplied by tests are respected instead of replaced.
    """

    def __init__(self, basetemp, *, enabled=True):
        self.basetemp = checked_path(basetemp)
        self.enabled = enabled
        self.original_connect = sqlite3.connect
        self.timeline = []
        self.path = None
        self.identity = None
        self.connections = 0
        self.explicit_factories = 0
        self.observation_errors = 0
        self.capped = False
        self.prepared_deletes = 0
        self.prepared_drops = 0
        self.commit_boundaries = 0
        self.lock = threading.RLock()
        observer = self

        class ObservedConnection(sqlite3.Connection):
            def commit(self):
                observer.capture(self, "commit_before")
                result = super().commit()
                observer.commit_boundaries += 1
                observer.capture(self, "commit_after")
                return result

            def rollback(self):
                observer.capture(self, "rollback_before")
                result = super().rollback()
                observer.capture(self, "rollback_after")
                return result

            def close(self):
                observer.capture(self, "close_before")
                result = super().close()
                observer.reopened("close_reopened", self._forensic_number)
                return result

            def execute(self, sql, *args, **kwargs):
                command = sql.strip().rstrip(";").strip().upper() if type(sql) is str else ""
                phase = "begin" if command in {
                    "BEGIN", "BEGIN IMMEDIATE", "BEGIN DEFERRED", "BEGIN EXCLUSIVE"} else {
                        "COMMIT": "commit", "END": "commit", "ROLLBACK": "rollback"}.get(command)
                if phase:
                    observer.capture(self, phase + "_before")
                result = super().execute(sql, *args, **kwargs)
                if phase == "commit":
                    observer.commit_boundaries += 1
                if phase:
                    observer.capture(self, phase + "_after")
                return result

            def __exit__(self, exc_type, exc_value, traceback):
                # The native context manager need not call Python's overridden
                # commit/rollback methods. Preserve its result/error semantics.
                phase = "rollback" if exc_type is not None else "commit"
                observer.capture(self, phase + "_before")
                result = super().__exit__(exc_type, exc_value, traceback)
                if phase == "commit":
                    observer.commit_boundaries += 1
                observer.capture(self, phase + "_after")
                return result

        self.connection_class = ObservedConnection

    def watches(self, path):
        return (path is not None and path.name == "nexus.sqlite3"
                and path.parent.parent == self.basetemp
                and path.parent.name.startswith("test_10000_message_reimport_an"))

    def connect(self, *args, **kwargs):
        path = _database_path(args[0] if args else kwargs.get("database"),
                              kwargs.get("uri", args[7] if len(args) > 7 else False))
        if not self.enabled or not self.watches(path):
            return self.original_connect(*args, **kwargs)
        if "factory" in kwargs or len(args) > 5:
            with self.lock:
                self.explicit_factories += 1
            return self.original_connect(*args, **kwargs)
        with self.lock:
            if self.connections >= MAX_CONNECTIONS:
                self.capped = True
                return self.original_connect(*args, **kwargs)
            if self.path is None:
                self.path = checked_path(path)
                self.identity = _identity(path)
            _require(path == self.path, "Synthetic forensic target ambiguity")
            self.connections += 1
            number = self.connections
        kwargs.setdefault("factory", self.connection_class)
        connection = self.original_connect(*args, **kwargs)
        connection._forensic_number = number

        def authorizer(action, table, _column, database, _trigger):
            if database == "main" and table in CORE_TABLES:
                with self.lock:
                    if action == sqlite3.SQLITE_DELETE:
                        self.prepared_deletes += 1
                    elif action in {sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_DROP_VTABLE}:
                        self.prepared_drops += 1
            return sqlite3.SQLITE_OK

        connection.set_authorizer(authorizer)
        self.capture(connection, "opened")
        return connection

    def capture(self, connection, phase, *, readonly=False, number=None):
        with self.lock:
            if len(self.timeline) >= MAX_CHECKPOINTS:
                self.capped = True
                return
            try:
                state = _snapshot(connection)
                same = _identity(self.path) == self.identity
                sidecars = {name: Path(str(self.path) + "-" + name).exists()
                            for name in ("journal", "wal", "shm")}
                self.timeline.append({
                    "sequence": len(self.timeline) + 1,
                    "connection": number if number is not None else connection._forensic_number,
                    "phase": phase, "readonly_observer": readonly, "file_identity_same": same,
                    "sidecars_present": sidecars, **state,
                })
            except (OSError, ValueError, sqlite3.Error):
                self.observation_errors += 1

    def reopened(self, phase, number):
        if self.path is None:
            return
        try:
            checked_database_path(self.path)
            with closing(self.original_connect(self.path.as_uri() + "?mode=ro", uri=True,
                                               timeout=2)) as connection:
                # Only this independent observer connection changes these PRAGMAs.
                connection.execute("PRAGMA query_only=ON")
                connection.execute("PRAGMA temp_store=MEMORY")
                connection.execute("BEGIN")
                self.capture(connection, phase, readonly=True, number=number)
        except (OSError, ValueError, sqlite3.Error):
            self.observation_errors += 1

    def final(self):
        if self.path is None:
            candidates = []
            for candidate in self.basetemp.iterdir():
                # pytest's '<name>current' alias is not another target. Never
                # follow it or a junction to inspect/create a database.
                if candidate.is_symlink() or candidate.is_junction():
                    continue
                checked_path(candidate)
                if (candidate.is_dir() and self.watches(candidate / "nexus.sqlite3")
                        and (candidate / "nexus.sqlite3").is_file()):
                    candidates.append(candidate / "nexus.sqlite3")
            if len(candidates) == 1:
                self.path = checked_path(candidates[0])
                self.identity = _identity(self.path)
        self.reopened("final", 0)


class _PytestEvidence:
    def __init__(self):
        self.counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}
        self.frozen_result = "NOT RUN"

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            self.counts[{"passed": "passed", "failed": "failed", "skipped": "skipped"}
                        [report.outcome]] += 1
            if report.nodeid == FROZEN_NODE:
                self.frozen_result = {"passed": "PASS", "failed": "FAIL",
                                      "skipped": "SKIP"}[report.outcome]
        elif report.failed:
            self.counts["errors"] += 1
            if report.nodeid == FROZEN_NODE:
                self.frozen_result = "FAIL"
        elif report.skipped and report.when == "setup":
            self.counts["skipped"] += 1
            if report.nodeid == FROZEN_NODE:
                self.frozen_result = "SKIP"


def _write_report(path, report):
    checked_path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=True, separators=(",", ":"))
        output.write("\n")


def _child(case, scope, observed):
    case = checked_path(case)
    _require(case.is_relative_to(checked_path(CHECKOUT_ROOT / "tmp")) and case.is_dir())
    # The parent creates this fresh directory and its empty process-local temp.
    # A child entrypoint must not reuse a populated previous evidence directory.
    _require({entry.name for entry in case.iterdir()} == {"process-temp"}
             and checked_path(case / "process-temp").is_dir()
             and not any((case / "process-temp").iterdir()))
    basetemp = case / "pytest"
    _require(not basetemp.exists() and scope in SCOPES)
    import pytest

    observer = CountObserver(basetemp, enabled=observed)
    evidence = _PytestEvidence()
    lifecycle = pytest_lifecycle(observer, FROZEN_NODE)
    nodes = [FROZEN_NODE] if scope == "single" else list(RELATED_FILES) if scope == "related" \
        else ["tests"]
    original_connect = sqlite3.connect
    try:
        if observed:
            sqlite3.connect = observer.connect
        exit_code = int(pytest.main(["-q", "--disable-warnings", "-p", "no:cacheprovider",
                                    "--basetemp", str(basetemp), *nodes], plugins=[evidence, lifecycle]))
    finally:
        sqlite3.connect = original_connect
    observer.final()
    report = {
        "schema": 2, "scope": scope, "observed": observed, "runtime": _runtime(),
        "exit_code": exit_code, "pytest": evidence.counts,
        "frozen_test": evidence.frozen_result, "connections": observer.connections,
        "explicit_factories_respected": observer.explicit_factories,
        "checkpoint_limit_reached": observer.capped,
        "observation_errors": observer.observation_errors,
        "prepared_core_deletes": observer.prepared_deletes,
        "prepared_core_drops": observer.prepared_drops, "timeline": observer.timeline,
        "lifecycle": lifecycle.report(),
    }
    _write_report(case / "case.json", report)
    return exit_code


def _integer(value, upper=10**12):
    return type(value) is int and 0 <= value <= upper


def _valid_checkpoint(point):
    fields = {"sequence", "connection", "phase", "readonly_observer", "file_identity_same",
              "sidecars_present", "counts", "foreign_key_errors", "foreign_keys_enabled",
              "temp_store", "journal_mode", "in_transaction", "total_changes"}
    return (type(point) is dict and set(point) == fields
            and _integer(point["sequence"], MAX_CHECKPOINTS)
            and _integer(point["connection"], MAX_CONNECTIONS)
            and type(point["phase"]) is str and point["phase"] in PHASES
            and all(type(point[name]) is bool for name in (
                "readonly_observer", "file_identity_same", "foreign_keys_enabled", "in_transaction"))
            and type(point["sidecars_present"]) is dict
            and set(point["sidecars_present"]) == {"journal", "wal", "shm"}
            and all(type(value) is bool for value in point["sidecars_present"].values())
            and type(point["counts"]) is dict and set(point["counts"]) == set(TABLES)
            and all(value is None or _integer(value) for value in point["counts"].values())
            and _integer(point["foreign_key_errors"])
            and _integer(point["total_changes"])
            and _integer(point["temp_store"], 2)
            and type(point["journal_mode"]) is str
            and point["journal_mode"] in {"delete", "wal", "truncate", "persist",
                                          "memory", "off", "unknown"})


def validate_case(report):
    """Reject rather than relay unallowlisted child output or arbitrary strings."""
    fields = {"schema", "scope", "observed", "runtime", "exit_code", "pytest", "frozen_test",
              "connections", "explicit_factories_respected", "checkpoint_limit_reached",
              "observation_errors", "prepared_core_deletes", "prepared_core_drops", "timeline"}
    _require(type(report) is dict)
    if type(report.get("schema")) is int and report["schema"] == 2:
        fields.add("lifecycle")
    _require(set(report) == fields)
    runtime = report["runtime"]
    _require(type(runtime) is dict and set(runtime) == {
        "python", "sqlite", "os", "sqlite_module", "connection_runtime"})
    _require(all(type(runtime[key]) is str and re.fullmatch(r"[0-9]{1,3}(\.[0-9]{1,3}){2}",
                                                          runtime[key])
                 for key in ("python", "sqlite")))
    _require(type(runtime["os"]) is str and runtime["os"] in {"Linux", "Windows", "Darwin", "Other"}
             and type(runtime["sqlite_module"]) is str
             and runtime["sqlite_module"] in {"builtin", "extension"}
             and runtime["connection_runtime"] == "current_python_sqlite3")
    _require(type(report["schema"]) is int and report["schema"] in (1, 2)
             and type(report["scope"]) is str and report["scope"] in SCOPES
             and type(report["observed"]) is bool
             and _integer(report["exit_code"], 5)
             and type(report["frozen_test"]) is str
             and report["frozen_test"] in {"PASS", "FAIL", "SKIP", "NOT RUN"})
    _require(type(report["pytest"]) is dict and set(report["pytest"]) == {
        "passed", "failed", "skipped", "errors"}
        and all(_integer(value, 100_000) for value in report["pytest"].values()))
    _require(all(_integer(report[key]) for key in (
        "connections", "explicit_factories_respected", "observation_errors",
        "prepared_core_deletes", "prepared_core_drops"))
        and report["connections"] <= MAX_CONNECTIONS
        and type(report["checkpoint_limit_reached"]) is bool)
    _require(type(report["timeline"]) is list and len(report["timeline"]) <= MAX_CHECKPOINTS
             and all(_valid_checkpoint(point) for point in report["timeline"]))
    _require(all(point["sequence"] == index + 1
                 for index, point in enumerate(report["timeline"])))
    if report["schema"] == 2:
        validate_lifecycle(report["lifecycle"], report["timeline"], _require)
        _require(report["lifecycle"]["boundary_observer_enabled"] is report["observed"])
    return report


def _load_case(path):
    _require(checked_path(path).is_file() and path.stat().st_size <= MAX_REPORT_BYTES)

    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result)
            result[key] = value
        return result

    try:
        return validate_case(json.loads(path.read_text(encoding="utf-8"),
                                        object_pairs_hook=object_pairs))
    except (TypeError, UnicodeError, ValueError, RecursionError):
        raise ForensicsProblem("Invalid synthetic forensic evidence") from None


def comparison_checks(report):
    """Compare only observed counts/identities; never infer a storage root cause."""
    final = [point for point in report["timeline"] if point["phase"] == "final"]
    expected = {"source_instances": 1, "conversations": 100, "messages": 10_000,
                "import_batches": 2, "message_search": 10_000,
                "source_events": 2, "audit_log": 2, "schema_migrations": 2}
    final_ok = (len(final) == 1 and final[0]["foreign_key_errors"] == 0
                and final[0]["file_identity_same"]
                and all(final[0]["counts"][table] == count for table, count in expected.items()))
    closed = {}
    changed_at_close = False
    for point in report["timeline"]:
        if point["phase"] == "close_before" and not point["in_transaction"]:
            closed[point["connection"]] = point["counts"]
        elif point["phase"] == "close_reopened" and point["connection"] in closed:
            changed_at_close |= closed[point["connection"]] != point["counts"]
    checks = {"final_expected_counts": final_ok,
              "file_identity_retained": all(point["file_identity_same"]
                                            for point in report["timeline"]),
              "foreign_keys_clean": all(point["foreign_key_errors"] == 0
                                        for point in report["timeline"]),
              "committed_close_counts_equal": not changed_at_close}
    if report["schema"] == 2:
        lifecycle = report["lifecycle"]
        events = lifecycle["events"]
        ordered = ("test_setup_before", "fixture_setup_before", "fixture_setup_after",
                   "test_setup_after", "test_call_before", "test_call_after",
                   "test_teardown_before", "fixture_teardown_after", "test_teardown_after")
        complete = (lifecycle["frozen_test_index"] is not None
                    and lifecycle["collection_sha256"] is not None)
        if report["observed"]:
            complete &= tuple(event["phase"] for event in events) == ordered
            complete &= all(event["status"] == "captured"
                            and event["identity_same"] is True
                            and event["main_header"]["valid"]
                            for event in events[2:])
        else:
            complete &= not events
        checks["lifecycle_complete"] = bool(complete)
    return checks


def _stop_owned(process):
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGINT)
        process.wait(timeout=5)
    except (OSError, subprocess.SubprocessError):
        if process.poll() is None:
            if os.name == "nt":
                process.terminate()
            else:
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)


def _run_case(case, scope, observed, timeout):
    case.mkdir(mode=0o700, exist_ok=False)
    scratch = case / "process-temp"
    scratch.mkdir(mode=0o700, exist_ok=False)
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("GIT_") and key not in {
                       "PYTEST_ADDOPTS", "NEXUS_DATA_DIR", "NEXUS_API_TOKEN", "PYTHONPATH"}}
    environment.update({"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONNOUSERSITE": "1",
                        "PYTHONPATH": str(CHECKOUT_ROOT / "src"),
                        "TMPDIR": str(scratch), "TMP": str(scratch), "TEMP": str(scratch)})
    command = [sys.executable, "-m", "nexus.data_forensics", "--child-root", str(case),
               "--scope", scope]
    if not observed:
        command.append("--unobserved")
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" \
        else {"start_new_session": True}
    process = subprocess.Popen(command, cwd=CHECKOUT_ROOT, env=environment,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, **options)
    try:
        code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _stop_owned(process)
        return {"status": "FAIL", "reason": "child_timeout", "evidence": None}
    except BaseException:
        _stop_owned(process)
        raise
    if not (case / "case.json").exists():
        return {"status": "FAIL", "reason": "child_evidence_unavailable", "evidence": None}
    try:
        report = _load_case(case / "case.json")
        _require(report["scope"] == scope and report["observed"] == observed
                 and report["exit_code"] == code)
    except (OSError, ValueError):
        return {"status": "FAIL", "reason": "child_evidence_invalid", "evidence": None}
    checks = comparison_checks(report)
    valid = (code == 0 and report["frozen_test"] == "PASS"
             and report["observation_errors"] == 0 and not report["checkpoint_limit_reached"]
             and all(checks.values()))
    return {"status": "PASS" if valid else "FAIL",
            "reason": "synthetic_comparison_passed" if valid else "synthetic_comparison_failed",
            "checks": checks, "evidence": report}


def _frozen_definition():
    path = checked_path(CHECKOUT_ROOT / FROZEN_FILE)
    current = path.read_text(encoding="utf-8")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    result = subprocess.run(["git", "-C", str(CHECKOUT_ROOT), "show", "HEAD:" + FROZEN_FILE],
                            capture_output=True, timeout=10, env=environment, check=False)
    _require(result.returncode == 0)

    def definition(text):
        lines = text.splitlines(keepends=True)
        nodes = [node for node in ast.parse(text).body
                 if isinstance(node, ast.FunctionDef) and node.name == FROZEN_FUNCTION]
        _require(len(nodes) == 1)
        return "".join(lines[nodes[0].lineno - 1:nodes[0].end_lineno])

    local = definition(current)
    _require(local == definition(result.stdout.decode("utf-8")),
             "Frozen synthetic forensic test changed")
    return hashlib.sha256(local.encode("utf-8")).hexdigest()


def run_forensics(root, *, scopes=("single", "related", "full"), trials=1,
                  observed=True, child_timeout=150, source_head=None):
    """Run at most nine sequential children; never reuse or erase a test root."""
    _require(type(trials) is int and 1 <= trials <= 3
             and type(observed) is bool and type(child_timeout) is int
             and 10 <= child_timeout <= 180,
             "Invalid synthetic forensic limits")
    _require(type(scopes) in {tuple, list} and 1 <= len(scopes) <= 3
             and all(type(scope) is str and scope in SCOPES for scope in scopes),
             "Invalid synthetic forensic scopes")
    scopes = tuple(scopes)
    _require(len(set(scopes)) == len(scopes),
             "Invalid synthetic forensic scopes")
    _require(source_head is None or type(source_head) is str
             and re.fullmatch(r"[0-9a-f]{40}", source_head), "Invalid source-head declaration")
    _require(".." not in Path(root).parts, "Synthetic forensics requires a new checkout-local root")
    root = checked_path(root)
    allowed = checked_path(CHECKOUT_ROOT / "tmp")
    _require(root != allowed and root.is_relative_to(allowed) and not root.exists(),
             "Synthetic forensics requires a new checkout-local root")
    checkout, clean = workspace_metadata(CHECKOUT_ROOT)
    _require(re.fullmatch(r"[0-9a-f]{40}", checkout)
             and not (CHECKOUT_ROOT / ".git" / "objects" / "info" / "alternates").exists())
    frozen_sha = _frozen_definition()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    cases = []
    for scope in scopes:
        for trial in range(1, trials + 1):
            case = _run_case(root / f"case-{len(cases) + 1:03d}", scope, observed, child_timeout)
            cases.append({"case": len(cases) + 1, "scope": scope, "trial": trial, **case})
    all_passed = all(case["status"] == "PASS" for case in cases)
    report = {
        "schema": 1, "repository": REPOSITORY, "data_kind": "synthetic",
        "checkout_head": checkout, "working_tree_clean": clean,
        "source_head": source_head if source_head is not None else
        None if os.environ.get("GITHUB_EVENT_NAME") == "pull_request" else checkout,
        "source_declaration": "operator_declared" if source_head is not None else
        "unavailable_pr_source" if os.environ.get("GITHUB_EVENT_NAME") == "pull_request"
        else "checkout_source",
        "frozen_function_sha256": frozen_sha, "frozen_function_matches_checkout": True,
        "conditions": {"trials_per_scope": trials, "scopes": list(scopes),
                       "child_timeout_seconds": child_timeout, "sequential_children": True,
                       "observer": "count_checkpoints" if observed else "post_exit_readonly",
                       "observer_affects_timing": observed, "existing_root_reused": False,
                       "external_ai_connections": 0, "paid_api_calls": 0},
        "result": "synthetic_comparisons_passed" if all_passed else "synthetic_comparison_failed",
        "historical_10k": {"status": "OPEN", "gate": "BLOCKED", "root_cause_resolved": False,
                           "reason": "not_reproduced_root_cause_unresolved" if all_passed else
                           "comparison_failed_root_cause_unresolved"},
        "official_v1": "BLOCKED", "cases": cases,
    }
    _write_report(root / "report.json", report)
    return report


def main():
    parser = PrivateArgumentParser(description="Bounded unchanged synthetic 10k comparisons")
    parser.add_argument("--root", type=Path, help="New directory under this checkout's tmp")
    parser.add_argument("--scopes", nargs="+", default=("single", "related", "full"))
    parser.add_argument("--trials", type=int, default=1, help="1..3 trials per selected scope")
    parser.add_argument("--timeout", type=int, default=150, help="10..180 seconds per owned child")
    parser.add_argument("--source-head", help="Optional independently checked 40-character source SHA")
    parser.add_argument("--unobserved", action="store_true", help="Post-exit read-only counts only")
    parser.add_argument("--child-root", type=Path, help="Child-process entrypoint", default=None)
    parser.add_argument("--scope", default="single", help="Child-process scope")
    args = parser.parse_args()
    try:
        if args.child_root is not None:
            raise SystemExit(_child(args.child_root, args.scope, not args.unobserved))
        root = args.root or CHECKOUT_ROOT / "tmp" / "data-forensics" / uuid.uuid4().hex
        report = run_forensics(root, scopes=args.scopes, trials=args.trials,
                               observed=not args.unobserved, child_timeout=args.timeout,
                               source_head=args.source_head)
    except (OSError, ValueError, sqlite3.Error, subprocess.SubprocessError, KeyboardInterrupt):
        print("Synthetic forensics refused or failed. Historical 10k gate remains BLOCKED.",
              file=sys.stderr)
        raise SystemExit(1) from None
    print("Synthetic comparisons completed. Historical 10k root cause remains unresolved/BLOCKED.")
    raise SystemExit(0 if report["result"] == "synthetic_comparisons_passed" else 1)


if __name__ == "__main__":
    main()
