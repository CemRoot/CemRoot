#!/usr/bin/env python3
"""Build every animated SVG used by the profile README.

    python scripts/profile/build.py            # all assets, both themes
    python scripts/profile/build.py --only stats

Output lands in ./assets as <name>-dark.svg / <name>-light.svg; the README
swaps between them with <picture> so each matches GitHub's colour mode.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import random
from pathlib import Path

import os

from kit import HERE, ICONS, THEMES, Doc, measure, num, pct, wrap

ROOT = HERE.parents[1]
OUT = ROOT / "assets"
STATS = Path(os.environ.get("PROFILE_STATS", HERE / "data" / "stats.json"))


# --------------------------------------------------------------------------
# shared bits
# --------------------------------------------------------------------------
def rrect(x, y, w, h, r):
    return (f"M{num(x + r)},{num(y)} H{num(x + w - r)} A{r},{r} 0 0 1 {num(x + w)},{num(y + r)} "
            f"V{num(y + h - r)} A{r},{r} 0 0 1 {num(x + w - r)},{num(y + h)} H{num(x + r)} "
            f"A{r},{r} 0 0 1 {num(x)},{num(y + h - r)} V{num(y + r)} A{r},{r} 0 0 1 {num(x + r)},{num(y)} Z")


def frame(d: Doc, r=20, fill=None, clip_id="card"):
    """Rounded card background + clip path; returns the clip id."""
    t = d.t
    d.defn(f'<clipPath id="{clip_id}"><rect x="0.5" y="0.5" width="{num(d.w - 1)}" '
           f'height="{num(d.h - 1)}" rx="{r}"/></clipPath>')
    d.add(f'<rect x="0.5" y="0.5" width="{num(d.w - 1)}" height="{num(d.h - 1)}" rx="{r}" '
          f'fill="{fill or t["panel"]}" stroke="{t["line"]}"/>')
    return clip_id


def comet(d: Doc, x, y, w, h, r, colors, dur=8.0, delay=0.0, width=1.6):
    """A short gradient highlight that travels around a rounded border."""
    gid = d.uid("cg")
    a, b = colors
    d.defn(f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">'
           f'<stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>')
    d.style(".comet{stroke-dasharray:14 86;animation:comet linear infinite}"
            "@keyframes comet{from{stroke-dashoffset:100}to{stroke-dashoffset:0}}")
    d.add(f'<path d="{rrect(x, y, w, h, r)}" pathLength="100" class="comet" stroke="url(#{gid})" '
          f'stroke-width="{width}" stroke-linecap="round" fill="none" '
          f'style="animation-duration:{num(dur)}s;animation-delay:{num(-delay)}s"/>')


def typewriter(d: Doc, x, y, lines, *, size=16, fill, cursor, cover, cycle, key="mono",
               cover_w=600, cover_h=None, prefix="tw", clip=None):
    """Cycle through `lines`: type, hold, erase. Works by sliding a solid
    cover (same colour as the surface below) off the text in character-sized
    steps, so it needs a flat background but no SMIL and no clip-path."""
    cw = 0.6 * size  # Geist Mono advance width
    cover_h = cover_h or size * 1.5
    n = len(lines)
    if clip:
        cid = d.uid("twc")
        d.defn(f'<clipPath id="{cid}"><rect x="{num(clip[0])}" y="{num(clip[1])}" width="{num(clip[2])}" '
               f'height="{num(clip[3])}" rx="{num(clip[4] if len(clip) > 4 else 0)}"/></clipPath>')
        d.add(f'<g clip-path="url(#{cid})">')
    d.style(f".{prefix}-blink{{animation:{prefix}-blink 1.05s steps(1) infinite}}"
            f"@keyframes {prefix}-blink{{0%,55%{{opacity:1}}56%,100%{{opacity:0}}}}")
    for i, line in enumerate(lines):
        L = len(line)
        w = L * cw
        seg = 100 / n
        a = i * seg
        dd = (i + 1) * seg - 0.6
        b = a + min(L * 0.055 / cycle * 100, seg * 0.45)
        c = dd - min(L * 0.022 / cycle * 100, seg * 0.18)
        name = f"{prefix}{i}"
        show = (f"@keyframes {name}s{{0%{{opacity:{1 if i == 0 else 0}}}"
                + (f"{pct(a)}{{opacity:0}}{pct(a + 0.01)}{{opacity:1}}" if i else "")
                + f"{pct(dd)}{{opacity:1}}{pct(dd + 0.01)}{{opacity:0}}100%{{opacity:0}}}}")
        move = (f"@keyframes {name}t{{0%,{pct(a)}{{transform:translateX(0);animation-timing-function:steps({L},end)}}"
                f"{pct(b)}{{transform:translateX({num(w)}px);animation-timing-function:linear}}"
                f"{pct(c)}{{transform:translateX({num(w)}px);animation-timing-function:steps({L},end)}}"
                f"{pct(dd)},100%{{transform:translateX(0)}}}}")
        d.style(show + move)
        rest_opacity = 1 if i == 0 else 0
        rest_shift = num(w) if i == 0 else 0
        top = y - size * 0.95
        d.add(f'<g style="opacity:{rest_opacity};animation:{name}s {num(cycle)}s infinite">'
              + d.text(x, y, line, key, size, fill)
              + f'<g style="transform:translateX({rest_shift}px);animation:{name}t {num(cycle)}s infinite">'
              f'<rect x="{num(x + cw)}" y="{num(top)}" width="{cover_w}" height="{num(cover_h)}" fill="{cover}"/>'
              f'<rect class="{prefix}-blink" x="{num(x + 1)}" y="{num(y - size * 0.82)}" width="{num(cw - 1)}" '
              f'height="{num(size * 1.05)}" rx="1.5" fill="{cursor}"/>'
              '</g></g>')
    if clip:
        d.add("</g>")


def softmax(xs):
    m = max(xs)
    e = [math.exp(v - m) for v in xs]
    s = sum(e)
    return [v / s for v in e]


# --------------------------------------------------------------------------
# hero
# --------------------------------------------------------------------------
def hero(theme):
    W, H = 1000, 420
    d = Doc(W, H, theme, "Cem Koyluoglu — GenAI Engineer & ML Researcher",
            "I turn frontier models into products people actually use. Based in Dublin, Ireland.")
    t = d.t
    clip = frame(d, 22, t["bg"])
    d.defn('<filter id="blur" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="64"/></filter>')
    d.defn(f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">'
           f'<circle cx="2" cy="2" r="1.1" fill="{t["faint"]}"/></pattern>')
    d.defn('<radialGradient id="dotfade" cx="72%" cy="45%" r="62%">'
           '<stop offset="0" stop-color="#fff" stop-opacity="1"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>')
    d.defn(f'<mask id="dotmask"><rect width="{W}" height="{H}" fill="url(#dotfade)"/></mask>')
    d.defn(f'<linearGradient id="ink" x1="0" y1="0" x2="1" y2="0">'
           f'<stop offset="0" stop-color="{t["v"]}"/><stop offset="1" stop-color="{t["c"]}"/></linearGradient>')
    d.style(".a1{animation:a1 16s ease-in-out infinite alternate}"
            ".a2{animation:a2 19s ease-in-out infinite alternate}"
            ".a3{animation:a3 23s ease-in-out infinite alternate}"
            "@keyframes a1{to{transform:translate(-140px,70px)}}"
            "@keyframes a2{to{transform:translate(90px,-80px)}}"
            "@keyframes a3{to{transform:translate(160px,40px)}}"
            ".pulse{transform-box:fill-box;transform-origin:center;animation:pulse 2.2s ease-out infinite}"
            "@keyframes pulse{0%{transform:scale(1);opacity:.7}100%{transform:scale(3.2);opacity:0}}")

    g = t["glow"]
    d.add(f'<g clip-path="url(#{clip})">'
          f'<g filter="url(#blur)">'
          f'<circle class="a1" cx="820" cy="70" r="150" fill="{t["v"]}" opacity="{g}"/>'
          f'<circle class="a2" cx="950" cy="380" r="130" fill="{t["c"]}" opacity="{g * 0.85}"/>'
          f'<circle class="a3" cx="300" cy="-30" r="110" fill="{t["coral"]}" opacity="{g * 0.45}"/>'
          f'</g>'
          f'<rect width="{W}" height="{H}" fill="url(#dots)" mask="url(#dotmask)" opacity=".75"/>'
          f'</g>')

    # top bar
    d.add(d.rich(56, 50, [("~/", "mono", t["muted"]), ("cemroot", "mono", t["sub"]),
                          ("  /  ", "mono", t["faint"]), ("README.md", "mono", t["muted"])], size=13))
    status = "building in Dublin, IE"
    sw = measure(status, "mono", 12.5) + 44
    sx = W - 44 - sw
    d.add(f'<rect x="{num(sx)}" y="31" width="{num(sw)}" height="28" rx="14" fill="{t["panel"]}" '
          f'stroke="{t["line"]}" opacity=".92"/>'
          f'<circle cx="{num(sx + 17)}" cy="45" r="4" fill="{t["lime"]}" class="pulse"/>'
          f'<circle cx="{num(sx + 17)}" cy="45" r="4" fill="{t["lime"]}"/>')
    d.add(d.text(sx + 30, 49.5, status, "mono", 12.5, t["sub"]))

    # identity
    d.add(d.text(56, 116, "GENAI ENGINEER  ·  ML RESEARCHER", "monoM", 13, t["c"], ls=1.6))
    d.add(d.text(53, 184, "Cem Koyluoglu", "sansB", 66, t["text"], ls=-2.2))
    d.add(d.text(56, 226, "I turn frontier models into", "sans", 22, t["sub"]))
    d.add(d.text(55, 270, "products people actually use.", "serif", 42, "url(#ink)"))

    # prompt
    px, py, pw, ph = 56, 294, 516, 46
    d.add(f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="12" fill="{t["panel2"]}" stroke="{t["line"]}"/>')
    d.add(d.text(px + 18, py + 29, "›", "monoM", 17, t["v"]))
    lines = [
        "building LLM agents that actually ship",
        "RAG over messy, real-world data",
        "evals first, vibes second",
        "deepfake research, published by Springer",
        "shipping Gleano on the Chrome Web Store",
    ]
    typewriter(d, px + 40, py + 29, lines, size=15.5, fill=t["text"], cursor=t["coral"],
               cover=t["panel2"], cycle=26, cover_w=pw, cover_h=26,
               clip=(px + 1, py + 1, pw - 2, ph - 2, 11))

    # facts
    fx = 56
    for label, col in [("MSc Artificial Intelligence", t["v"]), ("Springer CCIS · AICS 2025", t["c"]),
                       ("Agents · RAG · Evals", t["coral"])]:
        fw = measure(label, "mono", 12) + 36
        d.add(f'<rect x="{num(fx)}" y="362" width="{num(fw)}" height="28" rx="8" fill="{t["panel"]}" '
              f'stroke="{t["line"]}" opacity=".9"/>'
              f'<rect x="{num(fx + 13)}" y="373" width="6" height="6" rx="1.5" fill="{col}"/>')
        d.add(d.text(fx + 27, 380, label, "mono", 12, t["sub"]))
        fx += fw + 10

    # causal self-attention map
    toks = ["<s>", "turn", "models", "into", "real", "products"]
    N, cell, gap = len(toks), 33, 5
    gw = N * cell + (N - 1) * gap
    gx, gy = W - 48 - gw, 128
    d.defn(f'<linearGradient id="att" gradientUnits="userSpaceOnUse" x1="{gx}" y1="{gy}" '
           f'x2="{gx + gw}" y2="{gy + gw}"><stop offset="0" stop-color="{t["v"]}"/>'
           f'<stop offset="1" stop-color="{t["c"]}"/></linearGradient>')
    rng = random.Random(42)
    states = 5
    weights = []  # [state][row][col]
    for _ in range(states):
        rows = []
        for r in range(N):
            logits = [rng.gauss(0, 1.1) + (1.4 if c == r else 0) + (0.6 if c == 0 else 0) for c in range(r + 1)]
            p = softmax(logits)
            mx = max(p)
            rows.append([0.1 + 0.9 * (v / mx) for v in p])
        weights.append(rows)
    cyc = 12
    for r in range(N):
        for c in range(N):
            x = gx + c * (cell + gap)
            y = gy + r * (cell + gap)
            if c > r:
                d.add(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="7" fill="none" '
                      f'stroke="{t["line2"]}" stroke-dasharray="3 4" opacity=".7"/>')
                continue
            name = f"w{r}{c}"
            frames = "".join(f"{pct(k * 100 / states)}{{opacity:{num(weights[k % states][r][c])}}}"
                             for k in range(states + 1))
            d.style(f"@keyframes {name}{{{frames}}}")
            d.add(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="7" fill="{t["panel2"]}"/>'
                  f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="7" fill="url(#att)" '
                  f'style="opacity:{num(weights[0][r][c])};animation:{name} {cyc}s ease-in-out infinite"/>')
    for i, tok in enumerate(toks):
        cy = gy + i * (cell + gap) + cell / 2 + 4
        d.add(d.text(gx - 10, cy, tok, "mono", 11.5, t["muted"], anchor="end"))
        cx = gx + i * (cell + gap) + cell / 2 - 2
        d.add(d.text(cx, gy - 12, tok, "mono", 11.5, t["muted"],
                     extra=f' transform="rotate(-42 {num(cx)} {num(gy - 12)})"'))
    d.add(d.text(gx + gw, gy + gw + 30, "causal self-attention · L12 · H3", "mono", 11, t["muted"], anchor="end"))
    return d


# --------------------------------------------------------------------------
# marquee
# --------------------------------------------------------------------------
PHRASES = ["Retrieval-Augmented Generation", "Agentic Workflows", "LLM Evaluation", "Multimodal AI",
           "Computer Vision", "Fine-tuning", "LLMOps", "Deepfake Detection", "Prompt Engineering"]
MARQUEE_TOOLS = ["claude", "googlegemini", "huggingface", "langchain", "ollama", "pytorch", "tensorflow",
                 "python", "fastapi", "supabase", "postgresql", "docker", "typescript", "nextdotjs",
                 "react", "streamlit", "gradio", "n8n", "githubactions", "vercel", "googlecloud", "opencv"]


def star(cx, cy, r, fill):
    k = r * 0.28
    return (f'<path d="M{num(cx)},{num(cy - r)} Q{num(cx + k)},{num(cy - k)} {num(cx + r)},{num(cy)} '
            f'Q{num(cx + k)},{num(cy + k)} {num(cx)},{num(cy + r)} Q{num(cx - k)},{num(cy + k)} {num(cx - r)},{num(cy)} '
            f'Q{num(cx - k)},{num(cy - k)} {num(cx)},{num(cy - r)} Z" fill="{fill}"/>')


def marquee(theme):
    W, H = 1000, 156
    d = Doc(W, H, theme, "What I work on: RAG, agentic workflows, LLM evaluation, multimodal AI, computer vision",
            "Scrolling ticker of focus areas and the tools I build with.")
    t = d.t
    d.defn('<linearGradient id="edge" x1="0" y1="0" x2="1" y2="0">'
           '<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".09" stop-color="#fff"/>'
           '<stop offset=".91" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
           f'<mask id="fade"><rect width="{W}" height="{H}" fill="url(#edge)"/></mask>')

    # row 1: editorial phrases, alternating solid and outlined
    size, gap = 44, 30
    items, x = [], 0
    for i, ph in enumerate(PHRASES):
        w = measure(ph, "serif", size)
        if i % 2 == 0:
            items.append(d.text(x, 56, ph, "serif", size, t["text"]))
        else:
            items.append(d.text(x, 56, ph, "serif", size, "none",
                                extra=f' stroke="{t["sub"]}" stroke-width="0.9"'))
        x += w + gap
        items.append(star(x, 41, 9, t["v"] if i % 2 else t["c"]))
        x += gap
    w1 = x
    # row 2: tool pills
    pills, x = [], 0
    for slug in MARQUEE_TOOLS:
        name = ICONS[slug]["title"].replace("Google Gemini", "Gemini").replace("Google Cloud", "GCP")
        pw = 18 + 20 + 9 + measure(name, "sansM", 14.5) + 18
        pills.append(f'<rect x="{num(x)}" y="94" width="{num(pw)}" height="42" rx="21" fill="{t["panel"]}" stroke="{t["line"]}"/>'
                     + d.icon(slug, x + 18, 105, 20)
                     + d.text(x + 47, 120, name, "sansM", 14.5, t["sub"]))
        x += pw + 12
    w2 = x

    def row(content, width, dur, reverse):
        reps = max(2, math.ceil(W / width) + 1)
        groups = "".join(f'<g transform="translate({num(k * width)} 0)">{"".join(content)}</g>' for k in range(reps))
        name = f"m{d.uid('r')}"
        frm, to = (f"translateX(-{num(width)}px)", "translateX(0)") if reverse else ("translateX(0)", f"translateX(-{num(width)}px)")
        d.style(f"@keyframes {name}{{from{{transform:{frm}}}to{{transform:{to}}}}}")
        return f'<g style="animation:{name} {num(dur)}s linear infinite">{groups}</g>'

    d.add(f'<g mask="url(#fade)">{row(items, w1, w1 / 38, False)}{row(pills, w2, w2 / 30, True)}</g>')
    return d


# --------------------------------------------------------------------------
# section header
# --------------------------------------------------------------------------
def header(theme, number, title, kicker):
    W, H = 1000, 64
    d = Doc(W, H, theme, f"{number} — {title}")
    t = d.t
    d.add(d.text(0, 42, number, "monoM", 14, t["v"]))
    d.add(d.text(34, 43, title, "sansB", 27, t["text"], ls=-0.6))
    x0 = 34 + measure(title, "sansB", 27, -0.6) + 22
    kw = measure(kicker, "mono", 12.5)
    x1 = W - kw - 18
    d.add(f'<line x1="{num(x0)}" y1="34" x2="{num(x1)}" y2="34" stroke="{t["line2"]}" stroke-dasharray="2 5"/>')
    span = x1 - x0 - 8
    d.style(f".dot{{animation:dot 6s cubic-bezier(.65,0,.35,1) infinite alternate}}"
            f"@keyframes dot{{from{{transform:translateX(0)}}to{{transform:translateX({num(span)}px)}}}}")
    d.add(f'<rect class="dot" x="{num(x0)}" y="31" width="8" height="6" rx="3" fill="{t["coral"]}"/>')
    d.add(d.text(W, 38.5, kicker, "mono", 12.5, t["muted"], anchor="end"))
    return d


# --------------------------------------------------------------------------
# social pills
# --------------------------------------------------------------------------
def pill(theme, label, slug=None, glyph=None):
    t = THEMES[theme]
    w = 16 + 18 + 10 + measure(label, "sansM", 14) + 18
    d = Doc(w, 40, theme, label)
    d.add(f'<rect x=".5" y=".5" width="{num(w - 1)}" height="39" rx="20" fill="{t["panel"]}" stroke="{t["line"]}"/>')
    if slug:
        d.add(d.icon(slug, 16, 11, 18))
    elif glyph == "web":
        c = t["c"]
        d.add(f'<g stroke="{c}" stroke-width="1.6" fill="none"><circle cx="25" cy="20" r="8"/>'
              f'<ellipse cx="25" cy="20" rx="3.6" ry="8"/><path d="M17 20h16"/></g>')
    elif glyph == "in":
        d.add(f'<rect x="16" y="11" width="18" height="18" rx="4" fill="#0A66C2"/>'
              + d.text(19.6, 25.2, "in", "sansB", 12.5, "#fff"))
    d.add(d.text(44, 25, label, "sansM", 14, t["text"]))
    return d


# --------------------------------------------------------------------------
# about: an agent trace
# --------------------------------------------------------------------------
def about(theme):
    W, H = 1000, 472
    d = Doc(W, H, theme, "whoami — an agent trace",
            "GenAI Engineer in Dublin, Ireland. MSc in Artificial Intelligence from National College of Ireland. "
            "Published deepfake-detection research in Springer CCIS vol. 2950 (AICS 2025). Builds Gleano, "
            "AI Broker and cemkoyluoglu.codes. Focus: agents, RAG, evals, LLMOps and multimodal AI.")
    t = d.t
    frame(d, 18, t["panel"])
    d.add(f'<path d="M0.5,46 H{W - 0.5}" stroke="{t["line"]}"/>')
    for i, col in enumerate([t["coral"], t["amber"], t["lime"]]):
        d.add(f'<circle cx="{26 + i * 20}" cy="23" r="6" fill="{col}" opacity=".85"/>')
    d.add(d.text(W / 2, 28, "cem@dublin — ~/agent — zsh", "mono", 12.5, t["muted"], anchor="middle"))

    K, V, M, A = t["text"], t["sub"], t["muted"], t["c"]
    rows = [
        ("cmd", None),
        ("event", ("thinking", M, [("who am I, in one screen?", V)])),
        ("event", ("tool_call", A, [("profile", K), (".load(", M), ('"CemRoot"', t["amber"]), (")", M)])),
        ("kv", ("role", [("GenAI Engineer · Dublin, Ireland", K)])),
        ("kv", ("degree", [("MSc Artificial Intelligence · National College of Ireland", K)])),
        ("kv", ("paper", [("Deepfake detection · Springer CCIS vol. 2950 ", K), ("(AICS 2025)", M)])),
        ("event", ("tool_call", A, [("projects", K), (".shipped(", M), ("top", V), ("=", M), ("3", t["amber"]), (")", M)])),
        ("kv", ("Gleano", [("AI summaries + podcasts for any YouTube video · Chrome Web Store", V)])),
        ("kv", ("AI Broker", [("agentic trading advisor · FastAPI · pgvector · Telegram", V)])),
        ("kv", ("my site", [("cemkoyluoglu.codes — a portfolio that runs agents & RAG 24/7", V)])),
        ("event", ("tool_call", A, [("focus", K), (".now()", M)])),
        ("kv", ("stack", [("agents · RAG · evals · LLMOps · multimodal", K)])),
        ("event", ("answer", t["v"], [("I turn models into products people actually use.", K)])),
        ("meta", None),
    ]
    x0, y0, lh, size = 32, 84, 27.5, 15
    cycle = 20.0
    t_cmd_end = 1.9
    for i, (kind, data) in enumerate(rows):
        y = y0 + i * lh
        if kind == "cmd":
            cmd = "cem --introduce --verbose"
            d.add(d.rich(x0, y, [("$ ", "monoM", t["lime"])], size=size))
            cx = x0 + 2 * 0.6 * size
            L, cw = len(cmd), 0.6 * size
            b = t_cmd_end / cycle * 100
            d.style(f"@keyframes cmdt{{0%,3%{{transform:translateX(0);animation-timing-function:steps({L},end)}}"
                    f"{pct(b)},100%{{transform:translateX({num(L * cw)}px)}}}}"
                    f"@keyframes cmdc{{0%,{pct(b + 2)}{{opacity:1}}{pct(b + 2.1)},100%{{opacity:0}}}}"
                    f"@keyframes outall{{0%,94%{{opacity:1}}98%,100%{{opacity:0}}}}")
            d.add(f'<g style="animation:outall {num(cycle)}s infinite">'
                  + d.text(cx, y, cmd, "mono", size, K)
                  + f'<g style="transform:translateX({num(L * cw)}px);animation:cmdt {num(cycle)}s infinite">'
                  f'<rect x="{num(cx + cw)}" y="{num(y - 16)}" width="420" height="24" fill="{t["panel"]}"/>'
                  f'<rect x="{num(cx + 1)}" y="{num(y - 12.5)}" width="{num(cw - 1)}" height="16" rx="1.5" '
                  f'fill="{t["coral"]}" style="opacity:0;animation:cmdc {num(cycle)}s infinite"/></g></g>')
            continue
        start = (t_cmd_end + 0.35 + (i - 1) * 0.52) / cycle * 100
        name = f"ln{i}"
        d.style(f"@keyframes {name}{{0%,{pct(start)}{{opacity:0;transform:translateY(5px)}}"
                f"{pct(start + 2.2)},94%{{opacity:1;transform:translateY(0)}}98%,100%{{opacity:0}}}}")
        inner = ""
        if kind == "event":
            label, col, parts = data
            inner += f'<circle cx="{x0 + 5}" cy="{num(y - 5)}" r="4" fill="{col}"/>'
            inner += d.rich(x0 + 20, y, [(label.ljust(13), "monoM", col)] + [(s, "mono", c) for s, c in parts], size=size)
        elif kind == "kv":
            k, parts = data
            inner += d.rich(x0 + 20, y, [("↳ ", "mono", t["faint"]), (k.ljust(11), "mono", M)]
                            + [(s, "mono", c) for s, c in parts], size=size)
        elif kind == "meta":
            inner += d.rich(x0 + 20, y, [("└ ", "mono", t["faint"]),
                                         ("142 tokens · 0.41s · stop_reason=", "mono", M),
                                         ("end_turn", "mono", t["lime"])], size=13.5)
            mx = x0 + 20 + 0.6 * 13.5 * len("└ 142 tokens · 0.41s · stop_reason=end_turn") + 8
            d.style(".cur{animation:cur 1.05s steps(1) infinite}@keyframes cur{0%,55%{opacity:1}56%,100%{opacity:0}}")
            inner += f'<rect class="cur" x="{num(mx)}" y="{num(y - 12)}" width="8" height="15" rx="1.5" fill="{t["coral"]}"/>'
        d.add(f'<g style="animation:{name} {num(cycle)}s infinite">{inner}</g>')
    return d


# --------------------------------------------------------------------------
# project cards
# --------------------------------------------------------------------------
PROJECTS = [
    dict(key="gleano", title="Gleano", tag="CHROME EXTENSION", accent="coral", motif="wave",
         desc="Turns any YouTube video or article into a 30-second read: summary, key points, an AI podcast and grounded chat.",
         chips=["Manifest V3", "Gemini TTS", "Groq", "BYOK"]),
    dict(key="deepfake", title="DeepFake Detection", tag="PUBLISHED RESEARCH", accent="v", motif="scan",
         desc="EfficientNet-B7 with a custom attention block that flags GAN- and diffusion-generated images.",
         chips=["TensorFlow", "EfficientNet-B7", "Attention", "Gradio"]),
    dict(key="aibroker", title="AI Broker", tag="AGENTIC SYSTEM", accent="lime", motif="spark",
         desc="A trading advisor that fuses portfolio, technicals, news and RAG memory, then runs a disciplined paper-trading agent.",
         chips=["FastAPI", "Groq + Cerebras", "pgvector", "Telegram"]),
    dict(key="site", title="cemkoyluoglu.codes", tag="LIVE PLATFORM", accent="c", motif="pipe",
         desc="My portfolio is a running system: scrapers, agents that translate and rank tech news, and a RAG chatbot.",
         chips=["React 19", "Supabase", "Gemini + Groq", "n8n"]),
    dict(key="irelandrag", title="Ireland RAG Assistant", tag="RETRIEVAL", accent="v", motif="knn",
         desc="Answers expat questions on visas, tax and housing in Ireland, grounded in official government documents.",
         chips=["Next.js", "LlamaParse", "Pinecone", "TypeScript"]),
    dict(key="daft", title="Daft.ie Dublin Monitor", tag="AUTOMATION", accent="amber", motif="radar",
         desc="Watches Dublin rental listings around the clock and pings Telegram the moment a match appears.",
         chips=["Python", "GitHub Actions", "Render", "Telegram Bot"]),
]


def motif_wave(d, t, acc):
    rng = random.Random(3)
    d.defn(f'<linearGradient id="wf" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t[acc]}"/>'
           f'<stop offset="1" stop-color="{t["v"]}"/></linearGradient>')
    d.style(".bar{transform-box:fill-box;transform-origin:center;animation:bar ease-in-out infinite alternate}"
            "@keyframes bar{from{transform:scaleY(.18)}to{transform:scaleY(1)}}")
    out, n = [], 46
    for i in range(n):
        x = 26 + i * 9.4
        env = math.sin(math.pi * (i + 0.5) / n) ** 0.7
        h = 16 + env * 58 * rng.uniform(0.55, 1)
        out.append(f'<rect class="bar" x="{num(x)}" y="{num(52 - h / 2)}" width="5" height="{num(h)}" rx="2.5" '
                   f'fill="url(#wf)" style="animation-duration:{num(rng.uniform(.55, 1.1))}s;'
                   f'animation-delay:{num(-rng.uniform(0, 1.2))}s"/>')
    return "".join(out)


def motif_scan(d, t, acc):
    rng = random.Random(9)
    cols, rows, cell, pitch = 33, 6, 10, 13
    x0, y0 = 26, 14
    dur = 3.6
    d.defn(f'<linearGradient id="beam" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t[acc]}" stop-opacity="0"/>'
           f'<stop offset=".85" stop-color="{t[acc]}" stop-opacity=".35"/><stop offset="1" stop-color="{t[acc]}" stop-opacity=".9"/></linearGradient>')
    d.style(f".px{{animation:px {dur}s linear infinite}}@keyframes px{{0%{{opacity:.95}}30%,100%{{opacity:.12}}}}"
            f".beam{{animation:beam {dur}s linear infinite}}@keyframes beam{{from{{transform:translateX(-70px)}}to{{transform:translateX(480px)}}}}")
    out = []
    for r in range(rows):
        for c in range(cols):
            x, y = x0 + c * pitch, y0 + r * pitch
            fake = (c - 23) ** 2 / 30 + (r - 2.5) ** 2 / 5 < 1 + rng.uniform(-.25, .25)
            col = t["coral"] if fake else t["c"]
            delay = -(dur - (x + 70) / 550 * dur)
            out.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{t["line"]}"/>'
                       f'<rect class="px" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{col}" '
                       f'style="animation-delay:{num(delay)}s"/>')
    out.append(f'<rect class="beam" x="0" y="0" width="70" height="104" fill="url(#beam)"/>')
    return "".join(out)


def motif_spark(d, t, acc):
    rng = random.Random(21)
    pts, v = [], 0.0
    for i in range(64):
        v += rng.gauss(0.12, 1.0)
        pts.append(v)
    lo, hi = min(pts), max(pts)
    xy = [(26 + i * (428 / 63), 78 - (p - lo) / (hi - lo) * 46) for i, p in enumerate(pts)]
    path = "M" + " L".join(f"{num(x)},{num(y)}" for x, y in xy)
    area = path + f" L{num(xy[-1][0])},100 L26,100 Z"
    d.defn(f'<linearGradient id="sl" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t["c"]}"/>'
           f'<stop offset="1" stop-color="{t[acc]}"/></linearGradient>'
           f'<linearGradient id="sa" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t[acc]}" stop-opacity=".22"/>'
           f'<stop offset="1" stop-color="{t[acc]}" stop-opacity="0"/></linearGradient>')
    d.style(".draw{stroke-dasharray:1;animation:draw 7s linear infinite}"
            "@keyframes draw{0%{stroke-dashoffset:1}45%,90%{stroke-dashoffset:0}100%{stroke-dashoffset:0;opacity:0}}"
            ".area{animation:area 7s ease infinite}@keyframes area{0%,30%{opacity:0}50%,90%{opacity:1}100%{opacity:0}}")
    out = [f'<path d="M26,{y} H454" stroke="{t["line"]}" stroke-dasharray="2 4"/>' for y in (30, 56, 82)]
    out.append(f'<path class="area" d="{area}" fill="url(#sa)"/>')
    out.append(f'<path class="draw" d="{path}" pathLength="1" stroke="url(#sl)" stroke-width="2.2" '
               f'stroke-linejoin="round" stroke-linecap="round" fill="none"/>')
    # buy at the global dip, sell at the later peak
    i_lo = min(range(10, 40), key=lambda i: pts[i])
    i_hi = max(range(i_lo + 5, 64), key=lambda i: pts[i])
    for i, lab, col, up in [(i_lo, "buy", t["lime"], True), (i_hi, "sell", t["coral"], False)]:
        x, y = xy[i]
        at = 45 * (i / 63)
        n = f"mk{i}"
        d.style(f"@keyframes {n}{{0%,{pct(at)}{{opacity:0}}{pct(at + 4)},90%{{opacity:1}}100%{{opacity:0}}}}")
        tri = (f"M{num(x)},{num(y + 7)} l5,8 h-10 Z" if up else f"M{num(x)},{num(y - 7)} l5,-8 h-10 Z")
        lab_xy = (x + 9, y + 18, "start") if up else (x - 9, y - 9, "end")
        out.append(f'<g style="animation:{n} 7s infinite"><path d="{tri}" fill="{col}"/>'
                   + d.text(lab_xy[0], lab_xy[1], lab, "mono", 10.5, col, anchor=lab_xy[2]) + "</g>")
    return "".join(out)


def motif_pipe(d, t, acc):
    stages = ["scrape", "rank", "translate", "publish"]
    widths = [measure(s, "mono", 12) + 26 for s in stages]
    gap = (428 - sum(widths)) / (len(stages) - 1)
    x, out, centers = 26, [], []
    dur = 4.0
    d.style(f".node{{animation:node {dur}s ease-in-out infinite}}"
            f"@keyframes node{{0%,100%{{opacity:0}}8%,22%{{opacity:1}}34%{{opacity:0}}}}"
            f".pk{{animation:pk {dur / 4}s linear infinite}}")
    for i, (s, w) in enumerate(zip(stages, widths)):
        centers.append((x, x + w))
        out.append(f'<rect x="{num(x)}" y="38" width="{num(w)}" height="30" rx="15" fill="{t["panel"]}" stroke="{t["line2"]}"/>'
                   f'<rect class="node" x="{num(x)}" y="38" width="{num(w)}" height="30" rx="15" fill="none" '
                   f'stroke="{t[acc]}" stroke-width="1.6" style="animation-delay:{num(i * dur / 4 - dur)}s"/>'
                   + d.text(x + w / 2, 57.5, s, "mono", 12, t["sub"], anchor="middle"))
        x += w + gap
    for i in range(len(stages) - 1):
        a, b = centers[i][1], centers[i + 1][0]
        out.append(f'<path d="M{num(a + 4)},53 H{num(b - 4)}" stroke="{t["line2"]}" stroke-dasharray="2 3"/>')
        span = b - a - 14
        n = f"pk{i}"
        d.style(f"@keyframes {n}{{from{{transform:translateX(0);opacity:0}}15%{{opacity:1}}85%{{opacity:1}}"
                f"to{{transform:translateX({num(span)}px);opacity:0}}}}")
        for k in range(2):
            out.append(f'<circle cx="{num(a + 7)}" cy="53" r="2.6" fill="{t[acc]}" '
                       f'style="animation:{n} {num(dur / 2)}s linear infinite;animation-delay:{num(-k * dur / 4 - i * .3)}s"/>')
    out.append(d.text(26, 24, "cron · every 30 min", "mono", 10.5, t["muted"]))
    out.append(d.text(454, 92, "→ telegram · supabase · site", "mono", 10.5, t["muted"], anchor="end"))
    return "".join(out)


def motif_knn(d, t, acc):
    rng = random.Random(5)
    q = (250, 54)
    pts = []
    while len(pts) < 46:
        p = (rng.uniform(30, 410), rng.uniform(14, 92))
        if math.dist(p, q) > 16:
            pts.append(p)
    near = sorted(range(len(pts)), key=lambda i: math.dist(pts[i], q))[:3]
    dur = 4.5
    d.style(f".ln{{stroke-dasharray:1;animation:ln {dur}s ease infinite}}"
            f"@keyframes ln{{0%,20%{{stroke-dashoffset:1}}45%,85%{{stroke-dashoffset:0}}100%{{stroke-dashoffset:0;opacity:0}}}}"
            f".hi{{animation:hi {dur}s ease infinite}}@keyframes hi{{0%,38%{{opacity:0}}50%,88%{{opacity:1}}100%{{opacity:0}}}}"
            f".ring{{transform-box:fill-box;transform-origin:center;animation:ring 1.8s ease-out infinite}}"
            f"@keyframes ring{{from{{transform:scale(1);opacity:.8}}to{{transform:scale(3.4);opacity:0}}}}")
    out = []
    for i, (x, y) in enumerate(pts):
        out.append(f'<circle cx="{num(x)}" cy="{num(y)}" r="2.6" fill="{t["faint"]}"/>')
    for i in near:
        x, y = pts[i]
        out.append(f'<path class="ln" pathLength="1" d="M{q[0]},{q[1]} L{num(x)},{num(y)}" stroke="{t[acc]}" stroke-width="1.4"/>')
        out.append(f'<circle class="hi" cx="{num(x)}" cy="{num(y)}" r="4.2" fill="{t["c"]}"/>')
    out.append(f'<circle class="ring" cx="{q[0]}" cy="{q[1]}" r="5" fill="none" stroke="{t["coral"]}" stroke-width="1.5"/>'
               f'<circle cx="{q[0]}" cy="{q[1]}" r="5" fill="{t["coral"]}"/>')
    out.append(d.text(q[0] + 12, q[1] - 10, "query", "mono", 10.5, t["coral"]))
    out.append(d.text(454, 92, "top_k = 3 · cosine", "mono", 10.5, t["muted"], anchor="end"))
    return "".join(out)


def motif_radar(d, t, acc):
    cx, cy, R = 78, 52, 42
    dur = 4.0
    d.defn(f'<linearGradient id="sw" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t[acc]}" stop-opacity=".55"/>'
           f'<stop offset="1" stop-color="{t[acc]}" stop-opacity="0"/></linearGradient>')
    d.style(f".sweep{{transform-origin:{cx}px {cy}px;animation:sweep {dur}s linear infinite}}"
            f"@keyframes sweep{{from{{transform:rotate(0)}}to{{transform:rotate(360deg)}}}}"
            f".blip{{animation:blip {dur}s ease-out infinite}}@keyframes blip{{0%{{opacity:1}}40%,100%{{opacity:.08}}}}"
            f".toast{{animation:toast {dur * 2}s cubic-bezier(.2,.8,.2,1) infinite}}"
            f"@keyframes toast{{0%,8%{{opacity:0;transform:translateY(10px)}}16%,88%{{opacity:1;transform:translateY(0)}}96%,100%{{opacity:0;transform:translateY(-4px)}}}}")
    out = [f'<circle cx="{cx}" cy="{cy}" r="{r}" stroke="{t["line2"]}" fill="none"/>' for r in (14, 28, R)]
    out.append(f'<path d="M{cx - R},{cy} H{cx + R} M{cx},{cy - R} V{cy + R}" stroke="{t["line"]}"/>')
    a = math.radians(55)
    out.append(f'<path class="sweep" d="M{cx},{cy} L{cx + R},{cy} A{R},{R} 0 0 1 {num(cx + R * math.cos(a))},{num(cy + R * math.sin(a))} Z" '
               f'fill="url(#sw)"/>')
    for ang, rr in [(30, 30), (140, 22), (250, 36), (320, 17)]:
        x = cx + rr * math.cos(math.radians(ang))
        y = cy + rr * math.sin(math.radians(ang))
        delay = -(dur - ang / 360 * dur)
        out.append(f'<circle class="blip" cx="{num(x)}" cy="{num(y)}" r="3" fill="{t[acc]}" style="animation-delay:{num(delay)}s"/>')
    # telegram toast
    tx, ty, tw, th = 152, 24, 300, 58
    out.append(f'<g class="toast"><rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="12" fill="{t["panel"]}" stroke="{t["line2"]}"/>'
               + d.icon("telegram", tx + 14, ty + 17, 24)
               + d.text(tx + 50, ty + 25, "New listing · Dublin 8", "sansM", 13.5, t["text"])
               + d.text(tx + 50, ty + 44, "€1,950 / mo · matched 3 filters", "mono", 11, t["muted"])
               + d.text(tx + tw - 14, ty + 25, "now", "mono", 10.5, t["muted"], anchor="end")
               + "</g>")
    return "".join(out)


MOTIFS = dict(wave=motif_wave, scan=motif_scan, spark=motif_spark, pipe=motif_pipe, knn=motif_knn, radar=motif_radar)


def card(theme, p, idx):
    W, H = 480, 300
    d = Doc(W, H, theme, f"{p['title']} — {p['tag'].title()}", p["desc"])
    t = d.t
    acc = p["accent"]
    frame(d, 18, t["panel"])
    d.defn(f'<clipPath id="band"><path d="M0.5,104 V18.5 A18,18 0 0 1 18.5,0.5 H{W - 18.5} A18,18 0 0 1 {W - 0.5},18.5 V104 Z"/></clipPath>')
    d.add(f'<g clip-path="url(#band)"><rect width="{W}" height="104" fill="{t["panel2"]}"/>'
          f'{MOTIFS[p["motif"]](d, t, acc)}</g>')
    d.add(f'<path d="M0.5,104 H{W - 0.5}" stroke="{t["line"]}"/>')
    # label + title
    d.add(f'<rect x="26" y="128" width="7" height="7" rx="1.5" fill="{t[acc]}"/>')
    d.add(d.text(41, 135.5, p["tag"], "monoM", 11, t[acc], ls=1.3))
    d.add(d.text(25, 168, p["title"], "sansB", 24, t["text"], ls=-0.5))
    # arrow
    d.add(f'<circle cx="{W - 38}" cy="160" r="16" fill="{t["panel2"]}" stroke="{t["line"]}"/>'
          f'<path d="M{W - 43},165 L{W - 33},155 M{W - 41},155 H{W - 33} V163" stroke="{t["sub"]}" '
          f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" fill="none"/>')
    for k, line in enumerate(wrap(p["desc"], "sans", 15, W - 52)[:2]):
        d.add(d.text(26, 197 + k * 22, line, "sans", 15, t["sub"]))
    x = 26
    for chip in p["chips"]:
        cw = measure(chip, "mono", 11.5) + 20
        d.add(f'<rect x="{num(x)}" y="250" width="{num(cw)}" height="26" rx="7" fill="{t["panel2"]}" stroke="{t["line"]}"/>')
        d.add(d.text(x + 10, 267, chip, "mono", 11.5, t["sub"]))
        x += cw + 8
    comet(d, 0.5, 0.5, W - 1, H - 1, 18, (t[acc], t["v"]), dur=9, delay=idx * 1.7)
    return d


# --------------------------------------------------------------------------
# research
# --------------------------------------------------------------------------
def research(theme):
    W, H = 1000, 300
    title = "A Novel Deep Learning Framework for DeepFake Detection Using Attention-Enhanced EfficientNet-B7"
    d = Doc(W, H, theme, "Published research — " + title,
            "Koyluoglu, E.C., Staikopoulos, A., Raj, K. (2026). AICS 2025, Communications in Computer and "
            "Information Science vol. 2950, Springer, pp. 401–413. DOI 10.1007/978-3-032-25809-0_32")
    t = d.t
    frame(d, 20, t["panel"])
    vx, vy, vw, vh = 26, 26, 340, 248
    d.add(f'<rect x="{vx}" y="{vy}" width="{vw}" height="{vh}" rx="14" fill="{t["panel2"]}" stroke="{t["line"]}"/>')
    tile, gap = 92, 12
    gx = vx + (vw - (3 * tile + 2 * gap)) / 2
    gy = vy + 18
    hues = [("#6D5BD0", "#2B8FB8"), ("#C2556A", "#7A4FC2"), ("#2E9C8F", "#3D6FD1"),
            ("#B07A3A", "#9C4E7E"), ("#4A6FD8", "#2AA7A0"), ("#8D5AC9", "#D06B5B")]
    verdict = [("REAL", .98), ("FAKE", .94), ("REAL", .97), ("REAL", .99), ("FAKE", .91), ("REAL", .96)]
    dur = 6.0
    d.style(f".lab{{animation:lab {dur}s ease infinite}}"
            f".heat{{animation:heat {dur}s ease infinite}}"
            f".scanr{{animation:scanr {dur}s cubic-bezier(.45,0,.55,1) infinite}}"
            f"@keyframes scanr{{0%{{transform:translateX(0);opacity:0}}5%{{opacity:1}}55%{{transform:translateX({num(3 * tile + 2 * gap + 10)}px);opacity:1}}60%,100%{{transform:translateX({num(3 * tile + 2 * gap + 10)}px);opacity:0}}}}")
    for i in range(6):
        r, c = divmod(i, 3)
        x, y = gx + c * (tile + gap), gy + r * (tile + gap)
        a, b = hues[i]
        gid = f"tg{i}"
        d.defn(f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{a}"/>'
               f'<stop offset="1" stop-color="{b}"/></linearGradient>'
               f'<clipPath id="tc{i}"><rect x="{num(x)}" y="{num(y)}" width="{tile}" height="{tile}" rx="10"/></clipPath>')
        lab, conf = verdict[i]
        col = t["coral"] if lab == "FAKE" else t["c"]
        at = 5 + (c + 0.6) / 3 * 50
        d.style(f"@keyframes l{i}{{0%,{pct(at)}{{opacity:0}}{pct(at + 4)},92%{{opacity:1}}100%{{opacity:0}}}}")
        body = (f'<g clip-path="url(#tc{i})"><rect x="{num(x)}" y="{num(y)}" width="{tile}" height="{tile}" fill="url(#{gid})" opacity=".85"/>'
                f'<circle cx="{num(x + tile / 2)}" cy="{num(y + 38)}" r="17" fill="#fff" opacity=".28"/>'
                f'<ellipse cx="{num(x + tile / 2)}" cy="{num(y + 96)}" rx="34" ry="30" fill="#fff" opacity=".22"/>')
        if lab == "FAKE":
            hg = f"hg{i}"
            d.defn(f'<radialGradient id="{hg}"><stop offset="0" stop-color="{t["coral"]}" stop-opacity=".95"/>'
                   f'<stop offset="1" stop-color="{t["coral"]}" stop-opacity="0"/></radialGradient>')
            body += (f'<circle cx="{num(x + tile / 2 + 6)}" cy="{num(y + 36)}" r="30" fill="url(#{hg})" '
                     f'style="animation:l{i} {dur}s ease infinite"/>')
        body += "</g>"
        lw = measure(f"{lab} {conf:.2f}", "monoM", 10) + 12
        body += (f'<g style="animation:l{i} {dur}s ease infinite">'
                 f'<rect x="{num(x + 6)}" y="{num(y + tile - 24)}" width="{num(lw)}" height="18" rx="5" fill="{t["panel"]}" opacity=".94"/>'
                 + d.rich(x + 12, y + tile - 11.5, [(lab + " ", "monoM", col), (f"{conf:.2f}", "mono", t["sub"])], size=10)
                 + "</g>")
        d.add(body)
    d.defn(f'<linearGradient id="beam" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{t["c"]}" stop-opacity="0"/>'
           f'<stop offset="1" stop-color="{t["c"]}" stop-opacity=".55"/></linearGradient>')
    d.defn(f'<clipPath id="vis"><rect x="{vx}" y="{vy}" width="{vw}" height="{vh}" rx="14"/></clipPath>')
    d.add(f'<g clip-path="url(#vis)"><g class="scanr"><rect x="{num(gx - 24)}" y="{num(gy - 6)}" width="24" height="{num(2 * tile + gap + 12)}" fill="url(#beam)"/>'
          f'<rect x="{num(gx - 1)}" y="{num(gy - 6)}" width="2" height="{num(2 * tile + gap + 12)}" fill="{t["c"]}"/></g></g>')
    d.add(d.text(vx + vw / 2, vy + vh - 18, "real vs. generated · attention overlay", "mono", 11, t["muted"], anchor="middle"))

    tx = 400
    d.add(d.text(tx, 62, "PEER-REVIEWED  ·  SPRINGER NATURE  ·  2026", "monoM", 12, t["v"], ls=1.3))
    lines = wrap(title, "sansB", 25, W - tx - 36)
    for k, line in enumerate(lines):
        d.add(d.text(tx, 102 + k * 33, line, "sansB", 25, t["text"], ls=-0.4))
    y = 102 + len(lines) * 33 + 8
    d.add(d.rich(tx, y, [("E. C. Koyluoglu", "sansM", t["text"]), (", A. Staikopoulos, K. Raj", "sans", t["sub"])], size=15.5))
    d.add(d.text(tx, y + 26, "AICS 2025 · Springer CCIS vol. 2950 · pp. 401–413",
                 "mono", 11.5, t["muted"]))
    doi = "doi:10.1007/978-3-032-25809-0_32"
    dw = measure(doi, "mono", 12) + 44
    d.add(f'<rect x="{tx}" y="{num(H - 62)}" width="{num(dw)}" height="32" rx="9" fill="{t["panel2"]}" stroke="{t["line"]}"/>')
    d.add(d.text(tx + 14, H - 41, doi, "mono", 12, t["sub"]))
    d.add(d.text(tx + dw - 16, H - 41, "↗", "mono", 12, t["v"], anchor="end"))
    comet(d, 0.5, 0.5, W - 1, H - 1, 20, (t["v"], t["c"]), dur=12)
    return d


# --------------------------------------------------------------------------
# toolbox
# --------------------------------------------------------------------------
STACK = [
    ("LLMs & Agents", "v", ["claude", "googlegemini", "huggingface", "langchain", "ollama", "n8n"]),
    ("Deep Learning & CV", "coral", ["pytorch", "tensorflow", "keras", "scikitlearn", "opencv", "nvidia"]),
    ("Data & Retrieval", "c", ["postgresql", "supabase", "pandas", "numpy", "apachekafka", "jupyter"]),
    ("Backend & APIs", "lime", ["python", "fastapi", "django", "flask", "nodedotjs", "telegram"]),
    ("Product & Frontend", "amber", ["typescript", "react", "nextdotjs", "tailwindcss", "streamlit", "gradio"]),
    ("Cloud & Ops", "v", ["docker", "githubactions", "vercel", "googlecloud", "cloudflare", "sentry"]),
]
SHORT = {"Google Gemini": "Gemini", "Google Cloud": "Google Cloud", "Apache Kafka": "Kafka",
         "Node.js": "Node.js", "Tailwind CSS": "Tailwind", "scikit-learn": "scikit-learn"}


def toolbox(theme):
    W, gap = 1000, 14
    tw = (W - 2 * gap) / 3
    th = 176
    H = 2 * th + gap
    d = Doc(W, H, theme, "Toolbox",
            "; ".join(f"{name}: " + ", ".join(ICONS[s]["title"] for s in slugs) for name, _, slugs in STACK))
    t = d.t
    for i, (name, acc, slugs) in enumerate(STACK):
        r, c = divmod(i, 3)
        x, y = c * (tw + gap), r * (th + gap)
        d.add(f'<rect x="{num(x + .5)}" y="{num(y + .5)}" width="{num(tw - 1)}" height="{th - 1}" rx="16" '
              f'fill="{t["panel"]}" stroke="{t["line"]}"/>')
        d.add(d.text(x + 22, y + 36, f"0{i + 1}", "monoM", 11.5, t[acc]))
        d.add(d.text(x + 46, y + 37, name, "sansB", 16.5, t["text"], ls=-0.2))
        d.add(f'<path d="M{num(x + 22)},{y + 54} H{num(x + tw - 22)}" stroke="{t["line"]}"/>')
        for k, slug in enumerate(slugs):
            rr, cc = divmod(k, 2)
            ix = x + 22 + cc * (tw - 44) / 2
            iy = y + 76 + rr * 34
            label = SHORT.get(ICONS[slug]["title"], ICONS[slug]["title"])
            d.add(d.icon(slug, ix, iy - 14, 19))
            d.add(d.text(ix + 29, iy, label, "sansM", 14, t["sub"]))
    return d


# --------------------------------------------------------------------------
# activity (data refreshed daily by .github/workflows/profile-assets.yml)
# --------------------------------------------------------------------------
def streaks(days):
    counts = [c for _, c in days]
    longest = cur = 0
    for c in counts:
        cur = cur + 1 if c > 0 else 0
        longest = max(longest, cur)
    current = 0
    idx = len(counts) - 1
    if idx >= 0 and counts[idx] == 0:  # today may simply not have started yet
        idx -= 1
    while idx >= 0 and counts[idx] > 0:
        current += 1
        idx -= 1
    return current, longest


def activity(theme):
    W, H = 1000, 268
    data = json.loads(STATS.read_text()) if STATS.exists() else None
    d = Doc(W, H, theme, "GitHub activity over the last 12 months",
            "Contribution heatmap and totals, regenerated daily by a GitHub Action.")
    t = d.t
    frame(d, 20, t["panel"])
    lx = 32
    hx, hy, cell, pitch = 358, 58, 9.6, 11.6

    if not data:
        d.add(d.text(lx, 70, "ACTIVITY", "monoM", 12, t["v"], ls=1.3))
        d.add(d.text(lx, 128, "syncing…", "sansB", 44, t["text"], ls=-1.2))
        d.add(d.text(lx, 160, "first refresh runs on the next push", "sans", 15, t["sub"]))
        for wk in range(53):
            for dy in range(7):
                d.add(f'<rect x="{num(hx + wk * pitch)}" y="{num(hy + dy * pitch)}" width="{cell}" height="{cell}" '
                      f'rx="2.4" fill="{t["panel2"]}"/>')
        return d

    days = [(x["date"], x["count"]) for x in data["days"]]
    total = data["total"]
    current, longest = streaks(days)
    d.add(d.text(lx, 70, "LAST 12 MONTHS", "monoM", 12, t["v"], ls=1.3))
    d.add(d.text(lx - 2, 126, f"{total:,}", "sansB", 58, t["text"], ls=-2))
    d.add(d.text(lx, 152, "contributions on GitHub", "sans", 15, t["sub"]))
    stats = [(f"{current}d", "current streak"), (f"{longest}d", "longest streak"),
             (str(data.get("repos", "—")), "public repos"), (str(data.get("stars", "—")), "stars earned")]
    for i, (v, k) in enumerate(stats):
        sx = lx + (i % 2) * 150
        sy = 190 + (i // 2) * 42
        d.add(d.text(sx, sy, v, "sansB", 19, t["text"]))
        d.add(d.text(sx, sy + 17, k, "mono", 11, t["muted"]))

    # heatmap, aligned so each column is a Sunday-start week
    first = dt.date.fromisoformat(days[0][0])
    pad = (first.weekday() + 1) % 7
    peak = max((c for _, c in days), default=0) or 1
    ramp = [t["panel2"], t["v"], t["v"], t["c"], t["c"]]
    ops = [1, .35, .7, .75, 1]
    d.style(".wk{animation:wk .6s ease both}@keyframes wk{from{opacity:0;transform:translateY(4px)}}")
    months, cols = [], {}
    for i, (ds, c) in enumerate(days):
        k = i + pad
        wk, dy = divmod(k, 7)
        cols.setdefault(wk, []).append((dy, c, ds))
    for wk, cells in sorted(cols.items()):
        parts = []
        for dy, c, ds in cells:
            lvl = 0 if c == 0 else min(4, 1 + int(3 * c / peak + 0.25))
            parts.append(f'<rect x="{num(hx + wk * pitch)}" y="{num(hy + dy * pitch)}" width="{cell}" height="{cell}" '
                         f'rx="2.4" fill="{ramp[lvl]}" opacity="{ops[lvl]}"/>')
            day = dt.date.fromisoformat(ds)
            if day.day == 1:
                months.append((wk, day.strftime("%b")))
        d.add(f'<g class="wk" style="animation-delay:{num(wk * 0.025)}s">{"".join(parts)}</g>')
    last = -9
    for wk, m in months:
        if wk - last < 3 or wk > 50:
            continue
        last = wk
        d.add(d.text(hx + wk * pitch, hy - 12, m, "mono", 10.5, t["muted"]))
    for dy, lab in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        d.add(d.text(hx - 8, hy + dy * pitch + 8.5, lab, "mono", 10, t["muted"], anchor="end"))
    # legend + timestamp
    ly = hy + 7 * pitch + 22
    d.add(d.text(hx, ly + 9, f"updated {data.get('updated', '')[:10]} · auto-refreshed daily", "mono", 10.5, t["muted"]))
    lx2 = hx + 53 * pitch - 5 * 14 - 44
    d.add(d.text(lx2 - 8, ly + 9, "less", "mono", 10.5, t["muted"], anchor="end"))
    for i in range(5):
        d.add(f'<rect x="{num(lx2 + i * 14)}" y="{num(ly)}" width="{cell}" height="{cell}" rx="2.4" fill="{ramp[i]}" opacity="{ops[i]}"/>')
    d.add(d.text(lx2 + 5 * 14 + 4, ly + 9, "more", "mono", 10.5, t["muted"]))
    return d


# --------------------------------------------------------------------------
# footer: a tokenizer view
# --------------------------------------------------------------------------
def footer(theme):
    W, H = 1000, 150
    toks = ["Thanks", " for", " scrolling", " —", " let", "'s", " build", " something", " that", " ships", "."]
    d = Doc(W, H, theme, "Thanks for scrolling — let's build something that ships.")
    t = d.t
    size = 30
    pal = [t["v"], t["c"], t["coral"], t["lime"], t["amber"]]
    widths = [measure(s, "sansM", size) + 4 for s in toks]
    total = sum(widths) + 2 * (len(toks) - 1)
    x = (W - total) / 2
    cycle = 9.0
    for i, (tok, w) in enumerate(zip(toks, widths)):
        at = 4 + i * 4.2
        n = f"tk{i}"
        d.style(f"@keyframes {n}{{0%,{pct(at)}{{opacity:0;transform:translateY(6px)}}{pct(at + 3)},90%{{opacity:1;transform:translateY(0)}}97%,100%{{opacity:0}}}}")
        col = pal[i % len(pal)]
        d.add(f'<g style="animation:{n} {num(cycle)}s ease infinite">'
              f'<rect x="{num(x)}" y="34" width="{num(w)}" height="46" rx="8" fill="{col}" opacity="{.16 if theme == "dark" else .13}"/>'
              f'<rect x="{num(x)}" y="77" width="{num(w)}" height="3" rx="1.5" fill="{col}" opacity=".7"/>'
              + d.text(x + 2, 67, tok, "sansM", size, t["text"]) + "</g>")
        x += w + 2
    d.add(d.text(W / 2, 118, "11 tokens · generated one at a time · temperature 0.7", "mono", 12, t["muted"], anchor="middle"))
    return d


# --------------------------------------------------------------------------
def build(only=None):
    OUT.mkdir(exist_ok=True)
    jobs = {
        "hero": hero, "marquee": marquee, "about": about, "research": research,
        "toolbox": toolbox, "activity": activity, "footer": footer,
    }
    for i, p in enumerate(PROJECTS):
        jobs[f"card-{p['key']}"] = (lambda th, p=p, i=i: card(th, p, i))
    for num_, title, kicker in [("01", "whoami", "agent.run(\"introduce\")"),
                                ("02", "Selected work", "shipped, not just demoed"),
                                ("03", "Research", "peer-reviewed"),
                                ("04", "Toolbox", "what I reach for"),
                                ("05", "Activity", "refreshed daily")]:
        slug = title.lower().replace(" ", "-")
        jobs[f"h-{slug}"] = (lambda th, a=num_, b=title, c=kicker: header(th, a, b, c))
    for key, label, slug, glyph in [("site", "cemkoyluoglu.codes", None, "web"),
                                    ("linkedin", "LinkedIn", None, "in"),
                                    ("x", "@Cockroachs_", "x", None),
                                    ("hf", "Hugging Face", "huggingface", None),
                                    ("orcid", "ORCID", "orcid", None)]:
        jobs[f"pill-{key}"] = (lambda th, a=label, b=slug, c=glyph: pill(th, a, b, c))

    for name, fn in jobs.items():
        if only and not any(name == o or name.startswith(o + "-") for o in only):
            continue
        for theme in THEMES:
            svg = fn(theme).render()
            path = OUT / f"{name}-{theme}.svg"
            path.write_text(svg)
            print(f"{path.relative_to(ROOT)}  {len(svg) / 1024:.0f} KB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="asset names (or prefixes like 'card') to build")
    build(ap.parse_args().only)
