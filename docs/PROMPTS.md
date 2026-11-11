# Prompt Log

## 2026-11-11 — Kick-off: read the spec and start the build

1. "find hidden cities artifacts from nasa + ground data: build this project. Read find hidden cities artifacts from nasa + ground data.md in this folder and build what it describes, following its META-INSTRUCTIONS exactly."
   → Read the spec; listed the lessons that apply; pushed back on the idea and asked the first round of scoping questions before building anything.
   → Five rounds of questions settled the scope: real discovery in the Maya lowlands on NASA G-LiHT lidar, structures grouped into cities, a rule calibrated on known sites, exact coordinates only after expert review, a public repo on GitHub Pages. Answers were multiple choice with no added notes.
   → Built the pipeline (18 tests on synthetic terrain), ran it on 20 real strip segments (57.8 km²), and built the map site and docs. Finding: no recorded open-list site lies inside the strips, so the city rule fell back to a labelled ranking. A by-eye audit of the top 16 led to a strip-edge buffer; the result is 285 clusters, about half of which look natural.
