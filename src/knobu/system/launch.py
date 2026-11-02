"""Starting Knobu's own helper windows (color picker, text extractor) from the daemon."""

import subprocess
import sys


def knobu(*args: str) -> None:
    subprocess.Popen([sys.executable, "-m", "knobu", *args], start_new_session=True)
