.DEFAULT_GOAL := help
.PHONY: help doctor deps infra-init infra-plan infra-apply inventory cluster-bootstrap

help:
	@echo "doctor             Check local tools, configuration, and dependency references"
	@echo "deps               Install the pinned Ansible collection"
	@echo "infra-init         Initialize OpenTofu dependencies and backend"
	@echo "infra-plan         Preview infrastructure changes"
	@echo "infra-apply        Apply infrastructure changes (interactive approval)"
	@echo "inventory          Regenerate Ansible inventory from applied OpenTofu state"
	@echo "cluster-bootstrap  Generate inventory, check syntax, and run Ansible"

doctor:
	@sh scripts/doctor.sh

deps:
	cd ansible && ansible-galaxy collection install -r requirements.yml --force

infra-init:
	tofu -chdir=infra init

infra-plan:
	tofu -chdir=infra plan

infra-apply:
	tofu -chdir=infra apply

inventory:
	@sh scripts/inventory.sh

cluster-bootstrap: inventory
	cd ansible && ansible-playbook --syntax-check site.yml
	cd ansible && ansible-playbook site.yml
