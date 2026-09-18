#!/usr/bin/env python3
"""Generate PWA icons for the starter page. Pure stdlib: writes PNGs via zlib+struct.

Art: midnight-blue rounded background, amber sun disc with glow rising over a
horizon arc, a tiny star. Maskable variants keep all art inside the safe zone.
"""
import struct, zlib, math, os
try:
    import numpy as np
except ImportError:
    np = None

SIZES = {
    "icon-192.png": (192, False),
    "icon-512.png": (512, False),
    "icon-maskable-192.png": (192, True),
    "icon-maskable-512.png": (512, True),
}

def png_write(path, w, h, pixels):
    """pixels: list of rows, each row list of (r,g,b,a)."""
    raw = b"".join(b"\x00" + bytes(v for px in row for v in px) for row in pixels)
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        f.write(chunk(b"IEND", b""))

def lerp(a, b, t):
    return a + (b - a) * t

def mix(c1, c2, t):
    return tuple(lerp(c1[i], c2[i], t) for i in range(3))

def clamp01(v):
    return max(0.0, min(1.0, v))

def generate_np(size, maskable):
    """Vectorized version using numpy (present in anaconda)."""
    S = 3
    N = size * S
    scale = 0.72 if maskable else 1.0
    pad = (1.0 - scale) / 2.0
    corner = 0.24
    sun_c = (0.5, 0.60)
    sun_r = 0.14
    glow_r = 0.30
    horizon_y = 0.72
    star = (0.26, 0.22)

    idx = (np.arange(N * N, dtype=np.float64).reshape(N, N))
    xs = ((idx % N) + 0.5) / N
    ys = (idx // N + 0.5) / N
    # average S×S blocks down to size×size
    def shrink(arr):
        return arr.reshape(size, S, size, S).mean(axis=(1, 3))

    ax = shrink(xs)
    ay = shrink(ys)

    img = np.empty((size, size, 4), dtype=np.float64)

    # sky gradient
    t = ay
    for c in range(3):
        img[:, :, c] = 12 + (28 - 12) * t if c == 0 else (17 + (42 - 17) * t if c == 1 else 50 + (94 - 50) * t)

    # horizon arc
    h = horizon_y + 0.40 * (ax - 0.5) ** 2
    edge = np.clip((ay - (h - 0.015)) / 0.03, 0, 1)
    for c, dark in enumerate((10, 12, 28)):
        img[:, :, c] = img[:, :, c] * (1 - edge * 0.85) + dark * (edge * 0.85)

    # sun glow
    ds = np.hypot(ax - sun_c[0], ay - sun_c[1])
    g = np.where(ds < glow_r, (1 - ds / glow_r) ** 2 * 0.55, 0)
    for c, sc in enumerate((255, 215, 94)):
        img[:, :, c] = img[:, :, c] * (1 - g) + sc * g

    # sun disc
    edge_s = np.clip(1.0 - (1.0 - np.clip(ds / sun_r, 0, 1)) * 40, 0, 1)
    disc = np.clip(1 - edge_s, 0, 1) * (ds < sun_r)
    for c, base, hi in ((0, 255, 255), (1, 215, 245), (2, 94, 200)):
        sun_col = base + (hi - base) * np.clip((1 - ds / sun_r) * 0.5, 0, 1)
        img[:, :, c] = img[:, :, c] * (1 - disc) + sun_col * disc

    # star sparkle
    sd = np.abs(star[0] - ax) + np.abs(star[1] - ay)
    sm = np.clip(1 - sd / 0.035, 0, 1) * (ay < horizon_y - 0.3) * 0.9
    for c, sc in enumerate((223, 232, 255)):
        img[:, :, c] = img[:, :, c] * (1 - sm) + sc * sm

    # alpha: rounded corners for non-maskable
    if maskable:
        img[:, :, 3] = 255.0
    else:
        r = corner
        cx = np.clip(ax, r, 1 - r)
        cy = np.clip(ay, r, 1 - r)
        d = np.hypot(ax - cx, ay - cy)
        img[:, :, 3] = np.clip((r - d) * 40 + 0.5, 0, 1) * 255.0

    return [[tuple(int(v + 0.5) for v in row[j]) for j in range(size)] for row in img.tolist()]

def generate(size, maskable):
    if np is not None:
        return generate_np(size, maskable)
    S = 2  # supersampling (pure-python fallback)
    N = size * S
    # maskable: shrink art so it fits the 80% safe-zone circle
    scale = 0.72 if maskable else 1.0
    pad = (1.0 - scale) / 2.0
    corner = 0.24  # rounded corner radius as fraction of side
    # geometry (unit square coords)
    sun_c = (0.5, 0.60)   # sun center (y measured downward from top)
    sun_r = 0.14
    glow_r = 0.30
    horizon_y = 0.72      # horizon arc lowest point
    star = (0.26, 0.22)
    rows = []
    for y in range(N):
        row = []
        for x in range(N):
            # supersample → average
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in range(S):
                for sx in range(S):
                    px = (x + (sx + 0.5) / S) / N
                    py = (y + (sy + 0.5) / S) / N
                    acc[0:4] = [a + b for a, b in zip(acc, shade(px, py, maskable, pad, corner, sun_c, sun_r, glow_r, horizon_y, star))]
            r, g, b, a = [v / (S * S) for v in acc]
            row.append((int(r + 0.5), int(g + 0.5), int(b + 0.5), int(a + 0.5)))
        rows.append(row)
    return rows

def shade(px, py, maskable, pad, corner, sun_c, sun_r, glow_r, horizon_y, star):
    if maskable:
        # map the padded square back to art space
        ax = (px - pad) / (1 - 2 * pad)
        ay = (py - pad) / (1 - 2 * pad)
        if ax < 0 or ax > 1 or ay < 0 or ay > 1:
            return (0, 0, 0, 0)
    else:
        ax, ay = px, py
    # background with rounded corners (only for non-maskable; maskable gets full-bleed square)
    if maskable:
        inside = 1.0
    else:
        r = corner
        cx = min(max(ax, r), 1 - r)
        cy = min(max(ay, r), 1 - r)
        d = math.hypot(ax - cx, ay - cy)
        inside = clamp01((r - d) * 40 + 0.5)  # solid inside, ~0.025 feather at the rim
        if inside <= 0:
            return (0, 0, 0, 0)
    # sky gradient: top #0c1132 → bottom #1c2a5e
    bg = mix((12, 17, 50), (28, 42, 94), ay)
    # horizon arc: ground disc bulging up in the middle
    hx = ax - 0.5
    h = horizon_y + 0.10 * (hx * hx) * 4  # parabola: edges lower, center higher
    if ay > h - 0.015:
        edge = clamp01((ay - (h - 0.015)) / 0.03)
        bg = mix(bg, (10, 12, 28), edge * 0.85)  # dark ground strip
    # sun glow
    gs = math.hypot(ax - sun_c[0], ay - sun_c[1]) / glow_r
    if gs < 1.0:
        g = (1 - gs) ** 2 * 0.55
        bg = mix(bg, (255, 215, 94), g)
    # sun disc
    ds = math.hypot(ax - sun_c[0], ay - sun_c[1]) / sun_r
    if ds < 1.0:
        edge = clamp01(1.0 - (1.0 - ds) * 40)
        sun_col = mix((255, 215, 94), (255, 245, 200), (1 - ds) * 0.5)
        bg = mix(bg, sun_col, clamp01(1 - edge))
    # tiny star (4-point sparkle)
    sx_, sy_ = star[0] - ax, star[1] - ay
    sd = abs(sx_) + abs(sy_)
    if sd < 0.035 and ay < horizon_y - 0.3:
        s = clamp01(1 - sd / 0.035)
        bg = mix(bg, (223, 232, 255), s * 0.9)
    return (bg[0], bg[1], bg[2], 255 * inside)

def main():
    for name, (size, maskable) in SIZES.items():
        rows = generate(size, maskable)
        png_write(name, size, size, rows)
        print(f"wrote {name} ({os.path.getsize(name)} bytes)")

if __name__ == "__main__":
    main()
