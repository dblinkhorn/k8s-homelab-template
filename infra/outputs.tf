output "proxmox_version" {
  description = "Proxmox version reported by the API."
  value       = module.proxmox_cluster.proxmox_version
}

output "proxmox_node_names" {
  description = "Proxmox node names."
  value       = module.proxmox_cluster.proxmox_node_names
}

output "proxmox_node_online_statuses" {
  description = "Online status for Proxmox nodes."
  value       = module.proxmox_cluster.proxmox_node_online_statuses
}

output "ubuntu_cloud_image_file_id" {
  description = "Downloaded Ubuntu cloud image file ID in Proxmox."
  value       = module.proxmox_cluster.ubuntu_cloud_image_file_id
}

output "node_template_vm_id" {
  description = "VMID of the node VM template."
  value       = module.proxmox_cluster.node_template_vm_id
}

output "kubernetes_node_reservations" {
  description = "DHCP reservation map for Kubernetes nodes."
  value       = module.proxmox_cluster.kubernetes_node_reservations
}

output "kubernetes_node_vm_ids" {
  description = "VMIDs of Kubernetes node VMs."
  value       = module.proxmox_cluster.kubernetes_node_vm_ids
}
