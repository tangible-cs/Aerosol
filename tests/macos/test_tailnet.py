"""Safety boundaries for the optional host Tailscale bridge."""

import importlib.util
import io
import sqlite3
from pathlib import Path

import pytest

from compute_space.config import load_config
from compute_space.core.domains import Domain
from compute_space.core.domains import primary_domain
from compute_space.core.domains import seed_domains
from compute_space.db.schema import schema_path

SPEC = importlib.util.spec_from_file_location("aerosol_tailnet", Path(__file__).parents[2] / "macos/tailnet.py")
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_private_ipv4_required():
    assert (
        module.tailnet_domain({"BackendState": "Running", "Self": {"TailscaleIPs": ["100.93.27.24"]}})
        == "aerosol.100-93-27-24.sslip.io"
    )
    for address in ["127.0.0.1", "192.168.1.1", "8.8.8.8"]:
        with pytest.raises(ValueError):
            module.tailnet_domain({"BackendState": "Running", "Self": {"TailscaleIPs": [address]}})


def test_disconnected_tailnet_refused():
    with pytest.raises(ValueError):
        module.tailnet_domain({"BackendState": "Stopped"})


def test_funnel_and_conflicting_listeners_refused():
    module.check_serve({}, 8080)
    module.check_serve({"TCP": {"8080": {"TCPForward": "127.0.0.1:8080"}}}, 8080)
    module.check_serve({"TCP": {"443": {"HTTPS": True}}}, 8080)
    with pytest.raises(ValueError):
        module.check_serve({"AllowFunnel": {"mac:443": True}}, 8080)
    with pytest.raises(ValueError):
        module.check_serve({"TCP": {"8080": {"TCPForward": "localhost:9999"}}}, 8080)
    with pytest.raises(ValueError):
        module.check_serve({"Services": {"svc:test": {"AllowFunnel": {"mac:443": True}}}}, 8080)


def test_listener_check_allows_idempotent_tailnet_bridge_but_rejects_lan():
    module.check_listeners(
        ["127.0.0.1:8080", "100.93.27.24:8080", "[fd7a::1]:8080"], ["100.93.27.24", "fd7a::1"], 8080
    )
    for address in ["*:8080", "0.0.0.0:8080", "192.168.1.2:8080"]:
        with pytest.raises(ValueError):
            module.check_listeners(["127.0.0.1:8080", address], ["100.93.27.24"], 8080)


def test_open_setup_blocks_exposure(monkeypatch):
    class OpenSetup:
        def open(self, url, **kwargs):
            return io.BytesIO(b'{"status":"ok"}')

    monkeypatch.setattr(module.urllib.request, "build_opener", lambda *_: OpenSetup())
    with pytest.raises(ValueError, match="not protected"):
        module.verify_setup(8080, "http://example/setup?claim=secret")


def test_guest_claim_policy_and_domain_survive_repeated_configuration(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "tailnet_guest", Path(__file__).parents[2] / "macos/tailnet-guest.py"
    )
    guest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guest)
    path = tmp_path / "config.toml"
    original = '[openhost]\nclaim_token_required = false\ndata_root_dir = "' + str(tmp_path) + '"\n'
    path.write_text(original)
    monkeypatch.setenv("OPENHOST_ROUTER_CONFIG", str(path))
    config = load_config()
    Path(config.db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.db_path) as db:
        db.row_factory = sqlite3.Row
        db.executescript(Path(schema_path()).read_text())
        seed_domains(db, Domain("lvh.me:8080"), [])
    first = guest.configure("aerosol.100-93-27-24.sslip.io:8080")
    assert "?claim=" in first
    assert guest.configure("aerosol.100-93-27-24.sslip.io:8080") == first
    assert load_config().claim_token_required is True
    assert path.with_suffix(".before-tailnet.toml").read_text() == original
    with sqlite3.connect(config.db_path) as db:
        db.row_factory = sqlite3.Row
        assert primary_domain(db).name == "aerosol.100-93-27-24.sslip.io:8080"
        assert db.execute("SELECT COUNT(*) FROM domains").fetchone()[0] == 2
        assert Domain.match(db, "app.aerosol.100-93-27-24.sslip.io:8080") == primary_domain(db)
    with sqlite3.connect(config.db_path + ".before-tailnet") as db:
        db.row_factory = sqlite3.Row
        assert primary_domain(db).name == "lvh.me:8080"
