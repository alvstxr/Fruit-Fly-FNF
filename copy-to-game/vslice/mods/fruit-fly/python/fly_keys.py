from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading

ARROW_KEYS = ("left", "down", "up", "right")
DFJK_KEYS = ("d", "f", "j", "k")
WASD_KEYS = ("a", "s", "w", "d")
LAYOUTS = ("arrows", "dfjk", "wasd", "wasd_arrows", "both")

XDT_NAMES = {
    "left": "Left",
    "down": "Down",
    "up": "Up",
    "right": "Right",
    "a": "a",
    "s": "s",
    "w": "w",
    "d": "d",
    "f": "f",
    "j": "j",
    "k": "k",
}

YDO_CODES = {
    "left": 105,
    "down": 108,
    "up": 103,
    "right": 106,
    "a": 30,
    "s": 31,
    "d": 32,
    "w": 17,
    "f": 33,
    "j": 36,
    "k": 37,
}

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    VK = {
        "left": 0x25,
        "down": 0x28,
        "up": 0x26,
        "right": 0x27,
        "a": 0x41,
        "s": 0x53,
        "w": 0x57,
        "d": 0x44,
        "f": 0x46,
        "j": 0x4A,
        "k": 0x4B,
        "esc": 0x1B,
        "q": 0x51,
        "c": 0x43,
        "1": 0x31,
        "2": 0x32,
        "3": 0x33,
        "4": 0x34,
        "f8": 0x77,
    }
    ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = (
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        )

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = (
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        )

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = (
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        )

    class INPUT_UNION(ctypes.Union):
        _fields_ = (("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT))

    class INPUT(ctypes.Structure):
        _fields_ = (("type", wintypes.DWORD), ("union", INPUT_UNION))

    _USER32 = ctypes.windll.user32
    _USER32.SendInput.argtypes = (wintypes.UINT, ctypes.c_void_p, ctypes.c_int)
    _USER32.SendInput.restype = wintypes.UINT
    _USER32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    _USER32.MapVirtualKeyW.restype = wintypes.UINT
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    INPUT_KEYBOARD = 1
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    MAPVK_VK_TO_VSC = 0
else:
    VK = {}
    _USER32 = None

_PYNPUT_KB = None
_LINUX_DOWN = set()
_LINUX_LOCK = threading.Lock()
_LINUX_LISTENER = None

def _pynput_kb():
    global _PYNPUT_KB
    if _PYNPUT_KB is None:
        from pynput.keyboard import Controller

        _PYNPUT_KB = Controller()
    return _PYNPUT_KB

def _pynput_key(name: str):
    from pynput.keyboard import Key

    mapping = {
        "left": Key.left,
        "down": Key.down,
        "up": Key.up,
        "right": Key.right,
        "a": "a",
        "s": "s",
        "w": "w",
        "d": "d",
        "f": "f",
        "j": "j",
        "k": "k",
        "esc": Key.esc,
        "q": "q",
        "c": "c",
        "1": "1",
        "2": "2",
        "3": "3",
        "4": "4",
        "f8": Key.f8,
    }
    return mapping[name]

def _start_linux_hotkeys():
    global _LINUX_LISTENER
    if _LINUX_LISTENER is not None:
        return
    try:
        from pynput import keyboard
    except Exception:
        return

    names = {
        keyboard.Key.esc: "esc",
        keyboard.Key.f8: "f8",
    }

    def _name(key):
        if key in names:
            return names[key]
        try:
            ch = key.char
        except AttributeError:
            return None
        if not ch:
            return None
        ch = ch.lower()
        if ch in ("q", "c", "1", "2", "3", "4"):
            return ch
        return None

    def on_press(key):
        name = _name(key)
        if name:
            with _LINUX_LOCK:
                _LINUX_DOWN.add(name)

    def on_release(key):
        name = _name(key)
        if name:
            with _LINUX_LOCK:
                _LINUX_DOWN.discard(name)

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.daemon = True
    listener.start()
    _LINUX_LISTENER = listener

class KeySender:
    def __init__(self, layout="wasd_arrows"):
        self.layout = layout if layout in LAYOUTS else "wasd_arrows"
        self.held = [False, False, False, False]
        self.target = None

    def names_for_lane(self, index: int):
        if self.layout == "arrows":
            return (ARROW_KEYS[index],)
        if self.layout == "dfjk":
            return (DFJK_KEYS[index],)
        if self.layout == "wasd":
            return (WASD_KEYS[index],)
        if self.layout == "wasd_arrows":
            return (ARROW_KEYS[index], WASD_KEYS[index])
        return (ARROW_KEYS[index], DFJK_KEYS[index])

    def set_layout(self, layout: str):
        layout = layout if layout in LAYOUTS else "wasd_arrows"
        if layout != self.layout:
            self.release_all()
            self.layout = layout

    def set_held(self, bits):
        downs = []
        ups = []
        hwnd = None if self.target is None else getattr(self.target, "handle", self.target)
        for i in range(4):
            want = bool(bits[i])
            if want == self.held[i]:
                continue
            names = self.names_for_lane(i)
            if want:
                downs.extend(names)
            else:
                ups.extend(names)
            self.held[i] = want
        if os.name == "nt":
            try:
                _send_win_many(ups, True, hwnd)
                _send_win_many(downs, False, hwnd)
            except Exception:
                for name in ups:
                    _send_win(name, True, hwnd)
                for name in downs:
                    _send_win(name, False, hwnd)
            return
        for name in ups:
            _keyup(name, self.target)
        for name in downs:
            _keydown(name, self.target)

    def release_all(self):
        for i in range(4):
            if not self.held[i]:
                continue
            for name in self.names_for_lane(i):
                _keyup(name, self.target)
            self.held[i] = False

class EdgeKeys:
    def __init__(self):
        self.prev = {}
        if os.name != "nt":
            _start_linux_hotkeys()

    def pressed(self, name: str) -> bool:
        down = _async_down(name)
        was = self.prev.get(name, False)
        self.prev[name] = down
        return down and not was

def _async_down(name: str) -> bool:
    if os.name == "nt":
        vk = VK.get(name)
        if vk is None:
            return False
        return bool(_USER32.GetAsyncKeyState(vk) & 0x8000)
    with _LINUX_LOCK:
        return name in _LINUX_DOWN

def _keydown(name: str, target=None):
    if os.name == "nt":
        _send_win(name, False, None if target is None else getattr(target, "handle", target))
        return
    _send_posix(name, False, target)

def _keyup(name: str, target=None):
    if os.name == "nt":
        _send_win(name, True, None if target is None else getattr(target, "handle", target))
        return
    _send_posix(name, True, target)

def _key_flags(name: str, up: bool) -> int:
    flags = KEYEVENTF_EXTENDEDKEY if name in ARROW_KEYS else 0
    if up:
        flags |= KEYEVENTF_KEYUP
    return flags

def _key_input(name: str, up: bool) -> INPUT:
    vk = VK[name]
    scan = int(_USER32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC))
    return INPUT(
        type=INPUT_KEYBOARD,
        union=INPUT_UNION(ki=KEYBDINPUT(vk, scan, _key_flags(name, up), 0, 0)),
    )

def _post_hwnd(name: str, up: bool, hwnd):
    if not hwnd:
        return
    vk = VK[name]
    scan = int(_USER32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC))
    msg = WM_KEYUP if up else WM_KEYDOWN
    lparam = 1 | (scan << 16)
    if name in ARROW_KEYS:
        lparam |= 1 << 24
    if up:
        lparam |= 1 << 30
        lparam |= 1 << 31
    _USER32.PostMessageW(int(hwnd), msg, vk, lparam)

def _send_win_many(names, up: bool, hwnd=None):
    if not names:
        return
    n = len(names)
    arr = (INPUT * n)()
    for i, name in enumerate(names):
        arr[i] = _key_input(name, up)
    sent = 0
    try:
        sent = int(_USER32.SendInput(n, ctypes.cast(arr, ctypes.c_void_p), ctypes.sizeof(INPUT)))
    except Exception:
        sent = 0
    if sent != n:
        for name in names:
            _send_win(name, up, hwnd)
        return
    if hwnd:
        for name in names:
            _post_hwnd(name, up, hwnd)

def _send_win(name: str, up: bool, hwnd=None):
    inp = _key_input(name, up)
    sent = 0
    try:
        sent = int(
            _USER32.SendInput(
                1, ctypes.cast(ctypes.byref(inp), ctypes.c_void_p), ctypes.sizeof(INPUT)
            )
        )
    except Exception:
        sent = 0
    if sent != 1:
        vk = VK[name]
        scan = int(_USER32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC))
        _USER32.keybd_event(vk, scan, _key_flags(name, up), 0)
    _post_hwnd(name, up, hwnd)

def _send_posix(name: str, up: bool, target=None):
    if sys.platform == "darwin":
        _send_macos(name, up)
        return
    xname = XDT_NAMES.get(name, name)
    if sys.platform.startswith("linux") and shutil.which("xdotool"):
        action = "keyup" if up else "keydown"
        cmd = ["xdotool", action, xname]
        handle = getattr(target, "handle", None) if target is not None else None
        if isinstance(handle, int):
            cmd = ["xdotool", action, "--window", str(handle), xname]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return
    if sys.platform.startswith("linux") and shutil.which("ydotool"):
        code = YDO_CODES.get(name)
        if code is not None:
            subprocess.run(
                ["ydotool", "key", "%s:%s" % (code, "0" if up else "1")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return
    try:
        kb = _pynput_kb()
        key = _pynput_key(name)
        if up:
            kb.release(key)
        else:
            kb.press(key)
    except Exception:
        pass

MAC_KEY_CODES = {
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
    "a": 0,
    "s": 1,
    "d": 2,
    "w": 13,
    "f": 3,
    "j": 38,
    "k": 40,
}

def _send_macos(name: str, up: bool):
    code = MAC_KEY_CODES.get(name)
    if code is None:
        return
    action = "key up" if up else "key down"
    script = 'tell application "System Events" to %s (key code %s)' % (action, code)
    subprocess.run(
        ["osascript", "-e", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
