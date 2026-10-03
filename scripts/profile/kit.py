"""Tiny SVG toolkit for the profile assets.

Every SVG is self-contained: fonts are subset to the exact glyphs a file uses
and embedded as WOFF2, so the art renders identically through GitHub's image
proxy (which blocks external requests) on every OS. Animations are CSS only and
switch off under `prefers-reduced-motion`; every element's resting style is
its final, readable state, so a still frame never hides content.
"""
from __future__ import annotations

import base64
import io
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from functools import lru_cache
from html import escape
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
FONT_DIR = HERE / "fonts"

# key -> (css family, file)
FONTS = {
    "sans": ("pf-sans", "Geist-Regular.woff2"),
    "sansM": ("pf-sans-m", "Geist-Medium.woff2"),
    "sansB": ("pf-sans-b", "Geist-SemiBold.woff2"),
    "mono": ("pf-mono", "GeistMono-Regular.woff2"),
    "monoM": ("pf-mono-m", "GeistMono-Medium.woff2"),
    "serif": ("pf-serif", "InstrumentSerif-Italic.woff2"),
}
FALLBACK = {
    "sans": "ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif",
    "mono": "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace",
    "serif": "Georgia,'Times New Roman',serif",
}

THEMES = {
    "dark": dict(
        bg="#0A0B10", panel="#0E1017", panel2="#141722", line="#232838",
        line2="#30364A", text="#ECEEF5", sub="#A9AFC4", muted="#6E748C",
        faint="#3A4058", v="#8D6BFF", c="#2DD4EF", coral="#FF6B5B",
        lime="#B5F26B", amber="#FFC15E", glow=0.42,
    ),
    "light": dict(
        bg="#FBFAF7", panel="#FFFFFF", panel2="#F4F3EE", line="#E5E2D9",
        line2="#D3CFC3", text="#14151C", sub="#464B5D", muted="#6E7385",
        faint="#C4C0B4", v="#5B3DF5", c="#0A8DB0", coral="#E5484D",
        lime="#3F7A0C", amber="#B7791F", glow=0.20,
    ),
}


class Font:
    def __init__(self, key: str):
        self.key = key
        self.family, fname = FONTS[key]
        self.path = FONT_DIR / fname
        self.tt = TTFont(self.path)
        self.cmap = self.tt.getBestCmap()
        self.hmtx = self.tt["hmtx"]
        self.upm = self.tt["head"].unitsPerEm

    def width(self, s: str, size: float, ls: float = 0.0) -> float:
        total = 0
        for ch in s:
            g = self.cmap.get(ord(ch)) or self.cmap.get(ord("?"))
            total += self.hmtx[g][0]
        return total * size / self.upm + ls * len(s)

    def has(self, ch: str) -> bool:
        return ord(ch) in self.cmap


@lru_cache(maxsize=None)
def font(key: str) -> Font:
    return Font(key)


def measure(s: str, key: str, size: float, ls: float = 0.0) -> float:
    return font(key).width(s, size, ls)


def wrap(s: str, key: str, size: float, max_w: float) -> list[str]:
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if cur and measure(trial, key, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


@lru_cache(maxsize=None)
def _subset_b64(key: str, chars: str) -> str:
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga", "calt"]
    opts.hinting = False
    opts.desubroutinize = True
    opts.name_IDs = []
    opts.notdef_outline = True
    opts.drop_tables += ["meta"]
    tt = TTFont(font(key).path)
    sub = subset.Subsetter(opts)
    sub.populate(unicodes={ord(c) for c in chars})
    sub.subset(tt)
    buf = io.BytesIO()
    tt.flavor = "woff2"
    tt.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


ICONS = json.loads((HERE / "data" / "icons.json").read_text())


# Tools with no Simple Icons glyph get a monogram tile instead: slug -> (title, initials).
MONOGRAMS = {
    "openai": ("OpenAI", "AI"),
    "groq": ("Groq", "gq"),
    "llamaindex": ("LlamaIndex", "LI"),
    "pinecone": ("Pinecone", "Pc"),
}


def tool_title(slug: str) -> str:
    return ICONS[slug]["title"] if slug in ICONS else MONOGRAMS[slug][0]


def icon_color(slug: str, t: dict) -> str:
    """Brand colour, swapped for the text colour when it would vanish."""
    hx = "#" + ICONS[slug]["hex"]
    lum = luminance(hx)
    if t is THEMES["dark"] and lum < 0.06:
        return t["text"]
    if t is THEMES["light"] and lum > 0.7:
        return t["text"]
    return hx


def num(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


class Doc:
    """Accumulates defs, css and body markup for a single SVG file."""

    def __init__(self, w: float, h: float, theme: str, title: str, desc: str = ""):
        self.w, self.h = w, h
        self.theme = theme
        self.t = THEMES[theme]
        self.title, self.desc = title, desc
        self.defs: list[str] = []
        self.css: list[str] = []
        self.body: list[str] = []
        self._ids = defaultdict(int)

    # -- plumbing -------------------------------------------------------
    def uid(self, prefix: str) -> str:
        self._ids[prefix] += 1
        return f"{prefix}{self._ids[prefix]}"

    def add(self, markup: str):
        self.body.append(markup)

    def defn(self, markup: str):
        self.defs.append(markup)

    def style(self, css: str):
        self.css.append(css)

    # -- text -----------------------------------------------------------
    def text(self, x, y, s, key="sans", size=16, fill=None, anchor="start",
             ls=0.0, extra="", cls=""):
        """Single-style text. `fill` may be a colour or a paint server url."""
        fill = fill or self.t["text"]
        ls_attr = f' letter-spacing="{num(ls)}"' if ls else ""
        anchor_attr = f' text-anchor="{anchor}"' if anchor != "start" else ""
        c = f"f-{key}" + (f" {cls}" if cls else "")
        return (f'<text x="{num(x)}" y="{num(y)}" class="{c}" font-size="{num(size)}" '
                f'fill="{fill}"{anchor_attr}{ls_attr}{extra}>{escape(s, quote=False)}</text>')

    def rich(self, x, y, parts, size=16, anchor="start", extra="", cls=""):
        """parts: list of (string, font key, fill[, size])."""
        spans = []
        for p in parts:
            s, key, fill = p[0], p[1], p[2]
            sz = f' font-size="{num(p[3])}"' if len(p) > 3 else ""
            spans.append(f'<tspan class="f-{key}" fill="{fill}"{sz}>{escape(s, quote=False)}</tspan>')
        anchor_attr = f' text-anchor="{anchor}"' if anchor != "start" else ""
        c = f' class="{cls}"' if cls else ""
        return (f'<text x="{num(x)}" y="{num(y)}" font-size="{num(size)}"{anchor_attr}{c}'
                f' xml:space="preserve"{extra}>{"".join(spans)}</text>')

    def icon(self, slug, x, y, size, fill=None, extra=""):
        if slug not in ICONS:
            col = fill or self.t["text"]
            return (f'<rect x="{num(x + .75)}" y="{num(y + .75)}" width="{num(size - 1.5)}" height="{num(size - 1.5)}" '
                    f'rx="{num(size * .26)}" fill="none" stroke="{col}" stroke-width="1.5"/>'
                    + self.text(x + size / 2, y + size * .68, MONOGRAMS[slug][1], "monoM", size * .46, col,
                                anchor="middle", ls=-.4))
        fill = fill or icon_color(slug, self.t)
        s = size / 24
        return (f'<path transform="translate({num(x)} {num(y)}) scale({num(s)})" '
                f'fill="{fill}" d="{ICONS[slug]["path"]}"{extra}/>')

    # -- output ---------------------------------------------------------
    def _font_css(self, svg_body: str) -> str:
        used: dict[str, set] = defaultdict(set)
        root = ET.fromstring(
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink">{svg_body}</svg>')

        def walk(el, inherited):
            classes = (el.get("class") or "").split()
            key = next((c[2:] for c in classes if c.startswith("f-") and c[2:] in FONTS), inherited)
            if key and el.text:
                used[key].update(el.text)
            for child in el:
                walk(child, key)
                if key and child.tail:
                    used[key].update(child.tail)

        walk(root, None)
        out = []
        for key, chars in sorted(used.items()):
            chars = {c for c in chars if not c.isspace()} | {" "}
            fam = FONTS[key][0]
            b64 = _subset_b64(key, "".join(sorted(chars)))
            fb = FALLBACK["mono" if key.startswith("mono") else "serif" if key == "serif" else "sans"]
            out.append(f"@font-face{{font-family:'{fam}';src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
            out.append(f".f-{key}{{font-family:'{fam}',{fb}}}")
        return "".join(out)

    def render(self) -> str:
        body = "\n".join(self.body)
        defs = "\n".join(self.defs)
        font_css = self._font_css(defs + body)
        css = (font_css + "\n" + "\n".join(self.css) +
               "\n@media (prefers-reduced-motion: reduce){*{animation:none!important}}")
        desc = f'<desc id="desc">{escape(self.desc)}</desc>' if self.desc else ""
        labelled = "title desc" if self.desc else "title"
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{num(self.w)}" height="{num(self.h)}" '
            f'viewBox="0 0 {num(self.w)} {num(self.h)}" fill="none" role="img" aria-labelledby="{labelled}">\n'
            f'<title id="title">{escape(self.title)}</title>{desc}\n'
            f'<style>{css}</style>\n<defs>{defs}</defs>\n{body}\n</svg>\n'
        )


def pct(v: float) -> str:
    return num(max(0.0, min(100.0, v))) + "%"
