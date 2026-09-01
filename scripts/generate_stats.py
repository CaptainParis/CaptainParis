#!/usr/bin/env python3
"""Draw the profile README's graphics as an 80-column bulletin-board screen.

No third-party services and no dependencies — standard library only.

Every file is the same thing: a grid of monospace characters, 80 columns wide,
framed in box drawing, printed one line at a time. Charts are drawn in block
elements rather than paths, so a bar and a letter sit on the same grid.

Outputs:
  banner.svg  the name in shadowed block letters, plus a status line
  stats.svg   contribution totals and a 52-week sparkline
  streak.svg  current and longest streak
  langs.svg   top languages, by bytes and by repo count
  year.svg    the year as a 7x53 character map
  hd-*.svg    section heading rules

Motion is SMIL because GitHub strips <script> from READMEs: each line is
revealed by a clipPath wipe, staggered top to bottom, frozen when it lands.

Env:
  GITHUB_TOKEN  required
  GH_LOGIN      user to summarise (default: CaptainParis)
  OUT_DIR       where to write (default: repository root)
"""
import base64
import functools
import json
import os
import sys
import textwrap
import urllib.request
from datetime import date, datetime, timedelta, timezone

API = "https://api.github.com/graphql"

# Two things are pinned for determinism:
#  * the contribution window, to whole UTC days — otherwise "the past year" is
#    measured from request time and days drift between week buckets, moving the
#    sparkline a fraction of a cell and committing noise every night;
#  * privacy: PUBLIC on repositories — otherwise a personal token sees private
#    repos and a workflow token doesn't, so language totals disagree.
QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    login
    name
    createdAt
    followers { totalCount }
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date weekday } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 privacy: PUBLIC) {
      totalCount
      nodes {
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

LIGHT = dict(data="#6e7681", emph="#424a53", dim="#8c959f",
             rule="#d8dee4", surface="#ffffff")
DARK = dict(data="#c9d1d9", emph="#f0f6fc", dim="#8b949e",
            rule="#30363d", surface="#0d1117")
MONO = ("JBMono,ui-monospace,SFMono-Regular,Menlo,Consolas,"
        "&apos;Liberation Mono&apos;,monospace")
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

HEADINGS = ("about", "stack", "projects", "demo", "stats", "about this page")

MOTTO = ("Either way, you will suffer. Discipline hurts now, regret hurts "
         "later \u2014 one of them is temporary, the other follows you into "
         "every room for the rest of your life. Choose which pain you carry.")


@functools.lru_cache(maxsize=None)
def face(filename, weight):
    """One @font-face rule with the subset inlined as a data URI."""
    with open(os.path.join(FONT_DIR, filename), "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return (f"@font-face{{font-family:JBMono;font-style:normal;"
            f"font-weight:{weight};font-display:block;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")


def font_text():
    return face("jbmono-400.woff2", 400) + face("jbmono-600.woff2", 600)


def font_head():
    return face("jbmono-head.woff2", 600)


# The screen. 620px wide over 80 columns is 7.75px a cell, and JetBrains Mono
# advances 0.600 em, so the font size falls out of the cell width. Change one
# and the frames stop meeting at the corners.
WIDTH = 620
COLS = 80
CW = WIDTH / COLS
FS = CW / 0.600
LH = 15.5
PAD_T = 3
PAD_B = 5

SPARK = "▁▂▃▄▅▆▇█"          # eight heights, for the weekly line
EIGHTHS = "▏▎▍▌▋▊▉"         # partial cells, for the ends of bars
TRACK = "░"                 # the unfilled part of a bar
YEAR_RAMP = ["·", "░", "▒", "▓", "█"]

MON = ["jan", "feb", "mar", "apr", "may", "jun",
       "jul", "aug", "sep", "oct", "nov", "dec"]

# ANSI-shadow block letters, only for the name this profile actually prints.
# Anything else falls back to plain uppercase, which is why the fallback exists
# rather than a full 36-glyph alphabet nobody here would draw.
GLYPHS = {
    "P": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔═══╝ ", "██║     ", "╚═╝     "],
    "A": [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "R": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██║  ██║", "╚═╝  ╚═╝"],
    "I": ["██╗", "██║", "██║", "██║", "██║", "╚═╝"],
    "S": ["███████╗", "██╔════╝", "███████╗", "╚════██║", "███████║", "╚══════╝"],
}


# ---------------------------------------------------------------- data

def window():
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    return (f"{start.isoformat()}T00:00:00Z", f"{today.isoformat()}T23:59:59Z")


def fetch(login, token):
    since, until = window()
    body = json.dumps({"query": QUERY,
                       "variables": {"login": login,
                                     "from": since, "to": until}}).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": f"{login}-profile-stats"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL errors: {payload['errors']}")
    user = (payload.get("data") or {}).get("user")
    if not user:
        raise SystemExit(f"no such user: {login}")
    return user


def pretty(iso):
    d = date.fromisoformat(iso)
    return f"{MON[d.month - 1]} {d.day}"


def streaks(days):
    """Current and longest runs of days with at least one contribution.

    A zero on the final day doesn't break the current streak — the day isn't
    over yet. Any earlier zero does.
    """
    best = dict(length=0, start=None, end=None)
    run, run_start = 0, None
    for d in days:
        if d["contributionCount"] > 0:
            run += 1
            run_start = run_start or d["date"]
            if run > best["length"]:
                best = dict(length=run, start=run_start, end=d["date"])
        else:
            run, run_start = 0, None

    cur = dict(length=0, start=None, end=None)
    tail = days[:-1] if days and days[-1]["contributionCount"] == 0 else days
    for d in reversed(tail):
        if d["contributionCount"] == 0:
            break
        cur["length"] += 1
        cur["start"] = d["date"]
        cur["end"] = cur["end"] or d["date"]
    return cur, best


def languages(repos):
    by_size, by_repo = {}, {}
    for node in repos:
        edges = (node.get("languages") or {}).get("edges") or []
        for e in edges:
            name = e["node"]["name"]
            by_size[name] = by_size.get(name, 0) + e["size"]
        if edges:
            top = edges[0]["node"]["name"]
            by_repo[top] = by_repo.get(top, 0) + 1

    def rank(d):
        return sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:5]

    return rank(by_size), rank(by_repo)


def summarise(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [w["contributionDays"] for w in cal["weeks"]]
    days = [d for w in weeks for d in w]
    weekly = [sum(d["contributionCount"] for d in w) for w in weeks]
    cur, best = streaks(days)
    by_size, by_repo = languages(user["repositories"]["nodes"])
    return dict(
        login=user["login"],
        name=user.get("name") or user["login"],
        since=user["createdAt"][:4],
        repos=user["repositories"]["totalCount"],
        followers=user["followers"]["totalCount"],
        total=cal["totalContributions"],
        active=sum(1 for d in days if d["contributionCount"] > 0),
        days=len(days),
        best_week=max(weekly) if weekly else 0,
        weekly=weekly, weeks=weeks,
        current=cur, longest=best,
        by_size=by_size, by_repo=by_repo)


# ---------------------------------------------------------------- screen

def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;")


def run(col, text, cls="d-f", bold=False):
    return (col, text, cls, bold)


def rule(text):
    """A whole line of frame."""
    return [run(0, text, "m-f")]


def box(title, body, w=COLS):
    """Frame `body` in double lines with `title` cut into the top edge.

    A body entry is either a string, a list of runs whose columns are relative
    to the first content column, or the sentinel "-" for a light divider.
    """
    lead = f"╔═[ {title.upper()} ]"
    rows = [[run(0, lead, "m-f"), run(len(lead), "═" * (w - 1 - len(lead)) + "╗",
                                      "m-f")]]
    for entry in body:
        if entry == "-":
            rows.append(rule("╟" + "─" * (w - 2) + "╢"))
            continue
        runs = [run(0, "║", "m-f"), run(w - 1, "║", "m-f")]
        cells = [run(0, entry)] if isinstance(entry, str) else entry
        runs += [run(c + 2, t, cl, b) for c, t, cl, b in cells]
        rows.append(runs)
    rows.append(rule("╚" + "═" * (w - 2) + "╝"))
    return rows


def style(font=None):
    def block(t):
        return (f".d-f{{fill:{t['data']}}}.e-f{{fill:{t['emph']}}}"
                f".m-f{{fill:{t['dim']}}}.f-f{{fill:{t['rule']}}}")
    return (f"<style>{font or font_text()}"
            f"{block(LIGHT)}"
            f"@media(prefers-color-scheme:dark){{{block(DARK)}}}</style>")


def screen(rows, font=None, stagger=0.055, dur=0.34, cursor=None):
    """Print `rows` one line at a time, each wiped in left to right.

    `cursor` is (row, column) for a block that keeps blinking after the print —
    a terminal that has finished but is still waiting for you.
    """
    h = PAD_T + len(rows) * LH + PAD_B
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
           f'height="{h:.0f}" viewBox="0 0 {WIDTH} {h:.0f}" fill="none" '
           f'font-family="{MONO}" font-size="{FS:.4f}">' + style(font)]

    for i, runs in enumerate(rows):
        if not runs:
            continue
        y = PAD_T + i * LH + FS - 2.4
        span = max((c + len(t)) for c, t, _, _ in runs) * CW
        delay = 0.18 + i * stagger
        cid = f"w{i}"
        out.append(f'<clipPath id="{cid}"><rect x="0" y="{PAD_T + i * LH:.2f}" '
                   f'height="{LH:.2f}" width="0"><animate '
                   f'attributeName="width" from="0" to="{span:.1f}" '
                   f'begin="{delay:.2f}s" dur="{dur}s" fill="freeze"/>'
                   f'</rect></clipPath>')
        out.append(f'<g clip-path="url(#{cid})">')
        for c, t, cls, bold in sorted(runs):
            weight = ' font-weight="600"' if bold else ""
            out.append(f'<text xml:space="preserve" x="{c * CW:.2f}" '
                       f'y="{y:.2f}" class="{cls}"{weight}>{esc(t)}</text>')
        out.append("</g>")

    if cursor:
        r, c = cursor
        begin = 0.18 + len(rows) * stagger + dur
        out.append(f'<rect x="{c * CW:.2f}" y="{PAD_T + r * LH + 2.2:.2f}" '
                   f'width="{CW:.2f}" height="{LH - 4:.2f}" class="e-f" '
                   f'opacity="0"><set attributeName="opacity" to="1" '
                   f'begin="{begin:.2f}s"/><animate attributeName="opacity" '
                   f'values="1;1;0;0" dur="1.06s" begin="{begin:.2f}s" '
                   f'repeatCount="indefinite"/></rect>')

    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- charts

def bar(value, top, width):
    """A bar in block elements, to an eighth of a cell, on a dotted track."""
    if top <= 0:
        return TRACK * width
    cells = max(0.0, min(1.0, value / top)) * width
    full = int(cells)
    rest = cells - full
    part = EIGHTHS[int(rest * 8) - 1] if int(rest * 8) else ""
    return ("█" * full + part).ljust(width, TRACK)[:width]


def sparkline(values):
    peak = max(values) if values else 0
    if peak <= 0:
        return "·" * len(values)
    out = []
    for v in values:
        if v <= 0:
            out.append("·")
        else:
            i = int(round((v / peak) * (len(SPARK) - 1)))
            out.append(SPARK[i])
    return "".join(out)


def block_name(text):
    """The name in shadowed block letters, or None if a letter is missing."""
    if not all(ch in GLYPHS for ch in text):
        return None
    height = max(len(g) for g in GLYPHS.values())
    return ["".join(GLYPHS[ch][r] for ch in text) for r in range(height)]


# ---------------------------------------------------------------- drawing

def draw_banner(s):
    name = s["name"].upper().replace(" ", "")[:8]
    art = block_name(name)
    side = [f"github.com/{s['login']}",
            "MINECRAFT PLUGINS · DISCORD BOTS",
            f"SEATTLE, WASHINGTON · SINCE {s['since']}"]

    body = [""]
    if art:
        gap = max(len(art[0]) + 4, 44)
        for i, line in enumerate(art):
            cells = [run(0, line, "e-f", True)]
            if 1 <= i <= len(side):
                cells.append(run(gap, side[i - 1], "d-f"))
            body.append(cells)
    else:
        body.append([run(0, name, "e-f", True)])
        body += [[run(0, t)] for t in side]
    body.append("")
    body.append("-")
    for line in textwrap.wrap(MOTTO, COLS - 4):
        body.append([run(0, line, "d-f")])
    body.append("-")

    status = (f"REPOS {s['repos']}", f"FOLLOWERS {s['followers']}",
              f"CONTRIBUTIONS {s['total']:,}", "STATUS ONLINE")
    line, col = [], 0
    for item in status:
        head, tail = item.split(" ", 1)
        line.append(run(col, head, "m-f"))
        line.append(run(col + len(head) + 1, tail, "e-f", True))
        col += len(item) + 4
    body.append(line)

    rows = box(name or s["login"], body)
    return screen(rows, cursor=(len(rows) - 2, col + 2))


def draw_stats(s):
    weekly = s["weekly"] or [0]
    figures = [(f"{s['total']:,}", "TOTAL"),
               (f"{s['active']}", "ACTIVE DAYS"),
               (f"{s['best_week']}", "BEST WEEK"),
               (f"{s['total'] / max(len(weekly), 1):.1f}", "PER WEEK")]

    nums, labs, col = [], [], 0
    for value, label in figures:
        width = max(len(value), len(label)) + 5
        nums.append(run(col, value, "e-f", True))
        labs.append(run(col, label, "m-f"))
        col += width

    spark = sparkline(weekly)
    body = [nums, labs, "",
            [run(0, spark, "d-f"),
             run(len(spark) + 3, f"{len(weekly)} WEEKS", "m-f")]]
    return screen(box("contributions", body))


def draw_streak(s):
    mid = 38
    cells = []
    for key, label in (("current", "CURRENT"), ("longest", "LONGEST")):
        r = s[key]
        span = (f"{pretty(r['start'])} – {pretty(r['end'])}"
                if r["length"] else "—")
        cells.append((label, r["length"], span))

    body = []
    for line in range(2):
        row = [run(mid, "│", "m-f")]
        for i, (label, length, span) in enumerate(cells):
            x = 0 if i == 0 else mid + 3
            if line == 0:
                row.append(run(x, label, "m-f"))
                row.append(run(x + 10, f"{length}", "e-f", True))
                row.append(run(x + 10 + len(str(length)) + 1, "DAYS", "d-f"))
            else:
                row.append(run(x + 10, span, "d-f"))
        body.append(row)
    return screen(box("streak", body))


def draw_langs(s):
    barw, namew = 34, 12
    total = sum(v for _, v in s["by_size"]) or 1
    body = [[run(0, "BY BYTES", "m-f")]]
    for name, val in s["by_size"]:
        top = max(v for _, v in s["by_size"]) or 1
        pct = val / total * 100
        body.append([run(0, name.lower()[:namew - 1], "e-f", True),
                     run(namew, bar(val, top, barw), "d-f"),
                     run(namew + barw + 2, f"{pct:5.1f}%", "m-f")])
    if s["by_repo"]:
        body.append("-")
        top = max(v for _, v in s["by_repo"]) or 1
        line, col = [run(0, "BY REPOS", "m-f")], 12
        for name, val in s["by_repo"]:
            label = name.lower()[:10]
            line.append(run(col, label, "e-f", True))
            line.append(run(col + len(label) + 1, bar(val, top, 4), "d-f"))
            line.append(run(col + len(label) + 6, f"{val}", "m-f"))
            col += len(label) + 9
        body.append(line)
    return screen(box("languages", body))


def draw_year(s):
    weeks = s["weeks"]
    pad = 6

    def level(v):
        for i, cut in enumerate((0, 2, 5, 9)):
            if v <= cut:
                return i
        return 4

    legend = "LESS " + "".join(YEAR_RAMP) + " MORE"
    body = [[run(0, f"{s['active']}", "e-f", True),
             run(len(str(s['active'])) + 1,
                 f"of {s['days']} days had a contribution", "d-f"),
             run(76 - len(legend), legend, "m-f")], ""]

    months = [" "] * (pad + len(weeks))
    last, last_col = None, -99
    for i, w in enumerate(weeks):
        m = int(w[0]["date"][5:7])
        col = pad + i
        if m != last and i < len(weeks) - 1 and col - last_col >= 4:
            months[col:col + 3] = list(MON[m - 1])
            last_col = col
        last = m
    body.append([run(0, "".join(months).rstrip(), "m-f")])

    for r in range(7):
        chars = []
        for w in weeks:
            day = next((d for d in w if d.get("weekday") == r), None)
            chars.append(YEAR_RAMP[level(day["contributionCount"] if day else 0)])
        label = {1: "MON", 3: "WED", 5: "FRI"}.get(r, "")
        body.append([run(0, label, "m-f"), run(pad, "".join(chars), "d-f")])

    return screen(box("the year", body), stagger=0.07)


def draw_heading(word):
    text = word.upper()
    lead = "═══╡ "
    tail = " ╞"
    fill = COLS - len(lead) - len(text) - len(tail)
    rows = [[run(0, lead, "m-f", True),
             run(len(lead), text, "e-f", True),
             run(len(lead) + len(text), tail + "═" * fill, "m-f", True)]]
    return screen(rows, font=font_head(), dur=0.9)


# ---------------------------------------------------------------- main

def write(path, svg):
    old = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = f.read()
    if old == svg:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    return True


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    login = os.environ.get("GH_LOGIN", "CaptainParis")
    out_dir = os.environ.get("OUT_DIR", ".")

    s = summarise(fetch(login, token))
    files = {"banner.svg": draw_banner(s), "stats.svg": draw_stats(s),
             "streak.svg": draw_streak(s), "langs.svg": draw_langs(s),
             "year.svg": draw_year(s)}
    for word in HEADINGS:
        files[f"hd-{word.replace(' ', '-')}.svg"] = draw_heading(word)

    changed = [n for n, svg in files.items()
               if write(os.path.join(out_dir, n), svg)]
    print(f"{s['total']} contributions, {s['active']} active days, "
          f"best week {s['best_week']}, current streak "
          f"{s['current']['length']}, longest {s['longest']['length']}")
    print("languages by bytes: "
          + ", ".join(f"{n} {v}" for n, v in s["by_size"]))
    print("updated: " + (", ".join(sorted(changed)) if changed else "nothing"))


if __name__ == "__main__":
    main()
