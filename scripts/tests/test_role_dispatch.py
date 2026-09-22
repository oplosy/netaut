"""Role vendor dispatch contract (T-008, INV-003)."""
import pathlib
import re

import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
ROLES = ["common", "vlan_interface", "routing"]
VENDORS = ["ios", "eos"]
MODULE = re.compile(r"^\s*(cisco\.ios|arista\.eos)\.", re.M)


def test_each_role_has_every_vendor_file():
    for role in ROLES:
        for vendor in VENDORS:
            assert (REPO / "roles" / role / "tasks" / f"{vendor}.yml").is_file(), (role, vendor)


def test_main_has_no_vendor_modules_and_dispatches():
    for role in ROLES:
        text = (REPO / "roles" / role / "tasks" / "main.yml").read_text(encoding="utf-8")
        assert not MODULE.search(text), role
        tasks = yaml.safe_load(text)
        assert tasks[-1]["ansible.builtin.include_tasks"] == "{{ netaut_vendor }}.yml", role


def test_vendor_files_only_use_their_collection():
    for role in ROLES:
        for vendor, other in (("ios", "arista.eos."), ("eos", "cisco.ios.")):
            text = (REPO / "roles" / role / "tasks" / f"{vendor}.yml").read_text(encoding="utf-8")
            assert other not in text, (role, vendor)
            assert "netaut_module_state" in text, (role, vendor)
