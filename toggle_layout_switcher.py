#!/usr/bin/env python3
import os
import signal
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
TARGET = BASE_DIR / "layout_switcher.py"
PID_FILE = Path.home() / ".cache" / "layout_switcher.pid"
LOG_FILE = Path.home() / ".cache" / "layout_switcher.log"


def is_pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def stop_existing(pid):
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def remove_pid_file():
    if PID_FILE.exists():
        PID_FILE.unlink()


def start_new():
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [
                str(TARGET),
                "--hotkey",
                "Pause",
                "--layout-a",
                "us",
                "--layout-b",
                "ru",
            ],
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    print("ON")


def main():
    if not TARGET.exists():
        print(f"Missing target script: {TARGET}", file=sys.stderr)
        sys.exit(1)

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding="utf-8").strip())
        except ValueError:
            pid = 0

        if pid and is_pid_alive(pid):
            stop_existing(pid)
            remove_pid_file()
            print("OFF")
            return

        remove_pid_file()

    start_new()


if __name__ == "__main__":
    main()
