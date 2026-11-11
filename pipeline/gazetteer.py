"""Recorded sites from open lists, normalised and de-duplicated."""
import re
from dataclasses import dataclass, field
import numpy as np


@dataclass
class Site:
    name: str
    lon: float
    lat: float
    sources: list = field(default_factory=list)   # [{"source": "wikidata"|"osm", "id":..., "url":...}]


def parse(wikidata_json, osm_json) -> list[Site]:
    raw = []
    seen = set()
    for r in wikidata_json.get("results", {}).get("bindings", []):
        qid = r["item"]["value"].rsplit("/", 1)[-1]
        m = re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", r.get("coord", {}).get("value", ""))
        if not m or (qid, m[0]) in seen:
            continue
        seen.add((qid, m[0]))
        name = r.get("itemLabel", {}).get("value", qid)
        if re.fullmatch(r"Q\d+", name):
            name = "(unnamed)"
        raw.append(Site(name, float(m[1]), float(m[2]),
                        [{"source": "wikidata", "id": qid, "url": f"https://www.wikidata.org/wiki/{qid}"}]))
    for e in osm_json.get("elements", []):
        lat = e.get("lat", e.get("center", {}).get("lat"))
        lon = e.get("lon", e.get("center", {}).get("lon"))
        if lat is None or lon is None:
            continue
        tags = e.get("tags", {})
        raw.append(Site(tags.get("name") or tags.get("name:es") or "(unnamed)", float(lon), float(lat),
                        [{"source": "osm", "id": f"{e['type']}/{e['id']}",
                          "url": f"https://www.openstreetmap.org/{e['type']}/{e['id']}"}]))
    return raw


def dedupe(sites: list[Site], xy: np.ndarray, radius_m: float) -> tuple[list[Site], np.ndarray]:
    """Merge entries closer than radius_m (single linkage). Named entries win the name."""
    n = len(sites)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(n):
        d = np.hypot(xy[i + 1:, 0] - xy[i, 0], xy[i + 1:, 1] - xy[i, 1])
        for j in np.nonzero(d <= radius_m)[0] + i + 1:
            parent[find(j)] = find(i)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    out, oxy = [], []
    for idx in groups.values():
        named = [i for i in idx if sites[i].name != "(unnamed)"]
        lead = sites[(named or idx)[0]]
        src = [s for i in idx for s in sites[i].sources]
        uniq = list({(s["source"], s["id"]): s for s in src}.values())
        out.append(Site(lead.name, float(np.mean([sites[i].lon for i in idx])),
                        float(np.mean([sites[i].lat for i in idx])), uniq))
        oxy.append(xy[idx].mean(0))
    return out, np.array(oxy).reshape(-1, 2)
