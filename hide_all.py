#!/usr/bin/env python3
from Xlib import display

d = display.Display()
root = d.screen().root


for w in root.query_tree().children:
    try:
        w.map()
    except Exception:
        pass

d.flush()
