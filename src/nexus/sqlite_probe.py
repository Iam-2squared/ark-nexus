"""Opt-in, checkout-local synthetic SQLite evidence; private imports stay blocked."""

import _sqlite3
import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
import uuid
import warnings
from contextlib import closing
from pathlib import Path

from nexus.cli import PrivateArgumentParser
from nexus.machine_check import workspace_metadata
from nexus.private_storage import checked_path, configure_memory_temp
from nexus.sqlite_evidence import evidence_object, validate_native
from nexus.sqlite_workload import DEFAULT_ROWS, MAX_ROWS, ProbeProblem, require, run_workload

_CHECKOUT_ROOT = Path(__file__).absolute().parents[2]
SCHEMA = "nexus.sqlite-statement-evidence.v1"


def runtime_info() -> dict:
    with closing(sqlite3.connect(":memory:")) as db:
        options = sorted(row[0] for row in db.execute("PRAGMA compile_options"))
        configure_memory_temp(db)
        memory_temp = db.execute("PRAGMA temp_store").fetchone()[0]
    safe_options = [value for value in options
                    if re.fullmatch(r"[A-Z0-9_]+(?:=[A-Za-z0-9_.+-]+)?", value)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        module_version = getattr(sqlite3, "version", "unavailable")
    return {"python": platform.python_version(), "os": platform.system(),
            "sqlite3_module_version": module_version, "sqlite_version": sqlite3.sqlite_version,
            "extension_kind": "dynamic_module" if hasattr(_sqlite3, "__file__") else "builtin",
            "module_absolute_path_recorded": False, "temp_store": memory_temp,
            "compile_options": safe_options, "omitted_compile_option_count":
            len(options) - len(safe_options)}


def checked_root(root: Path, *, must_exist: bool = False) -> Path:
    if ".." in root.parts:
        raise ProbeProblem("A new checkout-local synthetic SQLite directory is required")
    root = checked_path(root)
    allowed = checked_path(_CHECKOUT_ROOT / "tmp")
    if root == allowed or not root.is_relative_to(allowed):
        raise ProbeProblem("A new checkout-local synthetic SQLite directory is required")
    if must_exist:
        require(root.is_dir())
    elif root.exists():
        raise ProbeProblem("A new checkout-local synthetic SQLite directory is required")
    return root


def native_subprocess(root: Path, rows: int) -> dict:
    environment = dict(os.environ)
    temporary = root / "native-temp"
    temporary.mkdir(mode=0o700, exist_ok=False)
    # Only this disposable child's environment changes, before sqlite3 is imported.
    for variable in ("SQLITE_TMPDIR", "TMPDIR", "TMP", "TEMP"):
        environment[variable] = str(temporary)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("PYTHONFAULTHANDLER", None)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "nexus.sqlite_probe", "--native-child",
             "--root", str(root), "--rows", str(rows)],
            env=environment, cwd=_CHECKOUT_ROOT, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60, check=False,
        )
        if result.returncode != 0 or len(result.stdout) > 65536:
            raise ProbeProblem("Native SQLite synthetic observation failed")
        native = json.loads(result.stdout, object_pairs_hook=evidence_object)
        validate_native(native, rows)
        return native
    except (subprocess.TimeoutExpired, ValueError, UnicodeError, OSError, RecursionError, TypeError):
        raise ProbeProblem("Native SQLite synthetic observation failed") from None


def run_probe(root: Path, *, rows: int = DEFAULT_ROWS, source_head: str | None = None) -> dict:
    if type(rows) is not int or not 32 <= rows <= MAX_ROWS:
        raise ProbeProblem("A bounded synthetic SQLite workload is required")
    if source_head is not None and (type(source_head) is not str
                                   or not re.fullmatch(r"[0-9a-f]{40}", source_head)):
        raise ProbeProblem("A verified source HEAD is required")
    root = checked_root(root)
    head, clean = workspace_metadata(_CHECKOUT_ROOT)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    runtime = runtime_info()
    logical = run_workload(root / "logical", rows=rows)
    native = native_subprocess(root, rows)
    report = {"schema": SCHEMA, "repository": "Iam-2squared/ark-nexus",
              "checkout_head": head, "working_tree_clean": clean,
              "source_head": source_head, "source_head_note": "verify_from_pr_not_merge_checkout",
              "data_kind": "synthetic", "official_v1": "BLOCKED", "runtime": runtime,
              "logical": logical, "native": native,
              "private_import_allowed": False, "os_settings_changed": False,
              "parent_temp_environment_changed": False}
    descriptor = os.open(root / "report.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY
                         | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=True, indent=2)
        output.write("\n")
    return report


def main() -> None:
    parser = PrivateArgumentParser(description="Bounded synthetic SQLite statement/native probe")
    parser.add_argument("--root", type=Path, help="New directory under this checkout's tmp")
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS, help="32..8192 synthetic rows")
    parser.add_argument("--source-head", help="40-character source HEAD; verify against the PR")
    parser.add_argument("--native-child", action="store_true", help="Internal disposable child")
    args = parser.parse_args()
    try:
        if args.native_child:
            if args.root is None or not 32 <= args.rows <= MAX_ROWS:
                raise ProbeProblem("Native SQLite synthetic observation failed")
            root = checked_root(args.root, must_exist=True)
            # A child accepts only the parent's new empty native-temp; no existing DB input.
            temporary = checked_path(root / "native-temp")
            require(temporary.is_dir() and not any(temporary.iterdir())
                    and {path.name for path in root.iterdir()} <= {"logical", "native-temp"}
                    and all(os.environ.get(variable) == str(temporary)
                            for variable in ("SQLITE_TMPDIR", "TMPDIR", "TMP", "TEMP")))
            from nexus._sqlite_vfs_probe import capture

            report = capture(root, args.rows)
        else:
            root = args.root or _CHECKOUT_ROOT / "tmp" / "sqlite-evidence" / uuid.uuid4().hex
            report = run_probe(root, rows=args.rows, source_head=args.source_head)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    except (Exception, KeyboardInterrupt):
        print("Synthetic SQLite probe refused or failed. Private imports remain blocked.",
              file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
