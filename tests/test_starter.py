"""Template contract tests; all OpenTofu applies use an output-only fake module.

Run with: python3 -m unittest discover -s tests -v
Requires tofu, make, ansible-inventory, ansible-galaxy, and ansible-playbook.
No Proxmox credentials, network access, or running cluster are used.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


STARTER = Path(__file__).resolve().parents[1]
TEST_FILES = (
    "Makefile", "ansible/ansible.cfg", "ansible/requirements.yml",
    "ansible/site.yml", "infra/.terraform.lock.hcl", "infra/inventory.tf",
    "infra/main.tf", "infra/outputs.tf", "infra/provider.tf",
    "infra/variables.tf", "infra/versions.tf", "scripts/doctor.sh",
    "scripts/inventory.sh",
)


class StarterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="homelab-starter-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "consumer"
        # Copy only public template files, never a consumer's local tfvars,
        # state, caches, or other private files.
        for name in TEST_FILES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(STARTER / name, target)
        self.env = dict(os.environ)
        # Do not inherit real provider inputs or Ansible inventory/configuration.
        for key in list(self.env):
            if key.startswith(("TF_VAR_", "ANSIBLE_", "TF_CLI_ARGS")):
                del self.env[key]
        self.env.update({
            "ANSIBLE_HOME": str(self.root / ".ansible-home"),
            "ANSIBLE_LOCAL_TEMP": str(self.root / ".ansible-tmp"),
            "TF_IN_AUTOMATION": "1",
        })
        self.config = {
            "proxmox_endpoint": "https://proxmox.example.invalid:8006/",
            "proxmox_api_token": "test-only",
            "proxmox_node_name": "pve",
            "kubernetes_nodes": {
                "cp": {"vm_id": 101, "role": "control-plane", "mac_address": "02:00:00:00:10:01", "reserved_ip": "192.0.2.51"},
                "worker": {"vm_id": 111, "role": "worker", "mac_address": "02:00:00:00:10:11", "reserved_ip": "192.0.2.61"},
            },
        }

    def run_command(self, *args, success=True, cwd=None):
        result = subprocess.run(args, cwd=cwd or self.root, env=self.env,
                                text=True, capture_output=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def fake_module(self):
        module = self.root / "fake-module"
        module.mkdir()
        # The fake module accepts the starter's inputs without requiring a
        # sibling checkout of the public implementation repository.
        module_inputs = (
            "proxmox_node_name", "image_datastore_id", "vm_datastore_id",
            "network_bridge", "ssh_public_key_path", "dns_servers",
            "qemu_guest_agent_enabled", "kubernetes_nodes",
            "template_vm_id", "template_name",
        )
        (module / "variables.tf").write_text(
            "".join(f'variable "{name}" {{}}\n' for name in module_inputs)
        )
        (module / "outputs.tf").write_text('''
output "kubernetes_node_reservations" { value = var.kubernetes_nodes }
output "kubernetes_node_vm_ids" { value = { for name, node in var.kubernetes_nodes : name => node.vm_id } }
output "proxmox_version" { value = "test" }
output "proxmox_node_names" { value = [var.proxmox_node_name] }
output "proxmox_node_online_statuses" { value = [true] }
output "ubuntu_cloud_image_file_id" { value = "test" }
output "node_template_vm_id" { value = var.template_vm_id }
output "image_datastore_id" { value = var.image_datastore_id }
output "vm_datastore_id" { value = var.vm_datastore_id }
''')
        main = self.root / "infra/main.tf"
        updated, replacements = re.subn(
            r'(?m)^  source = "git::https://github\.com/dblinkhorn/k8s-homelab\.git//infra/modules/proxmox-cluster\?ref=[^"]+"$',
            '  source = "../fake-module"', main.read_text(),
        )
        self.assertEqual(replacements, 1, "Expected one public module source")
        main.write_text(updated)
        outputs = self.root / "infra/outputs.tf"
        outputs.write_text(outputs.read_text() + '''
output "test_image_datastore_id" { value = module.proxmox_cluster.image_datastore_id }
output "test_vm_datastore_id" { value = module.proxmox_cluster.vm_datastore_id }
''')
        # Output-only fixture: no providers or resource blocks can be applied.
        for name in ("provider.tf", "versions.tf", ".terraform.lock.hcl"):
            (self.root / "infra" / name).unlink()
        self.write_config()
        self.run_command("tofu", "-chdir=infra", "init", "-backend=false")

    def write_config(self):
        (self.root / "infra/cluster.auto.tfvars.json").write_text(json.dumps(self.config))

    def apply_fixture(self):
        self.write_config()
        self.run_command("tofu", "-chdir=infra", "apply", "-auto-approve", "-input=false")
        self.run_command("make", "inventory")
        inventory = self.root / "ansible/inventory/homelab.yml"
        parsed = self.run_command("ansible-inventory", "-i", str(inventory), "--list")
        return json.loads(parsed.stdout)

    def test_inventory_defaults_overrides_and_removed_workers(self):
        self.fake_module()
        inventory = self.apply_fixture()
        self.assertEqual(inventory["k8s_control_plane"]["hosts"], ["cp"])
        self.assertEqual(inventory["k8s_workers"]["hosts"], ["worker"])
        self.assertEqual(inventory["_meta"]["hostvars"]["cp"]["ansible_user"], "ubuntu")
        self.assertEqual(inventory["_meta"]["hostvars"]["worker"]["ansible_host"], "192.0.2.61")
        nodes = json.loads(self.run_command("tofu", "-chdir=infra", "output", "-json", "kubernetes_node_reservations").stdout)
        self.assertEqual((nodes["worker"]["cpu_cores"], nodes["worker"]["memory_mb"], nodes["worker"]["disk_size_gb"]), (2, 4096, 40))
        self.config["kubernetes_nodes"]["worker"]["memory_mb"] = 8192
        self.config["kubernetes_nodes"]["worker2"] = dict(self.config["kubernetes_nodes"]["worker"], vm_id=112, reserved_ip="192.0.2.62", mac_address="02:00:00:00:10:12")
        self.assertEqual(self.apply_fixture()["k8s_workers"]["hosts"], ["worker", "worker2"])
        nodes = json.loads(self.run_command("tofu", "-chdir=infra", "output", "-json", "kubernetes_node_reservations").stdout)
        self.assertEqual(nodes["worker"]["memory_mb"], 8192)
        del self.config["kubernetes_nodes"]["worker2"]
        self.assertEqual(self.apply_fixture()["k8s_workers"]["hosts"], ["worker"])

    def test_datastore_defaults_and_overrides(self):
        self.fake_module()
        self.apply_fixture()
        image = self.run_command("tofu", "-chdir=infra", "output", "-raw", "test_image_datastore_id")
        vm = self.run_command("tofu", "-chdir=infra", "output", "-raw", "test_vm_datastore_id")
        self.assertEqual((image.stdout, vm.stdout), ("local", "local-lvm"))

        self.config["image_datastore_id"] = "custom-images"
        self.config["vm_datastore_id"] = "local-zfs"
        self.apply_fixture()
        image = self.run_command("tofu", "-chdir=infra", "output", "-raw", "test_image_datastore_id")
        vm = self.run_command("tofu", "-chdir=infra", "output", "-raw", "test_vm_datastore_id")
        self.assertEqual((image.stdout, vm.stdout), ("custom-images", "local-zfs"))

    def test_invalid_topology_and_addresses_fail_before_apply(self):
        self.fake_module()
        original = json.loads(json.dumps(self.config))
        for change in ("no-worker", "wrong-role", "duplicate-ip", "invalid-ip", "duplicate-id"):
            with self.subTest(change=change):
                self.config = json.loads(json.dumps(original))
                worker = self.config["kubernetes_nodes"]["worker"]
                if change == "no-worker":
                    del self.config["kubernetes_nodes"]["worker"]
                elif change == "wrong-role":
                    worker["role"] = "typo"
                elif change == "duplicate-ip":
                    worker["reserved_ip"] = "192.0.2.51"
                elif change == "invalid-ip":
                    worker["reserved_ip"] = "<worker-ip>"
                else:
                    worker["vm_id"] = 101
                self.write_config()
                self.run_command("tofu", "-chdir=infra", "plan", "-input=false", success=False)

    def test_failed_inventory_does_not_run_ansible_or_replace_old_file(self):
        inventory = self.root / "ansible/inventory/homelab.yml"
        inventory.parent.mkdir(parents=True, exist_ok=True)
        inventory.write_text("previous inventory\n")
        binaries = self.root / "bin"
        binaries.mkdir()
        for name, body in {"tofu": "echo partial-output; exit 1", "ansible-playbook": "touch ansible-ran"}.items():
            path = binaries / name
            path.write_text("#!/bin/sh\n" + body + "\n")
            path.chmod(0o755)
        self.env["PATH"] = str(binaries) + os.pathsep + self.env["PATH"]
        self.run_command("make", "cluster-bootstrap", success=False)
        self.assertEqual(inventory.read_text(), "previous inventory\n")
        self.assertFalse((self.root / "ansible/ansible-ran").exists())
        self.assertEqual(list(inventory.parent.glob(".homelab.*")), [])

    def test_doctor_reports_missing_config_credentials_and_mismatched_versions(self):
        self.run_command("make", "doctor", success=False)
        config = self.root / "infra/cluster.auto.tfvars"
        config.write_text('proxmox_node_name = "pve"\n')
        main = self.root / "infra/main.tf"
        updated, replacements = re.subn(r'(?<=\?ref=)[^"]+', "v0.1.0", main.read_text())
        self.assertEqual(replacements, 1)
        main.write_text(updated)
        requirements = self.root / "ansible/requirements.yml"
        updated, replacements = re.subn(
            r'(?m)^(\s*version:\s*).+$', r'\g<1>v0.1.0', requirements.read_text(),
        )
        self.assertEqual(replacements, 1)
        requirements.write_text(updated)
        self.run_command("make", "doctor", success=False)  # No credential.
        self.env["TF_VAR_proxmox_api_token"] = "test-only"
        self.run_command("make", "doctor")
        requirements.write_text(requirements.read_text().replace("v0.1.0", "v0.2.0"))
        self.run_command("make", "doctor", success=False)


if __name__ == "__main__":
    unittest.main()
