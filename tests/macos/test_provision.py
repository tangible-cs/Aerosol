import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_provisioner_can_use_the_exact_bundled_checkout():
    result = subprocess.run(["bash", str(ROOT / "scripts/provision.sh"), "--help"], capture_output=True, text=True)
    assert "--use-existing-checkout" in result.stdout
    source = (ROOT / "scripts/provision.sh").read_text()
    assert 'if [ "$USE_EXISTING_CHECKOUT" = "true" ]; then' in source
    assert 'git -C "$OPENHOST_DIR" rev-parse --verify HEAD' in source


def test_guest_installer_refuses_to_run_on_macos_before_doing_anything():
    result = subprocess.run(["bash", str(ROOT / "macos/provision-guest.sh"), "8080"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "Ubuntu guest" in result.stderr
