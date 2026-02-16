#!/usr/bin/env python3
from Xlib import X, display, protocol

d = display.Display()
root = d.screen().root

WM_CHANGE_STATE = d.intern_atom("WM_CHANGE_STATE")
ICONIC_STATE = 3
NET_CLIENT_LIST = d.intern_atom("_NET_CLIENT_LIST")
NET_WM_STATE = d.intern_atom("_NET_WM_STATE")
NET_WM_STATE_HIDDEN = d.intern_atom("_NET_WM_STATE_HIDDEN")


def minimize_window(win):
    event = protocol.event.ClientMessage(
        window=win,
        client_type=WM_CHANGE_STATE,
        data=(32, [ICONIC_STATE, X.CurrentTime, 0, 0, 0]),
    )
    root.send_event(
        event,
        event_mask=(X.SubstructureRedirectMask | X.SubstructureNotifyMask),
    )


def get_client_windows():
    try:
        prop = root.get_full_property(NET_CLIENT_LIST, X.AnyPropertyType)
        if not prop or prop.value is None:
            return []
        return [d.create_resource_object("window", int(wid)) for wid in prop.value]
    except Exception:
        return []


def is_hidden(win):
    try:
        state = win.get_full_property(NET_WM_STATE, X.AnyPropertyType)
        return bool(state and state.value is not None and NET_WM_STATE_HIDDEN in state.value)
    except Exception:
        return False


def unhide_window(win):
    event = protocol.event.ClientMessage(
        window=win,
        client_type=NET_WM_STATE,
        data=(32, [0, NET_WM_STATE_HIDDEN, 0, 1, 0]),
    )
    root.send_event(
        event,
        event_mask=(X.SubstructureRedirectMask | X.SubstructureNotifyMask),
    )
    win.map()


windows = get_client_windows()
has_normal = any(not is_hidden(w) for w in windows)

for w in windows:
    try:
        if has_normal:
            minimize_window(w)
        else:
            unhide_window(w)
    except Exception:
        pass

d.flush()
