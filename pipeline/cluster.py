"""Group structures into settlement clusters (DBSCAN: points linked through neighbours within eps)."""
from dataclasses import dataclass, field
import numpy as np
from sklearn.cluster import DBSCAN

from . import config as C


@dataclass
class Cluster:
    x: float
    y: float
    n: int
    max_h: float
    members: np.ndarray = field(repr=False)   # indices into the structure arrays
    extent_m: float = 0.0


def cluster(xy: np.ndarray, heights: np.ndarray, eps: float, min_samples: int = C.MIN_SAMPLES) -> list[Cluster]:
    """xy: (n, 2) projected metres. Returns clusters; noise points are dropped."""
    if len(xy) == 0:
        return []
    lab = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(xy)
    out = []
    for k in sorted(set(lab) - {-1}):
        idx = np.nonzero(lab == k)[0]
        p = xy[idx]
        out.append(Cluster(x=float(p[:, 0].mean()), y=float(p[:, 1].mean()), n=len(idx),
                           max_h=float(heights[idx].max()), members=idx,
                           extent_m=float(np.hypot(*(p.max(0) - p.min(0))))))
    return out
