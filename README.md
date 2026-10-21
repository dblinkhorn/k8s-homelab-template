# k8s-homelab template

This repository is the starting point for deploying [k8s-homelab](https://github.com/dblinkhorn/k8s-homelab) on your own Proxmox server. The public `k8s-homelab` repository provides a reusable infrastructure module and an Ansible collection. This template brings them together with the configuration for your cluster. Create a private repository from this template, then use the guide below to set it up for your Proxmox server and home network.

In your private repository, you define your nodes, their resources, and network addresses. The infrastructure module creates an Ubuntu VM template and the VMs that will become your cluster's nodes. This template generates an Ansible inventory from the provisioned nodes, and the `dblinkhorn.k8s_homelab` Ansible collection will prepare the VMs and bootstrap Kubernetes.

The supported cluster has one control-plane node and at least one worker, all running amd64 Ubuntu. It uses Cilium for pod networking, kube-proxy for Service routing, and CoreDNS for cluster DNS. The bootstrap also installs Flux controllers.

## Before you begin

You'll need a Proxmox host with API access and storage for the Ubuntu image and
VM disks. Install these tools on the machine where you'll run the bootstrap:

| Tool | Version | Used for |
| --- | --- | --- |
| OpenTofu | ≥1.13.1 | Provisioning the VMs |
| Ansible Core | ≥2.18.0 | Preparing nodes and bootstrapping Kubernetes |

OpenTofu's minimum is declared in `infra/versions.tf`; Ansible Core's is
declared in the public collection's `meta/runtime.yml`. Git, Make, and an
SSH client will also be needed.

Prepare a Proxmox API token with provisioning permissions, an SSH key pair,
and access to the VM network. Your DHCP server must support reservations
for the node MAC/IP pairs. The SSH public key goes into each VM; keep the
private key available to your SSH client, for example through `ssh-agent`.
The Proxmox host must be able to download the Ubuntu image, and the VMs must
be able to download packages and bootstrap tools.

## Create your private repository

On GitHub, select **Use this template → Create a new repository** and choose
**Private** visibility. Clone your new repository, then create a local
configuration file from the example:

```bash
cp infra/cluster.auto.tfvars.example infra/cluster.auto.tfvars
```

The template files become yours. The OpenTofu module and Ansible collection are downloaded
dependencies.

## Network setup

The VMs attach to the Proxmox bridge selected by `network_bridge` (default
`vmbr0`) and request IPv4 addresses through DHCP. The network setup assumes
the selected Proxmox bridge connects all node VMs to the same home LAN,
where your DHCP server assigns their reserved IP addresses.

For each node in `infra/cluster.auto.tfvars`, choose a unique MAC address and
an unused IP address on that network. This template does not configure your
DHCP server automatically, so before provisioning add a reservation on your
router or DHCP server that maps the MAC to the IP. The `reserved_ip` value
tells Ansible which address to use and check, but it does **not** assign a
static IP inside the VM.

The VMs obtain their IP addresses through DHCP. Unless you set `dns_servers`,
Proxmox passes its host DNS settings to them through cloud-init.
If those DNS servers are not suitable for the VM network, set `dns_servers`
in `infra/cluster.auto.tfvars` to the IP addresses you want the VMs to use.

## Configure your cluster

1. Edit `infra/cluster.auto.tfvars`: enter the Proxmox endpoint, node, and
   each Kubernetes node's MAC and reserved IP. Set `dns_servers` only if you
   need to override the Proxmox host's DNS settings. Confirm the default
   datastore IDs exist on your Proxmox host.
2. Confirm the Proxmox VM IDs (VMIDs) are unused: `9000` for the template and
   `101`, `111`, and `112` for the example nodes. If `9000` is taken, set
   `template_vm_id` at the top level of `infra/cluster.auto.tfvars`. If a node
   VMID is taken, change that node's `vm_id` inside `kubernetes_nodes`.
3. Set `TF_VAR_proxmox_api_token` in the terminal session where you'll run
   `make`. Do **not** put the token in a file you'll commit.

The example defines one control plane and two workers. Add or remove worker
entries as needed, but at least one worker is required.

You can keep these defaults
when they fit your Proxmox host:

| Setting | Default |
| --- | --- |
| Ubuntu image storage | `local` |
| VM disk storage | `local-lvm` |
| Network bridge | `vmbr0` |
| SSH public key | `~/.ssh/id_ed25519.pub` |
| VM login user | `ubuntu` |

Proxmox installations using ZFS commonly use `local-zfs` for VM disks instead.
Override `vm_datastore_id` if your storage IDs differ. Other optional overrides
go in the same configuration file, for example:

```hcl
network_bridge      = "vmbr1"
ssh_public_key_path = "~/.ssh/homelab.pub"
template_vm_id      = 9100
vm_datastore_id     = "local-zfs"
proxmox_insecure    = false # Use when the API certificate is trusted locally.
```

Be sure to update the default node sizing configuration if you would like something different. The default
`proxmox_insecure = true` retains support for self-signed Proxmox certificates.
Other available starter settings are documented in `infra/variables.tf`.

## Provision and bootstrap

Run these commands in order from your private repository root:

| Step | Command | What it does |
| --- | --- | --- |
| 1 | `make doctor` | Checks that required tools are installed, `infra/cluster.auto.tfvars` exists with no example values left, the OpenTofu module and Ansible collection use the same `k8s-homelab` tag or commit, and `TF_VAR_proxmox_api_token` is set. |
| 2 | `make deps` | Downloads and installs the pinned Ansible collection locally. |
| 3 | `make infra-init` | Initializes OpenTofu and downloads the Proxmox provider and module. |
| 4 | `make infra-plan` | Shows the proposed Proxmox changes for you to review. |
| 5 | `make infra-apply` | Applies the Proxmox changes after your approval. |
| 6 | `make cluster-bootstrap` | Generates inventory from OpenTofu state, checks Ansible syntax, prepares the nodes, bootstraps Kubernetes, and verifies Cilium, CoreDNS, kube-proxy, node readiness, and Flux. |

Review the plan carefully before approving `make infra-apply`. It may include
VM replacements or deletions when changing an existing cluster.

`make cluster-bootstrap` generates Ansible's inventory from OpenTofu's applied
state before running Ansible. If inventory generation fails then bootstrap stops.
Don't edit the generated `ansible/inventory/homelab.yml` file. To change the
nodes, edit `infra/cluster.auto.tfvars`, review and apply the OpenTofu plan,
then run bootstrap again. You can run `make inventory` if you only want to
regenerate the inventory.

Once bootstrap succeeds, run `make infra-plan` and `make cluster-bootstrap`
again to check that the infrastructure is stable and Ansible makes no further
changes.

## Keep your repository safe

Commit your non-secret cluster configuration, template files, and
`infra/.terraform.lock.hcl` to your private repository. Keep credentials,
kubeconfigs, generated inventory, and tool caches out of Git. OpenTofu state
is local and ignored by default; back it up securely or configure a private
remote backend before provisioning.

If you rebuild nodes at previously used IP addresses, verify their new SSH
host keys through a trusted channel before updating the matching known-hosts
entries. Keep SSH host-key checking enabled.

Normal users run `site.yml`. Advanced Ansible overrides can go in
`ansible/inventory/group_vars/k8s_nodes.yml`; public roles and templates stay
inside the installed collection. Some roles depend on earlier bootstrap
phases, so use the collection's orchestration playbooks for ordered execution.

To upgrade the public dependencies, update both dependency references to the
same newer commit or release tag and rerun
dependency installation and the relevant commands. Template files do not
automatically update in your repository. Kubernetes version upgrades remain
explicit work; changing a dependency reference does not itself upgrade a
running cluster. Fresh installations may also pick up newer unpinned OS
packages and Kubernetes patch releases.
