"""Shell-independent entry point for the plugin's hooks.

hooks.json used to run `PYTHONPATH=... python3 -m autoharness.hook.dispatch`, which is POSIX shell syntax and
fails where Windows runs hooks in PowerShell. dispatch also re-launches `sys.executable -m autoharness.hook.spawn`,
which needs PYTHONPATH in the inherited environment, so this file sets both the path and the environment itself.
"""
import os
import sys
from pathlib import Path

SRC = str(Path(__file__).resolve().parent.parent / "src")


def _bootstrap():
    if SRC not in sys.path:
        sys.path.insert(0, SRC)
    existing = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = SRC + os.pathsep + existing if existing else SRC
    os.environ.setdefault("PYTHONUTF8", "1")


_bootstrap()

from autoharness.hook import dispatch  # noqa: E402

if __name__ == "__main__":
    sys.exit(dispatch.main())
