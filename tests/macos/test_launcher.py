import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "scripts" / "aerosol"


def invoke(*args):
    return subprocess.run(["bash", str(LAUNCHER), *args], capture_output=True, text=True, timeout=10)


def test_native_guest_is_isolated_and_does_not_install_a_second_container_runtime():
    result = invoke("config")
    assert result.returncode == 0, result.stderr
    config = yaml.safe_load(result.stdout)
    assert config["vmType"] == "vz"
    assert config["arch"] == "aarch64"
    assert config["mounts"] == []
    assert "base" not in config
    assert config["containerd"] == {"system": False, "user": False}
    assert config["ssh"]["forwardAgent"] is False
    assert config["rosetta"]["enabled"] is False
    assert all(image["digest"].startswith("sha256:") for image in config["images"])
    assert config["portForwards"][0]["hostIP"] == "127.0.0.1"
    assert config["portForwards"][-1]["ignore"] is True
    assert config["portForwards"][-1]["guestPortRange"] == [1, 65535]


def test_resource_and_port_overrides():
    result = invoke("config", "--cpus", "6", "--memory", "8", "--disk", "80", "--port", "9080")
    assert result.returncode == 0, result.stderr
    config = yaml.safe_load(result.stdout)
    assert config["cpus"] == 6
    assert config["memory"] == "8GiB"
    assert config["disk"] == "80GiB"
    assert config["portForwards"][0]["guestPort"] == 8080
    assert config["portForwards"][0]["hostPort"] == 9080


@pytest.mark.parametrize(
    "args",
    [
        ("--cpus", "0"),
        ("--memory", "0"),
        ("--disk", "19"),
        ("--port", "80"),
        ("--port", "65536"),
        ("--cpus", "1;echo injected"),
        ("--memory", "08"),
        ("--port",),
        ("--unknown", "yes"),
    ],
)
def test_bad_options_fail_before_any_vm_action(args):
    result = invoke("config", *args)
    assert result.returncode != 0
    assert "Error:" in result.stderr


def test_no_destructive_lifecycle_command():
    result = invoke("delete")
    assert result.returncode != 0
    assert "Unknown command" in result.stderr
