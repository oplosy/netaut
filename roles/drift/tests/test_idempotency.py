"""Drift detection + idempotency tests (T-004).

Covers A1 (second consecutive run reports no-change) and A2 (seeded drift is
detected and reported without pushing config: inputs provably untouched).
Run: pytest roles/drift/tests/test_idempotency.py -q
"""
import hashlib
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
DRIFT = REPO / "roles" / "drift" / "files" / "drift.py"
INTENDED = REPO / "netbox" / "intended" / "sample.yml"
SNAP_DIR = REPO / "playbooks" / "drift" / "snapshots"


def run_tool(operational, report, extra=()):
    return subprocess.run(
        [sys.executable, str(DRIFT), "--intended", str(INTENDED),
         "--operational", str(operational), "--report", str(report), *extra],
        capture_output=True,
        text=True,
    )


def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def test_clean_snapshot_no_drift(tmp_path):
    report = tmp_path / "drift.md"
    proc = run_tool(SNAP_DIR / "clean.json", report)
    assert proc.returncode == 0, proc.stderr
    assert "NO DRIFT" in report.read_text(encoding="utf-8")


def test_second_run_reports_no_change(tmp_path):
    """A1: consecutive runs are byte-identical and still clean."""
    first, second = tmp_path / "first.md", tmp_path / "second.md"
    assert run_tool(SNAP_DIR / "clean.json", first).returncode == 0
    assert run_tool(SNAP_DIR / "clean.json", second).returncode == 0
    assert first.read_bytes() == second.read_bytes()
    assert "NO DRIFT" in second.read_text(encoding="utf-8")


def test_inputs_untouched_by_runs(tmp_path):
    """Read-only proof: input hashes identical before and after runs."""
    before = (sha(INTENDED), sha(SNAP_DIR / "clean.json"), sha(SNAP_DIR / "drifted.json"))
    run_tool(SNAP_DIR / "clean.json", tmp_path / "a.md")
    run_tool(SNAP_DIR / "drifted.json", tmp_path / "b.md", ("--fail-on-drift",))
    after = (sha(INTENDED), sha(SNAP_DIR / "clean.json"), sha(SNAP_DIR / "drifted.json"))
    assert before == after


def test_seeded_drift_detected_and_reported(tmp_path):
    """A2: vlan rename + rogue interface + syslog change are all reported."""
    report = tmp_path / "drift.md"
    proc = run_tool(SNAP_DIR / "drifted.json", report, ("--fail-on-drift",))
    assert proc.returncode == 2
    text = report.read_text(encoding="utf-8")
    assert "DRIFT FOUND" in text
    assert "MGMT-RENAMED" in text
    assert "GigabitEthernet0/1" in text
    assert "syslog_servers" in text


def test_tool_opens_no_device_connections():
    """Detection must be incapable of pushing: stdlib + yaml only."""
    source = DRIFT.read_text(encoding="utf-8")
    banned = ["socket", "paramiko", "netmiko", "napalm", "ncclient", "requests",
              "urllib", "ansible", "pyats", "pexpect", "ssh"]
    hits = [b for b in banned if b in source]
    assert not hits, f"network-capable imports in drift tool: {hits}"


def test_device_filter_ignores_other_devices(tmp_path):
    """--device compares one host only: the others do not count as missing."""
    snap = tmp_path / "one.json"
    snap.write_text(
        '{"devices": {"lab-sw01": {"vlans": [{"id": 99, "name": "MGMT"}],'
        ' "interfaces": [{"name": "GigabitEthernet0/0", "access_vlan": 99}],'
        ' "common": {"ntp_servers": ["10.0.0.53"], "dns_servers": ["10.0.0.53"],'
        ' "syslog_servers": ["10.0.0.54"]}}}}', encoding="utf-8")
    res = run_tool(snap, tmp_path / "r.md", ("--device", "lab-sw01", "--fail-on-drift"))
    assert res.returncode == 0, res.stderr


def test_device_filter_unknown_device_is_error(tmp_path):
    res = run_tool(SNAP_DIR / "clean.json", tmp_path / "r.md", ("--device", "nope"))
    assert res.returncode == 1


def test_intended_interface_missing_operationally_is_drift(tmp_path):
    """Review T-015 C1: a port the device does not report as access is drift."""
    snap = tmp_path / "no-iface.json"
    snap.write_text(
        '{"devices": {"lab-sw01": {"vlans": [{"id": 99, "name": "MGMT"}],'
        ' "interfaces": [],'
        ' "common": {"ntp_servers": ["10.0.0.53"], "dns_servers": ["10.0.0.53"],'
        ' "syslog_servers": ["10.0.0.54"]}}}}', encoding="utf-8")
    report = tmp_path / "r.md"
    res = run_tool(snap, report, ("--device", "lab-sw01", "--fail-on-drift"))
    assert res.returncode == 2
    assert "intended interface GigabitEthernet0/0 missing operationally" in report.read_text(
        encoding="utf-8")
