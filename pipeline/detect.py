"""Find mound-like structures in a bare-earth terrain model.

Idea: a 'white top-hat'. Imagine pressing a flat 61 m board up from under the
ground surface: it cannot follow anything narrower than the board. The gap
between the real ground and where the board reaches is the local relief, which
is high on small mounds and zero on broad hills and even slopes.
"""
from dataclasses import dataclass
import numpy as np
from scipy import ndimage

from . import config as C


@dataclass
class Structure:
    row: float
    col: float
    area_m2: float
    height_m: float
    elongation: float


def local_relief(dtm: np.ndarray, res: float, window_m: float = C.TOPHAT_WINDOW_M,
                 edge_m: float = C.EDGE_BUFFER_M) -> np.ndarray:
    """Ground height minus its morphological opening (white top-hat). NaN = no data."""
    if dtm.ndim != 2:
        raise ValueError("dtm must be a 2-D array")
    valid = np.isfinite(dtm)
    if not valid.any():
        return np.full(dtm.shape, np.nan, dtype="float32")
    size = max(3, int(round(window_m / res)) | 1)
    hi = np.nanmax(dtm) + 1000.0
    z = np.where(valid, dtm, hi).astype("float64")      # no-data cannot pull the minimum down
    opened = ndimage.maximum_filter(ndimage.minimum_filter(z, size=size), size=size)
    lrm = (z - opened).astype("float32")
    lrm[~valid] = np.nan
    # Next to no-data the opening is unreliable and the ground is thinly sampled (strip edges):
    # blank a rim of at least half a window, or edge_m, whichever is wider.
    rim_px = max(size // 2, int(round(edge_m / res)))
    rim = (ndimage.distance_transform_edt(valid) <= rim_px) & valid if (~valid).any() else np.zeros_like(valid)
    lrm[rim] = np.nan
    return lrm


def detect(dtm: np.ndarray, res: float,
           min_relief=C.MIN_RELIEF_M, min_area=C.MIN_AREA_M2, max_area=C.MAX_AREA_M2,
           max_elong=C.MAX_ELONGATION, window_m=C.TOPHAT_WINDOW_M) -> list[Structure]:
    lrm = local_relief(dtm, res, window_m)
    mask = np.nan_to_num(lrm, nan=0.0) >= min_relief
    labels, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if n == 0:
        return []
    px = res * res
    out = []
    for i, sl in enumerate(ndimage.find_objects(labels), start=1):
        m = labels[sl] == i
        area = m.sum() * px
        if area < min_area or area > max_area:
            continue
        rr, cc = np.nonzero(m)
        if len(rr) >= 3:
            cov = np.cov(np.vstack([rr, cc]))
            ev = np.sort(np.linalg.eigvalsh(cov))
            elong = float(np.sqrt(ev[1] / max(ev[0], 1e-6)))
        else:
            elong = 1.0
        if elong > max_elong:
            continue
        out.append(Structure(row=float(rr.mean() + sl[0].start), col=float(cc.mean() + sl[1].start),
                             area_m2=float(area), height_m=float(np.nanmax(lrm[sl][m])), elongation=elong))
    return out
