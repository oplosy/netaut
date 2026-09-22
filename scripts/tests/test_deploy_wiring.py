"""Deploy wiring (T-003/T-010): facts read via hostvars.localhost must land there."""
import pathlib

import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]


def test_intended_state_fact_is_stored_on_localhost():
    play = yaml.safe_load((REPO / "playbooks" / "deploy" / "site.yml").read_text(encoding="utf-8"))[0]
    load = next(t for t in play["pre_tasks"] if "ansible.builtin.set_fact" in t)
    assert load["delegate_to"] == "localhost"
    assert load.get("delegate_facts") is True, "without it hostvars.localhost.netaut_all is undefined"
