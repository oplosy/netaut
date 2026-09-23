"""ci_gate covers every vendor's intended file (T-012 follow-up)."""
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]


def test_every_lab_intended_file_is_validated_and_rendered():
    gate = (REPO / "scripts" / "ci_gate.py").read_text(encoding="utf-8")
    for intended in sorted((REPO / "netbox" / "intended").glob("lab-*.yml")):
        vendor = intended.stem.removeprefix("lab-")
        rel = f"netbox/intended/{intended.name}"
        assert gate.count(f'"{rel}"') >= 2, rel
        assert f'"--vendor", "{vendor}"' in gate, vendor
