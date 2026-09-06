# Aerosol on Apple Silicon

Aerosol is a fork of Cloud in a Bottle for M-series Macs. The control plane, systemd services, rootless Podman containers, and persistent data run inside an ARM64 Ubuntu 24.04 VM. Lima uses Apple's Virtualization.framework (`vz`) to run ARM instructions directly. The existing Linux server and x86 appliance installation paths remain available.

## Install and start

Requirements: an Apple Silicon Mac, macOS 13 or newer, Git, and an internet connection for the first install. Allow at least 20 GB of free space for the base system and initial apps, plus room for your app data. An 8 GB Mac can use the default 4 GB guest; a 16 GB or larger Mac has more room for demanding apps.

From the Aerosol checkout:

```bash
./scripts/aerosol up
```

The launcher downloads a checksum-pinned native Lima runtime locally and a checksum-pinned Ubuntu image. It copies the current **committed** source into the VM, then runs the project's existing provisioning playbook inside Ubuntu. First installation takes several minutes and needs access to Ubuntu, GitHub, conda-forge, PyPI, and container registries. Commit tracked edits before installing; uncommitted files are not shipped into the guest.

Open **http://lvh.me:8080/** and choose your own owner username and password. Your apps appear at `http://APP.lvh.me:8080/`. `lvh.me` and its wildcard resolve to loopback. If a VPN or DNS filter blocks this domain, the setup page is also reachable at `http://127.0.0.1:8080/`, but app subdomains still need wildcard resolution.

For the first creation you can choose resources and an unused port:

```bash
./scripts/aerosol up --cpus 4 --memory 8 --disk 80 --port 9080
```

Defaults are 4 vCPUs, 4 GiB RAM, and a 60 GiB sparse disk. The launcher refuses to allocate more than half the Mac's physical memory or more CPUs than the host has. Disk capacity is a limit, not a reservation of physical storage. Avoid filling the host disk. A larger VM is useful for more simultaneous containers; it does not make an individual request automatically faster.

## Everyday use

```bash
./scripts/aerosol status
./scripts/aerosol doctor
./scripts/aerosol logs
./scripts/aerosol shell
./scripts/aerosol stop
./scripts/aerosol up
```

`stop` shuts Ubuntu down gracefully and retains all data. `up` restarts an existing VM without reinstalling it, resetting source, or touching accounts. Health checks work both before and after owner setup. The shell opens as Lima's guest user; use `sudo -iu host` inside the guest for app administration. All `sudo` shown inside that shell operates in Ubuntu.

The VM has no automatic login-start service on the Mac. Start it when wanted. macOS sleep pauses availability; a laptop cannot serve requests while asleep. The launcher does not change sleep settings. Use a Mac that remains awake if continuous service is required.

Resource options apply only at creation. To change CPU or RAM later, gracefully stop the VM and use Lima's edit command, with the same private instance directory:

```bash
LIMA_HOME="$PWD/.aerosol/lima" ./.aerosol/tools/bin/limactl edit aerosol
```

Keep `vmType: vz`, `arch: aarch64`, no mounts, and loopback forwarding. Do not shrink the disk. Changing the public port also requires updating the platform's domain; prefer choosing the right port at creation.

## Isolation, persistence, and updates

- No host `sudo`, Homebrew changes, host network configuration, Docker Desktop, Rosetta installation, or shared home directory are needed.
- Only the dashboard port is forwarded to `127.0.0.1`; guest application ports are not automatically exposed. Lima's private SSH connection provides administration.
- Containers, images, Git worktrees, SQLite state and app data live on the guest's ext4 filesystem. This preserves Linux ownership, inotify, idmapped mounts and rootless isolation, without a shared-filesystem bottleneck.
- `.aerosol/` holds the VM disk, SSH keys, local runtime and installation state. Keep it private and excluded from Git. Lima also uses its normal macOS download cache at `~/Library/Caches/lima`. Pixi development dependencies are separate from the VM.
- Keep the checkout in place while using its VM. Before moving or backing up a disk, stop the VM. Copy the entire `.aerosol/` directory to your backup destination and retain the source checkout/revision. Backups contain credentials and app data.
- The guest's `origin` is the Aerosol fork. Fetching source on the Mac does not silently update a running guest. Use the platform's existing update flow when applying a tested release; the launcher does not reset an installed guest to a new checkout.

## Troubleshooting

`./scripts/aerosol doctor` checks the guest's CPU architecture, Ubuntu version, filesystem, memory, service state, rootless Podman, and the dashboard connection. `logs` shows recent router and archive-service logs. First-install output is printed to the terminal; keep it with `./scripts/aerosol up 2>&1 | tee install.log` if diagnosing a fresh install.

If provisioning fails, rerun `up`. The initial source bundle is reused even if you have since made more commits on the Mac. A completion marker is written only after the service starts. Retrying never overwrites a guest checkout with a different revision. Resolve network failures before retrying. If the launcher was forcibly terminated, verify no installation is still running before removing the empty `.aerosol/up.lock` directory.

An occupied port fails before creating a new VM. Use `--port` at first creation. For a restarted VM, inspect `lsof -nP -iTCP:8080 -sTCP:LISTEN` on the Mac for conflicts. Never kill an unrelated application to free the port automatically.

The pinned Ubuntu image deliberately has no unchecked fallback. If Canonical retires that dated image, update its URL and SHA-256 together from an official Ubuntu release manifest and rerun configuration tests.

Native ARM64 containers are preferred. Third-party images or downloaded executables that only support x86 will require an ARM build or an explicitly configured compatibility solution. GPU/Metal passthrough is not provided by this Ubuntu VM. Public TLS, DNS, archive backends, and server deployment remain upstream features; the default Mac instance stays local. See the existing home-network and public-server guides when deliberately exposing an instance.

## Development verification

```bash
./.aerosol/tools/bin/pixi run -e dev pytest -x tests/macos
```

The development tool is only present if Pixi was installed for development; normal use needs no host Python environment. Native VM integration results and any remaining limits are recorded in `docs/internal/aerosol-validation.md`.
