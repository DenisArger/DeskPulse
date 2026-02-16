#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import time

from Xlib import X, display
from Xlib.ext import record
from Xlib.protocol import rq


def run(cmd):
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return subprocess.run(cmd, check=False, text=True, capture_output=True, env=env)


def pactl(*args):
    return run(["pactl", *args])


def wpctl(*args):
    return run(["wpctl", *args])


def get_default_sink():
    out = pactl("info").stdout
    for line in out.splitlines():
        if line.startswith("Default Sink:"):
            return line.split(":", 1)[1].strip()
    return None


def pick_headphones_sink():
    out = pactl("list", "short", "sinks").stdout
    sinks = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            sinks.append(parts[1].strip())
    for sink in sinks:
        if ".analog-stereo" in sink:
            return sink
    if sinks:
        return sinks[0]
    return None


def set_headphones_port(sink):
    for port in ("analog-output-headphones", "headphones", "output-headphones"):
        if pactl("set-sink-port", sink, port).returncode == 0:
            return True
    return False


def set_volume(sink, step_percent):
    # PipeWire-native volume change is smoother and causes fewer glitches than pactl loop.
    val = abs(step_percent)
    if step_percent > 0:
        r = wpctl("set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", f"{val}%+")
    else:
        r = wpctl("set-volume", "@DEFAULT_AUDIO_SINK@", f"{val}%-")
    if r.returncode != 0:
        sign = "+" if step_percent > 0 else "-"
        pactl("set-sink-volume", sink, f"{sign}{val}%")


class HoverVolume:
    def __init__(self, sink, step, panel_height, panel_position, cooldown_ms, allow_grab):
        self.local_d = display.Display()
        self.rec_d = display.Display()
        self.root = self.local_d.screen().root
        self.sink = sink
        self.step = step
        self.panel_height = panel_height
        self.panel_position = panel_position
        self.cooldown = cooldown_ms / 1000.0
        self.last_action_ts = 0.0
        self.screen_h = self.root.get_geometry().height
        self.allow_grab = allow_grab

    def in_panel_zone(self, y):
        if self.panel_position == "top":
            return 0 <= y <= self.panel_height
        return (self.screen_h - self.panel_height) <= y <= self.screen_h

    def process_reply(self, reply):
        if reply.category != record.FromServer:
            return
        if reply.client_swapped:
            return
        if not reply.data or reply.data[0] < 2:
            return

        data = reply.data
        while data:
            event, data = rq.EventField(None).parse_binary_value(
                data, self.rec_d.display, None, None
            )
            if event.type != X.ButtonPress:
                continue

            if event.detail not in (4, 5):
                continue

            now = time.monotonic()
            if now - self.last_action_ts < self.cooldown:
                continue

            y = event.root_y
            if not self.in_panel_zone(y):
                continue

            if event.detail == 4:
                set_volume(self.sink, self.step)
            else:
                set_volume(self.sink, -self.step)
            self.last_action_ts = now

    def run(self):
        if not self.rec_d.has_extension("RECORD"):
            if self.allow_grab:
                self.run_fallback_grab()
                return
            print(
                "X RECORD extension is not available. "
                "Run with --allow-grab to force fallback (it can block wheel in apps).",
                file=sys.stderr,
            )
            sys.exit(1)

        ctx = self.rec_d.record_create_context(
            0,
            [record.AllClients],
            [
                {
                    "core_requests": (0, 0),
                    "core_replies": (0, 0),
                    "ext_requests": (0, 0, 0, 0),
                    "ext_replies": (0, 0, 0, 0),
                    "delivered_events": (0, 0),
                    "device_events": (X.ButtonPress, X.ButtonPress),
                    "errors": (0, 0),
                    "client_started": False,
                    "client_died": False,
                }
            ],
        )
        try:
            self.rec_d.record_enable_context(ctx, self.process_reply)
        finally:
            self.rec_d.record_free_context(ctx)

    def run_fallback_grab(self):
        # Fallback for environments without X RECORD extension.
        self.root.grab_button(
            4,
            X.AnyModifier,
            True,
            X.ButtonPressMask,
            X.GrabModeAsync,
            X.GrabModeAsync,
            X.NONE,
            X.NONE,
        )
        self.root.grab_button(
            5,
            X.AnyModifier,
            True,
            X.ButtonPressMask,
            X.GrabModeAsync,
            X.GrabModeAsync,
            X.NONE,
            X.NONE,
        )
        self.local_d.sync()

        while True:
            event = self.local_d.next_event()
            if event.type != X.ButtonPress or event.detail not in (4, 5):
                continue

            now = time.monotonic()
            if now - self.last_action_ts < self.cooldown:
                continue

            y = event.root_y
            if not self.in_panel_zone(y):
                continue

            if event.detail == 4:
                set_volume(self.sink, self.step)
            else:
                set_volume(self.sink, -self.step)
            self.last_action_ts = now


def main():
    parser = argparse.ArgumentParser(
        description="Adjust headphones volume with mouse wheel when cursor is on taskbar area."
    )
    parser.add_argument("--sink", default="", help="Sink name. Default: auto-detect.")
    parser.add_argument("--step", type=int, default=2, help="Volume step in percent.")
    parser.add_argument("--panel-height", type=int, default=48, help="Panel zone height in px.")
    parser.add_argument(
        "--panel-position",
        choices=("top", "bottom"),
        default="bottom",
        help="Panel position on screen.",
    )
    parser.add_argument("--cooldown-ms", type=int, default=220, help="Wheel event cooldown in ms.")
    parser.add_argument(
        "--allow-grab",
        action="store_true",
        help="Allow fallback grab mode when X RECORD is unavailable (can break wheel in apps).",
    )
    args = parser.parse_args()

    sink = args.sink or get_default_sink() or pick_headphones_sink()
    if not sink:
        print("No sink found.", file=sys.stderr)
        sys.exit(1)

    if sink == "auto_null":
        detected = pick_headphones_sink()
        if detected:
            sink = detected
            pactl("set-default-sink", sink)
    set_headphones_port(sink)

    app = HoverVolume(
        sink=sink,
        step=max(1, min(20, args.step)),
        panel_height=max(8, args.panel_height),
        panel_position=args.panel_position,
        cooldown_ms=max(10, args.cooldown_ms),
        allow_grab=args.allow_grab,
    )
    app.run()


if __name__ == "__main__":
    main()
