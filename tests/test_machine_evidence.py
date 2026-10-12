import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from nexus.machine_check import GATES, new_report, record, workspace_metadata


@pytest.mark.parametrize("field", ["gate", "status", "reason"])
def test_evidence_classification_cannot_include_private_error_text(field):
    report = new_report("a" * 40, True, "test_harness")
    values = {"gate": "cold_start", "status": "FAIL", "reason": "check_failed"}
    values[field] = "PRIVATE-SYNTHETIC-SECRET"
    with pytest.raises(ValueError, match="classification"):
        record(report, **values)
    assert "PRIVATE-SYNTHETIC-SECRET" not in json.dumps(report)


@pytest.mark.parametrize("context", ["github_runner", "owner_windows", "test_harness"])
def test_unexecuted_owner_gates_and_real_formats_stay_not_run(context):
    report = new_report("a" * 40, True, context)
    assert report["official_v1"] == "BLOCKED"
    assert set(report["gates"]) == set(GATES)
    assert all(gate["status"] == "NOT RUN" for gate in report["gates"].values())


def test_evidence_workspace_mismatch_refused_before_writes(tmp_path, monkeypatch):
    from nexus import machine_check
    monkeypatch.setattr(machine_check, "_command", lambda *_args: "https://example.invalid/other.git")
    with pytest.raises(ValueError, match="mismatch"):
        workspace_metadata(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_local_synthetic_machine_probe_anonymizes_report_and_ignores_private_profile(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    private = tmp_path / "PRIVATE-SYNTHETIC-PROFILE"
    secret = "PRIVATE-SYNTHETIC-TOKEN-DO-NOT-LOG"
    env["NEXUS_DATA_DIR"] = str(private)
    env["NEXUS_API_TOKEN"] = secret
    # Deliberately treated as runner evidence even on a developer Windows machine.
    env["GITHUB_ACTIONS"] = "true"
    result = subprocess.run([sys.executable, "-m", "nexus.machine_check", "--offline-attested"],
                            cwd=repo, env=env, capture_output=True, text=True, timeout=180, check=False)
    assert result.returncode == 0, "Synthetic machine probe failed; inspect its redacted report"
    assert result.stderr == ""
    relative = result.stdout.strip().removeprefix("Evidence: ")
    assert relative.startswith("tmp/windows-evidence/") and relative.endswith("/report.json")
    evidence = (repo / relative).read_text(encoding="utf-8")
    report = json.loads(evidence)
    assert report["context"] == "github_runner"
    for name in ("cold_start", "owner_auth", "host_origin_csrf", "synthetic_import_search",
                 "restart_persistence", "backup_restore_new_path"):
        assert report["gates"][name]["status"] == "PASS", name
    for name in ("owned_test_acl", "owned_loopback_listener"):
        assert report["gates"][name]["status"] == ("PASS" if os.name == "nt" else "SKIP")
    for name in ("offline_cold_start", "owner_browser_ui", "other_os_user_denied", "private_profile_acl",
                 "real_chatgpt_format", "real_claude_format"):
        assert report["gates"][name]["status"] == "NOT RUN"
    assert not private.exists()
    for forbidden in (secret, str(private), str(tmp_path), str(Path.home()), "日本語の合成検証", "S-1-5-"):
        assert forbidden not in evidence + result.stdout + result.stderr
