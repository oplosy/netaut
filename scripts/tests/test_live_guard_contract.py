"""live_guard contract (T-011): every entry point fails closed per vendor."""
import pathlib

import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
ROLE = REPO / "roles" / "live_guard"
TASKS = ROLE / "tasks"


def load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_entry_points_assert_vendor_and_wave_before_anything():
    for entry in ("backup", "postcheck", "restore"):
        first = load(TASKS / f"{entry}.yml")[0]["ansible.builtin.assert"]["that"]
        assert "netaut_vendor in ['eos']" in first, entry
        assert "netaut_wave | default('') | length > 0" in first, entry


def test_ios_has_no_live_implementation_yet():
    assert not (TASKS / "ios").exists()


def test_every_vendor_dir_implements_all_actions():
    for vendor_dir in (p for p in TASKS.iterdir() if p.is_dir()):
        for action in ("backup", "fetch", "restore"):
            assert (vendor_dir / f"{action}.yml").is_file(), (vendor_dir.name, action)


def test_backup_and_fetch_write_outside_repo():
    defaults = (ROLE / "defaults" / "main.yml").read_text(encoding="utf-8")
    assert "lookup('env','HOME')" in defaults
    assert "reports/" not in defaults


def test_restore_is_guarded_by_backup_presence():
    text = (TASKS / "restore.yml").read_text(encoding="utf-8")
    assert "netaut_backup_file is not defined" in text
    assert "netaut_backup_file is defined" in text


def test_postcheck_fails_on_any_drift():
    text = (TASKS / "postcheck.yml").read_text(encoding="utf-8")
    assert "--fail-on-drift" in text and "--device" in text
