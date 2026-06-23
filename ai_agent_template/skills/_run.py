"""Safe subprocess helper shared by command-wrapping skills.

Always invoked with an argument *list* (never a shell string) so user/LLM-
supplied values cannot inject shell syntax. Returns a small, predictable
tuple instead of raising on non-zero exit, so skills can turn failures into
recoverable observations.
"""
from __future__ import annotations

import shutil
import subprocess
from typing import List, Tuple


def have(executable: str) -> bool:
    """True if `executable` is on PATH."""
    return shutil.which(executable) is not None


def run(args: List[str], cwd: str = ".", timeout: int = 30) -> Tuple[int, str, str]:
    """Run a command; return (returncode, stdout, stderr). Never uses a shell."""
    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"command not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"command timed out after {timeout}s: {' '.join(args)}"
