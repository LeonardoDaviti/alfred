#!/usr/bin/env python3
"""Build the A.L.F.R.E.D. defense decks in three themes.

Themes: shinkawa-dark, shinkawa-light (black/white/gold, Inter + JetBrains Mono)
and thesis (white + steel-blue, matching the thesis figures).
Every number is taken verbatim from thesis/main.pdf.
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.ns import qn
import copy, os

OUT = os.path.dirname(os.path.abspath(__file__))

THEMES = {
    "shinkawa-dark": dict(
        bg="000000", panel="101010", panel2="161616", border="2A2A2A",
        text="E0E0E0", muted="969696", head="FFFFFF",
        accent="FFDE6E", accent_text="FFDE6E", on_accent="000000",
        strong="F2F2F2", bar_gray="4A4A4A",
    ),
    "shinkawa-light": dict(
        bg="FFFFFF", panel="F5F5F5", panel2="EDEDED", border="DDDDDD",
        text="333333", muted="757575", head="000000",
        accent="FFDE6E", accent_text="8A7129", on_accent="000000",
        strong="1A1A1A", bar_gray="C0C0C0",
    ),
    "thesis": dict(
        bg="FFFFFF", panel="F3F5F8", panel2="E9EDF3", border="D3DAE3",
        text="222222", muted="6A6A6A", head="111111",
        accent="4A7EBB", accent_text="35619B", on_accent="FFFFFF",
        strong="1A1A1A", bar_gray="B5B5B5",
    ),
}
F_HEAD, F_BODY, F_MONO = "Inter", "Inter", "JetBrains Mono"
W, H = Inches(13.333), Inches(7.5)


def rgb(h):
    return RGBColor.from_string(h)


def box(slide, x, y, w, h, fill=None, line=None, lw=1.0, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.shadow.inherit = False
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(lw)
    return s


def txt(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def para(tf, runs, size=14, color="000000", bold=False, font=F_BODY,
         align=PP_ALIGN.LEFT, space_after=4, space_before=0, first=False,
         line_spacing=None):
    p = tf.paragraphs[0] if first and not tf.paragraphs[0].runs else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(space_after)
    p.space_before = Pt(space_before)
    if line_spacing:
        p.line_spacing = line_spacing
    if isinstance(runs, str):
        runs = [(runs, {})]
    for text, ov in runs:
        r = p.add_run()
        r.text = text
        f = r.font
        f.size = Pt(ov.get("size", size))
        f.bold = ov.get("bold", bold)
        f.italic = ov.get("italic", False)
        f.name = ov.get("font", font)
        f.color.rgb = rgb(ov.get("color", color))
    return p


def set_cell_text(shape_or_tf, *args, **kw):
    pass  # unused


def arrow(slide, x1, y1, x2, y2, color, lw=1.75):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(lw)
    c.shadow.inherit = False
    ln = c.line._get_or_add_ln()
    end = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(end)
    return c


def node(slide, T, x, y, w, h, text, accent=False, mono=False, size=13, fill=None, sub=None):
    f = fill if fill else (T["accent"] if accent else T["panel"])
    lc = T["accent_text"] if accent else T["border"]
    s = box(slide, x, y, w, h, fill=f, line=lc, lw=1.2, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    try:
        s.adjustments[0] = 0.12
    except Exception:
        pass
    tf = s.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Emu(45000)
    tf.margin_top = tf.margin_bottom = Emu(18000)
    color = T["on_accent"] if accent else T["head"]
    para(tf, text, size=size, color=color, bold=True,
         font=F_MONO if mono else F_BODY, align=PP_ALIGN.CENTER, first=True, space_after=0)
    if sub:
        para(tf, sub, size=size - 3.5, color=T["on_accent"] if accent else T["muted"],
             align=PP_ALIGN.CENTER, space_after=0)
    return s


def chrome(prs, T, title=None, num=None, total=11):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box(slide, 0, 0, 13.333, 7.5, fill=T["bg"])
    if title:
        tf = txt(slide, 0.55, 0.32, 12.2, 0.7)
        para(tf, title, size=27, color=T["head"], bold=True, font=F_HEAD, first=True)
        box(slide, 0.57, 1.02, 1.35, 0.045, fill=T["accent"])
    if num:
        tf = txt(slide, 11.6, 7.08, 1.2, 0.35)
        para(tf, f"{num} / {total}", size=10, color=T["muted"], font=F_MONO,
             align=PP_ALIGN.RIGHT, first=True)
        tf = txt(slide, 0.55, 7.08, 8.0, 0.35)
        para(tf, "A.L.F.R.E.D. · Dissertation Defense · IBSU · July 2026",
             size=10, color=T["muted"], font=F_MONO, first=True)
    return slide


def bar_chart(slide, T, x, y, w, h, data, ymax=100, label_size=11, value_size=13):
    """data: list of (label, value, colorkey, sublabel)."""
    n = len(data)
    gap = w * 0.07
    bw = (w - gap * (n - 1)) / n
    base_y = y + h
    box(slide, x - 0.05, base_y, w + 0.1, 0.02, fill=T["border"])
    for i, (label, val, ck, sub) in enumerate(data):
        bx = x + i * (bw + gap)
        bh = h * (val / ymax)
        box(slide, bx, base_y - bh, bw, bh, fill=T[ck])
        tf = txt(slide, bx - 0.2, base_y - bh - 0.32, bw + 0.4, 0.3)
        para(tf, f"{val:g}", size=value_size, bold=True, font=F_MONO,
             color=T["accent_text"] if ck == "accent" else T["head"],
             align=PP_ALIGN.CENTER, first=True)
        tf = txt(slide, bx - 0.25, base_y + 0.08, bw + 0.5, 0.55)
        para(tf, label, size=label_size, bold=(ck == "accent"), color=T["text"],
             align=PP_ALIGN.CENTER, first=True, space_after=0)
        if sub:
            para(tf, sub, size=label_size - 2.5, color=T["muted"], align=PP_ALIGN.CENTER,
                 space_after=0)


# ────────────────────────────── slides ──────────────────────────────

def s1_title(prs, T):
    s = chrome(prs, T)
    tf = txt(s, 1.0, 1.15, 11.33, 0.8, anchor=MSO_ANCHOR.TOP)
    para(tf, "INTERNATIONAL BLACK SEA UNIVERSITY", size=14, color=T["muted"],
         font=F_MONO, align=PP_ALIGN.CENTER, first=True, space_after=2)
    para(tf, "School of Computer Science · Computer Science Program",
         size=12, color=T["muted"], font=F_MONO, align=PP_ALIGN.CENTER)
    tf = txt(s, 1.0, 2.5, 11.33, 1.9, anchor=MSO_ANCHOR.TOP)
    para(tf, "A.L.F.R.E.D.", size=44, color=T["head"], bold=True, font=F_HEAD,
         align=PP_ALIGN.CENTER, first=True, space_after=8)
    para(tf, "Adaptive Local-First Routing and Execution Distillation",
         size=24, color=T["head"], font=F_HEAD, align=PP_ALIGN.CENTER, space_after=2)
    para(tf, "for Small Language Models", size=24, color=T["head"], font=F_HEAD,
         align=PP_ALIGN.CENTER)
    box(s, 5.92, 4.62, 1.5, 0.05, fill=T["accent"])
    tf = txt(s, 1.0, 5.05, 11.33, 1.8)
    para(tf, "David Zoidze", size=20, color=T["head"], bold=True,
         align=PP_ALIGN.CENTER, first=True, space_after=4)
    para(tf, "Bachelor's Thesis in Computer Science", size=13, color=T["text"],
         align=PP_ALIGN.CENTER, space_after=4)
    para(tf, [("Supervisor: ", {"color": T["muted"]}),
              ("Giorgi Merabishvili", {"bold": True, "color": T["text"]})],
         size=14, align=PP_ALIGN.CENTER, space_after=14)
    para(tf, "Tbilisi · July 2026", size=12, color=T["muted"], font=F_MONO,
         align=PP_ALIGN.CENTER)


def s2_problem(prs, T):
    s = chrome(prs, T, "The problem", 2)
    tf = txt(s, 0.57, 1.28, 12.2, 0.75)
    para(tf, [("How much language model does reliable on-device ", {}),
              ("action", {"italic": True, "color": T["accent_text"], "bold": True}),
              (" actually require?", {})],
         size=21, color=T["head"], bold=False, font=F_HEAD, first=True)
    # left panel: why on-device
    box(s, 0.57, 2.15, 5.9, 3.6, fill=T["panel"], line=T["border"])
    tf = txt(s, 0.92, 2.42, 5.3, 3.2)
    para(tf, "WHY ON-DEVICE", size=12, color=T["muted"], font=F_MONO, bold=True,
         first=True, space_after=10)
    for name, desc in [
        ("Privacy", "action requests carry personal context that should never leave the device"),
        ("Cost & latency", "a local model answers in milliseconds, with no round-trip and no per-call bill"),
        ("Availability", "the device should still work offline"),
    ]:
        para(tf, [(name, {"bold": True, "color": T["head"]}),
                  ("  —  " + desc, {"color": T["text"]})], size=13.5, space_after=9,
             line_spacing=1.15)
    para(tf, "Google (Gemini Nano / AICore) and Apple (Apple Intelligence) already make this bet.",
         size=11.5, color=T["muted"], space_after=0, line_spacing=1.15)
    # right panel: the squeeze
    box(s, 6.83, 2.15, 5.93, 3.6, fill=T["panel"], line=T["border"])
    tf = txt(s, 7.18, 2.42, 5.3, 3.2)
    para(tf, "THE SQUEEZE", size=12, color=T["muted"], font=F_MONO, bold=True,
         first=True, space_after=10)
    para(tf, [("Small model, free-form", {"bold": True, "color": T["head"]}),
              ("  —  unreliable executor: fails to act, or invents commands from pretraining priors (30% binding)", {"color": T["text"]})],
         size=13.5, space_after=9, line_spacing=1.15)
    para(tf, [("Large model", {"bold": True, "color": T["head"]}),
              ("  —  does not fit on the phone, an order of magnitude slower, costs per call — and is still wrong on device conventions", {"color": T["text"]})],
         size=13.5, space_after=9, line_spacing=1.15)
    para(tf, "The interesting design space: a tiny model that does not have to be clever, paired with something that supplies the knowledge it lacks.",
         size=11.5, color=T["muted"], space_after=0, line_spacing=1.15)
    # bottom strip
    box(s, 0.57, 6.05, 12.19, 0.72, fill=T["panel2"], line=T["border"])
    tf = txt(s, 0.9, 6.05, 11.6, 0.72, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, [("Actions have a single correct outcome", {"bold": True, "color": T["head"]}),
              ("  —  either the alarm is set for 7:00 or it is not.", {"color": T["text"]})],
         size=15, first=True, space_after=0)


def s3_claim(prs, T):
    s = chrome(prs, T, "Thesis statement & research questions", 3)
    box(s, 0.57, 1.3, 12.19, 1.62, fill=T["panel"], line=T["border"])
    box(s, 0.57, 1.3, 0.09, 1.62, fill=T["accent"])
    tf = txt(s, 1.0, 1.3, 11.4, 1.62, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, [("On the repeatable, deterministic head of on-device tasks, ", {}),
              ("distillation substitutes for scale", {"bold": True, "color": T["accent_text"]}),
              (".", {})], size=19, color=T["head"], font=F_HEAD, first=True, space_after=5)
    para(tf, "A 2B executor handed a distilled symbolic pattern matches a 17× larger free-form agent in binding accuracy, at one on-device forward pass. The remaining open limit is routing, not execution.",
         size=13, color=T["text"], line_spacing=1.15, space_after=0)
    tf = txt(s, 0.57, 3.25, 12.2, 0.4)
    para(tf, "FIVE RESEARCH QUESTIONS", size=12, color=T["muted"], font=F_MONO,
         bold=True, first=True)
    rqs = [
        ("RQ1", "Scale vs. distillation", "how much model does reliable binding need — can a pattern close the gap?"),
        ("RQ2", "The spectrum", "does the reflexer's value change with API difficulty — efficiency win or accuracy win?"),
        ("RQ3", "The limit of scale", "are there difficulties model scale cannot solve but a distilled pattern can?"),
        ("RQ4", "Teacher quality", "how much does the choice of teacher (cloud vs. local) propagate to the student?"),
        ("RQ5", "Coverage & routing", "what fraction of real use-cases does this address — where is the bottleneck?"),
    ]
    y = 3.72
    for tag, name, q in rqs:
        box(s, 0.57, y, 12.19, 0.55, fill=T["panel"], line=T["border"], lw=0.75)
        tf = txt(s, 0.85, y, 11.7, 0.55, anchor=MSO_ANCHOR.MIDDLE)
        para(tf, [(tag + "  ", {"font": F_MONO, "bold": True, "color": T["accent_text"]}),
                  (name + "  —  ", {"bold": True, "color": T["head"]}),
                  (q, {"color": T["text"]})], size=13, first=True, space_after=0)
        y += 0.64


def s4_architecture(prs, T):
    s = chrome(prs, T, "System design: two tiers, one router", 4)
    tf = txt(s, 0.57, 1.22, 12.2, 0.5)
    para(tf, [("Most on-device requests do not need a model to ", {}),
              ("reason", {"italic": True}), ("; they need a model to ", {}),
              ("fill in a blank", {"italic": True, "bold": True, "color": T["accent_text"]}),
              (".", {})], size=15, color=T["text"], first=True)
    # diagram band
    dy = 2.0
    node(s, T, 0.7, dy + 0.85, 1.75, 0.95, "user\nrequest", size=13)
    arrow(s, 2.45, dy + 1.32, 3.15, dy + 1.32, T["muted"])
    node(s, T, 3.15, dy + 0.85, 1.6, 0.95, "Router", size=14)
    arrow(s, 4.75, dy + 1.1, 5.85, dy + 0.55, T["accent_text"])
    arrow(s, 4.75, dy + 1.55, 5.85, dy + 2.1, T["muted"])
    tf = txt(s, 4.85, dy + 0.42, 0.9, 0.3)
    para(tf, "head", size=10.5, color=T["accent_text"], font=F_MONO, first=True)
    tf = txt(s, 4.85, dy + 1.98, 0.9, 0.3)
    para(tf, "tail", size=10.5, color=T["muted"], font=F_MONO, first=True)
    node(s, T, 5.85, dy + 0.1, 2.5, 0.95, "Reflexer", accent=True, size=14,
         sub="2B · one forward pass")
    node(s, T, 5.85, dy + 1.75, 2.5, 0.95, "Thinker", size=14,
         sub="agent loop · the tail")
    arrow(s, 8.35, dy + 0.57, 9.45, dy + 1.15, T["accent_text"])
    arrow(s, 8.35, dy + 2.22, 9.45, dy + 1.6, T["muted"])
    node(s, T, 9.45, dy + 0.85, 2.5, 0.95, "skill CLI → device", mono=True, size=12.5)
    # bullets
    y = 5.15
    rows = [
        ("Reflexer — an executioner, not a generator",
         "extracts slots, fills a fixed command template, emits one shell command; escalates on any failure"),
        ("Thinker — a general ReAct agent for the tail",
         "multi-intent, planning, undistilled intents; built on the Pi coding-agent framework"),
        ("Skills — deep modules behind a CLI",
         "small intent-shaped vocabulary (clock timer -duration 10m) hiding messy device mechanism"),
    ]
    for name, desc in rows:
        tf = txt(s, 0.7, y, 12.0, 0.62)
        para(tf, [("▸ ", {"color": T["accent_text"], "bold": True}),
                  (name, {"bold": True, "color": T["head"]}),
                  ("  —  " + desc, {"color": T["text"]})], size=13.5, first=True,
             space_after=0, line_spacing=1.1)
        y += 0.58


def s5_distillation(prs, T):
    s = chrome(prs, T, "Symbolic distillation: teacher → pattern → student", 5)
    # offline / on-device split
    tf = txt(s, 0.7, 1.35, 5.8, 0.35)
    para(tf, "OFFLINE — once per intent", size=11.5, color=T["muted"], font=F_MONO,
         bold=True, first=True)
    tf = txt(s, 7.6, 1.35, 5.0, 0.35)
    para(tf, "ON-DEVICE — every request", size=11.5, color=T["muted"], font=F_MONO,
         bold=True, first=True)
    box(s, 7.28, 1.4, 0.02, 2.6, fill=T["border"])
    dy = 2.0
    node(s, T, 0.7, dy, 2.0, 0.95, "SKILL.md\n+ schema", mono=True, size=11.5)
    arrow(s, 2.7, dy + 0.47, 3.4, dy + 0.47, T["muted"])
    node(s, T, 3.4, dy, 2.0, 0.95, "Teacher", size=14, sub="strong model, one pass")
    arrow(s, 5.4, dy + 0.47, 6.1, dy + 0.47, T["accent_text"])
    node(s, T, 6.1, dy, 1.9, 0.95, "pattern", accent=True, mono=True, size=13,
         sub="frozen JSON")
    arrow(s, 8.0, dy + 0.47, 8.7, dy + 0.47, T["accent_text"])
    node(s, T, 8.7, dy, 2.0, 0.95, "Reflexer", size=14, sub="2B student")
    arrow(s, 10.7, dy + 0.47, 11.4, dy + 0.47, T["muted"])
    node(s, T, 11.4, dy, 1.45, 0.95, "device", size=12.5)
    tf = txt(s, 5.15, dy + 1.05, 3.8, 0.35)
    para(tf, "trigger · typed slots · args_template · validators", size=10,
         color=T["muted"], font=F_MONO, first=True, align=PP_ALIGN.LEFT)
    # bullets
    y = 3.85
    rows = [
        ("Distill into a symbolic artifact, not student weights",
         "inspectable, plug-and-play (adding a capability = adding a JSON file), auditable, composable"),
        ("Two regimes", "cold-start (teacher sees only docs + schema) vs. session-grounded (teacher reads the real device)"),
        ("Integrity by construction",
         "the teacher never sees evaluation tasks or gold outcomes; a minted pattern is frozen, never edited after failures"),
    ]
    for name, desc in rows:
        tf = txt(s, 0.7, y, 12.0, 0.62)
        para(tf, [("▸ ", {"color": T["accent_text"], "bold": True}),
                  (name, {"bold": True, "color": T["head"]}),
                  ("  —  " + desc, {"color": T["text"]})], size=13.5, first=True,
             space_after=0, line_spacing=1.1)
        y += 0.62
    box(s, 0.57, 6.05, 12.19, 0.72, fill=T["panel2"], line=T["border"])
    tf = txt(s, 0.9, 6.05, 11.6, 0.72, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, [("Same teacher→student axis as classical distillation (Hinton et al.), ", {"color": T["text"]}),
              ("different target: ", {"color": T["text"]}),
              ("knowledge into an artifact the user can read.", {"bold": True, "color": T["head"]})],
         size=14, first=True, space_after=0)


def s6_methodology(prs, T):
    s = chrome(prs, T, "Methodology: measuring only what is claimed", 6)
    cards = [
        ("BINDING-ONLY", "Isolate execution from routing",
         "routing assumed perfect: reflexer gets the gold pattern, thinker gets the right docs — only binding is under test; routing is measured separately"),
        ("END-STATE ORACLE", "Success = final device state",
         "requested keys reach target values and nothing else changed (no collateral edits); catches “right-looking command, wrong outcome”"),
        ("BENCHMARKS", "Three difficulty brackets",
         "409 expansion atoms across 7 skills · SET-1 clean settings API (30 tasks) · SET-2 realistic Android API, 32 settings, non-obvious encodings (48 tasks)"),
        ("INTEGRITY PROTOCOL", "Rules stated before results",
         "no fabricated numbers (every figure cites a saved run) · no benchmark leakage into patterns · sandboxed, destroyed-after-use state · sequential runs"),
    ]
    pos = [(0.57, 1.4), (6.83, 1.4), (0.57, 3.85), (6.83, 3.85)]
    for (tag, name, desc), (x, y) in zip(cards, pos):
        box(s, x, y, 5.93, 2.28, fill=T["panel"], line=T["border"])
        box(s, x, y, 5.93, 0.06, fill=T["accent"])
        tf = txt(s, x + 0.32, y + 0.24, 5.3, 1.9)
        para(tf, tag, size=11.5, color=T["accent_text"], font=F_MONO, bold=True,
             first=True, space_after=4)
        para(tf, name, size=15.5, color=T["head"], bold=True, space_after=6)
        para(tf, desc, size=12, color=T["text"], line_spacing=1.18, space_after=0)
    tf = txt(s, 0.57, 6.35, 12.2, 0.45)
    para(tf, "All models Q4-quantized GGUF (phone-class memory) · served by llama.cpp · agent loop driven by Pi",
         size=12, color=T["muted"], font=F_MONO, first=True, align=PP_ALIGN.CENTER)


def s7_result1(prs, T):
    s = chrome(prs, T, "Result 1 — Distillation substitutes for scale", 7)
    tf = txt(s, 0.57, 1.25, 12.2, 0.45)
    para(tf, "Binding accuracy, balanced-10, routing held fixed (binding-only).",
         size=13.5, color=T["muted"], first=True)
    bar_chart(s, T, 1.1, 2.15, 6.7, 3.55, [
        ("Thinker 2B", 30, "bar_gray", "free-form"),
        ("Thinker 4B*", 10, "bar_gray", "free-form"),
        ("Thinker 35B", 100, "strong", "free-form"),
        ("Reflexer 2B\n+ pattern", 100, "accent", "one pass"),
    ])
    tf = txt(s, 1.1, 6.35, 6.7, 0.35)
    para(tf, "*4B at ctx 4000 (confound) — scale alone is non-monotonic", size=10,
         color=T["muted"], first=True)
    # right callouts
    x = 8.45
    rows = [
        ("100% = 100%", "the 2B reflexer with a distilled pattern equals the 35B free-form thinker — at ~17× fewer parameters"),
        ("<1 s vs 6.4 s", "one on-device forward pass (~0.3k tokens) vs an off-device agent loop (~1.3k tokens)"),
        ("72/72 vs 14/72", "the effect persists on the full atom set: reflexer 100%, unaided 2B thinker 19.4%"),
    ]
    y = 2.05
    for big, small in rows:
        box(s, x, y, 4.3, 1.42, fill=T["panel"], line=T["border"])
        tf = txt(s, x + 0.28, y + 0.16, 3.8, 1.15)
        para(tf, big, size=17, color=T["accent_text"], bold=True, font=F_MONO,
             first=True, space_after=3)
        para(tf, small, size=11, color=T["text"], line_spacing=1.12, space_after=0)
        y += 1.58
    box(s, 0.57, 6.78, 12.19, 0.02, fill=T["border"])


def s8_result2(prs, T):
    s = chrome(prs, T, "Result 2 — Scale buys discovery, not convention", 8)
    # left: SET-1
    box(s, 0.57, 1.35, 5.9, 2.9, fill=T["panel"], line=T["border"])
    tf = txt(s, 0.9, 1.55, 5.3, 0.7)
    para(tf, "SET-1 · CLEAN API", size=11.5, color=T["muted"], font=F_MONO, bold=True,
         first=True, space_after=2)
    para(tf, "Efficiency win", size=16, color=T["head"], bold=True)
    bar_chart(s, T, 1.35, 2.45, 3.0, 1.35, [
        ("manual edit", 32, "bar_gray", "9 calls"),
        ("deep tool", 100, "accent", "2 calls"),
    ], value_size=12, label_size=10.5)
    tf = txt(s, 4.6, 2.5, 1.75, 1.6, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, "+65 pts", size=17, color=T["accent_text"], bold=True, font=F_MONO,
         first=True, space_after=2, align=PP_ALIGN.CENTER)
    para(tf, "3098 → 775 tokens", size=10.5, color=T["text"], align=PP_ALIGN.CENTER,
         space_after=0)
    # right: SET-2
    box(s, 6.83, 1.35, 5.93, 2.9, fill=T["panel"], line=T["border"])
    tf = txt(s, 7.16, 1.55, 5.3, 0.7)
    para(tf, "SET-2 · REALISTIC ANDROID API", size=11.5, color=T["muted"], font=F_MONO,
         bold=True, first=True, space_after=2)
    para(tf, "Accuracy win", size=16, color=T["head"], bold=True)
    bar_chart(s, T, 7.55, 2.45, 4.5, 1.35, [
        ("Thinker 2B", 25, "bar_gray", "free-form"),
        ("Thinker 35B", 62.5, "strong", "reasoning"),
        ("Reflexer 2B\n+ distilled", 80, "accent", "one pass"),
    ], value_size=12, label_size=10.5)
    # convention table
    box(s, 0.57, 4.55, 12.19, 1.55, fill=T["panel"], line=T["border"])
    tf = txt(s, 0.9, 4.72, 11.6, 1.35)
    para(tf, "THE 35B'S FAILURES ARE CONVENTIONS, NOT DISCOVERY", size=11,
         color=T["muted"], font=F_MONO, bold=True, first=True, space_after=6)
    for task, correct, produced in [
        ("“largest font”", 'font_scale "1.30"', '"1.5"'),
        ("“DND total silence”", "zen_mode 2", "1"),
    ]:
        para(tf, [(task + "   ", {"color": T["text"]}),
                  ("correct: " + correct, {"font": F_MONO, "color": T["accent_text"], "bold": True}),
                  ("    35B produced: " + produced, {"font": F_MONO, "color": T["muted"]})],
             size=12.5, space_after=4)
    para(tf, "It finds the right key by exploring (discovery) — then guesses the value and is wrong the same way every time.",
         size=11, color=T["muted"], space_after=0)
    box(s, 0.57, 6.32, 12.19, 0.62, fill=T["panel2"], line=T["border"])
    tf = txt(s, 0.9, 6.32, 11.6, 0.62, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, [("Convention is not discoverable from the API. ", {"color": T["text"]}),
              ("Scale rescues discovery; only a distilled pattern carries the convention.",
               {"bold": True, "color": T["head"]})], size=14, first=True, space_after=0)


def s9_result3(prs, T):
    s = chrome(prs, T, "Result 3 — Teacher quality, economics, and the honest bottleneck", 9)
    cols = [
        ("TEACHER QUALITY", "25% → 76–80%", [
            "cold-start distillation: the teacher sees only docs + schema, never a task",
            "cloud teacher (Sonnet 4.6): reflexer passes 80% · local 35B teacher: 60%",
            "the student faithfully executes whatever the teacher encoded — teacher choice propagates directly",
        ]),
        ("ECONOMICS", "break-even ≈ 10 calls", [
            "mint once: ~5–15k teacher tokens · run forever: ~0.3k tokens, <1 s, on-device",
            "head intent invoked thousands of times → 100–1000× net win",
            "big model spent where it pays: offline teacher + tail fallback",
        ]),
        ("HONEST BOTTLENECK", "routing, not binding", [
            "binding is effectively solved on the deterministic slice (96–100%)",
            "routing reaches 66–85%: retrieval is fine (top-3), selection picks the wrong sibling",
            "stated plainly: the open problem for a shippable system is the router",
        ]),
    ]
    x = 0.57
    for tag, big, items in cols:
        box(s, x, 1.4, 3.98, 5.25, fill=T["panel"], line=T["border"])
        box(s, x, 1.4, 3.98, 0.06, fill=T["accent"])
        tf = txt(s, x + 0.28, 1.66, 3.45, 4.8)
        para(tf, tag, size=11.5, color=T["muted"], font=F_MONO, bold=True, first=True,
             space_after=4)
        para(tf, big, size=19, color=T["accent_text"], bold=True, font=F_MONO,
             space_after=10)
        for it in items:
            para(tf, [("▸ ", {"color": T["accent_text"], "bold": True}),
                      (it, {"color": T["text"]})], size=12, space_after=8,
                 line_spacing=1.15)
        x += 4.105


def s10_future(prs, T):
    s = chrome(prs, T, "Future work — five methodologies, ordered by leverage", 10)
    rows = [
        ("1", "Session-based device grounding",
         "give the teacher read-only access to the real device, so guessed conventions become observed facts; ground on a development split, never on evaluation gold"),
        ("2", "Deterministic value transforms",
         "move arithmetic and enum lookups (percent → 0–255, label → code) out of the model into a small deterministic function inside the pattern"),
        ("3", "The router: sibling discrimination",
         "retrieval already places the right candidate in the top-3; invest in selection — better selection prompting or a learned selector over behavioural signals"),
        ("4", "Iterative, grounded distillation",
         "run → observe failures → re-distill over 2–3 rounds, lifting a weak local teacher toward cloud quality; the runtime reflex stays a frozen single pass, with a minimality check per round"),
        ("5", "Authoring & personalization at scale",
         "mine a user's repeated trajectories into candidate patterns; privacy-preserving pattern sharing; measure a parametric alternative (tiny fine-tune) against the symbolic approach"),
    ]
    y = 1.35
    for num, name, desc in rows:
        box(s, 0.57, y, 12.19, 0.92, fill=T["panel"], line=T["border"], lw=0.75)
        box(s, 0.57, y, 0.62, 0.92, fill=T["accent"])
        tf = txt(s, 0.57, y, 0.62, 0.92, anchor=MSO_ANCHOR.MIDDLE)
        para(tf, num, size=20, color=T["on_accent"], bold=True, font=F_MONO,
             align=PP_ALIGN.CENTER, first=True, space_after=0)
        tf = txt(s, 1.45, y + 0.1, 11.1, 0.78)
        para(tf, name, size=14, color=T["head"], bold=True, first=True, space_after=2)
        para(tf, desc, size=11.5, color=T["text"], line_spacing=1.08, space_after=0)
        y += 1.02
    tf = txt(s, 0.57, 6.5, 12.2, 0.45)
    para(tf, [("Development substrate: ", {"bold": True, "color": T["head"]}),
              ("all extensions built inside the Pi coding-agent framework — executor and agent loop share one runtime, one tool surface, one instrumentation path.",
               {"color": T["text"]})], size=12.5, first=True, align=PP_ALIGN.CENTER)


def s11_thanks(prs, T):
    s = chrome(prs, T)
    tf = txt(s, 1.0, 2.35, 11.33, 1.5)
    para(tf, "Thank you.", size=48, color=T["head"], bold=True, font=F_HEAD,
         align=PP_ALIGN.CENTER, first=True, space_after=10)
    para(tf, "Questions?", size=22, color=T["accent_text"], font=F_HEAD,
         align=PP_ALIGN.CENTER)
    box(s, 5.92, 4.35, 1.5, 0.05, fill=T["accent"])
    tf = txt(s, 1.0, 4.75, 11.33, 1.6)
    para(tf, "David Zoidze", size=16, color=T["head"], bold=True,
         align=PP_ALIGN.CENTER, first=True, space_after=4)
    para(tf, "A.L.F.R.E.D.: Adaptive Local-First Routing and Execution Distillation for Small Language Models",
         size=12, color=T["muted"], align=PP_ALIGN.CENTER, space_after=4)
    para(tf, "International Black Sea University · Tbilisi · July 2026",
         size=11, color=T["muted"], font=F_MONO, align=PP_ALIGN.CENTER)


def build(theme_name):
    T = THEMES[theme_name]
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H
    for fn in (s1_title, s2_problem, s3_claim, s4_architecture, s5_distillation,
               s6_methodology, s7_result1, s8_result2, s9_result3, s10_future,
               s11_thanks):
        fn(prs, T)
    path = os.path.join(OUT, f"ALFRED-defense-{theme_name}.pptx")
    prs.save(path)
    print("wrote", path)


if __name__ == "__main__":
    for name in THEMES:
        build(name)
