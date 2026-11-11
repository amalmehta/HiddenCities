"""One command regenerates everything the site shows.

    uv run python -m pipeline.run                # real test area (downloads ~tens of MB once)
    uv run python -m pipeline.run --synthetic    # sample data, no network
"""
import argparse, json, re, shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

import numpy as np
import shapely
import shapely.ops
from pyproj import Transformer

from . import config as C
from .calibrate import calibrate, _score
from .cluster import cluster
from .detect import detect
from .gazetteer import Site, parse, dedupe
from .rank import rank
from .render import hillshade, to_png, write_geojson, point


@dataclass
class Tile:
    name: str
    load: Callable  # () -> (dtm float32 with NaN, affine transform, res metres)


def strip_width_m(valid, res):
    """Rough swath width: valid area divided by the strip's long-axis length."""
    rr, cc = np.nonzero(valid[::4, ::4])
    if len(rr) < 10:
        return float("nan")
    p = np.vstack([rr, cc]).T * 4 * res
    p = p - p.mean(0)
    ev, evec = np.linalg.eigh(np.cov(p.T))
    proj = p @ evec[:, -1]
    length = proj.max() - proj.min()
    return float(valid.sum() * res * res / max(length, 1))


def analyse(tiles, sites, epsg, out_dir: Path, private_dir: Path, reviewed=frozenset(), meta=None):
    fwd = Transformer.from_crs(4326, epsg, always_xy=True)
    inv = Transformer.from_crs(epsg, 4326, always_xy=True)
    to_lonlat = lambda x, y: tuple(float(v) for v in inv.transform(x, y))
    if sites:
        sx, sy = fwd.transform([s.lon for s in sites], [s.lat for s in sites])
        sites, sites_xy = dedupe(sites, np.c_[sx, sy], C.SITE_DEDUPE_M)
    else:
        sites_xy = np.zeros((0, 2))

    xs, ys, hs, areas, tile_of = [], [], [], [], []
    eligible = set()
    footprints, widths, area_m2, tbounds = [], [], 0.0, []
    for ti, t in enumerate(tiles):
        dtm, tr, res = t.load()
        tbounds.append((tr.c, tr.f + tr.e * dtm.shape[0], tr.c + tr.a * dtm.shape[1], tr.f))
        valid = np.isfinite(dtm)
        area_m2 += valid.sum() * res * res
        widths.append(strip_width_m(valid, res))
        for s in detect(dtm, res):
            x, y = tr @ (s.col + 0.5, s.row + 0.5)
            xs.append(x); ys.append(y); hs.append(s.height_m); areas.append(s.area_m2); tile_of.append(ti)
        # lidar footprint as 25 m cells
        b = max(1, int(round(25 / res)))
        H, W = valid.shape[0] // b * b, valid.shape[1] // b * b
        blk = valid[:H, :W].reshape(H // b, b, W // b, b).any(axis=(1, 3))
        r, c = np.nonzero(blk)
        if len(r):
            x0, y0 = tr @ (c * b, r * b)
            x1, y1 = tr @ ((c + 1) * b, (r + 1) * b)
            footprints.append(shapely.union_all(shapely.box(x0, y1, x1, y0)))
        # which recorded sites have lidar nearby
        rad = int(C.SITE_COVER_M / res)
        for j, (px, py) in enumerate(sites_xy):
            col, row = ~tr @ (px, py)
            r0, c0 = int(row), int(col)
            if -rad <= r0 < dtm.shape[0] + rad and -rad <= c0 < dtm.shape[1] + rad:
                win = valid[max(0, r0 - rad):r0 + rad + 1, max(0, c0 - rad):c0 + rad + 1]
                if win.any():
                    eligible.add(j)

    xy = np.c_[xs, ys] if xs else np.zeros((0, 2))
    h = np.array(hs)
    elig = sorted(eligible)
    area_km2 = area_m2 / 1e6
    rule = calibrate(xy, h, sites_xy[elig], area_km2, all_sites_xy=sites_xy)
    cl = cluster(xy, h, rule.eps)
    passing, _, cand = _score(xy, cl, sites_xy[elig], sites_xy, rule.min_n, rule.min_h)
    public, private = rank(cand, to_lonlat, sites, sites_xy, reviewed)

    # ---- outputs -------------------------------------------------------------
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "img").mkdir(parents=True)
    private_dir.mkdir(parents=True, exist_ok=True)
    (private_dir / "candidates_exact.json").write_text(json.dumps(private, indent=1))

    # pictures: crop around each candidate / eligible site from the tile holding it
    from functools import lru_cache
    loaded = lru_cache(maxsize=2)(lambda i: tiles[i].load())

    def crop(x, y, label, marks_xy):
        for i, (bx0, by0, bx1, by1) in enumerate(tbounds):
            if not (bx0 <= x <= bx1 and by0 <= y <= by1):
                continue
            dtm, tr, res = loaded(i)
            col, row = ~tr @ (x, y)
            if 0 <= row < dtm.shape[0] and 0 <= col < dtm.shape[1]:
                hp = int(C.DOSSIER_HALF_M / res)
                r0, c0 = int(row) - hp, int(col) - hp
                win = np.full((2 * hp, 2 * hp), np.nan, dtype="float32")
                rs, cs = max(0, r0), max(0, c0)
                re_, ce = min(dtm.shape[0], r0 + 2 * hp), min(dtm.shape[1], c0 + 2 * hp)
                win[rs - r0:re_ - r0, cs - c0:ce - c0] = dtm[rs:re_, cs:ce]
                shade = hillshade(win, res)
                to_png(shade, out_dir / "img" / f"{label}.png")
                mk = []
                for mx, my, ma in marks_xy:
                    mc, mr = ~tr @ (mx, my)
                    if 0 <= mr - r0 < 2 * hp and 0 <= mc - c0 < 2 * hp:
                        mk.append((mr - r0, mc - c0, np.sqrt(ma / np.pi) / res + 3))
                to_png(shade, out_dir / "img" / f"{label}-marked.png", marks=mk)
                return True
        return False

    by_id = {p["id"]: c for p, c in zip(public, sorted(cand, key=lambda c: (-c.n, -c.max_h, c.x, c.y)))}
    for p in public:
        c = by_id[p["id"]]
        m = [(xy[i, 0], xy[i, 1], areas[i]) for i in c.members]
        p["img"] = crop(c.x, c.y, p["id"], m) if p["rank"] <= C.DOSSIER_TOP else False

    fp_m = shapely.union_all(footprints) if footprints else shapely.Polygon()

    site_feats = []
    for j, s in enumerate(sites):
        props = {"name": s.name, "sources": s.sources, "in_lidar": j in eligible}
        if j in eligible:
            caught = [c for c in passing if (np.hypot(xy[c.members, 0] - sites_xy[j, 0],
                                                      xy[c.members, 1] - sites_xy[j, 1]) <= C.SITE_MATCH_M).any()]
            props["caught"] = bool(caught)
            props["n"] = max((c.n for c in caught), default=0)
            near = np.hypot(xy[:, 0] - sites_xy[j, 0], xy[:, 1] - sites_xy[j, 1]) <= C.DOSSIER_HALF_M * 1.5 if len(xy) else []
            m = [(xy[i, 0], xy[i, 1], areas[i]) for i in np.nonzero(near)[0]] if len(xy) else []
            props["img"] = crop(sites_xy[j, 0], sites_xy[j, 1], f"site-{j}", m)
            props["id"] = f"site-{j}"
        elif not fp_m.is_empty:
            # just outside the strip: show the nearest part of the strip, so a reader can judge by eye
            pt = shapely.Point(sites_xy[j])
            dist = fp_m.distance(pt)
            if dist <= C.EDGE_M:
                q = shapely.ops.nearest_points(fp_m, pt)[0]
                near = np.hypot(xy[:, 0] - q.x, xy[:, 1] - q.y) <= C.DOSSIER_HALF_M * 1.5 if len(xy) else []
                m = [(xy[i, 0], xy[i, 1], areas[i]) for i in np.nonzero(near)[0]] if len(xy) else []
                props["edge_m"] = int(round(dist / 10) * 10)
                props["img"] = crop(q.x, q.y, f"site-{j}", m)
                props["id"] = f"site-{j}"
        site_feats.append(point(round(s.lon, 5), round(s.lat, 5), props))
    write_geojson(out_dir / "sites.geojson", site_feats)
    write_geojson(out_dir / "candidates.geojson",
                  [point(p["lon"], p["lat"], {k: v for k, v in p.items() if k not in ("lon", "lat")}) for p in public])

    fp = shapely.simplify(fp_m, 10)
    fp_ll = shapely.transform(fp, lambda a: np.c_[inv.transform(a[:, 0], a[:, 1])])
    (out_dir / "footprint.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
                                                    "geometry": json.loads(shapely.to_geojson(fp_ll))}]}))

    summary = {
        "generated": date.today().isoformat(),
        "tiles": len(tiles), "lidar_km2": round(area_km2, 1),
        "strip_width_m": round(float(np.nanmedian(widths)), 0) if widths and np.isfinite(widths).any() else None,
        "structures": int(len(xy)), "clusters": len(cl),
        "recorded_sites_nearby": len(sites), "recorded_sites_in_lidar": len(elig),
        "rule": rule.to_dict(), "candidates": len(public),
        "bounds": list(fp_ll.bounds) if not fp_ll.is_empty else None,
        "params": {k: getattr(C, k) for k in ("TOPHAT_WINDOW_M", "MIN_RELIEF_M", "MIN_AREA_M2", "MAX_AREA_M2",
                                               "MAX_ELONGATION", "MIN_SAMPLES", "SITE_MATCH_M", "SITE_COVER_M",
                                               "UNRECORDED_M", "PRIVACY_GRID_DEG", "TARGET_RECALL", "EDGE_M", "DOSSIER_TOP")},
        **(meta or {}),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


# ---- real data ---------------------------------------------------------------

def _parse_name(key):
    m = re.search(r"/([^/]+)_l(\d+)s(\d+)_DEM", key)
    return (m[1], int(m[2]), int(m[3])) if m else (key, -1, -1)


def test_area(headers, sites_xy, neighbours=2):
    """Tiles whose bounds hold a recorded site, plus +/- `neighbours` segments on the same line."""
    hit = set()
    for h in headers:
        x0, y0, x1, y1 = h["bounds"]
        if len(sites_xy) and ((sites_xy[:, 0] >= x0) & (sites_xy[:, 0] <= x1) &
                              (sites_xy[:, 1] >= y0) & (sites_xy[:, 1] <= y1)).any():
            hit.add(_parse_name(h["key"]))
    keep = []
    for h in headers:
        p, l, s = _parse_name(h["key"])
        if any(p == hp and l == hl and abs(s - hs) <= neighbours for hp, hl, hs in hit):
            keep.append(h)
    return keep


def load_tile(path):
    def _load():
        import rasterio
        with rasterio.open(path) as d:
            a = d.read(1, masked=True).astype("float32").filled(np.nan)
            a[(a > 1e30) | (a < -1e4)] = np.nan
            return a, d.transform, float(abs(d.res[0]))
    return _load


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--synthetic", action="store_true", help="run on generated sample data (no network)")
    ap.add_argument("--dataset", default="MX13W_Britton")
    ap.add_argument("--neighbours", type=int, default=2)
    ap.add_argument("--out", type=Path, default=C.SITE_DATA)
    a = ap.parse_args(argv)
    reviewed = frozenset(json.loads(C.REVIEWS.read_text()).get("reviewed", [])) if C.REVIEWS.exists() else frozenset()

    if a.synthetic:
        from .synthetic import make_area
        tiles, sites, epsg = make_area()
        s = analyse(tiles, sites, epsg, a.out, C.PRIVATE / "synthetic", reviewed, meta={"mode": "synthetic"})
    else:
        from . import fetch
        wd, osm = fetch.sites_raw()
        sites = parse(wd, osm)
        epsg = C.DATASETS[a.dataset]["epsg"]
        fwd = Transformer.from_crs(4326, epsg, always_xy=True)
        sx, sy = fwd.transform([q.lon for q in sites], [q.lat for q in sites])
        heads = fetch.headers(a.dataset)
        chosen = test_area(heads, np.c_[sx, sy], a.neighbours)
        print(f"test area: {len(chosen)} tiles, {sum(h['bytes'] for h in chosen) / 1e6:.0f} MB")
        tiles = [Tile(h["key"].rsplit("/", 1)[-1], load_tile(fetch.tile(h["key"], h["bytes"]))) for h in chosen]
        # keep sites near the area only (for 'nearest site' and the map)
        x0 = min(h["bounds"][0] for h in chosen) - 20000; x1 = max(h["bounds"][2] for h in chosen) + 20000
        y0 = min(h["bounds"][1] for h in chosen) - 20000; y1 = max(h["bounds"][3] for h in chosen) + 20000
        near = [q for q, x, y in zip(sites, sx, sy) if x0 <= x <= x1 and y0 <= y <= y1]
        s = analyse(tiles, near, epsg, a.out, C.PRIVATE, reviewed, meta={
            "mode": "real", "dataset": a.dataset, "doi": C.DATASETS[a.dataset]["doi"],
            "tile_keys": [h["key"] for h in chosen]})
    print(json.dumps({k: v for k, v in s.items() if k not in ("params", "tile_keys")}, indent=1))


if __name__ == "__main__":
    main()
