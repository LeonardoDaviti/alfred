# AICT2026 Paper — A.L.F.R.E.D.

**Deadline:** 2026-05-30 23:59 (submission via https://www.aict.info)
**Format:** IEEE conference, **A4**, two-column, 4–6 pages preferred (max 8 with over-length fee)
**Track:** T04 — Machine Learning and other AI Techniques (locked)
**Abstract limit:** **100 words MAX** (cover-page rule)
**PDF check:** IEEE PDF eXpress conference ID `70383X` (mandatory before submission)
**See:** `docs/paper/submission_steps.md` for full step-by-step submission guide

## Layout

```
tex/
  main.tex              Master file
  refs.bib              Bibliography
  sections/
    00_abstract.tex     150 words
    01_introduction.tex 0.5 page
    02_related_work.tex 0.5 page
    03_system.tex       1.0 page
    04_methodology.tex  0.5 page
    05_evaluation.tex   1.0 page
    06_discussion.tex   0.5 page
    07_conclusion.tex   short
    08_disclosure.tex   AI usage statement
figures/                PNG/PDF figures
Makefile                pdflatex + bibtex + 2x pdflatex
```

## Build

Local (after `pacman -S texlive-most texlive-publishers texlive-bibtexextra`):
```
cd paper && make
```

Overleaf alternative: upload `tex/` as a project, set `main.tex` as the main document. IEEEtran.cls is preloaded.

## Status

- [x] Scaffolding
- [ ] Lit-review (Sprint 1)
- [ ] Abstract + outline (Sprint 2)
- [ ] Full draft (Sprint 3)
- [ ] ARS peer-review pass (Sprint 4)
- [ ] Citations + IEEE format (Sprint 5)
- [ ] AI disclosure + submit (Sprint 6)
