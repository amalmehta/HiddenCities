"""Pictures and map data for the static site."""
import json
import numpy as np
from PIL import Image, ImageDraw


def hillshade(dtm, res, exaggeration=2.0, azimuths=(315, 45, 135, 225), altitude=45):
    """Average of four light directions, so no single sun angle hides a feature."""
    z = np.where(np.isfinite(dtm), dtm, np.nanmedian(dtm) if np.isfinite(dtm).any() else 0) * exaggeration
    dy, dx = np.gradient(z, res)
    slope = np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    alt = np.radians(altitude)
    out = np.zeros_like(z, dtype="float64")
    for az in azimuths:
        a = np.radians(360 - az + 90)
        out += np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(a - aspect)
    out = np.clip(out / len(azimuths), 0, 1)
    out[~np.isfinite(dtm)] = np.nan
    return out


WARM_LO = np.array([58, 50, 44])     # warm near-black
WARM_HI = np.array([247, 241, 232])  # warm off-white
NODATA = np.array([226, 220, 210])
TERRACOTTA = (196, 98, 64)


def stretch(shade):
    """Spread the middle 98 % of shading values over the full range, so low mounds show."""
    ok = np.isfinite(shade)
    if not ok.any():
        return shade
    lo, hi = np.percentile(shade[ok], [1, 99])
    return np.where(ok, np.clip((shade - lo) / max(hi - lo, 1e-6), 0, 1) * 0.85 + 0.15, np.nan)


def to_png(shade, path, marks=(), scale=2):
    v = np.nan_to_num(stretch(shade), nan=-1)
    rgb = (WARM_LO + (WARM_HI - WARM_LO) * np.clip(v, 0, 1)[..., None]).astype("uint8")
    rgb[v < 0] = NODATA
    img = Image.fromarray(rgb).resize((shade.shape[1] * scale, shade.shape[0] * scale), Image.LANCZOS)
    if marks:
        d = ImageDraw.Draw(img)
        for r, c, rad in marks:
            R = max(4, rad * scale)
            d.ellipse([c * scale - R, r * scale - R, c * scale + R, r * scale + R], outline=TERRACOTTA, width=2)
    img.quantize(64, method=Image.Quantize.MEDIANCUT).save(path, optimize=True)


def write_geojson(path, features):
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))


def point(lon, lat, props):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props}
