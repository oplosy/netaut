"""lab_verify recap parsing (T-010): rerun idempotency is judged from the recap."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import lab_verify  # noqa: E402

RECAP = """PLAY RECAP *********************************************************************
lab-sw01                   : ok=12   changed=0    unreachable=0    failed=0    skipped=2    rescued=0    ignored=0
lab-sw02                   : ok=12   changed=3    unreachable=0    failed=0    skipped=2    rescued=0    ignored=0
localhost                  : ok=1    changed=0    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
"""


def test_changed_counts_per_host():
    assert lab_verify.changed_counts(RECAP) == {"lab-sw01": 0, "lab-sw02": 3, "localhost": 0}


def test_empty_recap_is_empty():
    assert lab_verify.changed_counts("no recap here") == {}


def test_rerun_fails_when_a_host_is_missing_from_recap():
    assert not lab_verify.idempotent({"lab-sw01": 0})
    assert lab_verify.idempotent({"lab-sw01": 0, "lab-sw02": 0})


REPO = pathlib.Path(__file__).resolve().parents[2]


def test_inventory_hosts_reads_nested_groups():
    assert lab_verify.inventory_hosts(REPO / "inventories" / "lab-srlinux.yml") == {
        "lab-sw01": "172.20.21.11", "lab-sw02": "172.20.21.12"}


def test_wait_ready_returns_hosts_that_never_answer():
    now = [0.0]

    def connect(addr, timeout):
        if addr[0] == "10.0.0.2":
            raise OSError("refused")

        class Sock:
            def close(self):
                pass
        return Sock()

    def sleep(seconds):
        now[0] += seconds

    left = lab_verify.wait_ready({"a": "10.0.0.1", "b": "10.0.0.2"}, 443, 30,
                                 connect=connect, sleep=sleep, clock=lambda: now[0])
    assert left == ["b"]


def test_main_fails_before_any_play_when_a_host_is_not_ready(monkeypatch, capsys):
    """Review focus 3: an unready lab stops lab-verify before any wave."""
    monkeypatch.setattr(lab_verify, "wait_ready", lambda *a, **k: ["lab-sw02"])
    monkeypatch.setattr(lab_verify, "play",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("play ran")))
    rc = lab_verify.main(["--inventory", str(REPO / "inventories" / "lab-srlinux.yml"),
                          "--wave", "W-t", "--wait-port", "443", "--image", "img:1"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "image: img:1" in out
    assert "not ready: lab-sw02" in out


def test_failed_drill_stops_before_deploy_and_names_the_hosts(monkeypatch, capsys):
    """Review T-015 I3: no deploy/rerun on a lab whose restore was not verified."""
    import subprocess
    calls = []

    def fake_play(inventory, wave, extra):
        calls.append(wave)
        return subprocess.CompletedProcess([], 2, "restore verified for lab-sw01\n", "")

    monkeypatch.setattr(lab_verify, "play", fake_play)
    rc = lab_verify.main(["--inventory", str(REPO / "inventories" / "lab-srlinux.yml"),
                          "--wave", "W-t"])
    out = capsys.readouterr().out
    assert rc == 1
    assert calls == ["W-t-a"]
    assert "restore not verified: lab-sw02" in out
