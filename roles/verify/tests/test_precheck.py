"""Pre-check gate tests (T-003).

Covers A1: seeded conflicts abort (exit 1) while the clean sample passes,
and the gate opens zero device connections (static import check).
Run: pytest roles/verify/tests/test_precheck.py -q
"""
import pathlib
import subprocess
import sys

import yaml

REPO = pathlib.Path(__file__).resolve().parents[3]
PRECHECK = REPO / "roles" / "verify" / "files" / "precheck.py"
SAMPLE = REPO / "netbox" / "intended" / "sample.yml"

BASE = {
    "sites": [{"name": "LAB-DC1"}],
    "vrfs": [{"name": "MGMT", "rd": "65000:99"}],
    "vlans": [{"id": 99, "name": "MGMT", "vrf": "MGMT"}],
    "prefixes": [{"prefix": "10.0.0.0/24", "vlan": 99, "vrf": "MGMT"}],
    "devices": [
        {
            "name": "lab-sw01",
            "site": "LAB-DC1",
            "platform": "ios",
            "interfaces": [
                {"name": "GigabitEthernet0/0", "access_vlan": 99},
            ],
            "common": {"ntp_servers": ["10.0.0.53"]},
        }
    ],
}


def run_gate(path):
    return subprocess.run(
        [sys.executable, str(PRECHECK), "--input", str(path)],
        capture_output=True,
        text=True,
    )


def write(tmp_path, mutate):
    data = yaml.safe_load(yaml.safe_dump(BASE))
    mutate(data)
    target = tmp_path / "intended.yml"
    target.write_text(yaml.safe_dump(data), encoding="utf-8")
    return target


def test_clean_sample_passes():
    proc = run_gate(SAMPLE)
    assert proc.returncode == 0, proc.stderr
    assert "precheck OK" in proc.stdout


def test_duplicate_vlan_name_aborts(tmp_path):
    def mutate(d):
        d["vlans"].append({"id": 99, "name": "OTHER", "vrf": "MGMT"})

    proc = run_gate(write(tmp_path, mutate))
    assert proc.returncode == 1
    assert "conflicting names" in proc.stderr


def test_unknown_vlan_reference_aborts(tmp_path):
    def mutate(d):
        d["devices"][0]["interfaces"][0]["access_vlan"] = 4000

    proc = run_gate(write(tmp_path, mutate))
    assert proc.returncode == 1
    assert "unknown vlan" in proc.stderr


def test_overlapping_prefix_aborts(tmp_path):
    def mutate(d):
        d["prefixes"].append({"prefix": "10.0.0.128/25", "vlan": 99, "vrf": "MGMT"})

    proc = run_gate(write(tmp_path, mutate))
    assert proc.returncode == 1
    assert "overlapping prefixes" in proc.stderr


def test_duplicate_device_aborts(tmp_path):
    def mutate(d):
        d["devices"].append(dict(d["devices"][0]))

    proc = run_gate(write(tmp_path, mutate))
    assert proc.returncode == 1
    assert "duplicate device" in proc.stderr


def test_gate_opens_no_device_connections():
    """The gate must be incapable of touching devices: stdlib + yaml only."""
    source = PRECHECK.read_text(encoding="utf-8")
    banned = ["socket", "paramiko", "netmiko", "napalm", "ncclient", "requests",
              "urllib", "ansible", "pyats", "pexpect", "ssh"]
    hits = [b for b in banned if b in source]
    assert not hits, f"network-capable imports in gate: {hits}"
