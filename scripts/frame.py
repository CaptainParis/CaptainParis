# Renders frame.gif: the whole profile as one terminal screen, built grain by
# grain by falling sand, with a Doom-style flame burning behind it.
#
#   uv run --with pillow python scripts/frame.py
#
# Needs GITHUB_TOKEN (or a logged-in `gh`) to fetch the stats.
import json, math, os, random, subprocess, urllib.request
from datetime import date, timedelta
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
LOGIN = os.environ.get("GH_LOGIN", "CaptainParis")
random.seed(7)

# ---------------------------------------------------------------- stats
QUERY = """
query($login:String!){ user(login:$login){
  repositories(first:100, ownerAffiliations:OWNER, privacy:PUBLIC, isFork:false){
    totalCount nodes{ name stargazerCount
      languages(first:10, orderBy:{field:SIZE,direction:DESC}){ edges{ size node{ name } } } } }
  pullRequests{ totalCount } issues{ totalCount }
  contributionsCollection{ totalCommitContributions
    contributionCalendar{ totalContributions weeks{ contributionDays{ date contributionCount } } } }
}}"""

def token():
    t = os.environ.get("GITHUB_TOKEN")
    if t: return t
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()

def fetch():
    req = urllib.request.Request("https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)["data"]["user"]

u = fetch()
repos = [r for r in u["repositories"]["nodes"] if r["name"].lower() != LOGIN.lower()]
stars = sum(r["stargazerCount"] for r in repos)
langs = {}
for r in repos:
    for e in r["languages"]["edges"]:
        langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
tot = sum(langs.values()) or 1
top = sorted(langs.items(), key=lambda kv: -kv[1])[:4]
days = [d for w in u["contributionsCollection"]["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
days.sort(key=lambda d: d["date"])
active = sum(1 for d in days if d["contributionCount"] > 0)
longest = cur = run = 0
for d in days:
    run = run + 1 if d["contributionCount"] > 0 else 0
    longest = max(longest, run)
today = date.today().isoformat()
for d in reversed(days):
    if d["date"] == today and d["contributionCount"] == 0: continue
    if d["contributionCount"] == 0: break
    cur += 1
commits = u["contributionsCollection"]["totalCommitContributions"]
contribs = u["contributionsCollection"]["contributionCalendar"]["totalContributions"]
prs = u["pullRequests"]["totalCount"]

# ---------------------------------------------------------------- palette
BG = (26, 27, 39); LET = (192, 202, 245); SHD = (122, 162, 247); DIM = (86, 95, 137)
SANDC = (224, 175, 104); GROUND = (158, 206, 106); WALL = (224, 175, 104)
LANGC = {"Java": (224, 175, 104), "Kotlin": (187, 154, 247), "TypeScript": (122, 162, 247),
         "Python": (158, 206, 106), "JavaScript": (255, 158, 100)}

# ---------------------------------------------------------------- layout
name = [l.rstrip("\n") for l in open(os.path.join(HERE, "name.txt"))]
name = [l for l in name if l.strip()]
NW = len(max(name, key=len))
COLS = NW + 8
LEFT = 3
cells = {}  # (x, y) -> (char, color)
mask = set()  # text spans, spaces included: flame never draws here

def put(x, y, text, color):
    for i, ch in enumerate(text):
        mask.add((x + i, y))
        if ch != " ": cells[(x + i, y)] = (ch, color)

def row(y, label, parts):
    """parts: list of (text, color). Label sits in a fixed 11-col gutter."""
    put(LEFT, y, label.ljust(11), SHD)
    x = LEFT + 11
    for text, color in parts:
        put(x, y, text, color); x += len(text)

y = 2
for r, l in enumerate(name):
    for c, ch in enumerate(l):
        if ch != " ": cells[((COLS - NW) // 2 + c, y + r)] = (ch, LET if ch == "█" else SHD)
y += len(name)
tag = "block game developer   ·   java kotlin typescript   ·   doing cool things"
put((COLS - len(tag)) // 2, y, tag, DIM); y += 2

row(y, "stack", [("java   kotlin   python   typescript   gradle   docker   git", LET)]); y += 2

row(y, "projects", [("Mocap        ", LET), ("record & replay players as packet actors", DIM)]); y += 1
row(y, "", [("HeadSprites  ", LET), ("custom head sprites inline in chat", DIM)]); y += 2

row(y, "stats", [(f"commits {commits}", LET), ("   ", LET), (f"contributions {contribs}", LET),
                 ("   ", LET), (f"prs {prs}", LET), ("   ", LET), (f"stars {stars}", LET),
                 ("   ", LET), (f"repos {len(repos)}", LET)]); y += 1
parts = []
for n, size in top:
    pct = size / tot
    bar = "█" * max(1, round(pct * 12))
    parts += [(n.lower() + " ", LET), (bar, LANGC.get(n, DIM)), (f" {pct*100:.0f}%", DIM), ("   ", LET)]
row(y, "languages", parts); y += 1
row(y, "streak", [(f"current {cur}d", LET), ("   ", LET), (f"longest {longest}d", LET), ("   ", LET),
                  (f"active {active}/{len(days)} days", LET)]); y += 2

ROWS = y + 1
for x in range(COLS):
    cells[(x, 0)] = ("GROUND_"[x % 7], GROUND)
    cells[(x, ROWS - 1)] = ("GROUND_"[x % 7], GROUND)
for yy in range(1, ROWS - 1):
    cells[(0, yy)] = ("WALL"[yy % 4], WALL)
    cells[(COLS - 1, yy)] = ("WALL"[yy % 4], WALL)

# ---------------------------------------------------------------- render setup
FS = 13
font = ImageFont.truetype(os.path.join(HERE, "fonts", "JetBrainsMono-Regular.ttf"), FS)
bold = ImageFont.truetype(os.path.join(HERE, "fonts", "JetBrainsMono-Bold.ttf"), FS)
bb = font.getbbox("█"); CW = bb[2] - bb[0]; CH = int(FS * 1.25)
PAD = 10
W = COLS * CW + PAD * 2; H = ROWS * CH + PAD * 2
FPS = 12; BUILD = int(9 * FPS); HOLD = int(3 * FPS); TOTAL = BUILD + HOLD

grains = []
for (tx, ty), (ch, col) in cells.items():
    depth = (ROWS - 1) - ty
    spawn = int(depth * (BUILD - ROWS - 12) / ROWS) + random.randint(0, 12)
    sx = max(0, min(COLS - 1, tx + random.randint(-10, 10)))
    grains.append(dict(tx=tx, ty=ty, ch=ch, col=col, spawn=spawn, x=sx, y=-1, landed=False, fc=random.choice("sand")))

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
        val = int(4 + noise(i * 0.05, t) * 22)
        data[last + i] = min(val, data[last + i] + 2)
    for i in range(len(data)):
        r = i // COLS; c = i % COLS
        dest = r * COLS + max(0, min(COLS - 1, c + rndi(-1, 1)))
        src = min(ROWS - 1, r + 1) * COLS + c
        data[dest] = max(0, data[src] - rndi(0, 3))
def fcol(u):
    t = min(1, u / 28)
    stops = [(70, 30, 40), (150, 50, 40), (230, 110, 50), (255, 158, 100), (255, 220, 150)]
    x = t * (len(stops) - 1); i = min(int(x), len(stops) - 2); f = x - i
    a, b = stops[i], stops[i + 1]
    return tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3))

# ---------------------------------------------------------------- frames
def cell(d, x, y, ch, col, f=font):
    d.rectangle((PAD + x * CW, PAD + y * CH, PAD + x * CW + CW, PAD + y * CH + CH), fill=BG)
    if ch == "█": d.rectangle((PAD + x * CW, PAD + y * CH, PAD + x * CW + CW, PAD + y * CH + CH), fill=col)
    else: d.text((PAD + x * CW, PAD + y * CH), ch, font=f, fill=col)

frames = []
for fr in range(TOTAL):
    flame_step(fr * 0.06)
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
    for i, v in enumerate(data):
        if v <= 0: continue
        r, c = divmod(i, COLS)
        if (c, r) in mask: continue
        d.text((PAD + c * CW, PAD + r * CH), flame[min(v, len(flame) - 1)], font=font, fill=fcol(v))
    for g in grains:
        if fr < g["spawn"]: continue
        if not g["landed"]:
            g["y"] += 1
            dx = g["tx"] - g["x"]; left = g["ty"] - g["y"]
            if dx != 0 and (left <= abs(dx) or random.random() < 0.6): g["x"] += 1 if dx > 0 else -1
            if g["y"] >= g["ty"]: g["landed"] = True; g["x"] = g["tx"]; g["y"] = g["ty"]
            if not g["landed"]:
                if random.random() < 0.3: g["fc"] = random.choice("sand")
                cell(d, g["x"], g["y"], g["fc"], SANDC)
                continue
        cell(d, g["tx"], g["ty"], g["ch"], g["col"], bold if g["col"] in (SHD, GROUND, WALL) else font)
    frames.append(img.quantize(colors=32, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    if os.environ.get("PREVIEW") and fr in (50, TOTAL - 1): img.save(os.path.join(os.environ["PREVIEW"], f"f{fr}.png"))

# No loop extension: plays once and rests on the finished screen.
frames[0].save(os.path.join(HERE, "..", "frame.gif"), save_all=True, append_images=frames[1:],
               duration=int(1000 / FPS), optimize=True)
print(f"{W}x{H} {TOTAL} frames {COLS}x{ROWS} cells")
