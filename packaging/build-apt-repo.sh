#!/usr/bin/env bash
# Lagar ei signert APT-kjelde (flat struktur) som kan leggjast ut på GitHub Pages.
#
#   packaging/build-apt-repo.sh <utmappe> <gpg-nøkkel-id> <pakke.deb>...
set -euo pipefail

OUT="$1"; KEY="$2"; shift 2
[[ $# -gt 0 ]] || { echo "Manglar .deb-filer" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

rm -rf "$OUT"
mkdir -p "$OUT/pool"
cp "$@" "$OUT/pool/"

# Fast adresse til siste versjon, brukt i installasjonsrettleiinga.
LATEST="$(ls -1 "$OUT"/pool/froditor_*_all.deb | sort -V | tail -n1)"
cp "$LATEST" "$OUT/froditor_latest_all.deb"
VERSION="$(dpkg-deb -f "$LATEST" Version)"

cd "$OUT"
apt-ftparchive packages pool > Packages
gzip -9 -k -n Packages
apt-ftparchive \
    -o APT::FTPArchive::Release::Origin=Froditor \
    -o APT::FTPArchive::Release::Label=Froditor \
    -o APT::FTPArchive::Release::Suite=stable \
    -o APT::FTPArchive::Release::Codename=stable \
    -o APT::FTPArchive::Release::Architectures=all \
    -o "APT::FTPArchive::Release::Description=Froditor-pakkar" \
    release . > Release.tmp
mv Release.tmp Release
gpg --batch --yes --local-user "$KEY" --clearsign -o InRelease Release
gpg --batch --yes --local-user "$KEY" --armor --detach-sign -o Release.gpg Release
gpg --batch --yes --export "$KEY" > froditor-archive-keyring.gpg
gpg --batch --yes --armor --export "$KEY" > froditor-archive-keyring.asc

sed "s/@VERSION@/$VERSION/g" "$ROOT/packaging/index.html" > index.html
touch .nojekyll
echo "APT-kjelde klar i $OUT (versjon $VERSION)"
