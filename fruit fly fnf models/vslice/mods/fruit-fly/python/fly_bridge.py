from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_VERBOSE"] = "0"
os.environ.setdefault("OPENCV_OPENCL_RUNTIME", "disabled")
os.environ.setdefault("OPENCV_OPENCL_DEVICE", "disabled")

LAUNCH_CWD = Path.cwd()
ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

def _ipc_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir())
    return Path("/tmp")

def _ipc_files(name: str):
    tmp = _ipc_dir()
    found = []
    seen = set()
    cands = [
        ROOT / name,
        tmp / name,
        tmp / "funkin" / name,
        LAUNCH_CWD / name,
        LAUNCH_CWD / "mods" / "fruit-fly" / "python" / name,
        Path("mods/fruit-fly/python") / name,
    ]
    walk = ROOT
    for _ in range(8):
        cands.append(walk / name)
        cands.append(walk / "mods" / "fruit-fly" / "python" / name)
        if walk.parent == walk:
            break
        walk = walk.parent
    for path in cands:
        try:
            key = os.path.normcase(os.path.normpath(str(path)))
        except Exception:
            key = str(path)
        if key in seen:
            continue
        seen.add(key)
        found.append(path)
    return found

TMPDIR = _ipc_dir()
SENSE_PATHS = _ipc_files("fly_fnf_sense.txt")
PRESS_PATHS = _ipc_files("fly_fnf_press.txt")
SENSE = SENSE_PATHS[0]
PRESS = PRESS_PATHS[0]
CIRCUIT = ROOT / "circuit.json"
if not CIRCUIT.is_file():
    CIRCUIT = ROOT.parent / "data" / "circuit.json"

WINDOW_TITLE = "Fly brain"

def brain_already_showing() -> bool:
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        found = []
        buf = ctypes.create_unicode_buffer(512)
        proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def visit(hwnd, _param):
            if user32.IsWindowVisible(hwnd):
                user32.GetWindowTextW(hwnd, buf, 512)
                if buf.value == WINDOW_TITLE:
                    found.append(hwnd)
            return True

        user32.EnumWindows(proc_type(visit), 0)
        return bool(found)
    except Exception:
        return False

def take_lock():
    path = TMPDIR / "fly_fnf_py.lock"
    try:
        handle = open(path, "a+b")
    except OSError:
        return None
    try:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handle
    except OSError:
        handle.close()
        return None

if brain_already_showing():
    sys.exit(0)

LOCK = take_lock()
if LOCK is None:
    time.sleep(1.2)
    if brain_already_showing():
        sys.exit(0)

try:
    import cv2
    import numpy as np
    try:
        cv2.ocl.setUseOpenCL(False)
    except Exception:
        pass
except Exception:
    err = "Install: python -m pip install numpy opencv-python"
    print(err)
    try:
        (TMPDIR / "fly_fnf_brain_error.txt").write_text(err)
    except Exception:
        pass
    raise

from fly_keys import KeySender
from fly_viz import FlyBrainViewer, VIEW_H, VIEW_W, WINDOW_NAME, pin_overlay_window, focus_game_window

MOTOR_GO = 0.12
BUMP_GO = 0.04
INPUT_GAIN = 2.2
EXTRA_CELLS = 711
KD_D1, KD_HT1A = 0.40, 0.18
STEP_PERIOD = 0.016
DRAW_EVERY = 3
GAME_GONE = 0.0

def timing_bump(eta):
    if eta is None:
        return 0.0
    e = float(eta)
    if e < -0.18 or e > 0.22:
        return 0.0
    z = e / 0.07
    return math.exp(-0.5 * z * z)

def occ(c, kd):
    return c / (c + kd) if (c + kd) > 1e-9 else 0.0

def parse_sense(text: str):
    out = {
        "song": False,
        "t": 0.0,
        "combo": 0,
        "etas": [None, None, None, None],
        "sustain": [False, False, False, False],
        "due": [False, False, False, False],
        "rating": "",
        "keys": False,
        "layout": "wasd_arrows",
    }
    if not text:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or "=" not in line:
            continue
        if line.startswith("v="):
            for part in line.split():
                if "=" not in part:
                    continue
                k, v = part.split("=", 1)
                if k == "song":
                    out["song"] = v not in ("0", "false", "")
                elif k == "t":
                    out["t"] = float(v or 0)
                elif k == "combo":
                    out["combo"] = int(float(v or 0))
                elif k == "keys":
                    out["keys"] = v not in ("0", "false", "")
                elif k == "layout" and v:
                    out["layout"] = v
        elif line.startswith("e="):
            parts = line[2:].split(",")
            etas = [None, None, None, None]
            for i in range(min(4, len(parts))):
                p = parts[i].strip()
                if p:
                    etas[i] = float(p)
            out["etas"] = etas
        elif line.startswith("s="):
            parts = line[2:].split(",")
            out["sustain"] = [p.strip() not in ("", "0", "false") for p in parts[:4]] + [False] * 4
            out["sustain"] = out["sustain"][:4]
        elif line.startswith("d="):
            parts = line[2:].split(",")
            out["due"] = [p.strip() not in ("", "0", "false") for p in parts[:4]] + [False] * 4
            out["due"] = out["due"][:4]
        elif line.startswith("r="):
            out["rating"] = line[2:].strip()
    return out

class MiniBrain:
    def __init__(self, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        self.n = int(data.get("n") or 0)
        self.roles = np.array(data.get("roles") or [0] * self.n, dtype=np.int8)
        if len(self.roles) < self.n:
            self.roles = np.pad(self.roles, (0, self.n - len(self.roles)))
        self.fast = [(int(a), int(b), float(c)) for a, b, c in (data.get("fast") or [])]
        self.vis = list(zip(data.get("input_neuron_idx") or [], data.get("input_channel") or []))
        self.mot = list(zip(data.get("output_neuron_idx") or [], data.get("output_channel") or []))
        self.kc = list(zip(data.get("kc_neuron_idx") or [], data.get("kc_channel") or []))
        self.pam = [int(i) for i in (data.get("pam_idx") or [])]
        self.ppl = [int(i) for i in (data.get("ppl1_idx") or [])]
        fast = data.get("fast") or []
        if fast:
            arr = np.asarray(fast, dtype=np.float32)
            self.fast_s = arr[:, 0].astype(np.int32)
            self.fast_t = arr[:, 1].astype(np.int32)
            self.fast_w = arr[:, 2]
        else:
            self.fast_s = np.zeros(0, dtype=np.int32)
            self.fast_t = np.zeros(0, dtype=np.int32)
            self.fast_w = np.zeros(0, dtype=np.float32)
        self.core_n = self.n
        extra = EXTRA_CELLS
        self.n = self.core_n + extra
        if len(self.roles) < self.n:
            self.roles = np.pad(self.roles, (0, self.n - len(self.roles)), constant_values=6)
        self.hidden = np.zeros(self.n, dtype=np.float32)
        self.da = np.zeros(self.n, dtype=np.float32)
        self.ht = np.zeros(self.n, dtype=np.float32)
        self.oa = np.zeros(self.n, dtype=np.float32)
        rng = np.random.default_rng(289)
        self.w_in = rng.normal(0.0, 0.35, size=(extra, 4)).astype(np.float32)
        self.w_core = rng.normal(0.0, 0.08, size=(extra, max(self.core_n, 1))).astype(np.float32)
        self.w_rec = rng.normal(0.0, 0.045, size=extra).astype(np.float32)
        self.w_out = rng.normal(0.0, 0.28, size=(4, extra)).astype(np.float32)
        self.extra = np.zeros(extra, dtype=np.float32)
        self.reward = 0.0
        self.punish = 0.0
        self.motor = [0.0, 0.0, 0.0, 0.0]
        self.bump = [0.0, 0.0, 0.0, 0.0]
        self.extras = {"da": 0, "ht": 0, "oa": 0, "pam": 0, "ppl1": 0, "dop1r1": 0, "dop1r2": 0, "dop2r": 0, "dopecr": 0, "ht1a": 0, "ht2a": 0, "ht7": 0, "camp": 0}

    def learn(self, rating: str):
        r = (rating or "").lower()
        if r in ("sick", "perfect", "marvelous"):
            self.reward = 1.0
        elif r in ("good", "great"):
            self.reward = 0.65
        elif r == "bad":
            self.reward = 0.2
        elif r in ("shit", "awful"):
            self.punish = 0.45
        elif r == "miss":
            self.punish = 1.0

    def step(self, etas, combo=0):
        bump = [timing_bump(e) for e in etas]
        self.bump = bump
        sensory = np.zeros(self.n, dtype=np.float32)
        for idx, ch in self.vis:
            if 0 <= idx < self.n and 0 <= ch < 4:
                sensory[idx] += INPUT_GAIN * bump[ch]
        for idx, ch in self.kc:
            if 0 <= idx < self.n and 0 <= ch < 4:
                sensory[idx] += 1.15 * bump[ch]
        if self.reward and self.pam:
            for i in self.pam:
                if 0 <= i < self.n:
                    sensory[i] += self.reward * 2.4
        if self.punish and self.ppl:
            for i in self.ppl:
                if 0 <= i < self.n:
                    sensory[i] += self.punish * 2.4
        self.reward = 0.0
        self.punish = 0.0
        acc = np.zeros(self.n, dtype=np.float32)
        if self.fast_s.size:
            ok = (self.fast_s >= 0) & (self.fast_s < self.n) & (self.fast_t >= 0) & (self.fast_t < self.n)
            np.add.at(acc, self.fast_t[ok], np.maximum(self.hidden[self.fast_s[ok]], 0.0) * self.fast_w[ok])
        core_h = np.tanh(sensory[: self.core_n] + 0.9 * acc[: self.core_n])
        self.hidden[: self.core_n] = core_h
        bump_a = np.asarray(bump, dtype=np.float32)
        drive = self.w_in @ bump_a + self.w_core @ np.maximum(core_h, 0.0) + 0.55 * (self.w_rec * np.maximum(self.extra, 0.0))
        self.extra = np.tanh(drive)
        self.hidden[self.core_n :] = self.extra
        pam = float(np.mean(np.maximum(self.hidden[self.pam], 0))) if self.pam else 0.0
        ppl = float(np.mean(np.maximum(self.hidden[self.ppl], 0))) if self.ppl else 0.0
        da = 0.65 * float(np.mean(self.da)) + 0.35 * (0.5 * (pam + ppl) + 0.04 * min(combo, 20))
        ht = 0.72 * float(np.mean(self.ht)) + 0.28 * float(np.mean(np.maximum(self.hidden, 0)))
        self.da.fill(da)
        self.ht.fill(ht)
        means = [0.0, 0.0, 0.0, 0.0]
        counts = [0, 0, 0, 0]
        for idx, ch in self.mot:
            if 0 <= idx < self.n and 0 <= ch < 4:
                means[ch] += float(self.hidden[idx])
                counts[ch] += 1
        extra_m = self.w_out @ np.maximum(self.extra, 0.0)
        motor = [0.0, 0.0, 0.0, 0.0]
        for i in range(4):
            m = means[i] / counts[i] if counts[i] else 0.0
            m = m + 0.45 * math.tanh(float(extra_m[i]))
            vis = bump[i]
            go = vis * (0.60 + 0.65 / (1.0 + math.exp(-2.4 * m))) - 0.02
            motor[i] = 1.0 / (1.0 + math.exp(-5.2 * go + 2.0))
        self.motor = motor
        self.extras = {
            "da": occ(da, KD_D1),
            "ht": occ(ht, KD_HT1A),
            "oa": occ(0.2 + 0.01 * min(combo, 20), 0.22),
            "pam": pam,
            "ppl1": ppl,
            "dop1r1": occ(da, KD_D1),
            "dop1r2": occ(da, 0.50),
            "dop2r": occ(da, 0.08),
            "dopecr": occ(da, 0.35),
            "ht1a": occ(ht, KD_HT1A),
            "ht2a": occ(ht, 0.40),
            "ht7": occ(ht, 0.50),
            "camp": 0.5,
        }
        return motor, bump

def read_sense_text():
    best = ""
    best_mtime = 0.0
    now = time.time()
    for path in SENSE_PATHS:
        try:
            age = now - path.stat().st_mtime
            if age > 3.5:
                continue
            mtime = path.stat().st_mtime
            if mtime >= best_mtime:
                best = path.read_text(encoding="utf-8", errors="replace")
                best_mtime = mtime
        except OSError:
            pass
    return best

def write_press(bits, extras, alive=True, quit=False):
    parts = [f"v=1 t={time.time():.4f}", "alive=" + ("1" if alive else "0")]
    parts.append("quit=" + ("1" if quit else "0"))
    parts.append("m=" + ",".join("1" if b else "0" for b in bits[:4]))
    if extras:
        for key in ("da", "ht", "oa", "dop1r1"):
            if key in extras:
                parts.append(f"{key}={float(extras[key]):.4f}")
    text = " ".join(parts) + "\n"
    for path in PRESS_PATHS:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError:
            pass

def commit(motor, bump, due, sustain, held):
    bits = [False, False, False, False]
    for i in range(4):
        go = motor[i] >= MOTOR_GO or bump[i] >= 0.45
        if sustain[i] and (held[i] or go or due[i]):
            bits[i] = True
        elif due[i] and go:
            bits[i] = True
        elif due[i] and bump[i] == 0.0 and motor[i] >= 0.06:
            bits[i] = True
    return bits

def window_gone(name: str) -> bool:
    try:
        vis = float(cv2.getWindowProperty(name, cv2.WND_PROP_VISIBLE))
        return vis < 0
    except Exception:
        return False

def sense_active(sense) -> bool:
    if not sense:
        return False
    if sense.get("song"):
        return True
    if any(e is not None for e in (sense.get("etas") or [])):
        return True
    if any(sense.get("due") or []):
        return True
    if any(sense.get("sustain") or []):
        return True
    return False

def shutdown(keys, extras=None, quit=True):
    try:
        keys.release_all()
    except Exception:
        pass
    write_press([False] * 4, extras or {}, alive=False, quit=quit)
    try:
        cv2.destroyAllWindows()
    except Exception:
        pass

def run():
    if not CIRCUIT.is_file():
        print("Missing circuit.json next to fly_bridge.py")
        time.sleep(4)
        return 1
    brain = MiniBrain(CIRCUIT)
    viewer = FlyBrainViewer(brain.n, roles=brain.roles)
    keys = KeySender("wasd_arrows")
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, VIEW_W, VIEW_H)
    cv2.imshow(WINDOW_NAME, np.zeros((VIEW_H, VIEW_W, 3), np.uint8))
    cv2.waitKey(1)
    pin_overlay_window(place=True, noactivate=True)
    held = [False, False, False, False]
    last_rating = ""
    last_bits = [False, False, False, False]
    last_focus = 0.0
    placed = True
    starved = 0
    frame = 0
    gone = 0
    saw_game = False
    last_game = time.perf_counter()
    closed_by_user = True
    print("Fly brain running. Close this window, or press Esc / Q, to stop.")
    while True:
        cycle_start = time.perf_counter()
        sense = {"song": False, "etas": [None] * 4, "due": [False] * 4, "sustain": [False] * 4, "combo": 0, "rating": "", "keys": True, "layout": keys.layout}
        raw = read_sense_text()
        if raw:
            sense = parse_sense(raw)
            keys.set_layout(sense.get("layout") or "wasd_arrows")
            saw_game = True
            last_game = cycle_start
        playing = sense_active(sense)
        if sense.get("rating") and sense["rating"] != last_rating:
            brain.learn(sense["rating"])
            last_rating = sense["rating"]
        if playing:
            try:
                motor, bump = brain.step(sense["etas"], sense.get("combo") or 0)
            except MemoryError:
                motor, bump = brain.motor, brain.bump
            bits = commit(motor, bump, sense["due"], sense["sustain"], held)
        else:
            motor, bump = brain.motor, brain.bump
            bits = [False, False, False, False]
            brain.hidden *= 0.92
        held[:] = bits
        keys.release_all()
        write_press(bits, brain.extras, alive=True, quit=False)
        frame += 1
        key = 0
        if frame % DRAW_EVERY == 0:
            try:
                img = viewer.render(brain.hidden, extras=brain.extras, motor=motor, bits=bits, closeness=bump, sustain=sense.get("sustain"), show=False)
                cv2.imshow(WINDOW_NAME, img)
                if not placed:
                    pin_overlay_window(place=True, noactivate=True)
                    placed = True
            except (MemoryError, cv2.error):
                starved += 1
                if starved == 1 or starved % 200 == 0:
                    print("low memory: skipped drawing the brain (notes still running)")
            else:
                starved = 0
            key = cv2.waitKey(1) & 0xFF
            if window_gone(WINDOW_NAME):
                gone += 1
                if gone > 20:
                    closed_by_user = True
                    break
            else:
                gone = 0
        if key in (27, ord("q"), ord("Q")):
            break
        spare = STEP_PERIOD - (time.perf_counter() - cycle_start)
        if spare > 0:
            time.sleep(spare)
    shutdown(keys, brain.extras, quit=closed_by_user)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(run() or 0)
    except Exception:
        import traceback
        err = traceback.format_exc()
        traceback.print_exc()
        try:
            (TMPDIR / "fly_fnf_brain_error.txt").write_text(err)
        except Exception:
            pass
        time.sleep(6)
        sys.exit(1)
