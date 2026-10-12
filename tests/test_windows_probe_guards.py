"""Actual Windows helper checks. These do not supply owner-machine evidence."""

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from nexus.machine_check import powershell
from nexus.private_storage import checked_path

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Actual Windows token/junction inspection")


def test_windows_operator_helper_emits_only_standard_token_classification():
    repo = Path(__file__).resolve().parents[1]
    executable = shutil.which("pwsh") or shutil.which("powershell")
    assert executable, "Windows inspection tool must be available"
    result = subprocess.run(
        [executable, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
         str(repo / "scripts" / "Inspect-TestOperator.ps1")], capture_output=True, check=False,
        timeout=30,
    )
    assert result.stderr == b"", "Operator helper must not log private diagnostics"
    data = json.loads(result.stdout.decode("utf-8-sig"))
    assert set(data) == {"standard_user"} and type(data["standard_user"]) is bool
    assert result.returncode == (0 if data["standard_user"] else 1)


def test_windows_acl_helper_refuses_junction_without_changing_target():
    repo = Path(__file__).resolve().parents[1]
    root = checked_path(repo / "tmp" / "windows-evidence" / uuid.uuid4().hex)
    root.mkdir(parents=True, exist_ok=False)
    target = root / "target"
    target.mkdir()
    sentinel = target / "synthetic-sentinel"
    sentinel.write_bytes(b"unchanged")
    link = root / "redirect"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                            capture_output=True, check=False, timeout=10)
    assert result.returncode == 0, "Synthetic NTFS junction creation must succeed"
    try:
        with pytest.raises(ValueError, match="inspection"):
            powershell(repo, "Inspect-TestDirectory.ps1", "-Directory", str(link), "-Protect")
        assert sentinel.read_bytes() == b"unchanged"
        assert sorted(p.name for p in target.iterdir()) == ["synthetic-sentinel"]
    finally:
        # Remove only our new junction, never its target or any existing data.
        link.rmdir()
