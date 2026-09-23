# NetAut shortcuts. Every target mirrors a CI gate; `make gates` is the
# full local chain and must stay green before merge.
SAMPLE ?= netbox/intended/sample.yml
INVENTORY ?= inventories/lab.yml

.PHONY: gates lint scan validate render test preview-deploy preview-drift help \
	lab-up lab-down lab-vault lab-verify lab-cycle

help:
	@echo "gates | lint | scan | validate | render | test | preview-deploy | preview-drift"
	@echo "lab (inside WSL, LAB=srlinux|eos): lab-up | lab-vault | lab-verify | lab-down | lab-cycle"

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
	python scripts/render_idempotency.py --input netbox/intended/lab-srlinux.yml --vendor srlinux --repo .

test:
	python -m pytest roles scripts/tests -q

preview-deploy:
	ansible-playbook playbooks/deploy/site.yml -i $(INVENTORY) --check --diff

preview-drift:
	ansible-playbook playbooks/drift/report.yml -i $(INVENTORY) --check

# Live lab (T-009..T-011 cEOS / ADR-006, T-013..T-015 SR Linux / ADR-007).
# Run inside WSL. LAB=srlinux (default, public image) or LAB=eos (image
# imported by the OWNER: docker import cEOS64-lab-<ver>.tar.xz ceos:<ver>).
# Vault material and containerlab's lab dir stay under ~/.netaut, outside the
# repo (INV-001); SR Linux cannot boot with its lab dir under /mnt/c.
# WSL stops the VM when the last session ends: use lab-cycle from Windows.
# No sudo: members of the clab_admins group run containerlab directly.
LAB ?= srlinux
CEOS_IMAGE ?= ceos:latest
SRLINUX_IMAGE ?= ghcr.io/nokia/srlinux:26.7.2
LAB_TOPO_eos := lab/netaut.clab.yml
LAB_TOPO_srlinux := lab/netaut-srlinux.clab.yml
LAB_INV_eos := inventories/lab-eos.yml
LAB_INV_srlinux := inventories/lab-srlinux.yml
LAB_PORT_eos := 22
LAB_PORT_srlinux := 443
LAB_IMAGE_eos = $(CEOS_IMAGE)
LAB_IMAGE_srlinux = $(SRLINUX_IMAGE)
# Well-known containerlab default logins, not secrets; routed through Vault.
LAB_LOGIN_eos := admin
LAB_LOGIN_srlinux := NokiaSrl1!
LAB_VAULT ?= $(HOME)/.netaut/lab-vault-$(LAB).yml
LAB_VAULT_PASS ?= $(HOME)/.netaut/vault_pass
export CLAB_LABDIR_BASE ?= $(HOME)/.netaut/clab
WAVE ?= W-$(shell date +%Y%m%d-%H%M%S)

lab-up:
	mkdir -p $(CLAB_LABDIR_BASE)
	CEOS_IMAGE=$(CEOS_IMAGE) SRLINUX_IMAGE=$(SRLINUX_IMAGE) \
	  containerlab deploy -t $(LAB_TOPO_$(LAB)) --reconfigure

lab-down:
	containerlab destroy -t $(LAB_TOPO_$(LAB)) --cleanup

lab-vault:
	scripts/lab_vault.sh $(LAB_VAULT) $(LAB_VAULT_PASS) '$(LAB_LOGIN_$(LAB))'

lab-verify:
	python3 scripts/lab_verify.py --inventory $(LAB_INV_$(LAB)) --wave $(WAVE) \
	  --wait-port $(LAB_PORT_$(LAB)) --image $(LAB_IMAGE_$(LAB)) \
	  --vault-args "-e @$(LAB_VAULT) --vault-password-file $(LAB_VAULT_PASS)"

# One WSL session: up, vault, verify, always down; exit code is lab-verify's.
lab-cycle:
	$(MAKE) lab-up LAB=$(LAB)
	$(MAKE) lab-vault LAB=$(LAB)
	$(MAKE) lab-verify LAB=$(LAB) WAVE=$(WAVE); rc=$$?; \
	  $(MAKE) lab-down LAB=$(LAB); exit $$rc
