#!/bin/sh
# Run from the starter root; replace inventory only after output succeeds.
set -eu
mkdir -p ansible/inventory
inventory_tmp=$(mktemp ansible/inventory/.homelab.XXXXXX)
trap 'rm -f "$inventory_tmp"' EXIT HUP INT TERM
tofu -chdir=infra output -raw ansible_inventory > "$inventory_tmp"
if [ ! -s "$inventory_tmp" ]; then
    echo "No inventory output. Run make infra-apply successfully first." >&2
    exit 1
fi
mv "$inventory_tmp" ansible/inventory/homelab.yml
