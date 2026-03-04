#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import List

from Xlib import X, XK, display
from Xlib.ext import record, xtest
from Xlib.protocol import rq


EN_TO_RU_LOWER = {
    "q": "й",
    "w": "ц",
    "e": "у",
    "r": "к",
    "t": "е",
    "y": "н",
    "u": "г",
    "i": "ш",
    "o": "щ",
    "p": "з",
    "[": "х",
    "]": "ъ",
    "a": "ф",
    "s": "ы",
    "d": "в",
    "f": "а",
    "g": "п",
    "h": "р",
    "j": "о",
    "k": "л",
    "l": "д",
    ";": "ж",
    "'": "э",
    "z": "я",
    "x": "ч",
    "c": "с",
    "v": "м",
    "b": "и",
    "n": "т",
    "m": "ь",
    ",": "б",
    ".": "ю",
    "`": "ё",
}

RU_TO_EN_LOWER = {v: k for k, v in EN_TO_RU_LOWER.items()}

EN_TO_RU = {}
RU_TO_EN = {}
for en_ch, ru_ch in EN_TO_RU_LOWER.items():
    EN_TO_RU[en_ch] = ru_ch
    EN_TO_RU[en_ch.upper()] = ru_ch.upper()
    RU_TO_EN[ru_ch] = en_ch
    RU_TO_EN[ru_ch.upper()] = en_ch.upper()

WORD_CHARS = set(EN_TO_RU.keys()) | set(RU_TO_EN.keys())
RESET_KEY_NAMES = {
    "space",
    "Tab",
    "Return",
    "KP_Enter",
    "Escape",
    "Left",
    "Right",
    "Up",
    "Down",
    "Home",
    "End",
    "Prior",
    "Next",
    "Delete",
    "Insert",
    "Menu",
    "Shift_L",
    "Shift_R",
    "Control_L",
    "Control_R",
    "Alt_L",
    "Alt_R",
    "Super_L",
    "Super_R",
    "Meta_L",
    "Meta_R",
    "Caps_Lock",
    "Num_Lock",
    "Scroll_Lock",
}


def run(cmd):
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return subprocess.run(cmd, check=False, text=True, capture_output=True, env=env)


def convert_layout_word(word: str, direction: str) -> str:
    if direction == "en_to_ru":
        table = EN_TO_RU
    elif direction == "ru_to_en":
        table = RU_TO_EN
    else:
        raise ValueError(f"Unsupported direction: {direction}")
    return "".join(table.get(ch, ch) for ch in word)


@dataclass
class WordBuffer:
    max_len: int
    chars: List[str] = field(default_factory=list)
    last_input_ts: float = 0.0

    def add_char(self, ch: str) -> None:
        if len(self.chars) >= self.max_len:
            self.clear()
            return
        self.chars.append(ch)
        self.last_input_ts = time.monotonic()

    def backspace(self) -> None:
        if self.chars:
            self.chars.pop()
            self.last_input_ts = time.monotonic()

    def clear(self) -> None:
        self.chars.clear()

    def word(self) -> str:
        return "".join(self.chars)


def choose_direction_from_word(word: str) -> str:
    latin = sum(1 for ch in word if "a" <= ch.lower() <= "z")
    cyrillic = sum(1 for ch in word if "а" <= ch.lower() <= "я" or ch.lower() == "ё")
    return "ru_to_en" if cyrillic > latin else "en_to_ru"


class LayoutController:
    def __init__(self, layout_a: str, layout_b: str):
        self.layout_a = layout_a
        self.layout_b = layout_b
        self.has_xkb_switch = shutil.which("xkb-switch") is not None

    def current_layout(self):
        if self.has_xkb_switch:
            res = run(["xkb-switch"])
            if res.returncode == 0:
                value = res.stdout.strip()
                if value:
                    return value
        res = run(["setxkbmap", "-query"])
        if res.returncode != 0:
            return None
        for line in res.stdout.splitlines():
            if line.strip().startswith("layout:"):
                value = line.split(":", 1)[1].strip()
                if "," in value:
                    return value.split(",", 1)[0].strip()
                return value
        return None

    def set_layout(self, layout: str) -> bool:
        return run(["setxkbmap", "-layout", layout]).returncode == 0

    def switch_to(self, target_layout: str) -> bool:
        if self.has_xkb_switch:
            current = self.current_layout()
            if current and current != target_layout:
                if run(["xkb-switch", "-n"]).returncode == 0:
                    return True
        return self.set_layout(target_layout)


class LayoutSwitcher:
    def __init__(self, hotkey, max_word_len, cooldown_ms, layout_a, layout_b, verbose):
        self.local_d = display.Display()
        self.rec_d = display.Display()
        self.hotkey = hotkey
        self.cooldown = cooldown_ms / 1000.0
        self.last_action_ts = 0.0
        self.buffer = WordBuffer(max_len=max_word_len)
        self.verbose = verbose
        self.layout = LayoutController(layout_a=layout_a, layout_b=layout_b)

    def log(self, message):
        if self.verbose:
            print(f"[layout-switcher] {message}", flush=True)

    def _key_name(self, event):
        shift_pressed = bool(event.state & X.ShiftMask)
        caps_pressed = bool(event.state & X.LockMask)

        keysym = self.local_d.keycode_to_keysym(event.detail, 1 if shift_pressed else 0)
        if keysym == 0:
            keysym = self.local_d.keycode_to_keysym(event.detail, 0)
        name = XK.keysym_to_string(keysym) or ""

        if len(name) == 1 and name.isalpha() and (shift_pressed ^ caps_pressed):
            return name.upper()
        return name

    def _is_reset_key(self, key_name):
        if not key_name:
            return False
        if key_name in RESET_KEY_NAMES:
            return True
        return len(key_name) == 1 and not key_name.isalnum()

    def _type_text(self, text):
        for ch in text:
            self._type_char(ch)
        self.local_d.sync()

    def _erase_word(self, length):
        for _ in range(length):
            self._press_key_name("BackSpace")
        self.local_d.sync()

    def _press_keycode(self, keycode):
        xtest.fake_input(self.local_d, X.KeyPress, keycode)
        xtest.fake_input(self.local_d, X.KeyRelease, keycode)

    def _press_key_name(self, key_name):
        keysym = XK.string_to_keysym(key_name)
        if keysym == 0:
            return
        keycode = self.local_d.keysym_to_keycode(keysym)
        if keycode:
            self._press_keycode(keycode)

    def _char_to_key(self, ch):
        keysym = XK.string_to_keysym(ch)
        if keysym == 0:
            if len(ch) == 1:
                codepoint = ord(ch)
                keysym = codepoint if codepoint <= 0xFF else (0x01000000 | codepoint)
        if keysym == 0:
            return 0, False
        keycode = self.local_d.keysym_to_keycode(keysym)
        if not keycode:
            return 0, False
        if self.local_d.keycode_to_keysym(keycode, 0) == keysym:
            return keycode, False
        if self.local_d.keycode_to_keysym(keycode, 1) == keysym:
            return keycode, True
        return keycode, False

    def _type_char(self, ch):
        keycode, needs_shift = self._char_to_key(ch)
        if not keycode:
            return
        shift_keycode = self.local_d.keysym_to_keycode(XK.string_to_keysym("Shift_L"))
        if needs_shift and shift_keycode:
            xtest.fake_input(self.local_d, X.KeyPress, shift_keycode)
        self._press_keycode(keycode)
        if needs_shift and shift_keycode:
            xtest.fake_input(self.local_d, X.KeyRelease, shift_keycode)

    def _handle_hotkey(self):
        now = time.monotonic()
        if now - self.last_action_ts < self.cooldown:
            return

        word = self.buffer.word()
        if not word:
            self.log("hotkey pressed on empty buffer")
            return

        current = self.layout.current_layout()
        if current == self.layout.layout_a:
            direction = "en_to_ru"
            target_layout = self.layout.layout_b
        elif current == self.layout.layout_b:
            direction = "ru_to_en"
            target_layout = self.layout.layout_a
        else:
            direction = choose_direction_from_word(word)
            target_layout = self.layout.layout_b if direction == "en_to_ru" else self.layout.layout_a

        converted = convert_layout_word(word, direction)
        self._erase_word(len(word))
        self.layout.switch_to(target_layout)
        self._type_text(converted)

        self.log(f"fixed '{word}' -> '{converted}' ({direction}, {current or 'unknown'} -> {target_layout})")
        self.buffer.clear()
        self.last_action_ts = now

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
            if event.type != X.KeyPress:
                continue

            key_name = self._key_name(event)
            if not key_name:
                continue

            if key_name == self.hotkey:
                self._handle_hotkey()
                continue

            if key_name == "BackSpace":
                self.buffer.backspace()
                continue

            if self._is_reset_key(key_name):
                self.buffer.clear()
                continue

            if len(key_name) == 1 and key_name in WORD_CHARS:
                self.buffer.add_char(key_name)
            elif len(key_name) == 1 and key_name.isalpha():
                # Keep alphabetic chars that exist in system layout but are outside map.
                self.buffer.add_char(key_name)

    def run(self):
        if not self.rec_d.has_extension("RECORD"):
            print("X RECORD extension is not available.", file=sys.stderr)
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
                    "device_events": (X.KeyPress, X.KeyPress),
                    "errors": (0, 0),
                    "client_started": False,
                    "client_died": False,
                }
            ],
        )
        self.log("started")
        try:
            self.rec_d.record_enable_context(ctx, self.process_reply)
        finally:
            self.rec_d.record_free_context(ctx)


def check_dependencies():
    missing = []
    for tool in ("setxkbmap",):
        if shutil.which(tool) is None:
            missing.append(tool)
    if missing:
        print("Missing dependencies: " + ", ".join(missing), file=sys.stderr)
        return False
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Punto-like EN/RU layout fixer for last word via hotkey on X11."
    )
    parser.add_argument("--hotkey", default="Pause", help="Hotkey name (default: Pause).")
    parser.add_argument("--layout-a", default="us", help="First layout name (default: us).")
    parser.add_argument("--layout-b", default="ru", help="Second layout name (default: ru).")
    parser.add_argument("--max-word-len", type=int, default=64, help="Max tracked word length.")
    parser.add_argument("--cooldown-ms", type=int, default=220, help="Hotkey cooldown in ms.")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging.")
    args = parser.parse_args()

    if not check_dependencies():
        sys.exit(1)

    app = LayoutSwitcher(
        hotkey=args.hotkey,
        max_word_len=max(1, args.max_word_len),
        cooldown_ms=max(0, args.cooldown_ms),
        layout_a=args.layout_a,
        layout_b=args.layout_b,
        verbose=args.verbose,
    )
    app.run()


if __name__ == "__main__":
    main()
