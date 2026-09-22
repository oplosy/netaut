"""Routing render + policy tests (T-007).

Covers A1 (byte-identical rerender with expected IOS lines) and INV-005
(dangling prefix-list references fail the policy check).
Run: pytest roles/routing/tests/ -q
"""
import pathlib
import subprocess
import sys

import jinja2
import yaml

REPO = pathlib.Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "templates" / "ios" / "routing" / "static.j2"
SAMPLE = REPO / "netbox" / "intended" / "sample.yml"
POLICY_CHECK = REPO / "roles" / "routing" / "files" / "policy_check.py"


def routing_context(data):
    return {
        "netaut_static_routes": data.get("static_routes", []),
        "netaut_prefix_lists": data.get("prefix_lists", []),
        "netaut_route_maps": data.get("route_maps", []),
    }


def render(context):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE.parent)),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env.get_template(TEMPLATE.name).render(context)


def sample_data():
    return yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))


def test_rerender_is_byte_identical():
    """A1: same policy input renders byte-identical output twice."""
    context = routing_context(sample_data())
    assert render(context).encode() == render(context).encode()


def test_ios_routing_content():
    """A1: rendered output carries static route, prefix-list and route-map."""
    out = render(routing_context(sample_data()))
    assert "ip route 192.0.2.0/24 10.0.0.1 name LAB-WAN" in out
    assert "ip prefix-list PL-LAB-LOCAL seq 5 permit 10.0.0.0/24" in out
    assert "route-map RM-LAB-OUT permit 10" in out
    assert "match ip address prefix-list PL-LAB-LOCAL" in out


def test_policy_check_clean_sample():
    proc = subprocess.run(
        [sys.executable, str(POLICY_CHECK), "--input", str(SAMPLE)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stdout
    assert "policy-check OK" in proc.stdout


def test_policy_check_rejects_dangling_reference(tmp_path):
    """INV-005: undefined prefix-list reference fails closed."""
    data = sample_data()
    data["route_maps"][0]["sequences"][0]["match_prefix_list"] = "PL-NOPE"
    target = tmp_path / "intended.yml"
    target.write_text(yaml.safe_dump(data), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(POLICY_CHECK), "--input", str(target)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1
    assert "undefined prefix-list" in proc.stdout


def test_policy_tool_opens_no_device_connections():
    source = POLICY_CHECK.read_text(encoding="utf-8")
    banned = ["socket", "paramiko", "netmiko", "napalm", "ncclient", "requests",
              "urllib", "ansible", "pyats", "pexpect", "ssh"]
    hits = [b for b in banned if b in source]
    assert not hits, f"network-capable imports in policy tool: {hits}"


def test_each_command_on_its_own_line():
    """Regression: a trailing {% endif %} under trim_blocks glued the named
    static route onto the next prefix-list line."""
    lines = render(routing_context(sample_data())).splitlines()
    assert "ip route 192.0.2.0/24 10.0.0.1 name LAB-WAN" in lines
    assert "ip prefix-list PL-LAB-LOCAL seq 5 permit 10.0.0.0/24" in lines


def test_unnamed_route_renders_without_name():
    context = routing_context(sample_data())
    context["netaut_static_routes"] = [{"prefix": "198.51.100.0/24", "next_hop": "10.0.0.1"}]
    assert "ip route 198.51.100.0/24 10.0.0.1" in render(context).splitlines()
