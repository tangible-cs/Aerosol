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

## Private tailnet access

With the Tailscale Mac app already signed in and connected, run:

```bash
./scripts/aerosol tailnet
open "$(cat .aerosol/tailnet-setup.url)"
```

This optional command requires host Python 3.9 or newer. It uses the Mac's existing Tailscale identity, leaving Ubuntu and rootless containers intact. It briefly restarts the guest router, backs up its configuration and SQLite database, and promotes a tailnet domain while preserving the localhost domain. Existing apps may restart to pick up their new canonical URLs. The command refuses conflicting Tailscale port mappings and any enabled Funnel configuration.

The address is `http://aerosol.<hyphenated-Tailscale-IPv4>.sslip.io:<port>/`. Application subdomains resolve to that same private Tailscale IP. MagicDNS device names alone cannot provide the wildcard subdomains used by apps. This default uses a third-party wildcard DNS resolver; clients must be able to resolve it. DNS lookup reveals the hostname to the resolver, but does not make the service public. A DNS outage or DNS-rebinding filter can prevent resolution. Your own wildcard DNS pointing to the Tailscale IP is an alternative, configured through the existing domain settings.

Tailscale Serve forwards TCP only from the tailnet to the Mac's `127.0.0.1` dashboard port. Lima continues to forward no other application ports. No Funnel, router forwarding, public listener, host firewall change, or new Tailscale identity is created. Tailnet access follows your existing Tailscale ACLs/grants: this is not a restriction to a single user if your policy permits other members or shared devices.

The browser URL uses HTTP. Tailscale encrypts transport between devices with WireGuard; there is no browser TLS certificate, so browser features requiring an HTTPS secure context may be unavailable. Use the upstream private-domain/DNS-01 TLS setup if those features are needed. Do not enable Funnel to obtain HTTPS.

Before exposing an unclaimed instance, the command enables the existing claim-token protection and checks that the running setup page rejects a missing token and accepts the private claim link. The link is saved with owner-only permissions in `.aerosol/tailnet-setup.url`, excluded from Git. Do not share it. After claiming the instance, use the dashboard URL printed by `up`; the claim token is consumed by setup.

Serve runs in the background and persists in Tailscale's configuration across restarts. The Mac, Tailscale connection and Aerosol VM must be running. Inspect or disable just this mapping (substitute your chosen port):

```bash
/Applications/Tailscale.app/Contents/MacOS/Tailscale serve status --json
/Applications/Tailscale.app/Contents/MacOS/Tailscale serve --tcp=8080 off
```

Disabling the mapping preserves the VM, its data, owner account, claim protection and domain records. Rerun `./scripts/aerosol tailnet` to reconnect. If the Mac's Tailscale IP changes, rerun it to configure the new canonical hostname. Do not reuse the old hostname.

References: [Tailscale Serve](https://tailscale.com/docs/reference/tailscale-cli/serve), [MagicDNS](https://tailscale.com/docs/features/magicdns), and the project's [home network setup](home_network.md).
