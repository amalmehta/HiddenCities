# Hidden Cities — Setup, Run, Use

## Look at the map

Open the published site (GitHub Pages), or view it locally:

```bash
python3 -m http.server 8000 --directory site
```

Then open http://localhost:8000. Opening `index.html` straight from disk won't work, because browsers block `fetch` from `file://`.

**Using it**
- The list on the right ranks the places to check.
- Click a row or a square on the map to open its dossier: the lidar picture, the numbers, and why it ranks where it does.
- Switch the picture between *Terrain* and *Mounds marked* to see what the detector found.
- Compare it with a *Recorded site* lower in the list.
- Keyboard: `→` / `j` next, `←` / `k` previous, `Esc` back to the list, `⌘ ,` settings.

## Regenerate the results

You need [uv](https://docs.astral.sh/uv/). Python and every library are pinned in `pyproject.toml` and `uv.lock`.

```bash
uv sync
uv run python -m pipeline.run              # real data: downloads ~160 MB once into data/raw/
uv run python -m pipeline.run --synthetic  # sample data with a known answer, no network
uv run pytest -q                           # 18 tests: detector, clustering, calibration, privacy, end to end
```

The real run takes about 10–15 minutes on a laptop, mostly downloading and drawing pictures. It writes to `site/data/` (public) and `data/private/candidates_exact.json` (exact points, git-ignored).

## Mark a candidate as reviewed

When an archaeologist has looked at a candidate:
1. Add its ID to `data/reviews.json`, e.g. `{"reviewed": ["HC-18.05N90.15W-1"]}`.
2. Re-run the pipeline. Only reviewed candidates get exact coordinates on the public map.

IDs are based on the ranking within each grid cell, so check the ID again after any re-run that changes the parameters.

## Change the area or the thresholds

- Every tunable number is in `pipeline/config.py`, labelled INVENTED, FITTED or DECIDED.
- `--neighbours N` widens the test area along each strip.
- `--dataset MX13E_Britton` switches to the East strips (UTM 16N).
