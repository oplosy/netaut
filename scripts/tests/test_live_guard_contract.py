"""live_guard contract (T-011): every entry point fails closed per vendor."""
import json
import pathlib
import shutil
import subprocess

import pytest
import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
ROLE = REPO / "roles" / "live_guard"
TASKS = ROLE / "tasks"


def load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def guards(tasks):
    return [t["ansible.builtin.assert"]["that"][0] for t in tasks[:2]]


def test_entry_points_assert_vendor_and_wave_before_anything():
    for entry in ("backup", "postcheck"):
        assert guards(load(TASKS / f"{entry}.yml")) == [
            "netaut_vendor in ['eos', 'srlinux']", "netaut_wave | default('') | length > 0"], entry


def test_restore_guards_run_first_inside_the_backup_block():
    block = next(t for t in load(TASKS / "restore.yml") if "block" in t)
    assert block["when"] == "netaut_backup_file is defined"
    assert guards(block["block"]) == [
        "netaut_vendor in ['eos', 'srlinux']", "netaut_wave | default('') | length > 0"]


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


def test_backup_refuses_a_reused_wave_id():
    """A retry under the same wave id must not overwrite the pristine backup."""
    tasks = load(TASKS / "backup.yml")
    names = [t["name"] for t in tasks]
    refuse = names.index("Refuse to overwrite an existing backup (fail closed)")
    assert refuse < names.index("Take pre-wave backup")
    assert "live_guard_backup_prior.matched == 0" in tasks[refuse]["ansible.builtin.assert"]["that"]


def test_wave_id_is_unique_across_vendor_extensions():
    """Review T-015 minor 2: an eos .cfg backup blocks the same wave id on srlinux."""
    tasks = load(TASKS / "backup.yml")
    find = next(t for t in tasks if t.get("register") == "live_guard_backup_prior")
    args = find["ansible.builtin.find"]
    assert args["paths"] == "{{ netaut_backup_dir }}"
    assert args["patterns"] == "{{ inventory_hostname }}-{{ netaut_wave }}.*"
    assert "use_regex" not in args


def test_srlinux_restore_checks_the_backup_before_replacing():
    """Review T-015 minor 4: a corrupt backup fails with a readable, secret-free step."""
    tasks = load(TASKS / "srlinux" / "restore.yml")
    names = [t["name"] for t in tasks]
    check = next(t for t in tasks if "ansible.builtin.command" in t)
    assert names.index(check["name"]) < names.index("Replace running datastore with backup")
    assert "no_log" not in check
    argv = check["ansible.builtin.command"]["argv"]
    assert argv[1].endswith("srlinux_snapshot.py")
    assert "{{ inventory_hostname }}={{ netaut_backup_file }}" in argv


def test_restore_source_is_wrapped_in_raw():
    """eos_config templates src: the backup must not be rendered as Jinja."""
    text = (TASKS / "eos" / "restore.yml").read_text(encoding="utf-8")
    assert "{% raw %}" in text and "{% endraw %}" in text
    assert "src: \"{{ live_guard_restore_src }}\"" in text


def test_backup_paths_use_the_vendor_extension():
    defaults = (ROLE / "defaults" / "main.yml").read_text(encoding="utf-8")
    assert "live_guard_ext:" in defaults
    for entry in ("backup.yml", "postcheck.yml", "restore.yml", "eos/backup.yml"):
        text = (TASKS / entry).read_text(encoding="utf-8")
        assert ".cfg" not in text, entry
        assert "live_guard_ext" in text, entry


def test_srlinux_secret_tasks_are_no_log():
    """Review focus 4: backups and fetches carry the admin password hash."""
    for action in ("backup", "fetch", "restore"):
        for task in load(TASKS / "srlinux" / f"{action}.yml"):
            if any(k.startswith("nokia.srlinux.") or k == "ansible.builtin.copy" for k in task):
                assert task.get("no_log") is True, (action, task["name"])


def test_srlinux_restore_replaces_root_and_never_saves():
    (task,) = [t for t in load(TASKS / "srlinux" / "restore.yml")
               if "nokia.srlinux.config" in t]
    cfg = task["nokia.srlinux.config"]
    assert cfg["replace"][0]["path"] == "/"
    assert cfg["save_when"] == "never"


@pytest.mark.skipif(shutil.which("ansible-playbook") is None, reason="needs ansible-core")
def test_srlinux_restore_value_is_not_templated(tmp_path):
    """Review focus 1: braces in the backup must reach the device verbatim."""
    (task,) = [t for t in load(TASKS / "srlinux" / "restore.yml")
               if "nokia.srlinux.config" in t]
    expr = task["nokia.srlinux.config"]["replace"][0]["value"]
    backup = tmp_path / "b.json"
    backup.write_text(json.dumps({"system": {"banner": {"login-banner": "{{ 6 * 7 }}"}}}),
                      encoding="utf-8")
    result = tmp_path / "out.json"
    play = [{
        "hosts": "localhost", "gather_facts": False,
        "vars": {"netaut_backup_file": backup.as_posix(), "restored": expr},
        "tasks": [{"ansible.builtin.copy": {
            "content": "{{ restored | to_json }}", "dest": result.as_posix()}}],
    }]
    path = tmp_path / "p.yml"
    path.write_text(yaml.safe_dump(play), encoding="utf-8")
    res = subprocess.run(["ansible-playbook", "-i", "localhost,", "-c", "local", str(path)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stdout[-2000:]
    restored = json.loads(result.read_text(encoding="utf-8"))
    assert restored["system"]["banner"]["login-banner"] == "{{ 6 * 7 }}"


def test_postcheck_keeps_the_raw_fetch_apart_from_the_snapshot():
    """Review T-015 I1: the snapshot must not overwrite the fetched datastore."""
    tasks = load(TASKS / "postcheck.yml")
    fetch = next(t for t in tasks if t["name"] == "Fetch post-wave running-config")
    fetched = fetch["vars"]["live_guard_fetch_to"]
    snap = next(t for t in tasks if t["name"] == "Build operational snapshot from running-config")
    argv = snap["ansible.builtin.command"]["argv"]
    out = argv[argv.index("--out") + 1]
    assert argv[argv.index("--config") + 1].endswith("=" + fetched)
    for ext in ("cfg", "json"):  # live_guard_ext for eos and srlinux
        assert fetched.replace("{{ live_guard_ext }}", ext) != out, ext
