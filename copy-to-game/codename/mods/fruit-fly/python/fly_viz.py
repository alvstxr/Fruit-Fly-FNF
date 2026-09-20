import os
import sys

import numpy as np

WINDOW_NAME = "Fly brain"
VIEW_W = 480
VIEW_H = 520
HUD = 120
SKEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fly_skeletons.npz")
IO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fly_io_indices.npz")
TOKEN = os.environ.get("NEUPRINT_TOKEN", "").strip()
DATASET = os.environ.get("NEUPRINT_DATASET", "male-cns:v1.0").strip()
SERVER = os.environ.get("NEUPRINT_SERVER", "https://neuprint.janelia.org").strip()
POINTS_PER_NEURON = 48

ROLE_COLOR = {
    0: (0.28, 0.42, 0.58),
    1: (0.18, 0.78, 0.92),
    2: (0.28, 0.32, 0.90),
    3: (0.78, 0.28, 0.82),
    4: (0.18, 0.55, 0.95),
    5: (0.16, 0.40, 0.95),
    6: (0.38, 0.82, 0.42),
    7: (0.70, 0.38, 0.70),
    8: (0.40, 0.85, 0.55),
    9: (0.55, 0.70, 0.28),
}

def fetch_and_save_skeletons(body_ids, dest=SKEL_PATH, token=TOKEN):
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from neuprint import Client

    client = Client(SERVER, dataset=DATASET, token=token)
    body_ids = [int(b) for b in body_ids]
    print(f"Downloading {len(body_ids)} neuron skeletons from {DATASET}...")

    def one(body_id):
        try:
            df = client.fetch_skeleton(body_id, heal=False, format="pandas")
        except Exception:
            return body_id, None
        if df is None or len(df) == 0 or "x" not in df.columns:
            return body_id, None
        xyz = df[["x", "y", "z"]].to_numpy(dtype=np.float32)
        if len(xyz) > POINTS_PER_NEURON:
            idx = np.linspace(0, len(xyz) - 1, POINTS_PER_NEURON).astype(int)
            xyz = xyz[idx]
        return body_id, xyz

    chunks = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = [pool.submit(one, bid) for bid in body_ids]
        for i, fut in enumerate(as_completed(futs), 1):
            chunks.append(fut.result())
            if i % 40 == 0 or i == len(body_ids):
                print(f"  skeletons {i}/{len(body_ids)}")

    pts = []
    nidx = []
    kept = []
    for body_id, xyz in chunks:
        if xyz is None:
            continue
        kept.append(body_id)
        neuron = len(kept) - 1
        pts.append(xyz)
        nidx.append(np.full(len(xyz), neuron, dtype=np.int32))

    if not pts:
        raise RuntimeError("No skeletons could be downloaded from neuPrint.")

    xyz = np.concatenate(pts, axis=0)
    neuron_idx = np.concatenate(nidx, axis=0)
    center = xyz.mean(axis=0)
    xyz = xyz - center
    scale = np.percentile(np.linalg.norm(xyz, axis=1), 95)
    if scale > 0:
        xyz = xyz / scale
    xyz, neuron_idx = _crop_to_brain(xyz, neuron_idx)

    np.savez_compressed(
        dest,
        xyz=xyz.astype(np.float32),
        neuron_idx=neuron_idx,
        body_ids=np.array(kept, dtype=np.int64),
    )
    print(f"Wrote {dest} ({len(kept)} neurons, {len(xyz)} points)")
    return dest

def _crop_to_brain(xyz, neuron_idx):
    if len(xyz) < 80:
        return xyz, neuron_idx
    med = np.median(xyz, axis=0)
    dist = np.linalg.norm(xyz - med, axis=1)
    keep = dist <= np.percentile(dist, 91) * 1.08
    if int(keep.sum()) < 40:
        return xyz, neuron_idx
    return xyz[keep], neuron_idx[keep]

def _gaussian_cloud(rng, n, center, scale):
    pts = rng.normal(size=(int(n), 3)).astype(np.float32)
    return np.asarray(center, dtype=np.float32) + pts * np.asarray(scale, dtype=np.float32)

def placeholder_brain(num_neurons, roles=None):
    rng = np.random.default_rng(7)
    n = max(int(num_neurons), 32)
    if roles is None:
        roles = np.zeros(n, dtype=np.int8)
        roles[: max(1, n // 6)] = 1
        roles[n // 6 : n // 3] = 3
        roles[n // 3 : n // 3 + max(1, n // 12)] = 6
        roles[-max(1, n // 14) :] = 2
    buckets = {r: np.where(roles[:n] == r)[0] for r in range(10)}

    def ids_for(role):
        hit = buckets.get(int(role))
        if hit is not None and len(hit):
            return hit
        return np.arange(n, dtype=np.int32)

    clouds = (
        (1, 2600, (-0.78, 0.04, 0.02), (0.30, 0.20, 0.16)),
        (1, 2600, (0.78, 0.06, 0.04), (0.32, 0.22, 0.17)),
        (1, 800, (-0.44, 0.02, 0.00), (0.16, 0.14, 0.12)),
        (1, 800, (0.46, 0.04, 0.02), (0.16, 0.14, 0.12)),
        (0, 2000, (0.02, -0.02, -0.02), (0.40, 0.22, 0.18)),
        (3, 1200, (0.02, 0.10, 0.10), (0.20, 0.14, 0.10)),
        (4, 700, (0.22, 0.00, 0.02), (0.16, 0.14, 0.12)),
        (5, 500, (-0.18, 0.04, 0.06), (0.12, 0.10, 0.10)),
        (6, 700, (-0.06, -0.08, -0.08), (0.16, 0.12, 0.10)),
        (7, 360, (0.00, 0.12, 0.08), (0.18, 0.10, 0.08)),
        (8, 280, (0.14, 0.08, 0.12), (0.10, 0.08, 0.08)),
        (9, 280, (-0.12, 0.08, 0.12), (0.10, 0.08, 0.08)),
        (2, 420, (0.00, -0.16, -0.10), (0.14, 0.10, 0.08)),
    )
    xyz = []
    neuron_idx = []
    for role, count, center, scale in clouds:
        pts = _gaussian_cloud(rng, count, center, scale)
        ids = ids_for(role)
        idx = np.resize(ids, len(pts)).astype(np.int32)
        xyz.append(pts)
        neuron_idx.append(idx)
    return {
        "xyz": np.concatenate(xyz, axis=0).astype(np.float32),
        "neuron_idx": np.concatenate(neuron_idx, axis=0),
        "body_ids": np.arange(n, dtype=np.int64),
        "placeholder": True,
    }

def placeholder_cns(num_neurons, roles=None):
    return placeholder_brain(num_neurons, roles)

def load_or_fetch_skeletons(num_neurons, roles=None):
    if os.path.isfile(SKEL_PATH):
        data = np.load(SKEL_PATH)
        xyz, nidx = _crop_to_brain(np.asarray(data["xyz"]), np.asarray(data["neuron_idx"]))
        return {"xyz": xyz, "neuron_idx": nidx, "body_ids": data["body_ids"], "placeholder": False}
    return placeholder_brain(num_neurons, roles)

class FlyBrainViewer:
    def __init__(self, num_neurons, roles=None):
        self.num_neurons = num_neurons
        self.angle = 0.38
        self.placeholder = False
        self.role = np.zeros(num_neurons, dtype=np.int8)
        self.lane = np.full(num_neurons, -1, dtype=np.int8)
        if roles is not None:
            stored = np.asarray(roles).astype(np.int8).flatten()
            n = min(len(stored), num_neurons)
            self.role[:n] = stored[:n]
        elif os.path.isfile(IO_PATH):
            meta = np.load(IO_PATH)
            if "roles" in meta.files:
                stored = np.asarray(meta["roles"]).astype(np.int8)
                n = min(len(stored), num_neurons)
                self.role[:n] = stored[:n]
        try:
            self.data = load_or_fetch_skeletons(num_neurons, self.role)
        except Exception as exc:
            print(f"3D view fallback ({exc})")
            self.data = placeholder_brain(num_neurons, self.role)

        io_bodies = []
        if os.path.isfile(IO_PATH):
            meta = np.load(IO_PATH)
            io_bodies = [int(b) for b in meta["body_ids"]] if "body_ids" in meta.files else []
            if "input_neuron_idx" in meta.files and "input_channel" in meta.files:
                for neuron, ch in zip(meta["input_neuron_idx"], meta["input_channel"]):
                    ni, ci = int(neuron), int(ch)
                    if 0 <= ni < num_neurons and 0 <= ci < 4:
                        self.lane[ni] = ci
            if "output_neuron_idx" in meta.files and "output_channel" in meta.files:
                for neuron, ch in zip(meta["output_neuron_idx"], meta["output_channel"]):
                    ni, ci = int(neuron), int(ch)
                    if 0 <= ni < num_neurons and 0 <= ci < 4:
                        self.lane[ni] = ci
            if "kc_neuron_idx" in meta.files and "kc_channel" in meta.files:
                for neuron, ch in zip(meta["kc_neuron_idx"], meta["kc_channel"]):
                    ni, ci = int(neuron), int(ch)
                    if 0 <= ni < num_neurons and 0 <= ci < 4 and self.lane[ni] < 0:
                        self.lane[ni] = ci

        if isinstance(self.data, dict):
            self.placeholder = bool(self.data.get("placeholder"))
            self.xyz = self.data["xyz"]
            self.neuron_idx = self.data["neuron_idx"]
            body_ids = list(self.data["body_ids"])
        else:
            self.xyz = self.data["xyz"]
            self.neuron_idx = self.data["neuron_idx"]
            body_ids = list(self.data["body_ids"])

        io_map = {bid: i for i, bid in enumerate(io_bodies)}
        remap = np.zeros(len(self.neuron_idx), dtype=np.int32)
        for i, bid in enumerate(body_ids):
            remap[self.neuron_idx == i] = io_map.get(int(bid), min(i, num_neurons - 1))
        self.model_index = np.clip(remap, 0, num_neurons - 1)
        have = int(self.neuron_idx.max()) + 1 if len(self.neuron_idx) else 0
        if have < num_neurons:
            rng = np.random.default_rng(11)
            extra_ids = np.arange(have, num_neurons, dtype=np.int32)
            pts_each = 28
            extra_xyz = rng.normal(scale=(0.58, 0.44, 0.40), size=(len(extra_ids) * pts_each, 3)).astype(np.float32)
            extra_idx = np.repeat(extra_ids, pts_each)
            self.xyz = np.concatenate([self.xyz, extra_xyz], axis=0)
            self.neuron_idx = np.concatenate([self.neuron_idx, extra_idx], axis=0)
            self.model_index = np.concatenate([self.model_index, extra_idx], axis=0)
            for i, nid in enumerate(extra_ids):
                self.lane[int(nid)] = i % 4

    def render(
        self,
        hidden_state,
        extras=None,
        motor=None,
        bits=None,
        closeness=None,
        sustain=None,
        show=True,
    ):
        import cv2

        act = hidden_state.detach().cpu().numpy().flatten() if hasattr(hidden_state, "detach") else np.asarray(hidden_state).flatten()
        if len(act) < self.num_neurons:
            act = np.pad(act, (0, self.num_neurons - len(act)))
        fire = np.abs(act[: self.num_neurons]).astype(np.float32)
        used = np.zeros(4, dtype=np.float32)
        if closeness is not None:
            used = np.maximum(used, np.clip(np.asarray(closeness, dtype=np.float32)[:4], 0, 1))
        if motor is not None:
            used = np.maximum(used, 0.35 * np.clip(np.asarray(motor, dtype=np.float32)[:4], 0, 1))
        if bits is not None:
            for i in range(min(4, len(bits))):
                if bits[i]:
                    used[i] = 1.0
        for i in range(self.num_neurons):
            lane = int(self.lane[i])
            if lane < 0 or lane > 3:
                continue
            role = int(self.role[i])
            gain = 1.2 if role in (1, 2, 3) else 0.72
            fire[i] = max(float(fire[i]), float(used[lane]) * gain)
        peak = float(fire.max()) if fire.size else 0.0
        if peak > 1e-6:
            fire = fire / peak

        img = np.zeros((VIEW_H, VIEW_W, 3), dtype=np.uint8)
        img[:] = (12, 10, 10)
        self._draw_brain(img, fire)
        self._draw_hud(img, extras, motor, bits, closeness, sustain)
        if show:
            cv2.imshow(WINDOW_NAME, img)
        return img

    def _paint_points(self, img, u, v, heat, roles, x0, y0, w, h):
        on = (u >= 1) & (u < w - 1) & (v >= 1) & (v < h - 1)
        u, v, heat, roles = u[on], v[on], heat[on], roles[on]
        if len(u) == 0:
            return
        base = np.zeros((len(heat), 3), dtype=np.float32)
        for role, col in ROLE_COLOR.items():
            base[roles == role] = col
        mix = np.clip(heat, 0.0, 1.0) ** 2
        white = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        colors = np.clip((base * (1.0 - mix[:, None]) + white * mix[:, None]) * 255.0, 0, 255).astype(np.uint8)
        uu = np.clip(u + x0, 0, img.shape[1] - 1)
        vv = np.clip(v + y0, 0, img.shape[0] - 1)
        for dx, dy in ((0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)):
            img[np.clip(vv + dy, 0, img.shape[0] - 1), np.clip(uu + dx, 0, img.shape[1] - 1)] = colors
        hot = heat >= 0.72
        if np.any(hot):
            hu, hv, hc = uu[hot], vv[hot], colors[hot]
            for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                img[np.clip(hv + dy, 0, img.shape[0] - 1), np.clip(hu + dx, 0, img.shape[1] - 1)] = hc

    def _draw_brain(self, img, fire):
        import cv2

        panel_h = VIEW_H - HUD
        cv2.putText(img, "brain", (16, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 112, 200), 1, cv2.LINE_AA)
        self.angle += 0.006
        c, s = np.cos(self.angle), np.sin(self.angle)
        x = self.xyz[:, 0] * c - self.xyz[:, 1] * s
        z = self.xyz[:, 0] * s + self.xyz[:, 1] * c
        y = -self.xyz[:, 2] + 0.12 * z
        order = np.argsort(z)
        x, y = x[order], y[order]
        nidx = self.model_index[order]
        heat = fire[nidx]
        roles = self.role[nidx]
        w, h = VIEW_W - 32, panel_h - 48
        u = ((x + 1.45) / 2.90 * (w - 1)).astype(np.int32)
        v = ((y + 1.05) / 2.20 * (h - 1)).astype(np.int32)
        self._paint_points(img, u, v, heat, roles, 16, 40, w, h)

    def _draw_hud(self, img, extras, motor, bits, closeness, sustain):
        import cv2

        y0 = VIEW_H - HUD + 8
        cv2.rectangle(img, (8, y0), (VIEW_W - 8, VIEW_H - 8), (22, 18, 26), -1)
        extras = extras or {}

        def draw_bars(items, y):
            x = 16
            for name, val, col in items:
                cv2.putText(img, name, (x, y + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (200, 200, 210), 1, cv2.LINE_AA)
                cv2.rectangle(img, (x + 48, y + 2), (x + 120, y + 12), (40, 40, 48), -1)
                fill = int(72 * max(0.0, min(1.0, val)))
                cv2.rectangle(img, (x + 48, y + 2), (x + 48 + fill, y + 12), col, -1)
                x += 140

        draw_bars(
            (
                ("DA", float(extras.get("da", 0.0)), (40, 180, 255)),
                ("5HT", float(extras.get("ht", 0.0)), (80, 220, 120)),
                ("OA", float(extras.get("oa", 0.0)), (80, 200, 80)),
                ("PAM", float(extras.get("pam", 0.0)), (40, 200, 255)),
                ("PPL1", float(extras.get("ppl1", 0.0)), (40, 120, 240)),
            ),
            y0 + 8,
        )
        rec = 4.0
        draw_bars(
            (
                ("D1R1", float(extras.get("dop1r1", 0.0)) * rec, (40, 200, 255)),
                ("D1R2", float(extras.get("dop1r2", 0.0)) * rec, (30, 160, 230)),
                ("D2R", float(extras.get("dop2r", 0.0)) * rec, (20, 120, 200)),
                ("EcR", float(extras.get("dopecr", 0.0)) * rec, (80, 210, 255)),
                ("1A", float(extras.get("ht1a", 0.0)) * rec, (80, 220, 140)),
                ("2A", float(extras.get("ht2a", 0.0)) * rec, (70, 180, 120)),
                ("5HT7", float(extras.get("ht7", 0.0)) * rec, (90, 230, 160)),
            ),
            y0 + 32,
        )
        colors = ((200, 80, 200), (220, 200, 40), (60, 210, 80), (50, 50, 230))
        labels = ("L", "D", "U", "R")
        x0 = VIEW_W - 220
        for i in range(4):
            cx = x0 + i * 48
            close = float(closeness[i]) if closeness is not None and i < len(closeness) else 0.0
            fill = tuple(int(c * (0.22 + 0.78 * close)) for c in colors[i])
            cv2.circle(img, (cx, y0 + 78), 8, fill, -1, cv2.LINE_AA)
            down = bool(bits[i]) if bits is not None and i < len(bits) else False
            hold = bool(sustain[i]) if sustain is not None and i < len(sustain) else False
            ring = (240, 240, 240) if down else (50, 50, 50)
            cv2.circle(img, (cx, y0 + 78), 10, ring, 1, cv2.LINE_AA)
            tag = "H" if hold and down else ("T" if down else labels[i])
            cv2.putText(img, tag, (cx - 5, y0 + 104), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220, 220, 230), 1, cv2.LINE_AA)
        cv2.putText(img, "Esc / Q / close window to quit", (16, VIEW_H - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 190), 1, cv2.LINE_AA)

def draw_lane_hud(img, closeness, in_window, bits, motor=None, extras=None, sustain=None):
    return img

def focus_game_window():
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        found = []

        def _callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            name = (buf.value or "").lower()
            if name == WINDOW_NAME.lower():
                return True
            if "codename" in name or "funkin" in name or "friday night" in name:
                found.append(hwnd)
            return True

        user32.EnumWindows(EnumWindowsProc(_callback), 0)
        if not found:
            return False
        hwnd = found[0]
        try:
            user32.AllowSetForegroundWindow(-1)
        except Exception:
            pass
        fg = user32.GetForegroundWindow()
        mytid = kernel32.GetCurrentThreadId()
        fgtid = user32.GetWindowThreadProcessId(fg, None)
        gametid = user32.GetWindowThreadProcessId(hwnd, None)
        if fgtid:
            user32.AttachThreadInput(mytid, fgtid, True)
        if gametid:
            user32.AttachThreadInput(mytid, gametid, True)
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        if fgtid:
            user32.AttachThreadInput(mytid, fgtid, False)
        if gametid:
            user32.AttachThreadInput(mytid, gametid, False)
        return True
    except Exception:
        return False

def pin_overlay_window(title=WINDOW_NAME, place=False, game=None, noactivate=False):
    try:
        import cv2

        cv2.setWindowProperty(title, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass
    width, height = VIEW_W, VIEW_H
    pos_x, pos_y = 8, 8
    if game is not None:
        try:
            from fly_window import client_screen_rect

            gx, gy, gw, gh = client_screen_rect(game)
            if gx >= width + 16:
                pos_x = gx - width - 8
                pos_y = gy + 8
            else:
                pos_x = gx + 8
                pos_y = gy + 8
        except Exception:
            pass
    if sys.platform == "darwin":
        return True
    if os.name != "nt":
        return _pin_linux(title, width, height, place, pos_x, pos_y)
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    fly_hwnds = []

    def _callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        name = buf.value or ""
        if name == title:
            fly_hwnds.append(hwnd)
        return True

    proc = EnumWindowsProc(_callback)
    user32.EnumWindows(proc, 0)

    gwl_exstyle = -20
    ws_ex_noactivate = 0x08000000
    ws_ex_topmost = 0x00000008
    ws_ex_toolwindow = 0x00000080
    ws_ex_layered = 0x00080000
    ws_ex_transparent = 0x00000020
    hwnd_topmost = -1
    swp_nomove = 0x0002
    swp_nosize = 0x0001
    swp_noactivate = 0x0010
    swp_showwindow = 0x0040

    flags = swp_showwindow
    if noactivate:
        flags |= swp_noactivate
    if not place:
        flags |= swp_nomove | swp_nosize

    for hwnd in fly_hwnds:
        style = user32.GetWindowLongW(hwnd, gwl_exstyle)
        style &= ~(ws_ex_transparent | ws_ex_layered | ws_ex_toolwindow)
        if noactivate:
            style |= ws_ex_noactivate | ws_ex_topmost
        else:
            style &= ~ws_ex_noactivate
            style |= ws_ex_topmost
        user32.SetWindowLongW(hwnd, gwl_exstyle, style)
        if place:
            user32.SetWindowPos(hwnd, hwnd_topmost, int(pos_x), int(pos_y), int(width), int(height), flags)
        else:
            user32.SetWindowPos(hwnd, hwnd_topmost, 0, 0, 0, 0, flags)
    return bool(fly_hwnds)

def _pin_linux(title, width, height, place, pos_x=16, pos_y=None):
    import shutil
    import subprocess

    if not shutil.which("wmctrl"):
        return False
    subprocess.run(
        ["wmctrl", "-r", title, "-b", "add,above"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if place:
        y = int(pos_y) if pos_y is not None else 16
        x = int(pos_x)
        subprocess.run(
            ["wmctrl", "-r", title, "-e", f"0,{x},{y},{width},{height}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    return True
