# Renders page.gif: the whole profile page poured in as sand. Text cells
# fall as characters; images (skill icons, badges, stat cards) fall as
# 4x4 px grains coloured like the pixel they will become, so each picture
# piles up from the bottom until it is complete.
#
#   uv run --with pillow python scripts/frame.py
#
# Needs rsvg-convert on PATH to rasterise the SVG cards.
import io, os, random, subprocess, urllib.request
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
LOGIN = os.environ.get("GH_LOGIN", "CaptainParis")
random.seed(7)

BG = (26, 27, 39); LET = (192, 202, 245); SHD = (122, 162, 247); DIM = (86, 95, 137)
SANDC = (224, 175, 104)

SS = 2  # supersample: render at 2x, README shows it at 1x so it stays crisp on HiDPI
FS = 13 * SS
font = ImageFont.truetype(os.path.join(HERE, "fonts", "JetBrainsMono-Regular.ttf"), FS)
bold = ImageFont.truetype(os.path.join(HERE, "fonts", "JetBrainsMono-Bold.ttf"), FS)
bb = font.getbbox("█"); CW = bb[2] - bb[0]; CH = int(FS * 1.25)
COLS = 100
PAD = 12 * SS
G = 4 * SS  # image grain size in px

# ---------------------------------------------------------------- images
def svg_png(url, width_px):
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
    "icons":  "https://skillicons.dev/icons?i=java,kotlin,python,ts,gradle,docker,git&theme=dark",
    "mocap":  "https://img.shields.io/badge/Mocap-record%20%26%20replay%20players%20as%20packet%20actors-1a1b27?style=for-the-badge&logo=github&logoColor=c0caf5&labelColor=7aa2f7",
    "heads":  "https://img.shields.io/badge/HeadSprites-custom%20head%20sprites%20inline%20in%20chat-1a1b27?style=for-the-badge&logo=github&logoColor=c0caf5&labelColor=7aa2f7",
    "stats":  f"https://github-profile-summary-cards.vercel.app/api/cards/stats?username={LOGIN}&{T}",
    "langs":  f"https://github-profile-summary-cards.vercel.app/api/cards/repos-per-language?username={LOGIN}&{T}",
    "streak": f"https://github-readme-streak-stats.herokuapp.com?user={LOGIN}&{T}&hide_border=true&background=1a1b27",
}

# ---------------------------------------------------------------- layout
# grain: dict(x0, y0 = target px, w, h, kind, payload, colour)
grains = []

def put(x, y, text, color, f=font):
    for i, ch in enumerate(text):
        if ch == " ": continue
        grains.append(dict(x0=PAD + (x + i) * CW, y0=PAD + y * CH, w=CW, h=CH, kind="char",
                           ch=ch, col=color, f=f))

def place(img, y, rows, x=None, align="center"):
    """Scale img to `rows` rows (keeping aspect), position it, cut into GxG grains.
    x is in cells: the left edge, or with align="right" the right edge."""
    if img is None: return
    h = rows * CH; w = round(img.width * h / img.height)
    if w > (COLS - 4) * CW:
        w = (COLS - 4) * CW; h = round(img.height * w / img.width)
    img = img.resize((w, h), Image.LANCZOS)
    if x is None: x0 = PAD + (COLS * CW - w) // 2
    elif align == "right": x0 = PAD + x * CW - w
    else: x0 = PAD + x * CW
    y0 = PAD + y * CH + (rows * CH - h) // 2
    flat = Image.new("RGB", img.size, BG); flat.paste(img, (0, 0), img)
    for gy in range(0, h, G):
        for gx in range(0, w, G):
            tile = flat.crop((gx, gy, min(gx + G, w), min(gy + G, h)))
            if tile.getbbox() is None: continue
            px = tile.resize((1, 1), Image.BOX).getpixel((0, 0))
            if max(abs(px[i] - BG[i]) for i in range(3)) < 3: continue  # background: nothing to pour
            grains.append(dict(x0=x0 + gx, y0=y0 + gy, w=tile.width, h=tile.height, kind="tile", tile=tile, col=px))

name = [l.rstrip("\n") for l in open(os.path.join(HERE, "name.txt"))]
name = [l for l in name if l.strip()]
NW = len(max(name, key=len))

y = 1
for r, l in enumerate(name):
    for c, ch in enumerate(l):
        if ch != " ": put((COLS - NW) // 2 + c, y + r, ch, LET if ch == "█" else SHD, bold)
y += len(name) + 2
tag = "block game developer   ·   java kotlin typescript   ·   doing cool things"
put((COLS - len(tag)) // 2, y, tag, DIM); y += 3

imgs = {k: svg_png(u, 1600) for k, u in IMAGES.items()}
place(imgs["icons"], y, 3); y += 5
# badges: both left-aligned to the same column, the pair centred as a block
bw = max(round(im.width * 2 * CH / im.height) for im in (imgs["mocap"], imgs["heads"]) if im) // CW
bx = (COLS - bw) // 2
place(imgs["mocap"], y, 2, x=bx); y += 3
place(imgs["heads"], y, 2, x=bx); y += 4
cw = 44
place(imgs["stats"], y, 14, x=(COLS - 2 * cw - 2) // 2)
place(imgs["langs"], y, 14, x=(COLS - 2 * cw - 2) // 2 + cw + 2)
y += 16
place(imgs["streak"], y, 12); y += 13

W = COLS * CW + PAD * 2; H = y * CH + PAD * 2
FPS = 10; BUILD = int(9 * FPS); HOLD = int(2 * FPS); TOTAL = BUILD + HOLD
FALL = 28 * SS  # px per frame

# spawn: bottom of the page first, so everything piles up like sand
window = BUILD - H // FALL - 8
for g in grains:
    depth = (H - g["y0"]) / H
    g["spawn"] = int(depth * window) + random.randint(0, 8)
    g["x"] = max(0, min(W - g["w"], g["x0"] + random.randint(-40 * SS, 40 * SS)))
    g["y"] = -g["h"] - random.randint(0, FALL)
    g["landed"] = False
    if g["kind"] == "char": g["fc"] = random.choice("sand")

# ---------------------------------------------------------------- frames
def draw_char(d, x, y, g, ch, col, f):
    d.text((x, y), ch, font=f, fill=col)
def draw_block(d, x, y, g, col):
    d.rectangle((x, y, x + g["w"] - 1, y + g["h"] - 1), fill=col)

landed = Image.new("RGB", (W, H), BG)  # everything that has settled, drawn once
ld = ImageDraw.Draw(landed)
frames = []
preview = os.environ.get("PREVIEW")
for fr in range(TOTAL):
    falling = []
    for g in grains:
        if g["landed"] or fr < g["spawn"]: continue
        g["y"] += FALL
        dx = g["x0"] - g["x"]; left = g["y0"] - g["y"]
        if dx:
            step = min(abs(dx), 6 * SS if left > FALL * 2 else abs(dx))
            if random.random() < 0.7 or left <= FALL * 2: g["x"] += step if dx > 0 else -step
        if g["y"] >= g["y0"]:
            g["landed"] = True
            if g["kind"] == "tile": landed.paste(g["tile"], (g["x0"], g["y0"]))
            elif g["ch"] == "█": draw_block(ld, g["x0"], g["y0"], g, g["col"])
            else: draw_char(ld, g["x0"], g["y0"], g, g["ch"], g["col"], g["f"])
        else:
            if g["kind"] == "char" and random.random() < 0.3: g["fc"] = random.choice("sand")
            falling.append(g)
    img = landed.copy(); d = ImageDraw.Draw(img)
    for g in falling:
        if g["kind"] == "tile": draw_block(d, g["x"], g["y"], g, g["col"])
        else:
            d.rectangle((g["x"], g["y"], g["x"] + CW - 1, g["y"] + CH - 1), fill=BG)
            draw_char(d, g["x"], g["y"], g, g["fc"], SANDC, font)
    frames.append(img.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    if preview and fr in (40, 70, TOTAL - 1): img.save(os.path.join(preview, f"f{fr}.png"))

# No loop extension: plays once and rests on the finished page.
frames[0].save(os.path.join(HERE, "..", "page.gif"), save_all=True, append_images=frames[1:],
               duration=int(1000 / FPS), optimize=True)
print(f"{W}x{H} {TOTAL} frames {len(grains)} grains")
