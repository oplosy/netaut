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
