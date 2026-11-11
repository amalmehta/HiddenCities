"""Every tunable number in one place.

Each value is labelled:
  INVENTED  - a starting guess, not taken from any source; tuned on the test area.
  FITTED    - chosen by calibrate.py from recorded sites (these are search grids).
  DECIDED   - a project decision (privacy, scope), not a fact about the world.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"            # downloads, git-ignored
PRIVATE = ROOT / "data" / "private"    # exact candidate coordinates, git-ignored
REVIEWS = ROOT / "data" / "reviews.json"
SITE_DATA = ROOT / "site" / "data"

BUCKET = "https://opentopography.s3.sdsc.edu"
DATASETS = {  # OpenTopography G-LiHT 2013 bare-earth reprocessing (Britton)
    "MX13W_Britton": {"doi": "10.5069/G9Z899N1", "epsg": 32615},
    "MX13E_Britton": {"doi": "10.5069/G9TH8JX9", "epsg": 32616},
}
SITE_BBOX = (-94.5, 16.0, -86.5, 21.8)   # lon/lat box for recorded-site lists

# Detector (detect.py)
EDGE_BUFFER_M = 75         # DECIDED after the first real run: ground is poorly sampled along strip edges,
                           # which made beaded false mounds 30-70 m in from the edge (top-16 audit, 2026-11-11)
TOPHAT_WINDOW_M = 61      # INVENTED: features narrower than this count as 'on top of' the ground
MIN_RELIEF_M = 0.5        # INVENTED: lowest mound height we try to see
MIN_AREA_M2 = 50          # INVENTED: smallest footprint (~7 x 7 m house mound)
MAX_AREA_M2 = 2500        # INVENTED: largest footprint (~50 x 50 m platform)
MAX_ELONGATION = 5.0      # INVENTED: longer, thinner blobs are treated as ridges/roads

# Clustering and the city rule (cluster.py, calibrate.py)
MIN_SAMPLES = 3                                   # INVENTED: DBSCAN core size
EPS_GRID_M = [50, 75, 100, 150, 200]              # FITTED from this grid
MIN_N_GRID = [3, 5, 8, 12, 20, 30]                # FITTED from this grid
MIN_H_GRID = [0.5, 1.0, 2.0, 3.0, 5.0]            # FITTED from this grid
TARGET_RECALL = 0.90       # DECIDED (spec): rule must catch >= 90% of recorded sites
SITE_MATCH_M = 300         # INVENTED: a site point is 'caught' by a cluster member this close
SITE_COVER_M = 150         # INVENTED: a site counts only if lidar exists within this distance
UNRECORDED_M = 2000        # DECIDED (spec): candidates lie > 2 km from every recorded site
SITE_DEDUPE_M = 500        # INVENTED: list entries closer than this are one site

# Privacy (rank.py)
PRIVACY_GRID_DEG = 0.1     # DECIDED (Amal, round 2): unreviewed candidates snapped to ~11 km cells

# Rendering
DOSSIER_HALF_M = 200       # dossier picture covers 400 x 400 m
DOSSIER_TOP = 40           # DECIDED: pictures only for the top 40 candidates (keeps the site ~10 MB)
EDGE_M = 600               # INVENTED: recorded sites this close to the strip get a picture of the nearest strip edge
