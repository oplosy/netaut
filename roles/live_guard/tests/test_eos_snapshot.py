"""EOS running-config -> operational snapshot (T-010)."""
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
TOOL = REPO / "roles" / "live_guard" / "files" / "eos_snapshot.py"
sys.path.insert(0, str(TOOL.parent))
import eos_snapshot  # noqa: E402

FIX = HERE / "fixtures"


def read(name):
    return (FIX / name).read_text(encoding="utf-8")


def test_clean_config_matches_intended_shape():
    assert eos_snapshot.parse(read("clean.cfg")) == {
        "vlans": [{"id": 99, "name": "MGMT"}],
        "interfaces": [{"name": "Ethernet1", "access_vlan": 99}],
        "common": {"ntp_servers": ["10.0.0.53"], "dns_servers": ["10.0.0.53"],
                   "syslog_servers": ["10.0.0.54"]},
    }


def test_vlan_lists_and_default_names():
    snap = eos_snapshot.parse(read("drifted.cfg"))
    assert {"id": 10, "name": "VLAN0010"} in snap["vlans"]
    assert {"id": 21, "name": "VLAN0021"} in snap["vlans"]
    assert {"id": 99, "name": "WRONG"} in snap["vlans"]


def test_default_vlan_one_never_reported():
    snap = eos_snapshot.parse("vlan 1\n   name default\n!\nvlan 99\n")
    assert snap["vlans"] == [{"id": 99, "name": "VLAN0099"}]


def test_vrf_qualifiers_keep_only_ips():
    assert eos_snapshot.parse(read("vrf.cfg"))["common"] == {
        "ntp_servers": ["10.0.0.53"], "dns_servers": ["10.0.0.53", "10.0.0.55"],
        "syslog_servers": ["10.0.0.54"]}


def test_cli_writes_snapshot_that_drift_accepts(tmp_path):
    out = tmp_path / "snap.json"
    res = subprocess.run([sys.executable, str(TOOL), "--config", f"lab-sw01={FIX / 'clean.cfg'}",
                          "--out", str(out)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    drift = subprocess.run(
        [sys.executable, str(REPO / "roles" / "drift" / "files" / "drift.py"),
         "--intended", str(REPO / "netbox" / "intended" / "lab-eos.yml"),
         "--operational", str(out), "--report", str(tmp_path / "r.md"),
         "--device", "lab-sw01", "--fail-on-drift"], capture_output=True, text=True)
    assert drift.returncode == 0, drift.stderr
    assert json.loads(out.read_text())["devices"]["lab-sw01"]["vlans"][0]["id"] == 99


def test_drifted_config_fails_post_check(tmp_path):
    out = tmp_path / "snap.json"
    subprocess.run([sys.executable, str(TOOL), "--config", f"lab-sw01={FIX / 'drifted.cfg'}",
                    "--out", str(out)], check=True, capture_output=True)
    drift = subprocess.run(
        [sys.executable, str(REPO / "roles" / "drift" / "files" / "drift.py"),
         "--intended", str(REPO / "netbox" / "intended" / "lab-eos.yml"),
         "--operational", str(out), "--report", str(tmp_path / "r.md"),
         "--device", "lab-sw01", "--fail-on-drift"], capture_output=True, text=True)
    assert drift.returncode == 2


def test_compare_equal_and_different():
    same = subprocess.run([sys.executable, str(TOOL), "--compare", str(FIX / "clean.cfg"),
                           str(FIX / "clean.cfg")], capture_output=True, text=True)
    diff = subprocess.run([sys.executable, str(TOOL), "--compare", str(FIX / "clean.cfg"),
                           str(FIX / "drifted.cfg")], capture_output=True, text=True)
    assert same.returncode == 0
    assert diff.returncode == 2 and "vlans" in diff.stdout


def test_missing_config_file_is_error(tmp_path):
    res = subprocess.run([sys.executable, str(TOOL), "--config", f"x={tmp_path / 'nope.cfg'}",
                          "--out", str(tmp_path / "o.json")], capture_output=True, text=True)
    assert res.returncode == 1


def test_no_secret_material_in_snapshot():
    assert "sha512" not in json.dumps(eos_snapshot.parse(read("clean.cfg")))
