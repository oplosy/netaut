"""EOS routing render (T-008): twin of the IOS routing test."""
import pathlib

import jinja2
import yaml

REPO = pathlib.Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "templates" / "eos" / "routing" / "static.j2"
INTENDED = REPO / "netbox" / "intended" / "lab-eos.yml"


def render():
    data = yaml.safe_load(INTENDED.read_text(encoding="utf-8"))
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(TEMPLATE.parent)),
                             undefined=jinja2.StrictUndefined, trim_blocks=True,
                             lstrip_blocks=True)
    return env.get_template(TEMPLATE.name).render(
        netaut_static_routes=data["static_routes"],
        netaut_prefix_lists=data["prefix_lists"],
        netaut_route_maps=data["route_maps"])


def test_eos_routing_content():
    out = render()
    assert "ip route 192.0.2.0/24 10.0.0.1 name LAB-WAN\n" in out
    assert "ip prefix-list PL-LAB-LOCAL seq 5 permit 10.0.0.0/24\n" in out
    assert "route-map RM-LAB-OUT permit 10\n   match ip address prefix-list PL-LAB-LOCAL\n" in out


def test_rerender_is_byte_identical():
    assert render().encode() == render().encode()
