# Renders frame.gif: the whole profile page as one screen, built grain by
# grain by falling sand, with a Doom-style flame burning behind it. Text
# cells land as characters; image cells (skill icons, stat cards, badges)
# land as tiles of the fetched image.
#
#   uv run --with pillow python scripts/frame.py
#
# Needs rsvg-convert on PATH to rasterise the SVG cards.
import io, math, os, random, re, subprocess, urllib.request
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
LOGIN = os.environ.get("GH_LOGIN", "CaptainParis")
random.seed(7)

BG = (26, 27, 39); LET = (192, 202, 245); SHD = (122, 162, 247); DIM = (86, 95, 137)
SANDC = (224, 175, 104); GROUND = (158, 206, 106); WALL = (224, 175, 104)

FS = 13
font = ImageFont.truetype(os.path.join(HERE, "fonts", "JetBrainsMono-Regular.ttf"), FS)
bold = ImageFont.truetype(os.path.join(HERE, "fonts", "JetBrainsMono-Bold.ttf"), FS)
bb = font.getbbox("█"); CW = bb[2] - bb[0]; CH = int(FS * 1.25)
COLS = 100
PAD = 10

# ---------------------------------------------------------------- images
def svg_png(url, width_px):
    """Fetch an SVG and rasterise it to a PIL image `width_px` wide."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "frame.py"}), timeout=30) as r:
            svg = r.read().decode()
    except Exception as e:
        print("fetch failed:", url, e); return None
    svg = svg.replace("opacity: 0;", "opacity: 1;")  # streak card fades in via CSS; rsvg sees frame 0
    png = subprocess.run(["rsvg-convert", "-w", str(width_px), "-"], input=svg.encode(), capture_output=True).stdout
    if not png:
        print("rsvg failed:", url); return None
    return Image.open(io.BytesIO(png)).convert("RGBA")

T = "theme=tokyonight"
IMAGES = {
    "icons":  f"https://skillicons.dev/icons?i=java,kotlin,python,ts,gradle,docker,git&theme=dark",
    "mocap":  "https://img.shields.io/badge/Mocap-record%20%26%20replay%20players%20as%20packet%20actors-1a1b27?style=for-the-badge&logo=github&logoColor=c0caf5&labelColor=7aa2f7",
    "heads":  "https://img.shields.io/badge/HeadSprites-custom%20head%20sprites%20inline%20in%20chat-1a1b27?style=for-the-badge&logo=github&logoColor=c0caf5&labelColor=7aa2f7",
    "stats":  f"https://github-profile-summary-cards.vercel.app/api/cards/stats?username={LOGIN}&{T}",
    "langs":  f"https://github-profile-summary-cards.vercel.app/api/cards/repos-per-language?username={LOGIN}&{T}",
    "streak": f"https://github-readme-streak-stats.herokuapp.com?user={LOGIN}&{T}&hide_border=true&background=1a1b27",
}

# ---------------------------------------------------------------- layout
cells = {}   # (x, y) -> (char, color)           text targets
tiles = {}   # (x, y) -> PIL image (CW x CH)      image targets
mask = set() # cells the flame must never draw over

def put(x, y, text, color):
    for i, ch in enumerate(text):
        mask.add((x + i, y))
        if ch != " ": cells[(x + i, y)] = (ch, color)

def place(img, y, rows, x=None):
    """Scale img to fit `rows` rows (keeping aspect), centre it, cut into cell tiles."""
    if img is None: return
    h = rows * CH; w = round(img.width * h / img.height)
    if w > (COLS - 6) * CW:
        w = (COLS - 6) * CW; h = round(img.height * w / img.width)
    img = img.resize((w, h), Image.LANCZOS)
    x0 = (COLS * CW - w) // 2 if x is None else x * CW
    y0 = y * CH + (rows * CH - h) // 2
    canvas = Image.new("RGB", (COLS * CW, (y + rows) * CH), BG)
    canvas.paste(img, (x0, y0), img)
    for cy in range(y, y + rows):
        for cx in range(x0 // CW, min(COLS, -(-(x0 + w) // CW))):
            tiles[(cx, cy)] = canvas.crop((cx * CW, cy * CH, cx * CW + CW, cy * CH + CH))
            mask.add((cx, cy))

name = [l.rstrip("\n") for l in open(os.path.join(HERE, "name.txt"))]
name = [l for l in name if l.strip()]
NW = len(max(name, key=len))

y = 2
for r, l in enumerate(name):
    for c, ch in enumerate(l):
        if ch != " ": cells[((COLS - NW) // 2 + c, y + r)] = (ch, LET if ch == "█" else SHD)
y += len(name) + 1
tag = "block game developer   ·   java kotlin typescript   ·   doing cool things"
put((COLS - len(tag)) // 2, y, tag, DIM); y += 2

imgs = {k: svg_png(u, 1200) for k, u in IMAGES.items()}
place(imgs["icons"], y, 3); y += 4
place(imgs["mocap"], y, 2); y += 2
place(imgs["heads"], y, 2); y += 3
cw = 44  # card width in cells
place(imgs["stats"], y, 14, x=(COLS - 2 * cw - 2) // 2)
place(imgs["langs"], y, 14, x=(COLS - 2 * cw - 2) // 2 + cw + 2)
y += 15
place(imgs["streak"], y, 12); y += 13

ROWS = y + 1
for x in range(COLS):
    cells[(x, 0)] = ("GROUND_"[x % 7], GROUND)
    cells[(x, ROWS - 1)] = ("GROUND_"[x % 7], GROUND)
for yy in range(1, ROWS - 1):
    cells[(0, yy)] = ("WALL"[yy % 4], WALL)
    cells[(COLS - 1, yy)] = ("WALL"[yy % 4], WALL)

W = COLS * CW + PAD * 2; H = ROWS * CH + PAD * 2
FPS = 10; BUILD = int(9 * FPS); HOLD = int(2.5 * FPS); TOTAL = BUILD + HOLD
FALL = 2  # rows per frame

grains = []
for (tx, ty) in list(cells) + list(tiles):
    depth = (ROWS - 1) - ty
    spawn = int(depth * (BUILD - ROWS // FALL - 12) / ROWS) + random.randint(0, 12)
    sx = max(0, min(COLS - 1, tx + random.randint(-8, 8)))
    grains.append(dict(tx=tx, ty=ty, spawn=spawn, x=sx, y=-FALL, landed=False, fc=random.choice("sand")))

# ---------------------------------------------------------------- flame
flame = "...::/\\/\\/\\+=*abcdef01XYZ#"
data = [0] * (COLS * ROWS)
def rndi(a, b): return random.randint(a, b)
def vnoise():
    tbl = 256; r = [random.random() for _ in range(tbl)]; p = list(range(tbl)); random.shuffle(p); p = p + p
    def ss(t): return t * t * (3 - 2 * t)
    def f(px, py):
        xi, yi = math.floor(px), math.floor(py); tx, ty = px - xi, py - yi
        rx0, rx1, ry0, ry1 = xi % tbl, (xi + 1) % tbl, yi % tbl, (yi + 1) % tbl
        c00 = r[p[p[rx0] + ry0]]; c10 = r[p[p[rx1] + ry0]]; c01 = r[p[p[rx0] + ry1]]; c11 = r[p[p[rx1] + ry1]]
        sx, sy = ss(tx), ss(ty)
        nx0 = c00 + (c10 - c00) * sx; nx1 = c01 + (c11 - c01) * sx
        return nx0 + (nx1 - nx0) * sy
    return f
noise = vnoise()
def flame_step(t):
    last = COLS * (ROWS - 1)
    for i in range(COLS):
        val = int(6 + noise(i * 0.05, t) * 30)
        data[last + i] = min(val, data[last + i] + 2)
    for i in range(len(data)):
        r = i // COLS; c = i % COLS
        dest = r * COLS + max(0, min(COLS - 1, c + rndi(-1, 1)))
        src = min(ROWS - 1, r + 1) * COLS + c
        data[dest] = max(0, data[src] - rndi(0, 2))
def fcol(u):
    t = min(1, u / 30)
    stops = [(70, 30, 40), (150, 50, 40), (230, 110, 50), (255, 158, 100), (255, 220, 150)]
    x = t * (len(stops) - 1); i = min(int(x), len(stops) - 2); f = x - i
    a, b = stops[i], stops[i + 1]
    return tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3))

# ---------------------------------------------------------------- frames
def px(x, y): return (PAD + x * CW, PAD + y * CH)
def clear(d, x, y):
    d.rectangle((PAD + x * CW, PAD + y * CH, PAD + x * CW + CW - 1, PAD + y * CH + CH - 1), fill=BG)
def land(img, d, x, y):
    if (x, y) in tiles:
        img.paste(tiles[(x, y)], px(x, y)); return
    ch, col = cells[(x, y)]
    clear(d, x, y)
    if ch == "█": d.rectangle((PAD + x * CW, PAD + y * CH, PAD + x * CW + CW, PAD + y * CH + CH), fill=col)
    else: d.text(px(x, y), ch, font=bold if col in (SHD, GROUND, WALL) else font, fill=col)

frames = []
preview = os.environ.get("PREVIEW")
for fr in range(TOTAL):
    flame_step(fr * 0.06)
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
    for i, v in enumerate(data):
        if v <= 0: continue
        r, c = divmod(i, COLS)
        if (c, r) in mask: continue
        d.text(px(c, r), flame[min(v, len(flame) - 1)], font=font, fill=fcol(v))
    falling = []
    for g in grains:
        if fr < g["spawn"]: continue
        if not g["landed"]:
            g["y"] += FALL
            dx = g["tx"] - g["x"]; left = g["ty"] - g["y"]
            if dx != 0 and (left <= FALL * abs(dx) or random.random() < 0.6): g["x"] += 1 if dx > 0 else -1
            if g["y"] >= g["ty"]: g["landed"] = True; g["x"] = g["tx"]; g["y"] = g["ty"]
            if not g["landed"]:
                if random.random() < 0.3: g["fc"] = random.choice("sand")
                falling.append(g); continue
        land(img, d, g["tx"], g["ty"])
    for g in falling:  # draw last so grains show over what they pass
        clear(d, g["x"], g["y"]); d.text(px(g["x"], g["y"]), g["fc"], font=font, fill=SANDC)
    frames.append(img.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    if preview and fr in (70, TOTAL - 1): img.save(os.path.join(preview, f"f{fr}.png"))

# No loop extension: plays once and rests on the finished screen.
frames[0].save(os.path.join(HERE, "..", "frame.gif"), save_all=True, append_images=frames[1:],
               duration=int(1000 / FPS), optimize=True)
print(f"{W}x{H} {TOTAL} frames {COLS}x{ROWS} cells")
