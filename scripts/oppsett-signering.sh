#!/usr/bin/env bash
# Køyr ÉIN gong for å lage signeringsnøkkelen til APT-kjelda.
# Krev: gpg og GitHub CLI (gh) innlogga med tilgang til repoet.
#
#   scripts/oppsett-signering.sh
#
# Nøkkelen blir lagra som hemmelegheita GPG_PRIVATE_KEY i GitHub og så
# sletta frå maskina. Mistar du ho, køyr skriptet på nytt – men då må
# alle maskiner installere .deb-fila manuelt éin gong til.
set -euo pipefail
REPO="${REPO:-Frodolini/Froditor}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export GNUPGHOME="$TMP"
chmod 700 "$GNUPGHOME"

gpg --batch --passphrase '' --quick-gen-key \
    "Froditor APT-kjelde <Frodolini@users.noreply.github.com>" ed25519 sign never
KEY="$(gpg --list-secret-keys --with-colons | awk -F: '/^fpr/{print $10; exit}')"
gpg --batch --armor --export-secret-keys "$KEY" | gh secret set GPG_PRIVATE_KEY --repo "$REPO"

echo
echo "Ferdig. Nøkkel $KEY er lagra som GPG_PRIVATE_KEY i $REPO."
