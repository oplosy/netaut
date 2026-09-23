"""SR Linux running datastore JSON -> operational snapshot (T-012)."""
import copy
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
TOOL = REPO / "roles" / "live_guard" / "files" / "srlinux_snapshot.py"
DRIFT = REPO / "roles" / "drift" / "files" / "drift.py"
INTENDED = REPO / "netbox" / "intended" / "lab-srlinux.yml"
sys.path.insert(0, str(TOOL.parent))
import srlinux_snapshot  # noqa: E402

FIX = HERE / "fixtures" / "srlinux"
CLEAN_SNAPSHOT = {
    "vlans": [{"id": 99, "name": "MGMT"}],
    "interfaces": [{"name": "ethernet-1/1", "access_vlan": 99}],
    "common": {"ntp_servers": ["10.0.0.53"], "dns_servers": ["10.0.0.53"],
               "syslog_servers": ["10.0.0.54"]},
}


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def cli(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)],
                          capture_output=True, text=True)


def test_clean_matches_intended_shape():
    assert srlinux_snapshot.parse(load("clean.json")) == CLEAN_SNAPSHOT


def test_pristine_has_no_vlans_and_keeps_the_clab_dns():
    snap = srlinux_snapshot.parse(load("pristine.json"))
    assert snap["vlans"] == [] and snap["interfaces"] == []
    assert snap["common"] == {"ntp_servers": [], "dns_servers": ["10.255.255.254"],
                              "syslog_servers": []}


def test_prefix_free_document_parses_the_same():
    """Review focus 2: prefixes may come and go between releases."""
    bare = srlinux_snapshot.strip_prefixes(load("clean.json"))
    assert json.dumps(bare).count("srl_nokia-") == 0
    assert srlinux_snapshot.parse(bare) == CLEAN_SNAPSHOT


def test_tagged_subinterface_is_not_an_access_port():
    """Review focus 5: tagged or routed members are not access ports."""
    doc = load("clean.json")
    eth = doc["srl_nokia-interfaces:interface"][0]
    eth["subinterface"][0]["srl_nokia-interfaces-vlans:vlan"] = {
        "encap": {"single-tagged": {"vlan-id": 99}}}
    assert srlinux_snapshot.parse(doc)["interfaces"] == []
    doc = load("clean.json")
    doc["srl_nokia-interfaces:interface"][0]["subinterface"][0]["type"] = "routed"
    assert srlinux_snapshot.parse(doc)["interfaces"] == []


def test_only_mac_vrfs_named_vlan_n_are_vlans():
    doc = load("clean.json")
    nis = doc["srl_nokia-network-instance:network-instance"]
    nis.append({"name": "tenant-a", "type": "srl_nokia-network-instance:mac-vrf"})
    nis.append({"name": "vlan-7", "type": "srl_nokia-network-instance:ip-vrf"})
    assert srlinux_snapshot.parse(doc)["vlans"] == [{"id": 99, "name": "MGMT"}]


def test_vlan_without_description_is_named_after_the_instance():
    doc = load("clean.json")
    del doc["srl_nokia-network-instance:network-instance"][1]["description"]
    assert srlinux_snapshot.parse(doc)["vlans"] == [{"id": 99, "name": "vlan-99"}]


def test_non_ip_values_are_dropped():
    doc = load("clean.json")
    doc["srl_nokia-system:system"]["srl_nokia-ntp:ntp"]["server"].append(
        {"address": "ntp.example.net"})
    assert srlinux_snapshot.parse(doc)["common"]["ntp_servers"] == ["10.0.0.53"]


def test_cli_snapshot_feeds_drift_clean_and_drifted(tmp_path):
    out = tmp_path / "snap.json"
    assert cli("--config", f"lab-sw01={FIX / 'clean.json'}", "--out", out).returncode == 0
    drift = subprocess.run(
        [sys.executable, str(DRIFT), "--intended", str(INTENDED), "--operational", str(out),
         "--report", str(tmp_path / "r.md"), "--device", "lab-sw01", "--fail-on-drift"],
        capture_output=True, text=True)
    assert drift.returncode == 0, drift.stderr
    assert cli("--config", f"lab-sw01={FIX / 'pristine.json'}", "--out", out).returncode == 0
    drift = subprocess.run(
        [sys.executable, str(DRIFT), "--intended", str(INTENDED), "--operational", str(out),
         "--report", str(tmp_path / "r.md"), "--device", "lab-sw01", "--fail-on-drift"],
        capture_output=True, text=True)
    assert drift.returncode == 2


def test_compare_equal_and_parsed_difference():
    assert cli("--compare", FIX / "clean.json", FIX / "clean.json").returncode == 0
    res = cli("--compare", FIX / "pristine.json", FIX / "clean.json")
    assert res.returncode == 2
    assert "vlans" in res.stdout and "common" in res.stdout


def test_compare_catches_a_change_outside_the_parsed_fields(tmp_path):
    doc = load("clean.json")
    doc["srl_nokia-system:system"]["srl_nokia-logging:logging"]["buffer"][0]["rotate"] = 9
    other = tmp_path / "other.json"
    other.write_text(json.dumps(doc), encoding="utf-8")
    res = cli("--compare", FIX / "clean.json", other)
    assert res.returncode == 2
    assert "config sections differ: system" in res.stdout


def test_compare_output_never_contains_config_content(tmp_path):
    """Review focus 4: backups hold hashed secrets; print names and counts only."""
    doc = load("clean.json")
    hashed = "$y$j9T$notarealhashbutlookslikeone"
    doc["srl_nokia-system:system"]["aaa"] = {"authentication": {"user": [
        {"username": "admin", "password": hashed}]}}
    other = tmp_path / "other.json"
    other.write_text(json.dumps(doc), encoding="utf-8")
    res = cli("--compare", FIX / "clean.json", other)
    assert res.returncode == 2
    for needle in (hashed, "10.0.0.53", "mgmt-uplink", "admin"):
        assert needle not in res.stdout + res.stderr


def test_bad_input_is_an_error(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    assert cli("--compare", bad, bad).returncode == 1
    bad.write_text("not json", encoding="utf-8")
    assert cli("--config", f"x={bad}", "--out", tmp_path / "o.json").returncode == 1
    assert cli("--config", f"x={tmp_path / 'missing.json'}",
               "--out", tmp_path / "o.json").returncode == 1


def test_parse_does_not_mutate_its_input():
    doc = load("clean.json")
    before = copy.deepcopy(doc)
    srlinux_snapshot.parse(doc)
    assert doc == before
