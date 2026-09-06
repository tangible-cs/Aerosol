import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def executable(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/bash\nset -eu\n" + text)
    path.chmod(0o755)


@pytest.fixture
def installation(tmp_path):
    launcher = tmp_path / "scripts/aerosol"
    launcher.parent.mkdir()
    shutil.copy(ROOT / "scripts/aerosol", launcher)
    state = tmp_path / ".aerosol"
    instance = state / "lima/aerosol"
    instance.mkdir(parents=True)
    (instance / "lima.yaml").write_text("vmType: vz\n")
    (state / "port").write_text("9080\n")
    executable(state / "tools/bin/limactl", 'printf "%s\\n" "$*" >> "$CALLS"\n')
    bin_dir = tmp_path / "bin"
    executable(bin_dir / "uname", 'if [[ "$1" == -s ]]; then echo Darwin; else echo arm64; fi\n')
    executable(bin_dir / "sw_vers", "echo 26.0\n")
    executable(bin_dir / "id", "echo 501\n")
    executable(bin_dir / "curl", 'printf "%s\\n" "$*" >> "$HTTP_CALLS"\n[[ "$*" == *":9080/health"* ]]\n')
    executable(bin_dir / "sleep", "exit 0\n")
    env = dict(
        os.environ,
        PATH=f"{bin_dir}:{os.environ['PATH']}",
        CALLS=str(tmp_path / "calls"),
        HTTP_CALLS=str(tmp_path / "http"),
    )
    return launcher, tmp_path, env


def run(installation, *args):
    launcher, _, env = installation
    return subprocess.run(["bash", str(launcher), *args], env=env, capture_output=True, text=True, timeout=10)


def test_restart_checks_health_after_owner_has_already_claimed_instance(installation):
    result = run(installation, "up")
    assert result.returncode == 0, result.stderr
    assert "http://lvh.me:9080/" in result.stdout
    _, root, _ = installation
    calls = (root / "calls").read_text()
    assert "start --tty=false aerosol" in calls
    assert "copy" not in calls
    assert not (root / ".aerosol/up.lock").exists()


def test_cannot_silently_change_resources_of_existing_vm(installation):
    result = run(installation, "up", "--memory", "8")
    assert result.returncode != 0
    assert "already exists" in result.stderr
    assert not (installation[1] / "calls").exists()


def test_stop_is_graceful_and_never_deletes_disk(installation):
    result = run(installation, "stop")
    assert result.returncode == 0, result.stderr
    assert (installation[1] / "calls").read_text() == "stop --tty=false aerosol\n"


def test_another_up_operation_is_not_interrupted(installation):
    (installation[1] / ".aerosol/up.lock").mkdir()
    result = run(installation, "up")
    assert result.returncode != 0
    assert "Another up operation" in result.stderr
    assert (installation[1] / ".aerosol/up.lock").exists()
    assert not (installation[1] / "calls").exists()
