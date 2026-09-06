# Aerosol validation record

Validation host: Apple Silicon Mac, 16 CPU cores, 128 GiB physical RAM, macOS 26.6.2. Upstream base: `796257e5`. The fork preserves Ubuntu 24.04, the existing Python control plane, systemd and rootless Podman.

## Checks

- 22 new regression tests cover native ARM configuration, absence of shared mounts, restricted forwarding, argument validation, graceful stop, concurrent installation locks, post-setup readiness, false HTTP health responses, source-snapshot reuse, and local provisioning invariants. Tests were exercised failing before their respective fixes.
- Every implementation commit passed the configured Ruff, mypy and secret-scanning hooks.
- Lima 2.2.0 validated the generated VM configuration. Both Lima and the Ubuntu image are pinned by SHA-256.
- The primary test VM uses 4 vCPUs, 8 GiB RAM and a 60 GiB sparse disk. Guest checks confirmed `aarch64`, Ubuntu 24.04.4, ext4, cgroup v2, rootless Podman and `crun`.
- The browser rendered the first-run owner setup at `http://lvh.me:8080/setup`. No owner account was created in the primary installation.
- Host listener inspection confirmed the forwarded dashboard is bound only to `127.0.0.1:8080` by Lima.
- The native integration run deployed the six default apps: secrets, filestash, OAuth provider, catalog, backup and community chat. All reached `running` in its router test instance.

The native integration command was `pixi run -e dev pytest -x --run-containers --timeout=600 compute_space/src/compute_space/tests/test_integration.py tests/test_services_e2e.py` inside the guest as `host`, with `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` set for that user. **48 tests passed in 239.83 seconds**, covering setup/login, API tokens, native builds, proxy headers/cookies, app stop/reload, persistent-data reuse, router/container recovery, and cross-app secrets/permission flows. These tests use temporary data but share the guest container namespace; run them in a disposable VM, not an installation with user apps.

A second checkout installed successfully from committed source `bb26cdcd` using `./scripts/aerosol up --port 9080`, with the default 4 vCPUs, 4 GiB RAM and 60 GiB disk. The pinned Lima bootstrap, Ubuntu provisioning and dashboard readiness all succeeded without manual repair. A marker in `/var/lib/aerosol/` survived a second-VM stop/start; `doctor` passed, and that extra VM was shut down. The main installation also passed a graceful stop/start and `doctor` after reboot. Temporary integration containers were removed only after confirming their mounts/logs belonged to `/tmp/pytest-of-host/`.

[CI run 34009115381](https://github.com/tangible-cs/Aerosol/actions/runs/34009115381) passed every job on implementation commit `bb26cdcd`:

| Check | Result |
| --- | --- |
| Full Linux suite with containers | 1,908 passed, 3 skipped |
| Linux cross-app service E2E | 7 passed |
| Full Linux suite without containers | 1,867 passed, 44 skipped |
| Mac launcher regressions (macos-14) | 22 passed |
| Linux launcher regressions | 22 passed |
| Pre-commit (Ruff, mypy, secret scan) | Passed |

The final documentation commit records these results without changing implementation. Local logs are in `.aerosol/ci.log`, `.aerosol/native-tests.log`, `.aerosol/clean-install.log`, `.aerosol/clean-restart.log`, and `.aerosol/doctor-final.log`; they are excluded from Git. The stopped disposable fresh-install VM was removed after preserving its logs. The primary VM remains running at http://lvh.me:8080/setup with no owner account and no test containers.

## Responsiveness sample

A host-side probe issued 200 `/health` requests through the VM forwarder with concurrency 8 while integration work was running. There were no failed responses. Median latency was 1.70 ms, p95 19.21 ms, maximum 20.59 ms. This is a narrow setup-service/forwarding measurement, not an application throughput benchmark or a comparison against x86 emulation.

## Scope and limits

Actual Apple Silicon VM execution was tested locally. CI's Mac job checks launcher behavior with controlled command stubs, not nested virtualization. Public DNS/TLS and remote S3 are retained upstream paths and were not reconfigured on this Mac. Host sleep/wake and every third-party app were not tested; x86-only images and Metal/GPU workloads are outside the native Ubuntu path. The launcher does not promise uninterrupted service while macOS sleeps.

The developer tools, test VMs, downloads and caches were installed as the normal Mac user. System package installation, users, swap, sysctls, service changes and test-container cleanup occurred only inside the dedicated guests. No host sudo, host DNS/firewall changes, login items, or host shared directories were used.

## Tailnet configuration (2026-09-06)

Enabled a persistent Tailscale Serve TCP bridge on the existing Mac identity. The guest remains native ARM64 Ubuntu with rootless containers. No host firewall or router settings changed. Initial setup remains unclaimed and now requires its private claim URL.

Validation:

- All 28 Mac launcher/provisioning/lifecycle/tailnet tests passed. The new tests cover public Funnel refusal, listener conflicts, wildcard app domain matching, configuration/database backups, idempotency, private IP selection, and refusal to expose an unprotected setup page.
- Ruff, mypy and pre-commit secret checks passed.
- Live tailnet dashboard health and wildcard app-host health returned 200. Setup without a claim returned 403; the owner-only claim URL returned 200. Repeated configuration succeeded without changing the claim token.
- `lsof` showed Lima only on `127.0.0.1:8080` and Tailscale only on its private IPv4/IPv6 addresses. Connecting to port 8080 on the Mac's LAN address was refused.
- Serve status contained only the intended TCP-forward mapping and no enabled `AllowFunnel` configuration.

These checks ran from the host Mac. An independent second-device or external-internet probe was not available. Existing tailnet ACLs were preserved. No real owner account or application was created as part of this configuration; full application behavior after owner setup remains for user acceptance testing. Browser HTTPS and a private wildcard DNS server are not provided by the TCP bridge.
