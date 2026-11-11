# Hidden Cities — File Structure

| Path | What it is |
|---|---|
| `README.md` | What this is, the result, pictures, links |
| `pipeline/config.py` | Every threshold, each labelled INVENTED / FITTED / DECIDED |
| `pipeline/fetch.py` | Downloads lidar tiles and site lists; caches them in `data/raw/`; logs sources to `data/manifest.json` |
| `pipeline/gazetteer.py` | Wikidata + OpenStreetMap sites → one de-duplicated list |
| `pipeline/detect.py` | Local relief (white top-hat) → mound-like features |
| `pipeline/cluster.py` | DBSCAN grouping in metres |
| `pipeline/calibrate.py` | Fits the city rule on recorded sites (≥ 90 % recall, fewest candidates) |
| `pipeline/rank.py` | Ranking, IDs and the ~11 km privacy grid |
| `pipeline/render.py` | Hillshade pictures and GeoJSON helpers |
| `pipeline/run.py` | One command: fetch → detect → cluster → calibrate → rank → render |
| `pipeline/synthetic.py` | Sample strips with a known answer (two recorded cities, one unrecorded, decoys) |
| `tests/test_pipeline.py` | 18 tests: normal, edge and failure cases, privacy, end to end |
| `site/index.html`, `app.js`, `styles.css` | The map, list, dossier, settings and feedback tab |
| `site/method.html` | How it works, with equations, limits and references |
| `site/data/` | Generated results the site reads (summary, GeoJSON, pictures) |
| `site/icon.svg`, `icon-*.png` | App mark and favicon |
| `data/raw/` | Downloads (git-ignored, re-downloadable) |
| `data/private/` | Exact candidate coordinates (git-ignored, never published) |
| `data/manifest.json` | Source URL, size and fetch date of every download |
| `data/reviews.json` | Candidate IDs an archaeologist has reviewed |
| `docs/SYSTEM-DESIGN.md` | Architecture, decisions, threat model, scale, limits |
| `docs/INSTRUCTIONS.md` | Setup, run, use |
| `docs/PROMPTS.md` | Prompt log |
| `docs/outreach/` | Draft data-request emails (not sent) |
| `docs/REVIEW-CHECKLIST.md` | Manual checks that tests can't cover |
| `docs/screenshot.jpg`, `docs/icon-1024.png` | README pictures |
| `.github/workflows/pages.yml` | Publishes `site/` to GitHub Pages on each push to main |
| `.github/workflows/tests.yml` | Runs the tests on each push |
| `README.md` | The result, method, limits and how to reproduce |
| `find hidden cities artifacts from nasa + ground data.md` | The project spec, definitions, open questions and changelog |
