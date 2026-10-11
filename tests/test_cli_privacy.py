import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("module", ["nexus.maintenance", "nexus.machine_check"])
def test_invalid_cli_arguments_do_not_echo_private_values(module, tmp_path):
    marker = "PRIVATE-SYNTHETIC-CLI-ARGUMENT"
    arguments = ([str(tmp_path / "source"), str(tmp_path / "destination")]
                 if module == "nexus.maintenance" else [])
    result = subprocess.run([sys.executable, "-m", module, *arguments, "--" + marker],
                            cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 2
    assert marker not in result.stdout + result.stderr
    assert str(tmp_path) not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert not list(tmp_path.iterdir())
