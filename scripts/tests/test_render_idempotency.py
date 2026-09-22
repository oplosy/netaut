"""render_idempotency covers every template and refuses vacuous passes (T-008)."""
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
TOOL = REPO / "scripts" / "render_idempotency.py"


def run(inp, vendor):
    return subprocess.run([sys.executable, str(TOOL), "--input", inp, "--vendor", vendor,
                           "--repo", str(REPO)], capture_output=True, text=True)


def test_ios_renders_all_templates():
    res = run("netbox/intended/sample.yml", "ios")
    assert res.returncode == 0, res.stdout
    assert "lab-sw01 vlan_interface.j2: IDENTICAL" in res.stdout
    assert "lab-sw01 routing/static.j2: IDENTICAL" in res.stdout


def test_eos_renders_all_templates():
    res = run("netbox/intended/lab-eos.yml", "eos")
    assert res.returncode == 0, res.stdout
    assert "lab-sw02 routing/static.j2: IDENTICAL" in res.stdout


def test_no_matching_platform_fails_closed():
    res = run("netbox/intended/sample.yml", "eos")
    assert res.returncode == 1
    assert "no devices with platform eos" in res.stdout
