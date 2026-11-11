"""Fit the city rule (eps, N, H) on recorded sites, so nothing is a made-up threshold.

recall(rule)  = caught recorded sites / recorded sites inside the lidar
density(rule) = candidates per 100 km^2 of lidar
Pick, among rules with recall >= TARGET_RECALL, the one with the lowest density
(fewest places to check); ties go to the stricter rule.
"""
from dataclasses import dataclass, asdict
import numpy as np

from . import config as C
from .cluster import cluster


@dataclass
class Rule:
    eps: float
    min_n: int
    min_h: float
    recall: float
    caught: int
    eligible: int
    candidates: int
    per_100km2: float
    fallback: bool = False

    def to_dict(self):
        d = asdict(self)
        if d["recall"] != d["recall"]:  # NaN is not valid JSON
            d["recall"] = None
        return d


def _near(px, py, xy, r):
    return len(xy) > 0 and bool((np.hypot(xy[:, 0] - px, xy[:, 1] - py) <= r).any())


def _score(xy, cl, sites_xy, ref, min_n, min_h):
    passing = [c for c in cl if c.n >= min_n and c.max_h >= min_h]
    caught = sum(any(_near(sx, sy, xy[c.members], C.SITE_MATCH_M) for c in passing) for sx, sy in sites_xy)
    cand = [c for c in passing if len(ref) == 0 or
            np.hypot(ref[:, 0] - c.x, ref[:, 1] - c.y).min() > C.UNRECORDED_M]
    return passing, caught, cand


def calibrate(xy, h, sites_xy, area_km2, all_sites_xy=None) -> Rule:
    """sites_xy: recorded sites with lidar coverage (eligible). all_sites_xy: every recorded
    site nearby, used for the 2 km 'unrecorded' test (defaults to sites_xy)."""
    sites_xy = np.asarray(sites_xy, dtype=float).reshape(-1, 2)
    ref = sites_xy if all_sites_xy is None else np.asarray(all_sites_xy, dtype=float).reshape(-1, 2)
    best = None
    for eps in C.EPS_GRID_M:
        cl = cluster(xy, h, eps)
        for n in C.MIN_N_GRID:
            for hh in C.MIN_H_GRID:
                _, caught, cand = _score(xy, cl, sites_xy, ref, n, hh)
                if not len(sites_xy):
                    continue
                r = Rule(eps, n, hh, caught / len(sites_xy), caught, len(sites_xy), len(cand),
                         100 * len(cand) / area_km2 if area_km2 > 0 else float("nan"))
                if r.recall >= C.TARGET_RECALL:
                    key = (r.per_100km2, -n, -hh, eps)
                    if best is None or key < best[0]:
                        best = (key, r)
    if best is not None:
        return best[1]
    # Fallback: no rule reaches the target (or no eligible sites): loosest rule; the site
    # then shows a ranked list with no yes/no cut-off and says so.
    eps, n, hh = C.EPS_GRID_M[1], C.MIN_N_GRID[0], C.MIN_H_GRID[0]
    _, caught, cand = _score(xy, cluster(xy, h, eps), sites_xy, ref, n, hh)
    return Rule(eps, n, hh, caught / len(sites_xy) if len(sites_xy) else float("nan"), caught,
                len(sites_xy), len(cand), 100 * len(cand) / area_km2 if area_km2 > 0 else float("nan"),
                fallback=True)
