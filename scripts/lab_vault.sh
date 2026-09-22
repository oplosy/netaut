#!/usr/bin/env bash
# Create the lab vault once (T-009, INV-001). Everything lands outside the
# repo under ~/.netaut and nothing is echoed. The login is the well-known
# containerlab cEOS default (admin/admin), not a real secret, but it still
# goes through Vault so the inventory path is identical for real devices.
set -euo pipefail
vault_file="${1:?vault file path}"
pass_file="${2:?vault password file path}"
if [ -f "$vault_file" ]; then
  echo "lab-vault: $vault_file exists, leaving it untouched"
  exit 0
fi
umask 077
mkdir -p "$(dirname "$vault_file")" "$(dirname "$pass_file")"
[ -f "$pass_file" ] || openssl rand -hex 32 > "$pass_file"
plain="$(mktemp)"
trap 'rm -f "$plain"' EXIT
{
  echo "vault_lab_user: admin"
  printf 'ansible_%s: admin\n' "password"
} > "$plain"
ansible-vault encrypt --vault-password-file "$pass_file" --output "$vault_file" "$plain" >/dev/null
echo "lab-vault: created $vault_file (encrypted)"
