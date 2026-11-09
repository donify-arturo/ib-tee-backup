"""
IB TEE design system: one stylesheet and a few drawing helpers used by every subject.

Identity — "lab notebook": a deep navy sidebar that frames the work, a faint graph-paper canvas, white cards that float on soft
shadows, one signal-teal accent for action and progress and amber for what is happening now. Space Grotesk for headings (precise,
a little technical), Inter for reading, IBM Plex Mono for labels, codes and keys.
Light and dark palettes share the same CSS variables, so components never hard-code a colour. The sidebar stays navy in both.
"""
from __future__ import annotations

import html

import streamlit as st

PALETTES = {
    "light": {"bg": "#F4F6FA", "grid": "rgba(15,27,45,0.032)", "surface": "#FFFFFF", "surface2": "#F7F9FC", "border": "#E2E7EF",
              "ink": "#0F1B2D", "muted": "#5B6678", "faint": "#94A0B2", "accent": "#0E9384", "accent_soft": "#E3F6F3",
              "accent_ink": "#FFFFFF", "now": "#E7A33E", "now_soft": "#FDF3E1", "btn": "#0F1B2D", "btn_ink": "#FFFFFF",
              "shadow": "0 1px 2px rgba(15,27,45,0.06), 0 4px 14px rgba(15,27,45,0.05)",
              "side": "#0F1B2D", "side2": "#16253B", "side_ink": "#E8EDF5", "side_muted": "#8D9AB0", "side_line": "#22324B",
              "ok": "#0E9384", "ok_soft": "#E3F6F3", "warn": "#B7791F", "warn_soft": "#FDF3E1", "bad": "#D1435B", "bad_soft": "#FCE9EC"},
    "dark": {"bg": "#0B1220", "grid": "rgba(232,237,245,0.028)", "surface": "#121C2E", "surface2": "#17233A", "border": "#22324B",
             "ink": "#E8EDF5", "muted": "#9AA6BA", "faint": "#66738A", "accent": "#2DD4BF", "accent_soft": "#0F3A3A",
             "accent_ink": "#062A27", "now": "#F2B85B", "now_soft": "#3A2C14", "btn": "#2DD4BF", "btn_ink": "#062A27",
             "shadow": "0 1px 2px rgba(0,0,0,0.3), 0 6px 18px rgba(0,0,0,0.25)",
             "side": "#070D18", "side2": "#101A2C", "side_ink": "#E8EDF5", "side_muted": "#7D8AA1", "side_line": "#1B2840",
             "ok": "#2DD4BF", "ok_soft": "#0F3A3A", "warn": "#F2B85B", "warn_soft": "#3A2C14", "bad": "#F47A8C", "bad_soft": "#3D1C24"},
}
LEVEL_COLOURS = {"Not started": "#C7CFDB", "Learning": "#E7A33E", "Practising": "#5B8DEF", "Confident": "#38BFA0", "Mastered": "#0E7C70"}
SUBJECT_COLOURS = {"chem_hl": "#E4572E", "maths_ai_hl": "#5B6CF0"}


def css(mode: str) -> str:
    p = PALETTES[mode]
    vars_ = ";".join(f"--{k.replace('_', '-')}:{v}" for k, v in p.items())
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
:root {{ {vars_}; }}
/* canvas: graph paper */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{ background-color:var(--bg) !important; color:var(--ink); }}
[data-testid="stMain"] {{ background-image:linear-gradient(var(--grid) 1px, transparent 1px), linear-gradient(90deg, var(--grid) 1px, transparent 1px);
                          background-size:24px 24px; }}
header[data-testid="stHeader"] {{ background:transparent !important; }}
html, body, .stMarkdown, p, li, label, input, textarea, button, [class*="css"] {{ font-family:Inter, system-ui, sans-serif; }}
.stMarkdown, .stMarkdown p, .stMarkdown li, label {{ color:var(--ink); }}
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {{ color:var(--ink); }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p, .stCaption {{ color:var(--muted) !important; }}
.block-container {{ padding-top:2rem; max-width:1180px; }}
hr {{ border-color:var(--border) !important; }}
a {{ color:var(--accent); }}
/* headings: Space Grotesk everywhere, including Streamlit titles on the Chemistry pages */
h1, h2, h3, h4, h5 {{ color:var(--ink) !important; font-family:'Space Grotesk', Inter, sans-serif !important; }}
h1 {{ font-weight:600 !important; font-size:2.5rem !important; letter-spacing:-0.03em !important; line-height:1.1 !important; }}
h2, h3 {{ font-weight:600 !important; letter-spacing:-0.02em !important; }}
h4, h5 {{ font-weight:600 !important; letter-spacing:-0.01em !important; }}
/* sidebar: navy in both themes */
section[data-testid="stSidebar"] {{ background:var(--side) !important; border-right:0; }}
section[data-testid="stSidebar"] * {{ color:var(--side-ink); }}
section[data-testid="stSidebar"] .stButton > button {{ justify-content:flex-start; border:0; background:transparent; min-height:2.1rem;
  padding:0.15rem 0.75rem; border-radius:10px; }}
section[data-testid="stSidebar"] .stButton > button > div {{ justify-content:flex-start; text-align:left; }}
section[data-testid="stSidebar"] .stButton > button p {{ font-weight:500; font-size:0.93rem; text-align:left; color:var(--side-ink) !important; opacity:0.82; }}
section[data-testid="stSidebar"] .stButton > button span[data-testid="stIconMaterial"] {{ color:var(--side-muted) !important; }}
section[data-testid="stSidebar"] .stButton > button:hover {{ background:var(--side2); }}
section[data-testid="stSidebar"] .stButton > button:hover p {{ opacity:1; }}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] {{ background:var(--side2); box-shadow:inset 3px 0 0 var(--accent); }}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] p {{ opacity:1; font-weight:600; }}
section[data-testid="stSidebar"] .stButton > button[kind="primary"] span[data-testid="stIconMaterial"] {{ color:var(--accent) !important; }}
section[data-testid="stSidebar"] .stButton > button[kind="tertiary"] p {{ color:var(--side-muted) !important; }}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap:0.12rem; }}
section[data-testid="stSidebar"] [data-testid="stCheckbox"] p, section[data-testid="stSidebar"] .stToggle p {{ color:var(--side-muted) !important; }}
.brand {{ font-family:'Space Grotesk', sans-serif; font-weight:700; font-size:1.55rem; letter-spacing:-0.04em; margin:0 0 1rem 0.5rem;
          color:var(--side-ink); display:flex; align-items:center; gap:10px; }}
.brand .mark {{ width:30px; height:30px; border-radius:9px; background:var(--accent); display:inline-flex; align-items:center; justify-content:center;
                font-family:'IBM Plex Mono', monospace; font-size:0.85rem; font-weight:600; color:#fff; letter-spacing:0; }}
.brand i {{ font-style:normal; color:var(--accent); }}
.navhead {{ font-family:'IBM Plex Mono', monospace; font-size:0.68rem; letter-spacing:0.14em; text-transform:uppercase; color:var(--side-muted);
            margin:1.3rem 0 0.55rem 0.7rem; display:flex; align-items:center; gap:8px; line-height:1.8; padding:2px 0; }}
.navsub {{ font-size:0.7rem; color:var(--side-muted); margin:0.7rem 0 0.1rem 0.75rem; letter-spacing:0.04em; opacity:0.8; }}
.dot {{ display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--c, var(--accent)); }}
.userbox {{ display:flex; gap:10px; align-items:center; padding:10px 6px; border-top:1px solid var(--side-line); }}
.avatar {{ width:34px; height:34px; border-radius:10px; background:var(--accent); color:#fff; display:flex; align-items:center;
           justify-content:center; font-weight:600; font-family:'Space Grotesk', sans-serif; }}
.userbox small {{ color:var(--side-muted); display:block; }}
/* widgets */
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="textarea"], .stTextInput input, .stNumberInput input, .stDateInput input, textarea {{
  background:var(--surface) !important; color:var(--ink) !important; border-color:var(--border) !important; border-radius:10px !important; }}
[data-baseweb="popover"] li, [data-baseweb="menu"] {{ background:var(--surface) !important; color:var(--ink) !important; }}
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label, .stCheckbox p, .stToggle p, .stRadio p, [data-testid="stExpander"] summary p {{ color:var(--ink) !important; }}
.stButton > button, .stDownloadButton > button, [data-testid="stPopover"] > div > button, .stFormSubmitButton > button {{
  border-radius:10px; border:1px solid var(--border); background:var(--surface); color:var(--ink); font-weight:500; box-shadow:none; }}
.stButton > button:hover, .stFormSubmitButton > button:hover {{ border-color:var(--accent); color:var(--accent); background:var(--surface); }}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"] {{ background:var(--btn); color:var(--btn-ink); border-color:var(--btn); }}
.stButton > button[kind="primary"] p, .stFormSubmitButton > button[kind="primaryFormSubmit"] p {{ color:var(--btn-ink) !important; }}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primaryFormSubmit"]:hover {{ background:var(--accent); border-color:var(--accent); }}
.stButton > button[kind="primary"]:hover p {{ color:var(--accent-ink) !important; }}
.stButton > button[kind="tertiary"] {{ color:var(--muted); }}
.stButton > button[kind="tertiary"]:hover {{ color:var(--accent); border:0; }}
[data-testid="stExpander"] details {{ background:var(--surface); border-radius:12px !important; border-color:var(--border) !important; box-shadow:var(--shadow); }}
[data-testid="stForm"] {{ background:var(--surface); border-radius:14px; border-color:var(--border) !important; box-shadow:var(--shadow); }}
[data-baseweb="tab-list"] {{ gap:4px; border-bottom:1px solid var(--border); }}
[data-baseweb="tab"] {{ background:transparent !important; }}
[data-baseweb="tab"] * {{ color:var(--muted) !important; font-weight:500; }}
[data-baseweb="tab"][aria-selected="true"] *, [data-baseweb="tab"]:hover * {{ color:var(--ink) !important; }}
[data-baseweb="tab-highlight"] {{ background:var(--accent) !important; }}
[data-testid="stMetricValue"] {{ font-family:'Space Grotesk', sans-serif; font-weight:600; font-size:2.2rem !important; color:var(--ink); }}
[data-testid="stMetricLabel"] p {{ font-family:'IBM Plex Mono', monospace; text-transform:uppercase; letter-spacing:0.08em; font-size:0.7rem !important; color:var(--muted) !important; }}
[data-testid="stProgress"] > div > div > div > div {{ background:var(--accent) !important; }}
[data-testid="stAlert"] {{ border-radius:12px; }}
code {{ color:var(--accent); background:var(--accent-soft); }}
/* the view switch on every page with several views: pills */
[data-testid="stButtonGroup"] {{ margin:0.5rem 0 1.1rem; }}
[data-testid="stButtonGroup"] button {{ border-radius:999px !important; border:1px solid var(--border) !important; background:var(--surface) !important; padding:0.25rem 1.05rem !important; }}
[data-testid="stButtonGroup"] button p {{ color:var(--muted) !important; font-weight:500; }}
[data-testid="stButtonGroup"] button[kind*="Active"], [data-testid="stButtonGroup"] button[aria-checked="true"] {{ background:var(--ink) !important; border-color:var(--ink) !important; }}
[data-testid="stButtonGroup"] button[kind*="Active"] p, [data-testid="stButtonGroup"] button[aria-checked="true"] p {{ color:var(--bg) !important; }}
/* cards: white, soft shadow, no heavy border */
div[class*="st-key-card"] {{ background:var(--surface); border:1px solid var(--border) !important; border-radius:14px; padding:16px 20px 12px; box-shadow:var(--shadow); }}
/* page headers */
.kicker {{ font-family:'IBM Plex Mono', monospace; font-size:0.72rem; letter-spacing:0.12em; text-transform:uppercase; color:var(--muted);
           display:flex; align-items:center; gap:8px; margin:0.2rem 0 0.15rem; }}
.ptitle {{ font-family:'Space Grotesk', sans-serif; font-weight:600; font-size:2.6rem; line-height:1.08; letter-spacing:-0.035em; color:var(--ink); margin:0.15rem 0 0.35rem; }}
.psub {{ color:var(--muted); font-size:1rem; margin-bottom:0.5rem; }}
.crumbs {{ color:var(--faint); font-size:0.85rem; margin-bottom:0.6rem; }} .crumbs b {{ color:var(--ink); font-weight:500; }}
.rule {{ border-top:1px solid var(--border); margin:0.8rem 0 1.1rem; }}
.serif {{ font-family:'Space Grotesk', sans-serif; font-weight:600; }}
.h2 {{ font-family:'Space Grotesk', sans-serif; font-weight:600; font-size:1.45rem; letter-spacing:-0.02em; color:var(--ink); margin:0.7rem 0 0.45rem; line-height:1.2; }}
.mono {{ font-family:'IBM Plex Mono', monospace; }}
.muted {{ color:var(--muted); }}
/* chips */
.chips {{ display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin:0.15rem 0 0.4rem; }}
.chip {{ font-size:0.76rem; border:1px solid var(--border); border-radius:999px; padding:1px 9px; background:var(--surface); color:var(--muted); white-space:nowrap; }}
.chip.mono {{ font-family:'IBM Plex Mono', monospace; font-weight:600; border:0; background:transparent; padding-left:0; font-size:0.88rem; color:var(--ink); }}
.chip.ok {{ background:var(--ok-soft); color:var(--ok); border-color:transparent; }}
.chip.warn {{ background:var(--warn-soft); color:var(--warn); border-color:transparent; }}
.chip.bad {{ background:var(--bad-soft); color:var(--bad); border-color:transparent; }}
.chip.acc {{ background:var(--now-soft); color:var(--now); border-color:transparent; font-weight:600; }}
.lvl {{ display:inline-flex; align-items:center; gap:6px; font-size:0.8rem; color:var(--ink); }}
.lvl::before {{ content:""; width:9px; height:9px; border-radius:50%; background:var(--lc); }}
/* stats strip */
.stats {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin:0.4rem 0 1.4rem; }}
.stat {{ padding:16px 20px; min-height:112px; background:var(--surface); border:1px solid var(--border); border-radius:14px; box-shadow:var(--shadow); }}
.stat .lab {{ font-family:'IBM Plex Mono', monospace; font-size:0.68rem; letter-spacing:0.1em; text-transform:uppercase; color:var(--muted); display:flex; justify-content:space-between; }}
.stat .val {{ font-family:'Space Grotesk', sans-serif; font-weight:600; font-size:2.5rem; letter-spacing:-0.03em; line-height:1.2; color:var(--ink); }}
.stat .sub {{ font-size:0.78rem; color:var(--muted); }}
.bars {{ display:flex; gap:4px; align-items:flex-end; height:52px; margin-top:10px; }}
.bars span {{ flex:1; background:var(--accent); border-radius:3px; min-height:3px; }}
.bars span.zero {{ background:var(--border); }}
@media (max-width: 900px) {{ .stats {{ grid-template-columns:repeat(2, 1fr); }} .ptitle {{ font-size:2.1rem; }} }}
/* big link cards */
.bigcard .num {{ font-family:'IBM Plex Mono', monospace; font-size:0.75rem; color:var(--accent); }}
.bigcard .t {{ font-family:'Space Grotesk', sans-serif; font-weight:600; font-size:1.5rem; letter-spacing:-0.02em; margin:0.8rem 0 0.4rem; color:var(--ink); }}
.bigcard .d {{ color:var(--muted); min-height:3.2rem; }}
.bigcard .n {{ margin-top:0.8rem; color:var(--muted); }} .bigcard .n b {{ font-family:'Space Grotesk', sans-serif; font-size:1.5rem; color:var(--ink); margin-right:4px; }}
/* rows */
.rowcode {{ white-space:nowrap; font-family:'IBM Plex Mono', monospace; color:var(--accent); font-size:0.88rem; font-weight:600; padding-top:0.35rem; }}
.rowtitle {{ font-weight:600; font-size:1.02rem; color:var(--ink); }}
.rowdesc {{ color:var(--muted); font-size:0.88rem; }}
.bignum {{ font-family:'Space Grotesk', sans-serif; font-weight:700; font-size:2.4rem; letter-spacing:-0.04em; color:var(--accent); line-height:1; }}
/* progress bars */
.pbar {{ height:6px; background:var(--border); border-radius:4px; overflow:hidden; margin:6px 0 2px; }}
.pbar > span {{ display:block; height:100%; background:var(--accent); }}
.lvlbar {{ display:flex; height:8px; border-radius:999px; overflow:hidden; background:var(--border); margin:6px 0; gap:2px; }}
.lvlbar span {{ display:block; height:100%; }}
/* syllabus grid */
.grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(66px, 1fr)); gap:6px; margin:0.3rem 0 0.9rem; }}
.cell {{ border:1px solid var(--border); border-radius:10px; padding:6px 7px; background:var(--surface); font-family:'IBM Plex Mono', monospace;
         font-size:0.78rem; font-weight:600; color:var(--ink); border-bottom:4px solid var(--lc); }}
.cell small {{ display:block; color:var(--muted); font-family:Inter, sans-serif; font-weight:400; font-size:0.64rem; }}
/* questions, markschemes, notes */
[data-testid="stImage"] img {{ border-radius:8px; background:#fff; }}
.mshead {{ font-family:'IBM Plex Mono', monospace; font-size:0.7rem; font-weight:600; letter-spacing:0.12em; text-transform:uppercase; color:var(--accent); }}
.note {{ border-left:3px solid var(--accent); padding:8px 14px; background:var(--accent-soft); border-radius:0 10px 10px 0; margin:0.45rem 0; font-size:0.92rem; color:var(--ink); }}
.formula {{ border:1px solid var(--border); border-radius:12px; padding:10px 14px; background:var(--surface); margin-bottom:8px; }}
.kbd {{ font-family:'IBM Plex Mono', monospace; font-size:0.7rem; border:1px solid var(--border); border-bottom-width:2px; border-radius:5px; padding:0 6px; background:var(--surface2); }}
/* calendar */
.slot {{ border:1px solid var(--border); border-left:4px solid var(--sc, var(--border)); border-radius:10px; padding:8px 12px; background:var(--surface); }}
.slot.break {{ background:transparent; border-style:dashed; border-left-width:1px; color:var(--muted); }}
.slot .time {{ font-family:'IBM Plex Mono', monospace; font-size:0.78rem; color:var(--muted); }}
/* tablet: two-column pages (question + navigator) stack */
@media (max-width: 1100px) {{
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [class*="st-key-card_qnav"]) {{ flex-direction:column-reverse; }}
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [class*="st-key-card_qnav"]) > [data-testid="stColumn"] {{ width:100% !important; flex:1 1 100% !important; }}
  [class*="st-key-card_keys"] {{ display:none; }}
  [class*="st-key-card_sub_"] [data-testid="stHorizontalBlock"] {{ display:grid !important; grid-template-columns:3rem minmax(0, 1fr) 6rem; gap:1.2rem 0.6rem; }}
  [class*="st-key-card_sub_"] [data-testid="stColumn"] {{ width:auto !important; min-width:0 !important; }}
  [class*="st-key-card_sub_"] [data-testid="stColumn"]:nth-child(1) {{ grid-area:1 / 1; }}
  [class*="st-key-card_sub_"] [data-testid="stColumn"]:nth-child(2) {{ grid-area:1 / 2 / 1 / 4; }}
  [class*="st-key-card_sub_"] [data-testid="stColumn"]:nth-child(3) {{ grid-area:2 / 2; }}
  [class*="st-key-card_sub_"] [data-testid="stColumn"]:nth-child(3) div {{ text-align:left !important; }}
  [class*="st-key-card_sub_"] [data-testid="stColumn"]:nth-child(4) {{ grid-area:2 / 3; }}
}}
/* the Chemistry pages, which have their own CSS */
.tile, [class*="st-key-qcard_"] {{ background:var(--surface) !important; box-shadow:var(--shadow); }}
</style>
"""


def apply(mode: str) -> None:
    st.markdown(css(mode if mode in PALETTES else "light"), unsafe_allow_html=True)


def esc(text) -> str:
    """HTML-escape, and stop "$" from opening a LaTeX formula in Streamlit markdown ("$100000 … $150000" is money, not maths)."""
    return html.escape(str(text if text is not None else "")).replace("$", "&#36;")


def header(title: str, kicker: str = "", sub: str = "", dot: str | None = None) -> None:
    k = f'<div class="kicker">{f"<span class=dot style=--c:{dot}></span>" if dot else ""}{esc(kicker)}</div>' if kicker else ""
    s = f'<div class="psub">{sub}</div>' if sub else ""
    st.markdown(f'{k}<div class="ptitle">{esc(title)}</div>{s}', unsafe_allow_html=True)


def crumbs(*parts: str) -> None:
    if not parts:
        return
    inner = " &nbsp;›&nbsp; ".join(esc(p) for p in parts[:-1]) + (" &nbsp;›&nbsp; " if len(parts) > 1 else "") + f"<b>{esc(parts[-1])}</b>"
    st.markdown(f'<div class="crumbs">{inner}</div>', unsafe_allow_html=True)


def rule() -> None:
    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)


def chips(*items: tuple[str, str] | str) -> str:
    out = []
    for it in items:
        text, kind = (it, "") if isinstance(it, str) else it
        out.append(f'<span class="chip {kind}">{esc(text)}</span>')
    return f'<div class="chips">{"".join(out)}</div>'


def level_tag(level: str) -> str:
    return f'<span class="lvl" style="--lc:{LEVEL_COLOURS.get(level, "#999")}">{esc(level)}</span>'


def level_bar(counts: dict[str, int]) -> str:
    total = sum(counts.values()) or 1
    spans = "".join(f'<span style="width:{100 * n / total:.1f}%;background:{LEVEL_COLOURS[l]}" title="{l}: {n}"></span>'
                    for l, n in counts.items() if n)
    return f'<div class="lvlbar">{spans}</div>'


def pbar(fraction: float) -> str:
    return f'<div class="pbar"><span style="width:{max(0, min(1, fraction)) * 100:.0f}%"></span></div>'


def stats_strip(items: list[tuple[str, str, str]], bars: list[int] | None = None, bars_label: str = "") -> None:
    """items: (label, value, sub). If bars is given it becomes the last tile."""
    cells = "".join(f'<div class="stat"><div class="lab">{esc(l)}</div><div class="val">{esc(v)}</div><div class="sub">{esc(s)}</div></div>'
                    for l, v, s in items)
    if bars is not None:
        top = max(bars) or 1
        spans = "".join(f'<span class="{"zero" if not b else ""}" style="height:{max(4, 100 * b / top):.0f}%" title="{b}"></span>' for b in bars)
        cells += f'<div class="stat"><div class="lab"><span>Last {len(bars)} days</span><span style="text-transform:none;letter-spacing:0">{esc(bars_label)}</span></div><div class="bars">{spans}</div></div>'
    st.markdown(f'<div class="stats">{cells}</div>', unsafe_allow_html=True)


def empty(title: str, text: str) -> None:
    with st.container(border=True, key=f"card_empty_{abs(hash(title)) % 10**8}"):
        st.markdown(f'<div style="text-align:center;padding:1.4rem 0"><div class="h2">{esc(title)}</div><div class="muted">{text}</div></div>',
                    unsafe_allow_html=True)
