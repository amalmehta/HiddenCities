"""Sample data with a known answer: three lidar strips, two recorded 'cities',
one unrecorded city more than 2 km from both, plus things that must NOT count
(a broad natural hill, a road embankment, single-pixel noise, a no-data hole)."""
import numpy as np
from affine import Affine
from pyproj import Transformer

from .gazetteer import Site

EPSG = 32615
RES = 1.0
SHAPE = (400, 2000)            # rows (across strip) x cols (along strip), metres
ORIGINS = [(800000, 1990000), (800000, 1993000), (806000, 1996000)]   # top-left x, y of each strip


def bump(z, r, c, h, radius):
    rr, cc = np.ogrid[:z.shape[0], :z.shape[1]]
    z += h * np.exp(-((rr - r) ** 2 + (cc - c) ** 2) / (2 * (radius / 2) ** 2))


def city(z, rng, r0, c0, n, spread=120):
    for _ in range(n):
        bump(z, r0 + rng.normal(0, spread / 3), c0 + rng.normal(0, spread), rng.uniform(0.9, 2.5), rng.uniform(8, 16))
    bump(z, r0, c0, 8.0, 30)                     # one tall temple mound


def make_area(seed=7):
    rng = np.random.default_rng(seed)
    tiles = []
    from .run import Tile
    cities_xy = []
    for k, (x0, y0) in enumerate(ORIGINS):
        z = 50 + 0.002 * np.arange(SHAPE[1])[None, :] + np.zeros(SHAPE)       # gentle regional slope
        z = z + rng.normal(0, 0.03, SHAPE)                                  # sensor noise
        if k == 0:
            bump(z, 200, 1500, 20.0, 600)                                    # broad natural hill: not a mound
            z[100:106, 200:500] += 1.5                                       # road embankment: too long and thin
            z[300, 900] += 3.0                                               # single-pixel spike
            z[50:120, 1700:1850] = np.nan                                    # no-data hole
            for _ in range(4):                                               # a few scattered house mounds
                bump(z, rng.uniform(50, 350), rng.uniform(100, 1000), 1.2, 10)
        city(z, rng, 200, 700 if k != 0 else 600, 30)
        cities_xy.append((x0 + (700 if k != 0 else 600), y0 - 200))
        z[:15, :] = np.nan                                                   # ragged strip edge
        tr = Affine(RES, 0, x0, 0, -RES, y0)
        zz = z.astype("float32")
        tiles.append(Tile(f"synthetic_l0s{k}", (lambda zz=zz, tr=tr: (zz, tr, RES))))
    inv = Transformer.from_crs(EPSG, 4326, always_xy=True)
    sites = []
    for name, (x, y) in zip(["Recorded City A", "Recorded City B"], cities_xy[:2]):
        lon, lat = inv.transform(x + 40, y - 30)                              # list points are a bit off
        sites.append(Site(name, lon, lat, [{"source": "synthetic", "id": name, "url": ""}]))
    lon, lat = inv.transform(cities_xy[0][0] + 5000, cities_xy[0][1] - 15000)  # a listed site far from any lidar
    sites.append(Site("Site Without Lidar", lon, lat, [{"source": "synthetic", "id": "far", "url": ""}]))
    return tiles, sites, EPSG
