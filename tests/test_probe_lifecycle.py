"""Synthetic interruption/scope regressions; no user profile or unrelated process."""

import json
import socket
from pathlib import Path

import pytest

from nexus import machine_check


class Child:
    pid = 12345

    def poll(self):
        return None


def interrupt(*_args, **_kwargs):
    raise KeyboardInterrupt("PRIVATE-SYNTHETIC-INTERRUPTION")


def test_cold_start_interrupt_stops_child_even_before_ready(tmp_path, monkeypatch):
    child = Child()
    stopped = []
    monkeypatch.setattr(machine_check.subprocess, "Popen", lambda *_a, **_k: child)
    monkeypatch.setattr(machine_check, "request", interrupt)
    monkeypatch.setattr(machine_check, "_stop", stopped.append)
    with pytest.raises(KeyboardInterrupt):
        machine_check._start(tmp_path, tmp_path / "profile")
    assert stopped == [child], "Interrupted startup must stop only its own child"


def test_probe_interrupt_is_fixed_failure_and_unattempted_gates_remain_not_run(
    tmp_path, monkeypatch,
):
    root = tmp_path / "owned"
    root.mkdir()
    report = machine_check.new_report("a" * 40, True, "test_harness")
    monkeypatch.setattr(machine_check, "_start", interrupt)
    monkeypatch.setattr(machine_check, "powershell", lambda *_a: {
        "allowlist_only": True, "owner_allowed": True, "protected_root": True,
    })
    try:
        machine_check.run_probe(tmp_path, root, report)
    except KeyboardInterrupt:
        pytest.fail("Probe interruption escaped the fixed evidence boundary")
    assert report["gates"]["cold_start"] == {"status": "FAIL", "reason": "interrupted"}
    assert report["gates"]["synthetic_import_search"]["status"] == "NOT RUN"
    assert report["gates"]["restart_persistence"]["status"] == "NOT RUN"
    assert report["official_v1"] == "BLOCKED"
    assert "PRIVATE-SYNTHETIC" not in json.dumps(report)


def test_preflight_interrupt_has_no_traceback_or_private_values(monkeypatch, capsys):
    monkeypatch.setattr(machine_check.sys, "argv", ["nexus.machine_check"])
    monkeypatch.setattr(machine_check, "workspace_metadata", interrupt)
    try:
        with pytest.raises(SystemExit) as result:
            machine_check.main()
    except KeyboardInterrupt:
        pytest.fail("Preflight interruption escaped the redacted CLI boundary")
    output = capsys.readouterr()
    assert result.value.code == 1
    assert "PRIVATE-SYNTHETIC" not in output.out + output.err
    assert "Traceback" not in output.out + output.err
    assert str(Path.home()) not in output.out + output.err


def test_workspace_root_mismatch_rejected_before_new_files(tmp_path, monkeypatch):
    repo = tmp_path / "nexus"
    repo.mkdir()
    (repo / ".git").mkdir()

    def command(_repo, *args):
        if args == ("config", "--get", "remote.origin.url"):
            return "https://github.com/Iam-2squared/ark-nexus.git"
        if args == ("rev-parse", "--show-toplevel"):
            return str(tmp_path / "unrelated")
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        return ""

    monkeypatch.setattr(machine_check, "_command", command)
    with pytest.raises(ValueError, match="workspace"):
        machine_check.workspace_metadata(repo)
    assert sorted(p.name for p in repo.iterdir()) == [".git"]


def test_git_metadata_commands_ignore_inherited_context_and_disable_index_writes(
    tmp_path, monkeypatch,
):
    captured = {}
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "unrelated"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "private"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "private-index"))

    class Result:
        returncode = 0
        stdout = b"synthetic"

    def run(*_args, **kwargs):
        captured.update(kwargs)
        return Result()

    monkeypatch.setattr(machine_check.subprocess, "run", run)
    assert machine_check._command(tmp_path, "status", "--porcelain") == "synthetic"
    assert captured["env"]["GIT_OPTIONAL_LOCKS"] == "0"
    assert not {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"} & captured["env"].keys()


def test_occupied_port_refuses_without_starting_or_stopping_process(tmp_path, monkeypatch):
    def unexpected(*_a, **_k):
        pytest.fail("A busy port must not start or stop any process")

    monkeypatch.setattr(machine_check.subprocess, "Popen", unexpected)
    monkeypatch.setattr(machine_check, "_stop", unexpected)
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 8788))
        occupied.listen()
        with pytest.raises(OSError):
            machine_check._start(tmp_path, tmp_path / "profile")
    assert not (tmp_path / "profile").exists()


def test_dirty_owner_checkout_refused_before_test_files(monkeypatch, capsys):
    monkeypatch.setattr(machine_check.sys, "argv", ["nexus.machine_check"])
    monkeypatch.setenv("GITHUB_ACTIONS", "false")
    monkeypatch.setattr(machine_check, "workspace_metadata", lambda *_a: ("a" * 40, False))

    def unexpected(*_a, **_k):
        pytest.fail("Dirty owner checkout must not create a probe or call inspection scripts")

    monkeypatch.setattr(machine_check, "run_probe", unexpected)
    monkeypatch.setattr(machine_check, "powershell", unexpected)
    monkeypatch.setattr(machine_check.uuid, "uuid4", unexpected)
    with pytest.raises(SystemExit) as result:
        machine_check.main()
    assert result.value.code == 1
    assert "Evidence:" not in capsys.readouterr().out


def test_external_git_directory_pointer_refused_before_commands(tmp_path, monkeypatch):
    (tmp_path / ".git").write_text("gitdir: PRIVATE-SYNTHETIC-EXTERNAL", encoding="utf-8")
    before = (tmp_path / ".git").read_bytes()

    def unexpected(*_a, **_k):
        pytest.fail("A Git directory pointer must not invoke Git")

    monkeypatch.setattr(machine_check, "_command", unexpected)
    with pytest.raises(ValueError, match="workspace"):
        machine_check.workspace_metadata(tmp_path)
    assert (tmp_path / ".git").read_bytes() == before


@pytest.mark.parametrize("failure", [PermissionError("PRIVATE-SYNTHETIC-PATH"),
                                    ValueError("PRIVATE-SYNTHETIC-ACL")],
                         ids=["permission", "inspection"])
def test_probe_permission_failure_is_redacted_and_does_not_touch_sentinel(
    tmp_path, monkeypatch, failure,
):
    root = tmp_path / "owned"
    root.mkdir()
    sentinel = tmp_path / "unrelated-synthetic-file"
    sentinel.write_bytes(b"unchanged")

    def refused(*_a, **_k):
        raise failure

    monkeypatch.setattr(machine_check, "_start", refused)
    monkeypatch.setattr(machine_check, "powershell", lambda *_a: {
        "allowlist_only": True, "owner_allowed": True, "protected_root": True,
    })
    report = machine_check.new_report("a" * 40, True, "test_harness")
    machine_check.run_probe(tmp_path, root, report)
    assert report["gates"]["cold_start"] == {"status": "FAIL", "reason": "check_failed"}
    assert "PRIVATE-SYNTHETIC" not in json.dumps(report)
    assert sentinel.read_bytes() == b"unchanged"


@pytest.mark.parametrize("payload", [
    b'{"owned_loopback_only":"false"}', b'{"owned_loopback_only":1}',
    b'{"owned_loopback_only":true,"private_path":"PRIVATE-SYNTHETIC"}', b'{}',
])
def test_windows_inspection_rejects_non_boolean_or_unallowlisted_results(monkeypatch, payload):
    repo = Path(__file__).resolve().parents[1]

    class Result:
        returncode = 0
        stdout = payload

    monkeypatch.setattr(machine_check.shutil, "which", lambda *_a: "synthetic-inspector")
    monkeypatch.setattr(machine_check.subprocess, "run", lambda *_a, **_k: Result())
    with pytest.raises(ValueError, match="inspection"):
        machine_check.powershell(repo, "Inspect-TestListener.ps1", "-ProcessId", "12345")
