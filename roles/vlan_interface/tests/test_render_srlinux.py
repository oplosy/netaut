"""SR Linux VLAN/interface render (T-012): twin of the IOS/EOS render tests."""
import pathlib

import jinja2
import yaml

REPO = pathlib.Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "templates" / "srlinux" / "vlan_interface.j2"
INTENDED = REPO / "netbox" / "intended" / "lab-srlinux.yml"


def context():
    data = yaml.safe_load(INTENDED.read_text(encoding="utf-8"))
    device = next(d for d in data["devices"] if d["name"] == "lab-sw01")
    return {"netaut_vlans": data["vlans"], "netaut_interfaces": device["interfaces"]}


def render(ctx):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATE.parent)),
                             undefined=jinja2.StrictUndefined, trim_blocks=True,
                             lstrip_blocks=True)
    return env.get_template(TEMPLATE.name).render(ctx)


def test_rerender_is_byte_identical():
    assert render(context()).encode() == render(context()).encode()


def test_vlan_is_a_mac_vrf_named_by_id():
    out = render(context())
    assert "set / network-instance vlan-99 type mac-vrf\n" in out
    assert 'set / network-instance vlan-99 description "MGMT"\n' in out


def test_access_port_is_untagged_bridged_subinterface_in_the_mac_vrf():
    out = render(context())
    for line in ("set / interface ethernet-1/1 admin-state enable",
                 'set / interface ethernet-1/1 description "mgmt-uplink"',
                 "set / interface ethernet-1/1 vlan-tagging true",
                 "set / interface ethernet-1/1 subinterface 0 type bridged",
                 "set / interface ethernet-1/1 subinterface 0 vlan encap untagged",
                 "set / network-instance vlan-99 interface ethernet-1/1.0"):
        assert line + "\n" in out, line


def test_every_line_is_a_flat_set():
    assert all(ln.startswith("set / ") for ln in render(context()).splitlines())
