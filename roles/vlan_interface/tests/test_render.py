"""VLAN/interface render tests (T-002).

Covers A1 (byte-identical rerender) and A2 (IOS sample content).
Run: pytest roles/vlan_interface/tests/ -q
"""
import pathlib

import jinja2
import yaml

REPO = pathlib.Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "templates" / "ios" / "vlan_interface.j2"
SAMPLE = REPO / "netbox" / "intended" / "sample.yml"


def load_device(name="lab-sw01"):
    data = yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))
    device = next(d for d in data["devices"] if d["name"] == name)
    return {
        "netaut_vlans": data["vlans"],
        "netaut_interfaces": device["interfaces"],
    }


def render(context):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE.parent)),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template(TEMPLATE.name).render(context)


def test_rerender_is_byte_identical():
    """A1: same intended input renders byte-identical output twice."""
    context = load_device()
    assert render(context).encode() == render(context).encode()


def test_ios_sample_content():
    """A2: rendered IOS sample carries VLAN 99 + access interface."""
    out = render(load_device())
    assert "vlan 99" in out
    assert "name MGMT" in out
    assert "interface GigabitEthernet0/0" in out
    assert "switchport access vlan 99" in out
