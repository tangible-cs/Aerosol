#!/bin/bash
# Install a checksum-pinned native Lima distribution inside this checkout only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$ROOT/.aerosol"
VERSION=2.2.0
SHA256=bbdef91774885a0d05f7b048c4eb89ae2bcf3a0c252ae7ca7934e63df76d93c3
mkdir -p "$STATE/downloads" "$STATE/tools"
ARCHIVE="$STATE/downloads/lima-$VERSION-Darwin-arm64.tar.gz"
curl -fL --retry 3 --connect-timeout 20 \
    "https://github.com/lima-vm/lima/releases/download/v$VERSION/lima-$VERSION-Darwin-arm64.tar.gz" -o "$ARCHIVE.part"
printf '%s  %s\n' "$SHA256" "$ARCHIVE.part" | shasum -a 256 -c -
mv "$ARCHIVE.part" "$ARCHIVE"
tar -xzf "$ARCHIVE" -C "$STATE/tools"
"$STATE/tools/bin/limactl" --version
