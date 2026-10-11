"""Local synthetic evidence. No account access, network reconfiguration or private profiles."""

import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from nexus.cli import PrivateArgumentParser
from nexus.maintenance import copy_database
from nexus.private_storage import checked_path
from nexus.store import Store

REPOSITORY = "Iam-2squared/ark-nexus"
GATES = ("cold_start", "owned_loopback_listener", "owner_auth", "host_origin_csrf",
         "synthetic_import_search", "restart_persistence", "backup_restore_new_path",
         "owned_test_acl", "offline_cold_start", "owner_browser_ui", "other_os_user_denied",
         "private_profile_acl", "real_chatgpt_format", "real_claude_format")
STATUSES = {"PASS", "FAIL", "SKIP", "NOT RUN"}
REASONS = {"verified", "check_failed", "not_attempted", "windows_required",
           "operator_required", "approved_sample_required", "operator_attested", "interrupted"}


def new_report(head: str, clean: bool, context: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", head) or type(clean) is not bool:
        raise ValueError("Invalid public revision metadata")
    if context not in {"github_runner", "owner_windows", "test_harness"}:
        raise ValueError("Invalid evidence context")
    return {"schema": "nexus-machine-evidence-1", "repository": REPOSITORY, "head": head,
            "working_tree_clean": clean, "context": context,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "data_kind": "synthetic", "official_v1": "BLOCKED",
            "gates": {gate: {"status": "NOT RUN", "reason": "not_attempted"} for gate in GATES}}


def record(report: dict, gate: str, status: str, reason: str = "verified") -> None:
    # Error messages, values, paths, SIDs and raw responses cannot enter evidence.
    if gate not in GATES or status not in STATUSES or reason not in REASONS:
        raise ValueError("Invalid evidence classification")
    report["gates"][gate] = {"status": status, "reason": reason}


def _command(repo: Path, *args: str) -> str:
    # An inherited Git context must not redirect even an index refresh outside
    # this checkout. These metadata reads never need account/network variables.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False,
                            timeout=10, env=environment)
    if result.returncode:
        raise ValueError("Repository identity unavailable")
    return result.stdout.decode("utf-8").strip()


def workspace_metadata(repo: Path) -> tuple[str, bool]:
    repo = checked_path(repo)
    git_directory = checked_path(repo / ".git")
    if git_directory.exists() and not git_directory.is_dir():
        raise ValueError("Repository workspace must contain its own Git directory")
    remote = _command(repo, "config", "--get", "remote.origin.url")
    if remote not in {"https://github.com/" + REPOSITORY + ".git",
                      "https://github.com/" + REPOSITORY,
                      "git@github.com:" + REPOSITORY + ".git"}:
        raise ValueError("Repository identity mismatch")
    if Path(_command(repo, "rev-parse", "--show-toplevel")).absolute() != repo:
        raise ValueError("Repository workspace root mismatch")
    if not git_directory.is_dir():
        raise ValueError("Repository workspace Git directory unavailable")
    return _command(repo, "rev-parse", "HEAD"), not bool(_command(repo, "status", "--porcelain"))


def powershell(repo: Path, script: str, *arguments: str) -> dict:
    fields = {"Inspect-TestDirectory.ps1": {"allowlist_only", "owner_allowed", "protected_root"},
              "Inspect-TestListener.ps1": {"owned_loopback_only"},
              "Inspect-TestOperator.ps1": {"standard_user"}}
    if script not in fields:
        raise ValueError("Windows inspection not allowlisted")
    script_path = checked_path(repo / "scripts" / script)
    if not script_path.is_file():
        raise ValueError("Windows inspection unavailable")
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if not executable:
        raise ValueError("Windows inspection unavailable")
    result = subprocess.run([executable, "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                             "Bypass", "-File",
                             str(script_path), *arguments],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30, check=False)
    if result.returncode:
        raise ValueError("Windows inspection failed")
    if len(result.stdout) > 4096:
        raise ValueError("Windows inspection result too large")
    data = json.loads(result.stdout.decode("utf-8-sig"))
    if (type(data) is not dict or set(data) != fields[script]
            or any(type(value) is not bool for value in data.values())):
        raise ValueError("Invalid Windows inspection classification")
    return data


def request(path: str, key: str = "", method: str = "GET", body: bytes | None = None,
            extra: dict | None = None) -> tuple[int, dict]:
    # A literal loopback destination, no env proxy, redirects, remote DNS or raw logging.
    connection = http.client.HTTPConnection("127.0.0.1", 8788, timeout=2)
    headers = {"Authorization": "Bearer " + key} if key else {}
    headers.update(extra or {})
    try:
        connection.request(method, "/api/v1" + path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read(64 * 1024 + 1)
        if len(payload) > 64 * 1024:
            raise ValueError("Unexpected test response size")
        return response.status, json.loads(payload)
    finally:
        connection.close()


def _start(repo: Path, profile: Path) -> subprocess.Popen:
    with socket.socket() as port:
        port.bind(("127.0.0.1", 8788))  # Busy port: refuse; never use/terminate another service.
    environment = os.environ.copy()
    environment.pop("NEXUS_API_TOKEN", None)
    environment["NEXUS_DATA_DIR"] = str(profile)
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "nexus.api:app", "--host", "127.0.0.1",
         "--port", "8788", "--workers", "1", "--no-access-log", "--no-proxy-headers",
         "--log-level", "critical"], cwd=repo, env=environment,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise ValueError("Test server did not start")
            try:
                status, data = request("/health")
                if status == 200 and data.get("mode") == "synthetic_fixture_only":
                    return process
            except (OSError, ValueError):
                pass
            time.sleep(0.1)
        raise ValueError("Test server did not become ready")
    except BaseException:
        # Startup has not returned the child to run_probe yet. Ctrl+C must not
        # leave that child running; re-raise after cleaning up only our process.
        _stop(process)
        raise


def _stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _expect(condition: bool) -> None:
    if not condition:
        raise ValueError("Synthetic check failed")


def run_probe(repo: Path, root: Path, report: dict, offline_attested: bool = False) -> None:
    """root must be a new, empty directory owned by this invocation."""
    process = None
    gate = "owned_test_acl"
    try:
        if os.name == "nt":
            acl = powershell(repo, "Inspect-TestDirectory.ps1", "-Directory", str(root), "-Protect")
            _expect(acl["allowlist_only"] and acl["owner_allowed"] and acl["protected_root"])
        else:
            record(report, gate, "SKIP", "windows_required")
        # Windows mkdir(0o700) installs a separate user/admin DACL instead of
        # inheriting the root's reviewed user/SYSTEM/admin rules. Precreate ONLY
        # these new empty synthetic children after root protection, retaining the
        # exact same required grants; normal application storage is not changed.
        for name in ("profile", "backup", "restored"):
            checked_path(root / name).mkdir(mode=0o777 if os.name == "nt" else 0o700)
        gate = "cold_start"
        profile = root / "profile"
        process = _start(repo, profile)
        record(report, gate, "PASS")
        if offline_attested and report["context"] == "owner_windows":
            record(report, "offline_cold_start", "PASS", "operator_attested")
        gate = "owned_loopback_listener"
        if os.name == "nt":
            _expect(powershell(repo, "Inspect-TestListener.ps1", "-ProcessId",
                               str(process.pid))["owned_loopback_only"])
            record(report, gate, "PASS")
        else:
            record(report, gate, "SKIP", "windows_required")
        key = (profile / "nexus-access.key").read_text(encoding="ascii").strip()
        gate = "owner_auth"
        _expect(request("/overview")[0] == 401)
        _expect(request("/overview", key)[0] == 200)
        record(report, gate, "PASS")
        gate = "host_origin_csrf"
        _expect(request("/overview", key, extra={"Host": "foreign.invalid:8788"})[0] == 403)
        _expect(request("/overview", key, extra={"Origin": "https://foreign.invalid"})[0] == 403)
        _expect(request("/projects", key, "POST", b'{"name":"synthetic"}',
                        {"Content-Type": "application/json"})[0] == 403)
        record(report, gate, "PASS")
        gate = "synthetic_import_search"
        fixture = {"nexus_fixture": "synthetic-v1", "provider": "chatgpt", "conversations": [
            {"id": "probe-conversation", "title": "synthetic", "messages": [
                {"id": "probe-message", "role": "user", "text": "日本語の合成検証", "created_at": None}
            ]}]}
        boundary = "nexus-owned-synthetic-boundary"
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="provider"\r\n\r\nchatgpt\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="account_alias"\r\n\r\nprobe\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.json"\r\n'
                'Content-Type: application/json\r\n\r\n').encode("ascii")
        body += json.dumps(fixture, ensure_ascii=False).encode("utf-8")
        body += f"\r\n--{boundary}--\r\n".encode("ascii")
        headers = {"X-Nexus-Request": "1", "Content-Type": "multipart/form-data; boundary=" + boundary}
        _expect(request("/imports", key, "POST", body, headers)[0] == 201)
        _expect(request("/search?q=%E6%97%A5%E6%9C%AC%E8%AA%9E", key)[1]["total"] == 1)
        _expect(request("/imports", key, "POST", body, headers)[1]["counts"]["messages_inserted"] == 0)
        record(report, gate, "PASS")
        _stop(process)
        process = None
        gate = "restart_persistence"
        process = _start(repo, profile)
        _expect((profile / "nexus-access.key").read_text(encoding="ascii").strip() == key)
        _expect(request("/overview", key)[1]["counts"]["messages"] == 1)
        _expect(request("/integrity", key)[1]["ok"] is True)
        record(report, gate, "PASS")
        _stop(process)
        process = None
        gate = "backup_restore_new_path"
        backup = root / "backup" / "nexus.sqlite3"
        restored = root / "restored" / "nexus.sqlite3"
        copy_database(profile / "nexus.sqlite3", backup)
        copy_database(backup, restored)
        store = Store(restored)
        _expect(store.overview()["counts"]["messages"] == 1 and store.integrity_report()["ok"])
        process = _start(repo, restored.parent)
        restored_key = (restored.parent / "nexus-access.key").read_text(encoding="ascii").strip()
        _expect(request("/overview", restored_key)[1]["counts"]["messages"] == 1)
        _expect(request("/integrity", restored_key)[1]["ok"] is True)
        _stop(process)
        process = None
        record(report, gate, "PASS")
        gate = "owned_test_acl"
        if os.name == "nt":
            for path in (root, profile / "nexus-access.key", profile / "nexus.sqlite3", backup,
                         restored, restored.parent / "nexus-access.key"):
                result = powershell(repo, "Inspect-TestDirectory.ps1", "-Directory", str(path))
                _expect(result["allowlist_only"] and result["owner_allowed"])
            record(report, gate, "PASS")
    except KeyboardInterrupt:
        record(report, gate, "FAIL", "interrupted")
    except Exception:
        record(report, gate, "FAIL", "check_failed")
    finally:
        if process is not None:
            _stop(process)
        for name in ("owner_browser_ui", "other_os_user_denied", "private_profile_acl"):
            record(report, name, "NOT RUN", "operator_required")
        if report["gates"]["offline_cold_start"]["status"] == "NOT RUN":
            record(report, "offline_cold_start", "NOT RUN", "operator_required")
        for name in ("real_chatgpt_format", "real_claude_format"):
            record(report, name, "NOT RUN", "approved_sample_required")


def main() -> None:
    try:
        parser = PrivateArgumentParser(description="New-directory synthetic local evidence only")
        parser.add_argument("--offline-attested", action="store_true")
        args = parser.parse_args()
        repo = Path(__file__).absolute().parents[2]
        head, clean = workspace_metadata(repo)  # Validate before creating any files.
        context = ("github_runner" if os.environ.get("GITHUB_ACTIONS") == "true"
                   else "owner_windows" if os.name == "nt" else "test_harness")
        if not clean and context != "github_runner":
            raise ValueError("Owner evidence requires a clean reviewed checkout")
        if context == "owner_windows":
            _expect(powershell(repo, "Inspect-TestOperator.ps1")["standard_user"] is True)
        report = new_report(head, clean, context)
        root = checked_path(repo / "tmp" / "windows-evidence" / uuid.uuid4().hex)
        root.mkdir(mode=0o700, parents=True, exist_ok=False)
        run_probe(repo, root, report, args.offline_attested)
        with (root / "report.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=True, indent=2)
        print("Evidence: " + root.relative_to(repo).as_posix() + "/report.json")
        raise SystemExit(1 if any(g["status"] == "FAIL" for g in report["gates"].values()) else 0)
    except (OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt):
        print("Synthetic evidence check refused or failed; no private details logged.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
