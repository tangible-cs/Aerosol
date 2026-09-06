"""Opt-in, tailnet-only TCP bridge. Requires the signed-in Tailscale Mac app."""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".aerosol"
TAILSCALE = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"


def tailnet_domain(status: dict) -> str:
    if status.get("BackendState") != "Running":
        raise ValueError("Sign in to Tailscale and connect first")
    for address in status.get("Self", {}).get("TailscaleIPs", []):
        if ipaddress.ip_address(address) in ipaddress.ip_network("100.64.0.0/10"):
            return "aerosol." + address.replace(".", "-") + ".sslip.io"
    raise ValueError("No private Tailscale IPv4 address found")


def check_serve(config: dict, port: int) -> None:
    # Reject public exposure anywhere in the config, including named services.
    for key, value in config.items():
        if key == "AllowFunnel" and isinstance(value, dict) and any(value.values()):
            raise ValueError("Funnel is enabled on this Mac; disable it before enabling Aerosol")
        if isinstance(value, dict):
            check_serve(value, port)
    listener = config.get("TCP", {}).get(str(port))
    if listener is not None and listener != {"TCPForward": f"127.0.0.1:{port}"}:
        raise ValueError(f"Tailscale port {port} is already used by a different service")


def run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=120).stdout


def verify_setup(port: int, url: str) -> None:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _attempt in range(60):
        try:
            with opener.open(f"http://127.0.0.1:{port}/health", timeout=2) as response:
                if json.loads(response.read(4096)) == {"status": "ok"}:
                    break
        except (OSError, ValueError):
            pass
        time.sleep(1)
    else:
        raise ValueError("Router did not become healthy; tailnet access was not enabled")
    if "?claim=" in url:
        try:
            opener.open(f"http://127.0.0.1:{port}/setup", timeout=5).close()
        except urllib.error.HTTPError as error:
            if error.code == 403:
                claim_query = url.split("?", 1)[1]
                request = urllib.request.Request(f"http://127.0.0.1:{port}/setup?{claim_query}")
                with opener.open(request, timeout=5) as response:
                    if response.status == 200:
                        return
        raise ValueError("Unclaimed setup is not protected; tailnet access was not enabled")


def check_listeners(names: list[str], addresses: list[str], port: int) -> None:
    allowed = {f"127.0.0.1:{port}"}
    allowed.update(f"[{ip}]:{port}" if ":" in ip else f"{ip}:{port}" for ip in addresses)
    if f"127.0.0.1:{port}" not in names or not set(names).issubset(allowed):
        raise ValueError("Dashboard must listen only on loopback and this Mac's Tailscale IPs")


def main() -> None:
    if len(sys.argv) != 1:
        raise ValueError("Usage: ./scripts/aerosol tailnet")
    os.environ["LIMA_HOME"] = str(STATE / "lima")
    port = int((STATE / "port").read_text().strip())
    if not 1024 <= port <= 65535:
        raise ValueError("Invalid dashboard port")
    status = json.loads(run(TAILSCALE, "status", "--json"))
    domain = tailnet_domain(status)
    config = json.loads(run(TAILSCALE, "serve", "status", "--json"))
    check_serve(config, port)
    # A wildcard name is needed for application routing, not just the dashboard.
    expected_ip = domain.removeprefix("aerosol.").removesuffix(".sslip.io").replace("-", ".")
    for name in (domain, "probe." + domain):
        if set(socket.gethostbyname_ex(name)[2]) != {expected_ip}:
            raise ValueError(f"DNS for {name} must resolve only to {expected_ip}")
    # Verify the live Mac listener, not just the template used at VM creation.
    listeners = run("lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fn")
    names = [line[1:] for line in listeners.splitlines() if line.startswith("n")]
    check_listeners(names, status["Self"]["TailscaleIPs"], port)
    lima = str(STATE / "tools/bin/limactl")
    run(lima, "copy", str(ROOT / "macos/tailnet-guest.py"), "aerosol:/tmp/aerosol-tailnet.py")
    guest = (lima, "shell", "--workdir", "/tmp", "aerosol")
    if str(port) in config.get("TCP", {}):
        run(TAILSCALE, "serve", f"--tcp={port}", "off")
    # Stop before changing owner-claim policy; Serve is enabled only after restart.
    run(*guest, "sudo", "systemctl", "stop", "openhost")
    try:
        url = run(
            *guest,
            "sudo",
            "-iu",
            "host",
            "bash",
            "-c",
            "cd /home/host/openhost && "
            "OPENHOST_ROUTER_CONFIG=/home/host/.openhost/local_compute_space/config.toml "
            f"/home/host/.pixi/bin/pixi run python /tmp/aerosol-tailnet.py {domain}:{port}",
        ).strip()
    finally:
        run(*guest, "sudo", "systemctl", "start", "openhost")
    # Store the one-time setup URL privately, without printing the claim secret.
    with os.fdopen(os.open(STATE / "tailnet-setup.url", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(url + "\n")
    verify_setup(port, url)
    # Recheck immediately before changing Tailscale and preserve other listeners.
    check_serve(json.loads(run(TAILSCALE, "serve", "status", "--json")), port)
    run(TAILSCALE, "serve", "--bg", f"--tcp={port}", f"tcp://127.0.0.1:{port}")
    check_serve(json.loads(run(TAILSCALE, "serve", "status", "--json")), port)
    (STATE / "tailnet-domain").write_text(domain + f":{port}\n")
    print(f"Tailnet dashboard: http://{domain}:{port}/")
    print(f"Private setup link (if unclaimed): {STATE / 'tailnet-setup.url'}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        sys.exit(f"Tailnet setup failed: {error}")
