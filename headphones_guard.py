#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import time


def run(cmd):
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return subprocess.run(cmd, check=False, text=True, capture_output=True, env=env)


def pactl(*args):
    return run(["pactl", *args])


def amixer(*args):
    return run(["amixer", *args])


def get_default_sink():
    out = pactl("info").stdout
    for line in out.splitlines():
        if line.startswith("Default Sink:"):
            return line.split(":", 1)[1].strip()
    return None


def get_sinks_short():
    out = pactl("list", "short", "sinks").stdout
    sinks = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            sinks.append(parts[1].strip())
    return sinks


def get_cards_short():
    out = pactl("list", "short", "cards").stdout
    cards = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            cards.append(parts[1].strip())
    return cards


def get_sink_inputs():
    out = pactl("list", "short", "sink-inputs").stdout
    ids = []
    for line in out.splitlines():
        parts = line.split("\t")
        if parts and parts[0].isdigit():
            ids.append(parts[0])
    return ids


def get_card_profile(card_name):
    out = pactl("list", "cards").stdout
    blocks = out.split("Card #")
    for block in blocks:
        if f"Name: {card_name}" not in block:
            continue
        m = re.search(r"Active Profile:\s*(.+)", block)
        if m:
            return m.group(1).strip()
    return None


def set_best_card_profile(card_name):
    wanted = [
        "output:analog-stereo+input:analog-stereo",
        "output:analog-stereo",
    ]
    current = get_card_profile(card_name)
    if current in wanted:
        return False
    for profile in wanted:
        r = pactl("set-card-profile", card_name, profile)
        if r.returncode == 0:
            return True
    return False


def reset_card_profile(card_name):
    pactl("set-card-profile", card_name, "off")
    time.sleep(0.7)
    for profile in (
        "output:analog-stereo+input:analog-stereo",
        "output:analog-stereo",
    ):
        r = pactl("set-card-profile", card_name, profile)
        if r.returncode == 0:
            return True
    return False


def set_headphones_port(sink_name):
    candidates = [
        "analog-output-headphones",
        "headphones",
        "output-headphones",
    ]
    for port in candidates:
        r = pactl("set-sink-port", sink_name, port)
        if r.returncode == 0:
            return True
    return False


def get_sink_ports_availability(sink_name):
    out = pactl("list", "sinks").stdout
    blocks = out.split("Sink #")
    for block in blocks:
        if f"Name: {sink_name}" not in block:
            continue
        result = {}
        for line in block.splitlines():
            s = line.strip()
            if not s.startswith("analog-output-"):
                continue
            if ":" not in s:
                continue
            port, rest = s.split(":", 1)
            m = re.search(r"(available|not available|availability unknown)", rest)
            if m:
                result[port.strip()] = m.group(1)
        return result
    return {}


def set_best_output_port(sink_name):
    ports = get_sink_ports_availability(sink_name)
    preferred = [
        "analog-output-headphones",
        "analog-output-lineout",
    ]
    for port in preferred:
        if ports.get(port) == "available":
            return pactl("set-sink-port", sink_name, port).returncode == 0
    for port in preferred:
        if port in ports:
            return pactl("set-sink-port", sink_name, port).returncode == 0
    return set_headphones_port(sink_name)


def get_sink_active_port(sink_name):
    out = pactl("list", "sinks").stdout
    blocks = out.split("Sink #")
    for block in blocks:
        if f"Name: {sink_name}" not in block:
            continue
        m = re.search(r"Active Port:\s*(.+)", block)
        if m:
            return m.group(1).strip()
    return None


def pick_real_sink():
    sinks = get_sinks_short()
    for sink in sinks:
        if ".analog-stereo" in sink:
            return sink
    for sink in sinks:
        if sink != "auto_null":
            return sink
    return None


def move_streams_to_sink(sink_name):
    for input_id in get_sink_inputs():
        pactl("move-sink-input", input_id, sink_name)


def recover_output(cards, verbose=False):
    changed = False
    for card in cards:
        if verbose:
            print(f"[guard] resetting card profile: {card}")
        if reset_card_profile(card):
            changed = True
            time.sleep(0.7)

    real_sink = pick_real_sink()
    if real_sink:
        pactl("set-default-sink", real_sink)
        if set_best_output_port(real_sink):
            if verbose:
                print(f"[guard] sink port adjusted: {real_sink}")
        pactl("set-sink-mute", real_sink, "0")
        amixer("-c", "0", "sset", "Front", "unmute")
        move_streams_to_sink(real_sink)
        changed = True
        if verbose:
            print(f"[guard] recovered sink -> {real_sink}")
    return changed


def heal_once(verbose=False):
    changed = False

    cards = get_cards_short()
    if cards:
        if set_best_card_profile(cards[0]):
            changed = True
            if verbose:
                print(f"[guard] card profile fixed: {cards[0]}")

    default_sink = get_default_sink()
    sinks = get_sinks_short()
    if default_sink == "auto_null" or not default_sink or len(sinks) == 0 or sinks == ["auto_null"]:
        if recover_output(cards, verbose=verbose):
            changed = True
        default_sink = get_default_sink()

    if default_sink and default_sink != "auto_null":
        active_port = get_sink_active_port(default_sink)
        ports = get_sink_ports_availability(default_sink)
        active_unavailable = bool(active_port and ports.get(active_port) == "not available")
        if (active_port not in ("analog-output-headphones", "analog-output-lineout") or active_unavailable) and set_best_output_port(default_sink):
            changed = True
            if verbose:
                print(f"[guard] sink port adjusted: {default_sink}")
        pactl("set-sink-mute", default_sink, "0")

    return changed


def main():
    parser = argparse.ArgumentParser(
        description="Fixes random audio output switching and keeps headphones active."
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run continuously and auto-heal audio route.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Watch interval in seconds (default: 2.0).",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not args.watch:
        heal_once(verbose=args.verbose)
        return

    if args.verbose:
        print("[guard] started watch mode")
    while True:
        try:
            heal_once(verbose=args.verbose)
            time.sleep(args.interval)
        except KeyboardInterrupt:
            if args.verbose:
                print("\n[guard] stopped")
            break


if __name__ == "__main__":
    main()
