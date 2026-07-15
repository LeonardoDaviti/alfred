#!/usr/bin/env python3
"""Plain-language ("Karpathy-style") defense deck: intuition first, one running
example, minimal jargon. Reuses the visual system of build_decks.py.
Outputs ALFRED-defense-plain-<theme>.pptx for the three themes.
"""
from build_decks import (THEMES, W, H, F_HEAD, F_BODY, F_MONO, rgb, box, txt,
                         para, arrow, node, chrome, bar_chart, Presentation,
                         Inches, Pt, MSO_ANCHOR, PP_ALIGN, MSO_SHAPE)
import os

OUT = os.path.dirname(os.path.abspath(__file__))
TOTAL = 11


def s1_title(prs, T):
    s = chrome(prs, T)
    tf = txt(s, 1.0, 1.15, 11.33, 0.8)
    para(tf, "INTERNATIONAL BLACK SEA UNIVERSITY", size=14, color=T["muted"],
         font=F_MONO, align=PP_ALIGN.CENTER, first=True, space_after=2)
    para(tf, "School of Computer Science · Computer Science Program",
         size=12, color=T["muted"], font=F_MONO, align=PP_ALIGN.CENTER)
    tf = txt(s, 1.0, 2.5, 11.33, 1.9)
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
    s = chrome(prs, T, "The problem: easy tasks, huge models", 2, TOTAL)
    tf = txt(s, 0.57, 1.3, 12.2, 1.0)
    para(tf, [("You say: ", {"color": T["muted"]}),
              ("“set an alarm for 7:00.”", {"bold": True, "color": T["head"], "size": 20})],
         size=18, first=True, space_after=4)
    para(tf, "Today, an agent system answers that with a billion-dollar habit: send it to the biggest model available and let it think.",
         size=15, color=T["text"])
    box(s, 0.57, 2.5, 12.19, 2.5, fill=T["panel"], line=T["border"])
    tf = txt(s, 0.92, 2.75, 11.5, 2.1)
    para(tf, "WHAT THE BIG-MODEL HABIT COSTS", size=12, color=T["muted"],
         font=F_MONO, bold=True, first=True, space_after=10)
    for name, desc in [
        ("It doesn't fit", "a model big enough to reason reliably does not run on a phone"),
        ("It's slow and costs money", "seconds and a cloud bill, for a task a human does with one tap"),
        ("It leaks", "the request carries personal context that never needed to leave the device"),
        ("And it is still wrong", "we will show that even a 35-billion-parameter model fails on real phone settings"),
    ]:
        para(tf, [(name, {"bold": True, "color": T["head"]}),
                  ("  —  " + desc, {"color": T["text"]})], size=14, space_after=8,
             line_spacing=1.12)
    box(s, 0.57, 5.35, 12.19, 1.15, fill=T["panel2"], line=T["border"])
    tf = txt(s, 0.9, 5.35, 11.6, 1.15, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, [("Setting an alarm is an easy task. ", {"color": T["text"]}),
              ("Why does it need a model that can write poetry?",
               {"bold": True, "color": T["head"], "size": 17})],
         size=15, first=True, space_after=2)
    para(tf, "This thesis asks: how little model does a phone action actually need?",
         size=13, color=T["muted"], space_after=0)


def s3_observation(prs, T):
    s = chrome(prs, T, "The observation: these tasks are repetitive", 3, TOTAL)
    tf = txt(s, 0.57, 1.3, 12.2, 0.5)
    para(tf, "Look at what people actually ask a phone to do. The same requests, over and over, with one word changing:",
         size=15, color=T["text"], first=True)
    box(s, 0.57, 2.0, 5.9, 2.35, fill=T["panel"], line=T["border"])
    tf = txt(s, 0.92, 2.22, 5.3, 2.0)
    para(tf, "THE REQUEST", size=11.5, color=T["muted"], font=F_MONO, bold=True,
         first=True, space_after=8)
    for q in ["“set an alarm for 7:00”", "“set an alarm for 8:30”",
              "“set an alarm for noon”"]:
        para(tf, q, size=15, color=T["head"], space_after=6)
    box(s, 6.83, 2.0, 5.93, 2.35, fill=T["panel"], line=T["border"])
    tf = txt(s, 7.18, 2.22, 5.3, 2.0)
    para(tf, "THE COMMAND", size=11.5, color=T["muted"], font=F_MONO, bold=True,
         first=True, space_after=8)
    for c, hl in [("clock alarm -t 7:00", "7:00"), ("clock alarm -t 8:30", "8:30"),
                  ("clock alarm -t noon", "noon")]:
        pre, post = c.split(hl)
        para(tf, [(pre, {"color": T["text"]}),
                  (hl, {"color": T["accent_text"], "bold": True}),
                  (post, {"color": T["text"]})],
             size=15, font=F_MONO, space_after=6)
    tf = txt(s, 0.57, 4.55, 12.2, 0.9)
    para(tf, [("The command never changes shape. Only the blank changes. ",
               {"bold": True, "color": T["head"]}),
              ("And there is exactly one right answer — the alarm is set for 7:00 or it is not.",
               {"color": T["text"]})], size=16, first=True, line_spacing=1.15)
    box(s, 0.57, 5.6, 12.19, 1.1, fill=T["panel2"], line=T["border"])
    tf = txt(s, 0.9, 5.6, 11.6, 1.1, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, [("So here is the idea: ", {"color": T["text"]}),
              ("make the command shape a fixed, deterministic template — and let a tiny model do the only creative part: filling in the blank.",
               {"bold": True, "color": T["head"], "size": 16})],
         size=15, first=True, space_after=0)


def s4_idea(prs, T):
    s = chrome(prs, T, "The idea: a reflex for the routine, a brain for the rest", 4, TOTAL)
    dy = 1.75
    node(s, T, 0.7, dy + 0.85, 1.75, 0.95, "request", size=13)
    arrow(s, 2.45, dy + 1.32, 3.15, dy + 1.32, T["muted"])
    node(s, T, 3.15, dy + 0.85, 1.6, 0.95, "Router", size=14, sub="seen this before?")
    arrow(s, 4.75, dy + 1.1, 5.85, dy + 0.55, T["accent_text"])
    arrow(s, 4.75, dy + 1.55, 5.85, dy + 2.1, T["muted"])
    tf = txt(s, 4.8, dy + 0.38, 1.0, 0.3)
    para(tf, "yes", size=10.5, color=T["accent_text"], font=F_MONO, first=True)
    tf = txt(s, 4.8, dy + 1.98, 1.0, 0.3)
    para(tf, "no", size=10.5, color=T["muted"], font=F_MONO, first=True)
    node(s, T, 5.85, dy + 0.1, 2.8, 0.95, "tiny model (2B)", accent=True, size=13.5,
         sub="fills the blank · one step")
    node(s, T, 5.85, dy + 1.75, 2.8, 0.95, "big model", size=13.5,
         sub="thinks it through · many steps")
    arrow(s, 8.65, dy + 0.57, 9.75, dy + 1.15, T["accent_text"])
    arrow(s, 8.65, dy + 2.22, 9.75, dy + 1.6, T["muted"])
    node(s, T, 9.75, dy + 0.85, 2.2, 0.95, "phone acts", size=13)
    y = 4.6
    rows = [
        ("It is the reflex-vs-thinking split from psychology",
         "practiced actions run fast and automatically; novel problems get slow, deliberate thought. We give the phone the same two speeds."),
        ("The tiny model is never asked to be clever",
         "it gets the template and the request, and extracts one thing: the value for the blank. It cannot invent a wrong command — the shape is fixed."),
        ("The big model is reserved for the rare, genuinely new request",
         "multi-step routines, vague asks, anything without a template. That is where thinking earns its cost."),
    ]
    for name, desc in rows:
        tf = txt(s, 0.7, y, 12.0, 0.7)
        para(tf, [("▸ ", {"color": T["accent_text"], "bold": True}),
                  (name, {"bold": True, "color": T["head"]}),
                  ("  —  " + desc, {"color": T["text"]})], size=13.5, first=True,
             space_after=0, line_spacing=1.12)
        y += 0.72


def s5_cheatsheet(prs, T):
    s = chrome(prs, T, "Where do the templates come from? Write them once.", 5, TOTAL)
    tf = txt(s, 0.57, 1.28, 12.2, 0.55)
    para(tf, "Nobody hand-writes templates at scale. We have a smart model write them — once, offline, like a cheat sheet.",
         size=15, color=T["text"], first=True)
    dy = 2.15
    node(s, T, 0.7, dy, 2.2, 0.95, "skill docs", size=13, sub="how the tool works")
    arrow(s, 2.9, dy + 0.47, 3.6, dy + 0.47, T["muted"])
    node(s, T, 3.6, dy, 2.3, 0.95, "smart model", size=13.5, sub="reads once, offline")
    arrow(s, 5.9, dy + 0.47, 6.6, dy + 0.47, T["accent_text"])
    node(s, T, 6.6, dy, 2.4, 0.95, "cheat sheet", accent=True, size=13.5,
         sub="a small JSON file")
    arrow(s, 9.0, dy + 0.47, 9.7, dy + 0.47, T["accent_text"])
    node(s, T, 9.7, dy, 3.1, 0.95, "tiny model uses it\nforever, on-device", size=12.5)
    y = 3.6
    rows = [
        ("The cheat sheet holds the knowledge, so the model doesn't have to",
         "the command shape, what goes in each blank, and sanity checks on the result"),
        ("It is a file you can read",
         "the usual way to compress a big model is to bake it into a smaller model's weights — a black box. A JSON file can be inspected, corrected, and shared. Adding a capability = adding a file."),
        ("Pay once, use thousands of times",
         "the smart model's cost is paid at writing time, not every time you set an alarm"),
        ("We play fair", "the smart model never sees our test tasks or answers, and a written cheat sheet is frozen — no quiet fixing after seeing what failed"),
    ]
    for name, desc in rows:
        tf = txt(s, 0.7, y, 12.0, 0.75)
        para(tf, [("▸ ", {"color": T["accent_text"], "bold": True}),
                  (name, {"bold": True, "color": T["head"]}),
                  ("  —  " + desc, {"color": T["text"]})], size=13.5, first=True,
             space_after=0, line_spacing=1.12)
        y += 0.78


def s6_testing(prs, T):
    s = chrome(prs, T, "How we tested it (without fooling ourselves)", 6, TOTAL)
    cards = [
        ("A FAKE PHONE", "A sandboxed settings backend",
         "every task runs on a fresh copy of the phone's state; the copy is destroyed afterward — no real device, no network, nothing persists"),
        ("JUDGE THE OUTCOME, NOT THE WORDS", "Did the phone end up right?",
         "a command can look perfect and do the wrong thing — so we only check the final state, and fail the task if anything else was touched"),
        ("THREE DIFFICULTY LEVELS", "From friendly to realistic",
         "409 one-shot tasks across 7 tools · a clean, helpful settings interface · a faithful copy of Android's messy one, which accepts wrong values silently"),
        ("EVERY NUMBER IS A SAVED RUN", "No hand-edited results",
         "each figure cites the log file it came from; models run one at a time; all models are quantized to fit a real phone's memory"),
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
    para(tf, "To measure the executor alone, routing is assumed correct in these tests — the router is measured separately (slide 9).",
         size=12, color=T["muted"], first=True, align=PP_ALIGN.CENTER)


def s7_result1(prs, T):
    s = chrome(prs, T, "Result 1 — The cheat sheet replaces 17× the parameters", 7, TOTAL)
    tf = txt(s, 0.57, 1.25, 12.2, 0.45)
    para(tf, "Same tasks, same scoring. How often does each setup produce the correct command?",
         size=13.5, color=T["muted"], first=True)
    bar_chart(s, T, 1.1, 2.15, 6.7, 3.55, [
        ("2B alone", 30, "bar_gray", "free-form"),
        ("4B alone*", 10, "bar_gray", "free-form"),
        ("35B alone", 100, "strong", "free-form"),
        ("2B + cheat\nsheet", 100, "accent", "one step"),
    ])
    tf = txt(s, 1.1, 6.35, 6.7, 0.35)
    para(tf, "*4B ran with a small context window (a known confound) — the point: size alone is not a reliable lever",
         size=10, color=T["muted"], first=True)
    x = 8.45
    rows = [
        ("100% = 100%", "the tiny model with a cheat sheet matches the 35B model that reasons freely — at ~17× fewer parameters"),
        ("<1 s vs 6.4 s", "one step on the phone, versus a multi-step conversation that has to run in the cloud"),
        ("72/72 vs 14/72", "holds on the full task set too: with the sheet, everything passes; without it, the same tiny model gets 1 in 5"),
    ]
    y = 2.05
    for big, small in rows:
        box(s, x, y, 4.3, 1.42, fill=T["panel"], line=T["border"])
        tf = txt(s, x + 0.28, y + 0.16, 3.8, 1.15)
        para(tf, big, size=17, color=T["accent_text"], bold=True, font=F_MONO,
             first=True, space_after=3)
        para(tf, small, size=11, color=T["text"], line_spacing=1.12, space_after=0)
        y += 1.58


def s8_result2(prs, T):
    s = chrome(prs, T, "Result 2 — Why even the big model fails on a real phone", 8, TOTAL)
    tf = txt(s, 0.57, 1.25, 12.2, 0.8)
    para(tf, [("On realistic Android settings, the 35B model scores only ",
               {"color": T["text"]}),
              ("62.5%", {"bold": True, "color": T["head"], "font": F_MONO}),
              (". Its mistakes reveal that “hard” is really two different problems:",
               {"color": T["text"]})], size=15, first=True, line_spacing=1.15)
    # two kinds of hard
    box(s, 0.57, 2.2, 5.9, 2.6, fill=T["panel"], line=T["border"])
    tf = txt(s, 0.92, 2.42, 5.3, 2.25)
    para(tf, "FINDING THE RIGHT KNOB", size=11.5, color=T["muted"], font=F_MONO,
         bold=True, first=True, space_after=4)
    para(tf, "Which setting controls this?", size=15, color=T["head"], bold=True,
         space_after=6)
    para(tf, "This is searchable. The big model explores the interface, lists the settings, and finds the right one. Being smarter helps.",
         size=12.5, color=T["text"], line_spacing=1.18, space_after=6)
    para(tf, "✓ solved by scale", size=13, color=T["accent_text"], font=F_MONO,
         bold=True, space_after=0)
    box(s, 6.83, 2.2, 5.93, 2.6, fill=T["panel"], line=T["border"])
    tf = txt(s, 7.18, 2.42, 5.3, 2.25)
    para(tf, "KNOWING THE SECRET CODE", size=11.5, color=T["muted"], font=F_MONO,
         bold=True, first=True, space_after=4)
    para(tf, "What value does it expect?", size=15, color=T["head"], bold=True,
         space_after=6)
    para(tf, "“Total silence” is the number 2. “Largest font” is the string 1.30. That is written nowhere. The model guesses — and guesses wrong the same way every time.",
         size=12.5, color=T["text"], line_spacing=1.18, space_after=6)
    para(tf, "✗ no amount of thinking helps", size=13, color=T["accent_text"],
         font=F_MONO, bold=True, space_after=0)
    # evidence strip
    box(s, 0.57, 5.0, 12.19, 0.95, fill=T["panel"], line=T["border"])
    tf = txt(s, 0.9, 5.13, 11.6, 0.75)
    para(tf, [("Real example:  ", {"color": T["muted"]}),
              ("“DND, total silence”", {"color": T["text"]}),
              ("  →  correct: ", {"color": T["muted"]}),
              ("zen_mode 2", {"font": F_MONO, "bold": True, "color": T["accent_text"]}),
              ("   the 35B answered: ", {"color": T["muted"]}),
              ("1", {"font": F_MONO, "color": T["text"]}),
              ("  — every single time it was asked.", {"color": T["muted"]})],
         size=13, first=True, space_after=0)
    box(s, 0.57, 6.15, 12.19, 0.72, fill=T["panel2"], line=T["border"])
    tf = txt(s, 0.9, 6.15, 11.6, 0.72, anchor=MSO_ANCHOR.MIDDLE)
    para(tf, [("The secret codes live in the cheat sheet. ", {"bold": True, "color": T["head"]}),
              ("With it, the tiny model reaches 80% — beating the 35B that reasons from scratch.",
               {"color": T["text"]})], size=15, first=True, space_after=0)


def s9_honest(prs, T):
    s = chrome(prs, T, "What we can claim — and what is still broken", 9, TOTAL)
    cols = [
        ("THE TEACHER MATTERS", "80% vs 60%", [
            "cheat sheets written by a strong cloud model: the tiny model passes 80% of tasks",
            "written by a mid-size local model: 60% — it bakes its own wrong guesses into the sheet",
            "the tiny model faithfully executes whatever it is given, right or wrong — so write the sheet with the best teacher you have",
        ]),
        ("THE MATH WORKS OUT", "pays off after ~10 uses", [
            "writing a cheat sheet costs roughly 10,000 tokens of a smart model, once",
            "each later use saves ~1,000 tokens and 5+ seconds, and runs on the phone",
            "for anything you do daily, that is a 100–1000× win; one-off requests just go to the big model",
        ]),
        ("STILL BROKEN: THE PICKER", "66–85%", [
            "executing a chosen template is basically solved (96–100%)",
            "choosing which template a request matches — the router — is not; it confuses similar-looking options",
            "we say this plainly: the router is now the open problem, and it is where our future work points",
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
    s = chrome(prs, T, "Future work — in order of how much each would help", 10, TOTAL)
    rows = [
        ("1", "Let the teacher look at the real phone",
         "today the cheat-sheet writer works from documentation alone, so some secret codes stay guesses; give it read-only access to a real device and guesses become observed facts"),
        ("2", "Take arithmetic away from the model",
         "converting “80% brightness” to the number 204 is math, not language — do it with a plain function inside the cheat sheet, so neither model can get it wrong"),
        ("3", "Fix the picker (the router)",
         "the right template is almost always in the top 3 candidates; the failure is choosing between look-alikes — better selection prompting, or a small trained chooser"),
        ("4", "Let cheat sheets improve from their own mistakes",
         "run the sheet, watch what fails on a practice device, rewrite, repeat 2–3 times — a mediocre teacher climbs toward cloud quality; the on-phone part stays a frozen single step"),
        ("5", "Learn new cheat sheets from the user",
         "if you do the same three-step routine every night, that repetition can be mined into a new template — plus privacy-safe sharing of sheets between users"),
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
    para(tf, "All of it is planned inside one small, transparent agent framework (Pi) — the executor and the big-model loop share a single runtime.",
         size=12.5, color=T["muted"], first=True, align=PP_ALIGN.CENTER)


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
    for fn in (s1_title, s2_problem, s3_observation, s4_idea, s5_cheatsheet,
               s6_testing, s7_result1, s8_result2, s9_honest, s10_future,
               s11_thanks):
        fn(prs, T)
    path = os.path.join(OUT, f"ALFRED-defense-plain-{theme_name}.pptx")
    prs.save(path)
    print("wrote", path)


if __name__ == "__main__":
    for name in THEMES:
        build(name)
