module "proxmox_cluster" {
  # When updating to a newer k8s-homelab commit or release, update this ref
  # and ansible/requirements.yml to the same commit or tag.
  source = "git::https://github.com/dblinkhorn/k8s-homelab.git//infra/modules/proxmox-cluster?ref=e0cb37decc9a2263ab4593d30bb87bd0e36a13f3"

  proxmox_node_name  = var.proxmox_node_name
  image_datastore_id = var.image_datastore_id
  vm_datastore_id    = var.vm_datastore_id
  network_bridge     = var.network_bridge

  ssh_public_key_path      = var.ssh_public_key_path
  dns_servers              = var.dns_servers
  qemu_guest_agent_enabled = var.qemu_guest_agent_enabled
  kubernetes_nodes         = var.kubernetes_nodes

  template_vm_id = var.template_vm_id
  template_name  = var.template_name
}
