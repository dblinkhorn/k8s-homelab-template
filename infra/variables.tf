variable "proxmox_endpoint" {
  type        = string
  description = "Do not include /api2/json."
}

variable "proxmox_api_token" {
  type        = string
  description = "Format: user@realm!token-name=token-secret. Supply with TF_VAR_proxmox_api_token."
  sensitive   = true
}

variable "proxmox_insecure" {
  type        = bool
  description = "Skip TLS verification for Proxmox self-signed certificates."
  default     = true
}

variable "proxmox_node_name" {
  type        = string
  description = "Proxmox node name where images and VMs are managed."
}

variable "image_datastore_id" {
  type        = string
  description = "Proxmox storage ID for cloud images (default: local)."
  default     = "local"
}

variable "vm_datastore_id" {
  type        = string
  description = "Proxmox storage ID for VM disks (default: local-lvm)."
  default     = "local-lvm"
}

variable "network_bridge" {
  type        = string
  description = "Bridge attached to VM network devices."
  default     = "vmbr0"
}

variable "ssh_public_key_path" {
  type        = string
  description = "Path to the SSH public key cloud-init should authorize for VM access."
  default     = "~/.ssh/id_ed25519.pub"
}

variable "dns_servers" {
  type        = list(string)
  description = "Optional DNS override for cloned node VMs. Null uses the Proxmox host's DNS settings."
  default     = null
}

variable "qemu_guest_agent_enabled" {
  type        = bool
  description = "Enable the Proxmox QEMU guest agent channel for node VMs."
  default     = false
}

variable "template_vm_id" {
  type        = number
  description = "VMID for the node VM template."
  default     = 9000
}

variable "template_name" {
  type        = string
  description = "Name for the node VM template."
  default     = "ubuntu-2404-cloudinit"
}

variable "kubernetes_nodes" {
  type = map(object({
    vm_id        = number
    role         = string
    mac_address  = string
    reserved_ip  = string
    cpu_cores    = optional(number, 2)
    memory_mb    = optional(number, 4096)
    disk_size_gb = optional(number, 40)
  }))

  description = "Kubernetes node VM definitions."

  validation {
    condition = (
      length([for node in var.kubernetes_nodes : node if node.role == "control-plane"]) == 1 &&
      length([for node in var.kubernetes_nodes : node if node.role == "worker"]) >= 1 &&
      alltrue([for node in var.kubernetes_nodes : contains(["control-plane", "worker"], node.role)])
    )
    error_message = "Define exactly one control-plane node and at least one worker; roles must be control-plane or worker."
  }

  validation {
    condition     = length(distinct([for node in var.kubernetes_nodes : node.vm_id])) == length(var.kubernetes_nodes)
    error_message = "Each node must have a unique VM ID."
  }

  validation {
    condition = (
      alltrue([for node in var.kubernetes_nodes : can(cidrnetmask("${node.reserved_ip}/32"))]) &&
      length(distinct([for node in var.kubernetes_nodes : node.reserved_ip])) == length(var.kubernetes_nodes)
    )
    error_message = "Each node must have a unique IPv4 reserved_ip."
  }
}
