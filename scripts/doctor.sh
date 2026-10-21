#!/bin/sh
set -eu
for tool in tofu ansible-galaxy ansible-playbook ssh git; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "Missing required command: $tool" >&2
        exit 1
    fi
done
if [ ! -f infra/cluster.auto.tfvars ]; then
    echo "Copy infra/cluster.auto.tfvars.example to infra/cluster.auto.tfvars and fill in your environment." >&2
    exit 1
fi
if grep -q '<[^>]*>' infra/cluster.auto.tfvars infra/main.tf ansible/requirements.yml; then
    echo "Replace configuration placeholders before provisioning." >&2
    exit 1
fi
infra_release=$(sed -n 's/.*?ref=\([^" ]*\)".*/\1/p' infra/main.tf)
ansible_release=$(sed -n 's/^[[:space:]]*version:[[:space:]]*//p' ansible/requirements.yml | tr -d '\r"\047')
if [ -z "$infra_release" ] || [ "$infra_release" != "$ansible_release" ]; then
    echo "Pin the same release tag or commit in infra/main.tf and ansible/requirements.yml." >&2
    exit 1
fi
if [ -z "${TF_VAR_proxmox_api_token:-}" ]; then
    echo "Set TF_VAR_proxmox_api_token from your secret manager before provisioning." >&2
    exit 1
fi
echo "Local setup checks passed. Run make infra-init, then make infra-plan."
echo "The plan validates OpenTofu requirements and inputs; confirm SSH key access, free VM IDs, and DHCP reservations before apply."
