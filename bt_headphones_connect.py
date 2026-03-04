#!/usr/bin/env python3
import argparse
import re
import shutil
import subprocess
import sys
import time


def run(cmd, timeout=10, input_text=None):
    try:
        return subprocess.run(
            cmd,
            input=input_text,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout or ""
        stderr = e.stderr or ""
        if not isinstance(stdout, str):
            stdout = stdout.decode(errors="ignore")
        if not isinstance(stderr, str):
            stderr = stderr.decode(errors="ignore")
        stderr = (stderr + "\ncommand timed out").strip()
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=124,
            stdout=stdout,
            stderr=stderr,
        )


def run_bt(commands, timeout=12):
    payload = "\n".join(commands + ["quit"]) + "\n"
    return run(["bluetoothctl"], timeout=timeout, input_text=payload)


def run_bt_cmd(args, timeout=20):
    return run(["bluetoothctl", *args], timeout=timeout)


def bt_lines(*commands, timeout=12):
    r = run_bt(list(commands), timeout=timeout)
    return (r.stdout + "\n" + r.stderr).splitlines()


def sanitize_mac(mac):
    m = mac.strip().upper()
    if not re.fullmatch(r"[0-9A-F]{2}(:[0-9A-F]{2}){5}", m):
        return None
    return m


def device_list():
    lines = bt_lines("devices", timeout=8)
    result = []
    for line in lines:
        m = re.match(r"Device\s+([0-9A-F:]{17})\s+(.+)$", line.strip(), re.I)
        if m:
            result.append((m.group(1).upper(), m.group(2).strip()))
    return result


def paired_device_list():
    lines = bt_lines("paired-devices", timeout=8)
    result = []
    for line in lines:
        m = re.match(r"Device\s+([0-9A-F:]{17})\s+(.+)$", line.strip(), re.I)
        if m:
            result.append((m.group(1).upper(), m.group(2).strip()))
    return result


def choose_device_interactive(scan_seconds):
    print(f"Scanning Bluetooth devices for {scan_seconds}s...")
    start_scan(scan_seconds)
    devs = device_list()
    if not devs:
        devs = paired_device_list()
        if devs:
            print("No new devices found. Using paired devices list.")
        else:
            return None

    print("Found devices:")
    for i, (mac, name) in enumerate(devs, start=1):
        print(f"{i}. {name} ({mac})")

    if len(devs) == 1:
        print(f"Auto-selected: {devs[0][1]} ({devs[0][0]})")
        return devs[0][0]

    if not sys.stdin.isatty():
        return devs[0][0]

    while True:
        raw = input("Choose device number (or Enter to cancel): ").strip()
        if raw == "":
            return None
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(devs):
                return devs[idx - 1][0]
        print("Invalid selection. Try again.")


def find_mac_by_name(name):
    name_l = name.lower().strip()
    exact = []
    contains = []
    for mac, dev_name in device_list():
        dn = dev_name.lower()
        if dn == name_l:
            exact.append(mac)
        elif name_l in dn:
            contains.append(mac)
    if exact:
        return exact[0]
    if contains:
        return contains[0]
    return None


def start_scan(seconds):
    run_bt(["scan on"], timeout=6)
    time.sleep(max(1, seconds))
    run_bt(["scan off"], timeout=6)


def bt_info(mac):
    r = run_bt_cmd(["info", mac], timeout=10)
    return (r.stdout + "\n" + r.stderr)


def is_connected(mac):
    return "Connected: yes" in bt_info(mac)


def ensure_bt_ready():
    run_bt_cmd(["power", "on"], timeout=10)
    run_bt_cmd(["agent", "on"], timeout=10)
    run_bt_cmd(["default-agent"], timeout=10)


def trust_pair_connect(mac, retries=4):
    for i in range(1, retries + 1):
        # Device may be temporarily out of discovery cache; refresh before connect.
        run_bt_cmd(["scan", "on"], timeout=8)
        time.sleep(2.0)
        run_bt_cmd(["scan", "off"], timeout=8)
        run_bt_cmd(["trust", mac], timeout=10)
        run_bt_cmd(["pair", mac], timeout=35)
        run_bt_cmd(["connect", mac], timeout=35)
        time.sleep(1.5)
        if is_connected(mac):
            return True
        if i < retries:
            time.sleep(2.0)
    return False


def list_cards_short():
    out = run(["pactl", "list", "short", "cards"], timeout=8).stdout
    cards = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            cards.append(parts[1].strip())
    return cards


def card_block(card_name):
    out = run(["pactl", "list", "cards"], timeout=10).stdout
    for block in out.split("Card #"):
        if f"Name: {card_name}" in block:
            return block
    return ""


def pick_best_bt_profile(card_name):
    block = card_block(card_name)
    if not block:
        return None
    profiles = {}
    for line in block.splitlines():
        s = line.strip()
        if not s or ":" not in s:
            continue
        if "(sinks:" not in s:
            continue
        profile = s.split(":", 1)[0].strip()
        if profile not in ("a2dp_sink", "handsfree_head_unit"):
            continue
        available_yes = "available: yes" in s
        profiles[profile] = available_yes

    # Prefer A2DP, fallback to HFP/HSP handsfree profile.
    if profiles.get("a2dp_sink") is True:
        return "a2dp_sink"
    if profiles.get("handsfree_head_unit") is True:
        return "handsfree_head_unit"
    if "a2dp_sink" in profiles:
        return "a2dp_sink"
    if "handsfree_head_unit" in profiles:
        return "handsfree_head_unit"
    return None


def set_best_bt_profile(card_name):
    profile = pick_best_bt_profile(card_name)
    if not profile:
        return False
    r = run(["pactl", "set-card-profile", card_name, profile], timeout=8)
    return r.returncode == 0


def find_bt_sink(mac):
    mac_u = mac.replace(":", "_")
    out = run(["pactl", "list", "short", "sinks"], timeout=8).stdout
    sinks = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            sinks.append(parts[1].strip())
    preferred = [s for s in sinks if mac_u in s and ".a2dp" in s]
    if preferred:
        return preferred[0]
    fallback = [
        s for s in sinks
        if mac_u in s or s.startswith("bluez_output.") or s.startswith("bluez_sink.")
    ]
    return fallback[0] if fallback else None


def configure_audio(mac, set_default_sink=True):
    mac_u = mac.replace(":", "_")
    card = f"bluez_card.{mac_u}"
    cards = list_cards_short()
    if card in cards:
        set_best_bt_profile(card)
    time.sleep(1.0)
    sink = find_bt_sink(mac)
    if sink and set_default_sink:
        run(["pactl", "set-default-sink", sink], timeout=8)
        run(["pactl", "set-sink-mute", sink, "0"], timeout=8)
    return sink


def main():
    parser = argparse.ArgumentParser(
        description="Reliable Bluetooth headphones connect helper (BlueZ + PipeWire/PulseAudio)."
    )
    parser.add_argument("--mac", default="", help="Headphones MAC (AA:BB:CC:DD:EE:FF).")
    parser.add_argument("--name", default="", help="Headphones name (used if --mac is omitted).")
    parser.add_argument("--scan-seconds", type=int, default=8, help="Scan duration when device is not found.")
    parser.add_argument("--retries", type=int, default=4, help="Connection retries.")
    parser.add_argument("--no-default-sink", action="store_true", help="Do not set BT sink as default.")
    args = parser.parse_args()

    if not shutil.which("bluetoothctl"):
        print("bluetoothctl not found", file=sys.stderr)
        sys.exit(1)

    mac = sanitize_mac(args.mac) if args.mac else ""
    if args.mac and not mac:
        print("Invalid --mac format. Use AA:BB:CC:DD:EE:FF", file=sys.stderr)
        sys.exit(2)

    ensure_bt_ready()

    if not mac and args.name:
        mac = find_mac_by_name(args.name)
        if not mac:
            start_scan(args.scan_seconds)
            mac = find_mac_by_name(args.name)

    if not mac:
        mac = choose_device_interactive(args.scan_seconds)

    if not mac:
        print("No device selected.", file=sys.stderr)
        sys.exit(3)

    ok = trust_pair_connect(mac, retries=max(1, args.retries))
    if not ok:
        print(f"Failed to connect: {mac}", file=sys.stderr)
        sys.exit(4)

    sink = configure_audio(mac, set_default_sink=not args.no_default_sink)
    print(f"Connected: {mac}")
    if sink:
        print(f"Sink: {sink}")
    else:
        print("Connected, but BT sink was not detected yet.")


if __name__ == "__main__":
    main()
