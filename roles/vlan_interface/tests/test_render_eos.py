"""EOS VLAN/interface render (T-008): twin of the IOS render test."""
import pathlib

import jinja2
import yaml

REPO = pathlib.Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "templates" / "eos" / "vlan_interface.j2"
INTENDED = REPO / "netbox" / "intended" / "lab-eos.yml"


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


def test_eos_content_uses_eos_indent_and_names():
    out = render(context())
    assert "vlan 99\n   name MGMT\n" in out
    assert "interface Ethernet1\n" in out
    assert "   switchport access vlan 99\n" in out
