"""Lab make targets (T-013 follow-up, review T-015 minors 1 and 5)."""
import os
import pathlib
import shutil
import subprocess

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
MAKEFILE = (REPO / "Makefile").read_text(encoding="utf-8")
needs_make = pytest.mark.skipif(not (shutil.which("make") and shutil.which("sh")),
                                reason="needs make and sh")


def recipe(target):
    lines = MAKEFILE.split(f"\n{target}:", 1)[1].split("\n")[1:]
    return "\n".join(ln for ln in lines if ln.startswith("\t")) if lines else ""


def test_lab_login_travels_by_environment_and_is_not_echoed():
    vault = recipe("lab-vault")
    assert vault.startswith("\t@"), vault
    assert "LAB_LOGIN=" in vault
    assert "$(LAB_VAULT_PASS) '" not in vault  # no positional login argument
    script = (REPO / "scripts" / "lab_vault.sh").read_text(encoding="utf-8")
    assert 'login="${LAB_LOGIN:-admin}"' in script
    assert "${3" not in script


@needs_make
def test_unknown_lab_stops_with_a_clear_message():
    res = subprocess.run(["make", "-n", "lab-up", "LAB=bogus"], cwd=REPO,
                         capture_output=True, text=True)
    assert res.returncode != 0
    assert "unknown LAB=bogus" in res.stdout + res.stderr


@needs_make
def test_lab_cycle_tears_down_even_when_bring_up_fails(tmp_path):
    fake = tmp_path / "clab"
    log = tmp_path / "calls.log"
    fake.write_text('#!/bin/sh\necho "$1" >> "$FAKE_CLAB_LOG"\n'
                    '[ "$1" = deploy ] && exit 1\nexit 0\n', encoding="utf-8")
    fake.chmod(0o755)
    env = dict(os.environ, FAKE_CLAB_LOG=str(log), CLAB_LABDIR_BASE=str(tmp_path / "lab"))
    res = subprocess.run(["make", "lab-cycle", "LAB=srlinux", f"CLAB={fake.as_posix()}"],
                         cwd=REPO, capture_output=True, text=True, env=env)
    assert res.returncode != 0
    assert log.read_text(encoding="utf-8").split() == ["deploy", "destroy"]
