"""Schema validation for both vendor intended-state files (T-008)."""
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
VALIDATE = REPO / "scripts" / "validate_model.py"


def run(input_path):
    return subprocess.run(
        [sys.executable, str(VALIDATE), "--schema", str(REPO / "netbox" / "schema.yml"),
         "--input", str(input_path)], capture_output=True, text=True)


def test_ios_sample_still_valid():
    assert run(REPO / "netbox" / "intended" / "sample.yml").returncode == 0


def test_eos_lab_intended_valid():
    res = run(REPO / "netbox" / "intended" / "lab-eos.yml")
    assert res.returncode == 0, res.stdout


def test_unknown_platform_rejected(tmp_path):
    text = (REPO / "netbox" / "intended" / "lab-eos.yml").read_text(encoding="utf-8")
    bad = tmp_path / "bad.yml"
    bad.write_text(text.replace("platform: eos", "platform: junos"), encoding="utf-8")
    res = run(bad)
    assert res.returncode == 1
    assert "disallowed platform" in res.stdout
