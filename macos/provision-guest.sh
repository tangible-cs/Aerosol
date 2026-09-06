#!/bin/bash
# This installer must only execute inside the dedicated Lima Ubuntu VM.
set -euo pipefail
if [[ "$(uname -s)" != Linux || "$(uname -m)" != aarch64 || ! -f /etc/os-release ]]; then
    echo "Error: run this installer inside the ARM64 Ubuntu guest only" >&2
    exit 1
fi
source /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 && "$(id -u)" == 0 ]] || {
    echo "Error: Ubuntu 24.04 guest with root privileges required" >&2; exit 1;
}
PORT="${1:?Dashboard port required}"
[[ "$PORT" =~ ^[1-9][0-9]{3,4}$ && "$PORT" -ge 1024 && "$PORT" -le 65535 ]]
[[ ! -f /var/lib/aerosol/provisioned ]] || exit 0
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git
if ! id host >/dev/null 2>&1; then
    useradd -m -s /bin/bash -G sudo host
    echo 'host ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/host
    chmod 0440 /etc/sudoers.d/host
fi
if [[ ! -d /home/host/openhost ]]; then
    su host -c 'git clone /tmp/aerosol-source.bundle /home/host/openhost'
    su host -c 'git -C /home/host/openhost checkout -B main HEAD'
    su host -c 'git -C /home/host/openhost remote set-url origin https://github.com/tangible-cs/Aerosol.git'
fi
# Retry only the same committed source after a failed provision, never overwrite a checkout.
EXPECTED="$(git bundle list-heads /tmp/aerosol-source.bundle HEAD | cut -d' ' -f1)"
ACTUAL="$(su host -c 'git -C /home/host/openhost rev-parse HEAD')"
[[ -n "$EXPECTED" && "$EXPECTED" == "$ACTUAL" ]] || {
    echo 'Error: guest source differs from the bundle; refusing to overwrite it' >&2; exit 1;
}
bash /home/host/openhost/scripts/provision.sh \
    --use-existing-checkout --domain "lvh.me:$PORT" \
    --local-http-only --bind-host 0.0.0.0 --open-claim --swap-size 2
systemctl is-active --quiet openhost
install -d -m 0755 /var/lib/aerosol
printf '%s\n' "$ACTUAL" > /var/lib/aerosol/provisioned
rm -f /tmp/aerosol-source.bundle /tmp/aerosol-provision.sh
