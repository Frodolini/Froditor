#!/usr/bin/env bash
# Byggjer froditor_<versjon>_all.deb i mappa dist/
#
#   packaging/build-deb.sh [versjon]
#
# Set KEYRING=sti/til/nokkel.gpg for å ta med APT-kjelda, slik at
# maskina får oppdateringar automatisk etter første installasjon.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="${1:-$(python3 -c 'import froditor; print(froditor.__version__)')}"
VERSION="${VERSION#v}"
KEYRING="${KEYRING:-}"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
PKG="$STAGE/froditor"

install -d "$PKG/DEBIAN" \
    "$PKG/usr/bin" \
    "$PKG/usr/lib/froditor/froditor" \
    "$PKG/usr/share/applications" \
    "$PKG/usr/share/icons/hicolor/scalable/apps" \
    "$PKG/usr/share/doc/froditor"

install -m 0644 froditor/*.py "$PKG/usr/lib/froditor/froditor/"
sed -i "s/^__version__ = .*/__version__ = \"$VERSION\"/" "$PKG/usr/lib/froditor/froditor/__init__.py"
install -m 0755 bin/froditor "$PKG/usr/bin/froditor"
install -m 0644 data/no.frodolini.Froditor.desktop "$PKG/usr/share/applications/"
install -m 0644 data/no.frodolini.Froditor.svg "$PKG/usr/share/icons/hicolor/scalable/apps/"
install -m 0644 packaging/copyright "$PKG/usr/share/doc/froditor/copyright"

if [[ -n "$KEYRING" ]]; then
    install -d "$PKG/etc/apt/sources.list.d" "$PKG/usr/share/keyrings"
    install -m 0644 data/froditor.sources "$PKG/etc/apt/sources.list.d/froditor.sources"
    install -m 0644 "$KEYRING" "$PKG/usr/share/keyrings/froditor-archive-keyring.gpg"
    echo "/etc/apt/sources.list.d/froditor.sources" > "$PKG/DEBIAN/conffiles"
fi

INSTALLED_SIZE="$(du -sk --exclude=DEBIAN "$PKG" | cut -f1)"
cat > "$PKG/DEBIAN/control" <<EOF
Package: froditor
Version: $VERSION
Architecture: all
Maintainer: Frode (Frodolini) <Frodolini@users.noreply.github.com>
Installed-Size: $INSTALLED_SIZE
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0
Section: editors
Priority: optional
Homepage: https://github.com/Frodolini/Froditor
Description: Enkel tekstbehandlar for .txt-filer
 Froditor er ein enkel tekstbehandlar i stil med Notisblokk.
 Han opnar og lagrar vanlege tekstfiler, og har søk og erstatt,
 linjebryting og val av skrifttype.
EOF

(cd "$PKG" && find usr etc -type f 2>/dev/null | sort | xargs md5sum) > "$PKG/DEBIAN/md5sums"

mkdir -p dist
OUT="dist/froditor_${VERSION}_all.deb"
dpkg-deb --root-owner-group -Zxz --build "$PKG" "$OUT" >/dev/null
echo "$OUT"
