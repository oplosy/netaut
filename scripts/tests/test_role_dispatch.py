"""Role vendor dispatch contract (T-008, INV-003)."""
import pathlib
import re

import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
ROLES = ["common", "vlan_interface", "routing"]
VENDORS = ["ios", "eos"]
MODULE = re.compile(r"^\s*(cisco\.ios|arista\.eos|nokia\.srlinux)\.", re.M)


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


def test_access_ports_force_access_mode_like_the_templates():
    """Role and template must converge: both templates render switchport mode access."""
    for vendor in VENDORS:
        tasks = yaml.safe_load((REPO / "roles" / "vlan_interface" / "tasks" / f"{vendor}.yml")
                               .read_text(encoding="utf-8"))
        l2 = next(t for t in tasks if t["name"] == "Ensure access interfaces")
        module = next(v for k, v in l2.items() if k.endswith("_l2_interfaces"))
        assert module["config"][0]["mode"] == "access", vendor


SRLINUX_ROLES = ["common", "vlan_interface"]


def srlinux_tasks(role):
    return yaml.safe_load((REPO / "roles" / role / "tasks" / "srlinux.yml")
                          .read_text(encoding="utf-8"))


def test_srlinux_exists_only_for_live_roles_and_routing_fails_closed():
    for role in SRLINUX_ROLES:
        assert (REPO / "roles" / role / "tasks" / "srlinux.yml").is_file(), role
    assert not (REPO / "roles" / "routing" / "tasks" / "srlinux.yml").exists()
    routing = (REPO / "roles" / "routing" / "tasks" / "main.yml").read_text(encoding="utf-8")
    assert "'srlinux'" not in routing


def test_supported_vendor_asserts_include_srlinux():
    for role in SRLINUX_ROLES:
        tasks = yaml.safe_load((REPO / "roles" / role / "tasks" / "main.yml")
                               .read_text(encoding="utf-8"))
        vendor = next(t for t in tasks if t["name"] == "Require a supported vendor (fail closed)")
        assert vendor["ansible.builtin.assert"]["that"] == [
            "netaut_vendor in ['ios', 'eos', 'srlinux']"], role


def test_srlinux_files_only_call_config_and_never_save():
    for role in SRLINUX_ROLES:
        for task in srlinux_tasks(role):
            modules = [k for k in task if "." in k]
            assert modules == ["nokia.srlinux.config"], (role, task["name"])
            assert task["nokia.srlinux.config"]["save_when"] == "never", (role, task["name"])


def test_srlinux_access_port_matches_the_template():
    """Role and template must converge on the same access-port shape."""
    task = next(t for t in srlinux_tasks("vlan_interface")
                if t["name"] == "Ensure access interfaces")
    iface, member = task["nokia.srlinux.config"]["update"]
    assert iface["path"] == "/interface[name={{ item.name }}]"
    assert iface["value"]["vlan-tagging"] is True
    sub = iface["value"]["subinterface"][0]
    assert sub == {"index": 0, "type": "bridged", "vlan": {"encap": {"untagged": {}}}}
    assert member["path"] == "/network-instance[name=vlan-{{ item.access_vlan }}]"
    assert member["value"] == {"interface": [{"name": "{{ item.name }}.0"}]}


def test_srlinux_vlan_is_mac_vrf_named_by_id():
    task = next(t for t in srlinux_tasks("vlan_interface") if t["name"] == "Ensure VLANs exist")
    (vlan,) = task["nokia.srlinux.config"]["update"]
    assert vlan["path"] == "/network-instance[name=vlan-{{ item.id }}]"
    assert vlan["value"] == {"type": "mac-vrf", "description": "{{ item.name }}"}


def test_srlinux_dns_replaces_the_server_list():
    task = next(t for t in srlinux_tasks("common") if t["name"] == "Configure DNS name servers")
    (dns,) = task["nokia.srlinux.config"]["replace"]
    assert dns["path"].endswith("/server-list")
    assert dns["value"] == "{{ netaut_common.dns_servers }}"
