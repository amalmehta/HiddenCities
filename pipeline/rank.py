"""Rank candidate clusters and apply coordinate privacy."""
import math
import numpy as np

from . import config as C


def cell_centre(lon, lat, step=C.PRIVACY_GRID_DEG):
    """Centre of the grid cell containing (lon, lat). Used for unreviewed candidates."""
    return (round((math.floor(lon / step) + 0.5) * step, 4), round((math.floor(lat / step) + 0.5) * step, 4))


def cell_id(lon, lat, step=C.PRIVACY_GRID_DEG):
    cx, cy = cell_centre(lon, lat, step)
    return f"{abs(cy):.2f}{'N' if cy >= 0 else 'S'}{abs(cx):.2f}{'W' if cx < 0 else 'E'}"


def rank(cands, to_lonlat, sites, sites_xy, reviewed=frozenset()):
    """cands: Cluster list (already > 2 km from recorded sites).
    Returns (public, private): public has cell centres unless reviewed; private keeps exact points."""
    order = sorted(cands, key=lambda c: (-c.n, -c.max_h, c.x, c.y))
    per_cell, public, private = {}, [], []
    for r, c in enumerate(order, start=1):
        lon, lat = to_lonlat(c.x, c.y)
        cid = cell_id(lon, lat)
        per_cell[cid] = per_cell.get(cid, 0) + 1
        ident = f"HC-{cid}-{per_cell[cid]}"
        if len(sites_xy):
            d = np.hypot(sites_xy[:, 0] - c.x, sites_xy[:, 1] - c.y)
            j = int(d.argmin())
            near = {"name": sites[j].name, "km": round(float(d[j]) / 1000, 1)}
        else:
            near = None
        exact = ident in reviewed
        plon, plat = (round(lon, 5), round(lat, 5)) if exact else cell_centre(lon, lat)
        public.append({"id": ident, "rank": r, "n": c.n, "max_h": round(c.max_h, 1),
                       "extent_m": int(round(c.extent_m, -1)), "nearest": near,
                       "lon": plon, "lat": plat, "exact": exact})
        private.append({"id": ident, "lon": lon, "lat": lat, "x": c.x, "y": c.y})
    return public, private
