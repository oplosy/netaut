# NetAut shortcuts. Every target mirrors a CI gate; `make gates` is the
# full local chain and must stay green before merge.
SAMPLE ?= netbox/intended/sample.yml
INVENTORY ?= inventories/lab.yml

.PHONY: gates lint scan validate render test preview-deploy preview-drift help

help:
	@echo "gates | lint | scan | validate | render | test | preview-deploy | preview-drift"

gates: lint scan validate render test

lint:
	python -m yamllint -c .yamllint.yml .

scan:
	python scripts/secret_scan.py --root .

validate:
	python scripts/validate_model.py --schema netbox/schema.yml --input $(SAMPLE)
	python scripts/validate_model.py --schema netbox/schema.yml --input netbox/intended/lab-eos.yml

render:
	python scripts/render_idempotency.py --input $(SAMPLE) --vendor ios --repo .

test:
	python -m pytest roles scripts/tests -q

preview-deploy:
	ansible-playbook playbooks/deploy/site.yml -i $(INVENTORY) --check --diff

preview-drift:
	ansible-playbook playbooks/drift/report.yml -i $(INVENTORY) --check
