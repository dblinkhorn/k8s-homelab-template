# Keep inventory tied to the module's applied node definitions. yamlencode
# handles quoting so inventory values cannot accidentally become YAML syntax.
output "ansible_inventory" {
  description = "Generated Ansible inventory for the applied cluster."
  value = yamlencode({
    all = {
      children = {
        k8s_nodes = {
          vars = { ansible_user = "ubuntu" }
          children = {
            k8s_control_plane = {
              hosts = {
                for name, node in module.proxmox_cluster.kubernetes_node_reservations :
                name => { ansible_host = node.reserved_ip } if node.role == "control-plane"
              }
            }
            k8s_workers = {
              hosts = {
                for name, node in module.proxmox_cluster.kubernetes_node_reservations :
                name => { ansible_host = node.reserved_ip } if node.role == "worker"
              }
            }
          }
        }
      }
    }
  })
}
