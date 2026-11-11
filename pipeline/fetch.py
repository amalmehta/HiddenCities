"""Download and cache public inputs. Every file's source URL, size and fetch date go in data/manifest.json."""
import json, os, re, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from . import config as C

UA = {"User-Agent": "HiddenCitiesResearch/0.1 (open research script)"}
MANIFEST = C.ROOT / "data" / "manifest.json"
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")


def _get(url, data=None, timeout=180):
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _manifest_add(path, url, size):
    m = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    m[str(path.relative_to(C.ROOT))] = {"url": url, "bytes": size, "fetched": date.today().isoformat()}
    MANIFEST.write_text(json.dumps(m, indent=1, sort_keys=True))


def list_keys(dataset, product="DTM_1m"):
    """All object keys (and sizes) under a dataset/product prefix in the public bucket."""
    cache = C.RAW / f"keys_{dataset}_{product}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    keys, tok = [], None
    while True:
        u = f"{C.BUCKET}/raster?list-type=2&max-keys=1000&prefix={dataset}/{product}/"
        if tok:
            u += "&continuation-token=" + urllib.parse.quote(tok)
        x = _get(u).decode()
        keys += [[k, int(s)] for k, s in zip(re.findall(r"<Key>([^<]*)</Key>", x), re.findall(r"<Size>([^<]*)</Size>", x))]
        m = re.search(r"<NextContinuationToken>([^<]*)<", x)
        if not m:
            break
        tok = m.group(1)
    C.RAW.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(keys))
    return keys


def headers(dataset, product="DTM_1m"):
    """Bounds of every tile, read from remote file headers (a few KB each)."""
    import rasterio
    cache = C.RAW / f"headers_{dataset}_{product}.json"
    if cache.exists():
        return json.loads(cache.read_text())

    def one(k):
        with rasterio.open(f"/vsicurl/{C.BUCKET}/raster/{k[0]}") as d:
            return {"key": k[0], "bytes": k[1], "bounds": list(d.bounds), "epsg": d.crs.to_epsg() or C.DATASETS[dataset]["epsg"]}
    with ThreadPoolExecutor(16) as ex:
        h = list(ex.map(one, list_keys(dataset, product)))
    cache.write_text(json.dumps(h))
    return h


def tile(key, expected_bytes=None):
    """Download one tile unless an identical-size copy is cached. Returns its local path."""
    path = C.RAW / "tiles" / key
    if path.exists() and (expected_bytes is None or path.stat().st_size == expected_bytes):
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"{C.BUCKET}/raster/{key}"
    blob = _get(url, timeout=600)
    if expected_bytes is not None and len(blob) != expected_bytes:
        raise IOError(f"size mismatch for {key}: got {len(blob)}, expected {expected_bytes}")
    tmp = path.with_suffix(".part")
    tmp.write_bytes(blob)
    tmp.rename(path)
    _manifest_add(path, url, len(blob))
    return path


WIKIDATA_Q = """SELECT ?item ?itemLabel ?coord WHERE {{
 SERVICE wikibase:box {{ ?item wdt:P625 ?coord .
   bd:serviceParam wikibase:cornerSouthWest "Point({0} {1})"^^geo:wktLiteral .
   bd:serviceParam wikibase:cornerNorthEast "Point({2} {3})"^^geo:wktLiteral . }}
 ?item wdt:P31/wdt:P279* wd:Q839954 .
 SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,es". }} }}"""
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]


def sites_raw():
    """Wikidata (CC0) and OpenStreetMap (ODbL) archaeological sites in SITE_BBOX, cached."""
    C.RAW.mkdir(parents=True, exist_ok=True)
    wd, osm = C.RAW / "sites_wikidata.json", C.RAW / "sites_osm.json"
    if not wd.exists():
        url = "https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(WIKIDATA_Q.format(*C.SITE_BBOX))
        wd.write_bytes(_get(url))
        _manifest_add(wd, "https://query.wikidata.org/sparql (archaeological site, Q839954 + subclasses)", wd.stat().st_size)
    if not osm.exists():
        w, s, e, n = C.SITE_BBOX
        q = f'[out:json][timeout:120];nwr["historic"="archaeological_site"]({s},{w},{n},{e});out center tags;'
        last = None
        for ep in OVERPASS:
            try:
                osm.write_bytes(_get(ep, data=urllib.parse.urlencode({"data": q}).encode()))
                _manifest_add(osm, ep + " (historic=archaeological_site)", osm.stat().st_size)
                break
            except Exception as ex:  # try the next mirror
                last = ex
                time.sleep(2)
        else:
            raise IOError(f"all Overpass mirrors failed: {last}")
    return json.loads(wd.read_text()), json.loads(osm.read_text())
