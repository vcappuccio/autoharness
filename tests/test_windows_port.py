"""Regression tests for the Windows port: shell-independent hook entry, bounded child sessions, detach flags."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from autoharness import config
from autoharness.hook import dispatch, spawn

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "bin" / "hook.py"


def _clean_env(home):
    # no PYTHONPATH: bin/hook.py must make the package importable by itself
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env.update(HOME=str(home), USERPROFILE=str(home))
    return env


def _run_hook(stdin_text, cwd, home):
    return subprocess.run([sys.executable, str(HOOK)], input=stdin_text, capture_output=True,
                          text=True, encoding="utf-8", cwd=str(cwd), env=_clean_env(home), timeout=60)


# --- hooks.json: every event goes through the shell-independent entry point ---

def test_hook_commands_reference_bin_hook_and_no_shell_prefix():
    hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
    for groups in hooks.values():
        for group in groups:
            for hook in group["hooks"]:
                cmd = hook["command"]
                assert "bin/hook.py" in cmd
                assert "PYTHONPATH=" not in cmd  # POSIX prefix: PowerShell would reject it
    assert HOOK.is_file()


# --- bin/hook.py end to end ---

def test_hook_unknown_event_exits_clean(tmp_path):
    r = _run_hook('{"hook_event_name": "SomethingUnknown"}', tmp_path, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Traceback" not in r.stderr


def test_hook_malformed_stdin_exits_clean(tmp_path):
    r = _run_hook("not json", tmp_path, tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Traceback" not in r.stderr


# --- child session argv: bounded by turns, still non-interactive ---

def test_build_command_bounds_turns():
    cmd = spawn.build_command(agent="autoharness:reflector", claude_bin="claude")
    i = cmd.index("--max-turns")
    assert cmd[i + 1] == str(config.CHILD_MAX_TURNS)
    assert "--dangerously-skip-permissions" in cmd


def test_build_fork_command_bounds_turns():
    cmd = spawn.build_fork_command(session_id="sess-1", claude_bin="claude")
    i = cmd.index("--max-turns")
    assert cmd[i + 1] == str(config.CHILD_MAX_TURNS)
    assert "--dangerously-skip-permissions" in cmd


# --- _run_bounded: success, timeout, and missing executable ---

def test_run_bounded_success_passes_bundle_through_stdin():
    argv = [sys.executable, "-c", "import sys; sys.stdout.write(sys.stdin.read().upper())"]
    proc = spawn._run_bounded(argv, dict(os.environ), "abc", 60)
    assert proc.returncode == 0
    assert proc.stdout == "ABC"


def test_run_bounded_timeout_stops_child_and_reports_it():
    argv = [sys.executable, "-c", "import time; time.sleep(60)"]
    started = time.monotonic()
    proc = spawn._run_bounded(argv, dict(os.environ), "", 1)
    assert time.monotonic() - started < 20
    assert proc.returncode == spawn.TIMEOUT_RETURNCODE
    assert "exceeded" in proc.stderr


def test_run_bounded_missing_executable_returns_launch_code():
    proc = spawn._run_bounded(["definitely-not-a-real-binary-xyz"], dict(os.environ), "", 60)
    assert proc.returncode == spawn.LAUNCH_RETURNCODE


# --- detached launch flags per platform ---

def test_detach_kwargs_match_platform():
    kw = dispatch._detach_kwargs()
    if sys.platform == "win32":
        assert set(kw) == {"creationflags"}
        assert kw["creationflags"]
        assert "start_new_session" not in kw
    else:
        assert kw == {"start_new_session": True}


# --- hard bounds are positive ---

def test_child_bounds_are_positive():
    assert config.CHILD_TIMEOUT_S >= 1
    assert config.CHILD_MAX_TURNS >= 1
