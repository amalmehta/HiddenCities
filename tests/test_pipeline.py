import json, math
import numpy as np
import pytest

from pipeline import config as C
from pipeline.detect import detect, local_relief
from pipeline.cluster import cluster
from pipeline.calibrate import calibrate
from pipeline.rank import rank, cell_centre
from pipeline.gazetteer import parse, dedupe, Site
from pipeline.synthetic import bump


def flat(shape=(300, 300)):
    return np.full(shape, 100.0, dtype="float32")


# ---- detector: normal cases -----------------------------------------------------
def test_planted_mounds_found_once_with_right_height():
    z = flat()
    for r, c, h in [(60, 60, 1.0), (150, 200, 2.5), (240, 90, 4.0)]:
        bump(z, r, c, h, 14)
    s = detect(z, 1.0)
    assert len(s) == 3
    got = sorted(round(x.height_m, 1) for x in s)
    assert got == pytest.approx([1.0, 2.5, 4.0], rel=0.1)


def test_works_on_a_slope():
    z = flat() + 0.05 * np.arange(300)[None, :]          # 5% slope
    bump(z, 150, 150, 1.5, 14)
    s = detect(z, 1.0)
    assert len(s) == 1 and s[0].height_m == pytest.approx(1.5, rel=0.15)


# ---- detector: things that must not count -----------------------------------------
def test_plain_slope_gives_nothing():
    assert detect(flat() + 0.1 * np.arange(300)[None, :], 1.0) == []


def test_broad_natural_hill_rejected():
    z = flat((800, 800)); bump(z, 400, 400, 20.0, 600)
    assert detect(z, 1.0) == []


def test_single_pixel_spike_rejected():
    z = flat(); z[100, 100] += 3
    assert detect(z, 1.0) == []


def test_road_embankment_rejected():
    z = flat(); z[100:106, 20:280] += 1.5
    assert detect(z, 1.0) == []


def test_nodata_hole_makes_no_false_mounds():
    z = flat(); z[100:160, 100:160] = np.nan
    assert detect(z, 1.0) == []


def test_mound_at_tile_edge_still_found():
    z = flat(); bump(z, 150, 8, 2.0, 12)
    assert len(detect(z, 1.0)) == 1


def test_mounds_near_strip_edge_are_ignored():
    # strip edges are thinly sampled; mounds within EDGE_BUFFER_M of no-data are dropped
    z = flat(); z[:, :40] = np.nan
    bump(z, 100, 40 + int(C.EDGE_BUFFER_M) - 25, 2.0, 12)   # inside the buffer
    bump(z, 220, 40 + int(C.EDGE_BUFFER_M) + 40, 2.0, 12)   # clear of it
    found = detect(z, 1.0)
    assert len(found) == 1 and abs(found[0].row - 220) < 3


# ---- detector: failure cases ------------------------------------------------------
def test_all_nodata_returns_empty():
    assert detect(np.full((50, 50), np.nan, dtype="float32"), 1.0) == []


def test_wrong_shape_is_a_clear_error():
    with pytest.raises(ValueError, match="2-D"):
        local_relief(np.zeros(10), 1.0)


# ---- clustering and calibration --------------------------------------------------
def test_two_groups_two_clusters_noise_dropped():
    rng = np.random.default_rng(0)
    a = rng.normal([0, 0], 20, (15, 2)); b = rng.normal([1000, 0], 20, (10, 2)); noise = np.array([[5000, 5000]])
    xy = np.vstack([a, b, noise]); h = np.ones(len(xy))
    cl = cluster(xy, h, eps=50)
    assert sorted(c.n for c in cl) == [10, 15]


def test_calibration_hits_target_recall_and_flags_unrecorded():
    rng = np.random.default_rng(1)
    groups = [rng.normal(c, 30, (25, 2)) for c in ([0, 0], [4000, 0], [8000, 0])]
    xy = np.vstack(groups); h = np.r_[np.full(24, 1.0), 6.0, np.full(24, 1.0), 6.0, np.full(24, 1.0), 6.0]
    sites = np.array([[10, 0], [4010, 0]])            # third group is unrecorded
    r = calibrate(xy, h, sites, area_km2=10)
    assert not r.fallback and r.recall >= 0.9 and r.candidates == 1


def test_calibration_falls_back_without_sites():
    xy = np.random.default_rng(2).normal(0, 30, (20, 2))
    r = calibrate(xy, np.ones(20), np.zeros((0, 2)), area_km2=1)
    assert r.fallback and math.isnan(r.recall)
    # the summary must stay strict JSON (browsers reject NaN)
    json.loads(json.dumps(r.to_dict(), allow_nan=False))


# ---- privacy ------------------------------------------------------------------
class _C:
    def __init__(self, x, y, n, h): self.x, self.y, self.n, self.max_h, self.extent_m = x, y, n, h, 100


def test_unreviewed_candidates_only_get_cell_centres():
    inv = lambda x, y: (-90.123456, 18.987654)
    pub, priv = rank([_C(0, 0, 10, 3)], inv, [], np.zeros((0, 2)))
    assert (pub[0]["lon"], pub[0]["lat"]) == cell_centre(-90.123456, 18.987654) == (-90.15, 18.95)
    assert pub[0]["exact"] is False and priv[0]["lon"] == -90.123456


def test_reviewed_candidate_gets_exact_point():
    inv = lambda x, y: (-90.123456, 18.987654)
    pub, _ = rank([_C(0, 0, 10, 3)], inv, [], np.zeros((0, 2)), reviewed={"HC-18.95N90.15W-1"})
    assert pub[0]["exact"] and pub[0]["lon"] == -90.12346


# ---- gazetteer ------------------------------------------------------------------
def test_wikidata_duplicates_and_osm_merge():
    wd = {"results": {"bindings": [
        {"item": {"value": "http://www.wikidata.org/entity/Q1"}, "itemLabel": {"value": "Nadzca'an"}, "coord": {"value": "Point(-90.0 18.0)"}},
        {"item": {"value": "http://www.wikidata.org/entity/Q1"}, "itemLabel": {"value": "Nadzca'an"}, "coord": {"value": "Point(-90.0 18.0)"}},
        {"item": {"value": "http://www.wikidata.org/entity/Q2"}, "itemLabel": {"value": "Q2"}, "coord": {"value": "Point(-91.0 18.0)"}}]}}
    osm = {"elements": [{"type": "node", "id": 5, "lat": 18.001, "lon": -90.001, "tags": {}}]}
    s = parse(wd, osm)
    assert len(s) == 3 and s[1].name == "(unnamed)"
    xy = np.array([[0, 0], [100000, 0], [150, 0]], dtype=float)
    m, mxy = dedupe(s, xy, 500)
    assert len(m) == 2 and {q.name for q in m} == {"Nadzca'an", "(unnamed)"}
    assert len(next(q for q in m if q.name == "Nadzca'an").sources) == 2


# ---- end to end on sample data ---------------------------------------------------
def test_end_to_end_synthetic(tmp_path):
    from pipeline.run import analyse
    from pipeline.synthetic import make_area
    tiles, sites, epsg = make_area()
    s = analyse(tiles, sites, epsg, tmp_path / "out", tmp_path / "private")
    assert s["recorded_sites_in_lidar"] == 2 and s["recorded_sites_nearby"] == 3
    assert s["rule"]["recall"] == 1.0 and not s["rule"]["fallback"]
    assert s["candidates"] == 1                          # the unrecorded city, nothing else
    cand = json.loads((tmp_path / "out" / "candidates.geojson").read_text())["features"]
    priv = json.loads((tmp_path / "private" / "candidates_exact.json").read_text())
    lon, lat = cand[0]["geometry"]["coordinates"]
    assert (lon, lat) == cell_centre(priv[0]["lon"], priv[0]["lat"])
    assert (tmp_path / "out" / "img" / f"{cand[0]['properties']['id']}.png").exists()
    text = "".join(p.read_text() for p in (tmp_path / "out").glob("*.json*"))
    assert f"{priv[0]['lon']:.4f}" not in text           # exact point never leaks into site data
    assert 300 <= s["strip_width_m"] <= 420
