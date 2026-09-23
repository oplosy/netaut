# NetAut shortcuts. Every target mirrors a CI gate; `make gates` is the
# full local chain and must stay green before merge.
SAMPLE ?= netbox/intended/sample.yml
INVENTORY ?= inventories/lab.yml

.PHONY: gates lint scan validate render test preview-deploy preview-drift help \n	lab-up lab-down lab-vault lab-verify

help:
	@echo "gates | lint | scan | validate | render | test | preview-deploy | preview-drift"
	@echo "lab (run inside WSL): lab-up | lab-vault | lab-verify | lab-down"

gates: lint scan validate render test

lint:
	python -m yamllint -c .yamllint.yml .

scan:
	python scripts/secret_scan.py --root .

validate:
	python scripts/validate_model.py --schema netbox/schema.yml --input $(SAMPLE)
	python scripts/validate_model.py --schema netbox/schema.yml --input netbox/intended/lab-eos.yml
	python scripts/validate_model.py --schema netbox/schema.yml --input netbox/intended/lab-srlinux.yml

render:
	python scripts/render_idempotency.py --input $(SAMPLE) --vendor ios --repo .
	python scripts/render_idempotency.py --input netbox/intended/lab-eos.yml --vendor eos --repo .

test:
	python -m pytest roles scripts/tests -q

preview-deploy:
	ansible-playbook playbooks/deploy/site.yml -i $(INVENTORY) --check --diff

preview-drift:
	ansible-playbook playbooks/drift/report.yml -i $(INVENTORY) --check

# Live lab (T-009..T-011, ADR-006). Run inside WSL with the cEOS image
# imported locally (docker import cEOS64-lab-<ver>.tar.xz ceos:<ver>).
# Vault material stays under ~/.netaut, outside the repo (INV-001).
# No sudo: members of the clab_admins group run containerlab directly.
CEOS_IMAGE ?= ceos:latest
LAB_VAULT ?= $(HOME)/.netaut/lab-vault.yml
LAB_VAULT_PASS ?= $(HOME)/.netaut/vault_pass
WAVE ?= W-$(shell date +%Y%m%d-%H%M%S)

lab-up:
	CEOS_IMAGE=$(CEOS_IMAGE) containerlab deploy -t lab/netaut.clab.yml --reconfigure

lab-down:
	containerlab destroy -t lab/netaut.clab.yml --cleanup

lab-vault:
	scripts/lab_vault.sh $(LAB_VAULT) $(LAB_VAULT_PASS)

lab-verify:
	python3 scripts/lab_verify.py --inventory inventories/lab-eos.yml --wave $(WAVE) 	  --vault-args "-e @$(LAB_VAULT) --vault-password-file $(LAB_VAULT_PASS)"
