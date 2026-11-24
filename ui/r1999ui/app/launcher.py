import os
import subprocess
import sys
from pathlib import Path

from .. import winutil

CREATE_NO_WINDOW = 0x08000000


def launch_engine(port):
    flags = CREATE_NO_WINDOW if winutil.IS_WINDOWS else 0
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).parent / "engine" / "r1999-engine.exe"
        cmd, cwd, env = [str(exe), "--port", str(port)], None, None
    else:
        root = Path(__file__).resolve().parents[3] / "engine"
        cmd = [sys.executable, "-m", "r1999engine", "--port", str(port)]
        cwd, env = str(root), dict(os.environ, PYTHONPATH=str(root))
    if os.environ.get("R1999_FAKE"):
        cmd.append("--fake")
    return subprocess.Popen(cmd, cwd=cwd, env=env, creationflags=flags)
