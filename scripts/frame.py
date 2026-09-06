# Renders name.gif and page.gif: the profile poured in as ASCII sand.
# Every grain is a coloured character while it falls. Text grains land as
# their letter; image grains (icons, badges, cards) roll through a few
# characters on landing and then resolve into the pixels they stand for.
#
#   uv run --with pillow python scripts/frame.py
#
# Needs rsvg-convert on PATH to rasterise the SVG cards.
import io, os, random, subprocess, urllib.request
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
LOGIN = os.environ.get("GH_LOGIN", "CaptainParis")
random.seed(7)

BG = (26, 27, 39); LET = (192, 202, 245); SHD = (122, 162, 247); SANDC = (224, 175, 104)

SS = 2                    # render at 2x, README shows it at 1x so it stays crisp on HiDPI
FS = 13 * SS
font = ImageFont.truetype(os.path.join(HERE, "fonts", "JetBrainsMono-Regular.ttf"), FS)
bold = ImageFont.truetype(os.path.join(HERE, "fonts", "JetBrainsMono-Bold.ttf"), FS)
bb = font.getbbox("█"); CW = bb[2] - bb[0]; CH = int(FS * 1.25)
Q = CH // 2               # image grain: a Q x Q square, drawn as one small character while loose
small = ImageFont.truetype(os.path.join(HERE, "fonts", "JetBrainsMono-Bold.ttf"), Q)
COLS = 100
PAD = 12 * SS
W = COLS * CW + PAD * 2
RAMP = ".:-=+*#%@"        # dim to bright
FPS = 10; FALL = 28 * SS  # px per frame

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

# ---------------------------------------------------------------- layout helpers
def put(grains, x, y, text, color, f=font):
    for i, ch in enumerate(text):
        if ch == " ": continue
        grains.append(dict(x0=PAD + (x + i) * CW, y0=PAD + y * CH, w=CW, h=CH, kind="char", ch=ch, col=color, f=f))

def place(grains, img, y, rows, x=None):
    """Scale img to `rows` rows (keeping aspect), position it, cut into Q x Q grains."""
    if img is None: return
    h = rows * CH; w = round(img.width * h / img.height)
    if w > (COLS - 4) * CW:
        w = (COLS - 4) * CW; h = round(img.height * w / img.width)
    img = img.resize((w, h), Image.LANCZOS)
    x0 = PAD + ((COLS * CW - w) // 2 if x is None else x * CW)
    y0 = PAD + y * CH + (rows * CH - h) // 2
    flat = Image.new("RGB", img.size, BG); flat.paste(img, (0, 0), img)
    for gy in range(0, h, Q):
        for gx in range(0, w, Q):
            tile = flat.crop((gx, gy, min(gx + Q, w), min(gy + Q, h)))
            px = tile.resize((1, 1), Image.BOX).getpixel((0, 0))
            if max(abs(px[i] - BG[i]) for i in range(3)) < 3: continue  # background: nothing to pour
            lum = (0.3 * px[0] + 0.59 * px[1] + 0.11 * px[2]) / 255
            ch = RAMP[min(len(RAMP) - 1, int(lum * len(RAMP)))]
            grains.append(dict(x0=x0 + gx, y0=y0 + gy, w=tile.width, h=tile.height, kind="tile", tile=tile,
                               col=px, ch=ch))

# ---------------------------------------------------------------- animation
def render(grains, H, path, build_s, hold_s):
    total = int((build_s + hold_s) * FPS); build = int(build_s * FPS)
    window = max(1, build - H // FALL - 8)
    for g in grains:
        depth = (H - g["y0"]) / H            # bottom of the page first: it piles up
        g["spawn"] = int(depth * window) + random.randint(0, 8)
        g["x"] = max(0, min(W - g["w"], g["x0"] + random.randint(-40 * SS, 40 * SS)))
        g["y"] = -g["h"] - random.randint(0, FALL)
        g["state"] = "loose"
        g["fc"] = random.choice("sand") if g["kind"] == "char" else random.choice(RAMP)
        g["settle"] = 0

    landed = Image.new("RGB", (W, H), BG); ld = ImageDraw.Draw(landed)
    frames = []
    for fr in range(total):
        active = []
        for g in grains:
            st = g["state"]
            if st == "done" or fr < g["spawn"]: continue
            if st == "loose":
                g["y"] += FALL
                dx = g["x0"] - g["x"]; left = g["y0"] - g["y"]
                if dx:
                    step = min(abs(dx), 6 * SS if left > FALL * 2 else abs(dx))
                    if random.random() < 0.7 or left <= FALL * 2: g["x"] += step if dx > 0 else -step
                if random.random() < 0.35: g["fc"] = random.choice("sand" if g["kind"] == "char" else RAMP)
                if g["y"] >= g["y0"]:
                    g["x"], g["y"] = g["x0"], g["y0"]
                    if g["kind"] == "char":
                        g["state"] = "done"
                        if g["ch"] == "█": ld.rectangle((g["x0"], g["y0"], g["x0"] + CW, g["y0"] + CH), fill=g["col"])
                        else: ld.text((g["x0"], g["y0"]), g["ch"], font=g["f"], fill=g["col"])
                        continue
                    g["state"] = "settle"; g["settle"] = random.randint(2, 4)
            elif st == "settle":
                # roll through a few characters, then resolve into the image pixels
                g["settle"] -= 1
                g["fc"] = random.choice(RAMP)
                if g["settle"] <= 0:
                    g["state"] = "done"; landed.paste(g["tile"], (g["x0"], g["y0"])); continue
            active.append(g)
        img = landed.copy(); d = ImageDraw.Draw(img)
        for g in active:
            if g["kind"] == "char":
                d.rectangle((g["x"], g["y"], g["x"] + CW - 1, g["y"] + CH - 1), fill=BG)
                d.text((g["x"], g["y"]), g["fc"], font=font, fill=SANDC)
            else:
                d.rectangle((g["x"], g["y"], g["x"] + Q - 1, g["y"] + Q - 1), fill=BG)
                d.text((g["x"], g["y"] - Q // 6), g["fc"], font=small, fill=g["col"])
        frames.append(img.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
        if os.environ.get("PREVIEW") and fr in (30, total - 1):
            img.save(os.path.join(os.environ["PREVIEW"], f"{os.path.basename(path)}-{fr}.png"))
    # No loop extension: plays once and rests on the finished picture.
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=int(1000 / FPS), optimize=True)
    print(f"{path}: {W}x{H} {total} frames {len(grains)} grains")

# ---------------------------------------------------------------- name.gif
name = [l.rstrip("\n") for l in open(os.path.join(HERE, "name.txt"))]
name = [l for l in name if l.strip()]
NW = len(max(name, key=len))
grains = []
for r, l in enumerate(name):
    for c, ch in enumerate(l):
        if ch != " ": put(grains, (COLS - NW) // 2 + c, 1 + r, ch, LET if ch == "█" else SHD, bold)
render(grains, (len(name) + 2) * CH + PAD * 2, os.path.join(HERE, "..", "name.gif"), 4, 1)

# ---------------------------------------------------------------- page.gif
imgs = {k: svg_png(u, 1600) for k, u in IMAGES.items()}
grains = []
y = 1
place(grains, imgs["icons"], y, 3); y += 5
bw = max(round(im.width * 2 * CH / im.height) for im in (imgs["mocap"], imgs["heads"]) if im) // CW
bx = (COLS - bw) // 2
place(grains, imgs["mocap"], y, 2, x=bx); y += 3
place(grains, imgs["heads"], y, 2, x=bx); y += 4
cw = 44
place(grains, imgs["stats"], y, 14, x=(COLS - 2 * cw - 2) // 2)
place(grains, imgs["langs"], y, 14, x=(COLS - 2 * cw - 2) // 2 + cw + 2)
y += 16
place(grains, imgs["streak"], y, 12); y += 13
render(grains, y * CH + PAD * 2, os.path.join(HERE, "..", "page.gif"), 8, 1.5)
