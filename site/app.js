"use strict";
// Hidden Cities: static map + ranked list + dossier. All text from data files is inserted with
// textContent (never innerHTML), because place names come from open, editable lists.

const $ = (s, el = document) => el.querySelector(s);
const el = (tag, props = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const k of kids) if (k != null) n.append(k);
  return n;
};
const fmt = (x, d = 0) => Number(x).toLocaleString("en", { maximumFractionDigits: d, minimumFractionDigits: d });
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---- preferences (this browser only) -------------------------------------------------
const PREF_KEYS = ["hc-theme", "hc-strips", "hc-sites"];
const pref = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : v; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode: fine */ } },
  clear() { try { PREF_KEYS.forEach(k => localStorage.removeItem(k)); } catch { } },
};
const themeNow = () => {
  const t = pref.get("hc-theme", "auto");
  return t === "auto" ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : t;
};
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

// ---- data ------------------------------------------------------------------------------
const state = { summary: null, cands: [], sites: [], footprint: null, selected: null };

async function load() {
  const get = p => fetch(`data/${p}`).then(r => { if (!r.ok) throw new Error(p); return r.json(); });
  const [summary, cands, sites, footprint] = await Promise.all(
    ["summary.json", "candidates.geojson", "sites.geojson", "footprint.geojson"].map(get));
  state.summary = summary;
  state.cands = cands.features;
  state.sites = sites.features;
  state.footprint = footprint;
}

// ---- list pane ----------------------------------------------------------------------------
function candTitle(p) { return `${fmt(p.n)} mounds in one cluster`; }
function candSub(p) {
  const near = p.nearest ? ` · ${fmt(p.nearest.km, 1)} km from ${p.nearest.name}` : "";
  return `tallest ${fmt(p.max_h, 1)} m${near}`;
}

function renderList() {
  const s = state.summary, r = s.rule;
  $("#lede").textContent = !state.cands.length ? "No place in this area passed the rule."
    : r.fallback
      ? `${fmt(state.cands.length)} clusters of ancient-looking mounds in NASA lidar, more than 2 km from any site in the open lists.`
      : `${fmt(state.cands.length)} ${state.cands.length === 1 ? "place" : "places"} in NASA lidar look like towns that no open list records.`;
  $("#sub").textContent = `From ${fmt(s.structures)} mound-like features in ${fmt(s.lidar_km2, 0)} km² of 2013 NASA G-LiHT lidar, southern Mexico.`;
  const stats = $("#stats"); stats.replaceChildren();
  const recall = r.eligible ? `${r.caught} of ${r.eligible}` : "0";
  [[recall, r.eligible ? "known sites the rule catches" : "known sites inside the strips"], [fmt(s.lidar_km2, 0) + " km²", "of lidar searched"],
   [fmt(r.per_100km2, 1), "candidates per 100 km²"]].forEach(([v, k]) =>
    stats.append(el("div", { class: "stat" }, el("div", { class: "v", text: v }), el("div", { class: "k", text: k }))));

  const list = $("#cand-list"); list.replaceChildren();
  $("#cand-count").textContent = state.cands.length ? `· ${state.cands.length}` : "";
  if (!state.cands.length) {
    list.append(el("li", { class: "empty" }, el("img", { src: "icon.svg", alt: "" }),
      el("p", { text: "Every dense cluster here lies within 2 km of a recorded site. That's a useful result: the open lists already cover this area." }),
      el("a", { href: "method.html#rule", text: "See how the rule is set" })));
  }
  state.cands.forEach((f, i) => {
    const p = f.properties;
    list.append(el("li", {}, el("button", { "data-id": p.id, onclick: () => openDossier(f, "cand") },
      el("span", { class: "rank", text: p.rank }),
      p.img ? el("img", { class: "thumb", src: `data/img/${p.id}.png`, alt: "", loading: i < 8 ? "eager" : "lazy" }) : el("span", { class: "thumb" }),
      el("span", {}, el("div", { class: "row-t", text: candTitle(p) }), el("div", { class: "row-s", text: candSub(p) })))));
  });

  const sl = $("#site-list"); sl.replaceChildren();
  const inLidar = state.sites.filter(compareSite);
  $("#site-count").textContent = inLidar.length ? `· ${inLidar.length}` : "";
  inLidar.forEach(f => {
    const p = f.properties;
    sl.append(el("li", {}, el("button", { "data-id": p.id, onclick: () => openDossier(f, "site") },
      el("span", { class: "rank site", text: "◆" }),
      p.img ? el("img", { class: "thumb", src: `data/img/${p.id}.png`, alt: "", loading: "lazy" }) : el("span", { class: "thumb" }),
      el("span", {}, el("div", { class: "row-t", text: p.name }),
        el("div", { class: "row-s", text: p.edge_m != null ? `${fmt(p.edge_m)} m outside the strip` : p.caught ? `caught by the rule · ${p.n} mounds` : "missed by the rule" })))));
  });
}

const compareSite = f => f.properties.in_lidar || f.properties.edge_m != null;

// ---- dossier ----------------------------------------------------------------------------
function openDossier(f, kind) {
  state.selected = { f, kind };
  const p = f.properties, pane = $("#dossier-pane");
  document.querySelectorAll("ol.list button").forEach(b => b.classList.toggle("on", b.dataset.id === p.id));
  const big = el("img", { class: "big", alt: kind === "cand" ? "Shaded lidar terrain around the candidate, 400 by 400 metres" : `Shaded lidar terrain around ${p.name}`, src: `data/img/${p.id}.png` });
  const seg = el("div", { class: "seg", role: "group", "aria-label": "Picture style" });
  const mk = (label, marked) => el("button", { "aria-pressed": String(!marked), onclick: e => {
    big.src = `data/img/${p.id}${marked ? "-marked" : ""}.png`;
    seg.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", String(b === e.currentTarget)));
  } }, label);
  seg.append(mk("Terrain", false), mk("Mounds marked", true));
  const s = state.summary;

  const body = [];
  if (kind === "cand") {
    body.push(el("p", { class: "lede" }, candTitle(p), el("span", { class: "tag", text: p.exact ? "reviewed" : "area only" })));
    body.push(p.img ? big : null, p.img ? seg : null);
    if (!p.img) body.push(el("p", { class: "sub", text: `Pictures are drawn for the top ${s.params.DOSSIER_TOP ?? 40} only, to keep the site small. Run the pipeline locally to draw the rest.` }));
    body.push(el("p", { class: "why", text:
      `Ranked ${p.rank} of ${state.cands.length}: ${p.n} mound-like features within a ${fmt(p.extent_m)} m stretch of the lidar strip, ` +
      `the tallest standing ${fmt(p.max_h, 1)} m above its surroundings.` +
      (p.nearest ? ` The nearest recorded site in the open lists, ${p.nearest.name}, is ${fmt(p.nearest.km, 1)} km away.` : "") }));
    body.push(el("dl", { class: "facts" },
      el("dt", { text: "Mounds" }), el("dd", { text: fmt(p.n) }),
      el("dt", { text: "Tallest" }), el("dd", { text: `${fmt(p.max_h, 1)} m (local relief)` }),
      el("dt", { text: "Stretch" }), el("dd", { text: `${fmt(p.extent_m)} m across` }),
      el("dt", { text: "Location" }), el("dd", { text: p.exact ? `${fmt(f.geometry.coordinates[1], 4)}°, ${fmt(f.geometry.coordinates[0], 4)}°` : "within the ~11 km square on the map" })));
    if (!p.exact) body.push(el("div", { class: "note" }, el("div", {},
      el("b", { text: "Why only an area? " }),
      "Looters use published coordinates. A candidate gets an exact point only after an archaeologist has looked at it.")));
    body.push(el("p", { class: "sub", text: "How to check it: compare the picture with a recorded site below. Real Maya mounds tend to sit in groups around small plazas; karst hills are rounder and scattered." }));
  } else {
    body.push(el("p", { class: "lede" }, p.name, el("span", { class: "tag blue", text: "recorded site" })));
    body.push(p.img ? big : null, p.img ? seg : null);
    if (p.edge_m != null) body.push(el("p", { class: "why", text:
      `${p.name}'s listed point lies ${fmt(p.edge_m)} m outside the lidar strip, so it can't set the rule. ` +
      "The picture shows the nearest part of the strip. If mounds crowd that edge, the site probably reaches into the strip." }));
    else body.push(el("p", { class: "why", text: p.caught
      ? `The rule catches ${p.name}: a cluster of ${p.n} mounds lies within ${s.params.SITE_MATCH_M} m of its listed point.`
      : `The rule misses ${p.name}. Either too little of the site falls inside the strip, or its mounds are lower or sparser than the rule asks for.` }));
    const src = el("p", { class: "sub" }, "Listed in: ");
    p.sources.forEach((q, i) => { if (i) src.append(", "); src.append(el("a", { href: q.url, target: "_blank", rel: "noopener", text: q.source === "osm" ? "OpenStreetMap" : "Wikidata" })); });
    body.push(src);
  }
  pane.replaceChildren(el("button", { class: "back", onclick: closeDossier, "aria-label": "Back to the list" }, "← All places"), ...body.filter(Boolean));
  pane.scrollTop = 0;
  pane.classList.remove("off-right");
  $("#list-pane").classList.add("off-left");
  const [lon, lat] = f.geometry.coordinates;
  map && map.easeTo({ center: [lon, lat], zoom: kind === "cand" && !p.exact ? 10 : 13, duration: reduceMotion ? 0 : 600 });
  highlight(p.id);
}

function closeDossier() {
  state.selected = null;
  $("#dossier-pane").classList.add("off-right");
  $("#list-pane").classList.remove("off-left");
  highlight(null);
}

function step(d) {
  if (!state.selected) return;
  const arr = state.selected.kind === "cand" ? state.cands : state.sites.filter(compareSite);
  const i = arr.indexOf(state.selected.f);
  const n = arr[(i + d + arr.length) % arr.length];
  if (n) openDossier(n, state.selected.kind);
}

// ---- map -------------------------------------------------------------------------------
let map = null;
// OpenFreeMap: free OpenStreetMap vector tiles, no key or sign-up (openfreemap.org)
const basemap = t => `https://tiles.openfreemap.org/styles/${t === "dark" ? "dark" : "positron"}`;
const LIDAR_CREDIT = 'Lidar: NASA G-LiHT (2013), reprocessed by B. Britton via <a href="https://opentopography.org">OpenTopography</a>';

// One square per ~11 km cell (many candidates share a cell). Clicking a square opens its best-ranked candidate.
function cellPolys() {
  const h = (state.summary.params.PRIVACY_GRID_DEG || 0.1) / 2;
  const feats = [], byKey = new Map();
  state.cellIndex = new Map();
  state.cands.forEach(f => {
    const [x, y] = f.geometry.coordinates, p = f.properties;
    if (p.exact) { state.cellIndex.set(p.id, feats.length); feats.push(f); return; }
    const key = `${x},${y}`;
    if (!byKey.has(key)) {
      byKey.set(key, feats.length);
      feats.push({ type: "Feature", properties: { ...p, count: 0 },
        geometry: { type: "Polygon", coordinates: [[[x - h, y - h], [x + h, y - h], [x + h, y + h], [x - h, y + h], [x - h, y - h]]] } });
    }
    const i = byKey.get(key);
    feats[i].properties.count++;
    state.cellIndex.set(p.id, i);
  });
  return { type: "FeatureCollection", features: feats };
}

function addLayers() {
  const terra = cssVar("--terra"), accent = cssVar("--accent");
  map.addSource("strips", { type: "geojson", data: state.footprint });
  map.addSource("cands", { type: "geojson", data: cellPolys(), generateId: true });
  // at low zoom an 11 km square is a few pixels, so also mark each cell with a dot
  map.addSource("celldots", { type: "geojson", data: { type: "FeatureCollection", features: state.cands
    .filter((f, i, all) => !f.properties.exact && all.findIndex(g => !g.properties.exact && g.geometry.coordinates.join() === f.geometry.coordinates.join()) === i)
    .map(f => ({ type: "Feature", geometry: f.geometry, properties: f.properties })) } });
  map.addSource("sites", { type: "geojson", data: { type: "FeatureCollection", features: state.sites }, generateId: true });
  map.addLayer({ id: "cells", type: "fill", source: "cands", filter: ["==", ["geometry-type"], "Polygon"],
    paint: { "fill-color": terra, "fill-opacity": ["case", ["boolean", ["feature-state", "on"], false], 0.32, 0.14] } });
  map.addLayer({ id: "cells-line", type: "line", source: "cands", filter: ["==", ["geometry-type"], "Polygon"],
    paint: { "line-color": terra, "line-width": ["case", ["boolean", ["feature-state", "on"], false], 2.5, 1.2] } });
  map.addLayer({ id: "strips", type: "fill", source: "strips", paint: { "fill-color": "#8C7B6B", "fill-opacity": 0.45 } });
  map.addLayer({ id: "strips-line", type: "line", source: "strips", paint: { "line-color": "#8C7B6B", "line-width": 1, "line-opacity": 0.8 } });
  map.addLayer({ id: "cell-dots", type: "circle", source: "celldots", maxzoom: 8.5,
    paint: { "circle-color": terra, "circle-radius": 5, "circle-stroke-color": cssVar("--bg"), "circle-stroke-width": 1.5 } });
  map.addLayer({ id: "cand-pts", type: "circle", source: "cands", filter: ["==", ["geometry-type"], "Point"],
    paint: { "circle-color": terra, "circle-radius": 7, "circle-stroke-width": 2, "circle-stroke-color": "#fff" } });
  map.addLayer({ id: "sites", type: "circle", source: "sites",
    paint: { "circle-color": accent, "circle-radius": ["case", ["has", "id"], 6.5, 3.5],
      "circle-opacity": ["case", ["has", "id"], 1, 0.55],
      "circle-stroke-width": ["case", ["boolean", ["feature-state", "on"], false], 3, 1.2], "circle-stroke-color": "#fff" } });
  applyLayerPrefs();
}

function applyLayerPrefs() {
  if (!map || !map.getLayer("strips")) return;
  const vis = b => (b ? "visible" : "none");
  ["strips", "strips-line"].forEach(l => map.setLayoutProperty(l, "visibility", vis(pref.get("hc-strips", "1") === "1")));
  map.setLayoutProperty("sites", "visibility", vis(pref.get("hc-sites", "1") === "1"));
}

let lit = [];
function highlight(id) {
  if (!map || !map.getSource("cands")) return;
  lit.forEach(([src, fid]) => map.setFeatureState({ source: src, id: fid }, { on: false }));
  lit = [];
  if (id == null) return;
  const ci = state.cellIndex ? state.cellIndex.get(id) : undefined;
  if (ci != null) lit.push(["cands", ci]);
  const si = state.sites.findIndex(f => f.properties.id === id);
  if (si >= 0) lit.push(["sites", si]);
  lit.forEach(([src, fid]) => map.setFeatureState({ source: src, id: fid }, { on: true }));
}

function initMap() {
  const b = state.summary.bounds;
  map = new maplibregl.Map({ container: "map", style: basemap(themeNow()), bounds: b ? [[b[0], b[1]], [b[2], b[3]]] : undefined,
    fitBoundsOptions: { padding: 40 }, attributionControl: { compact: true, customAttribution: LIDAR_CREDIT }, fadeDuration: 150 });
  map.__style = basemap(themeNow());
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
  // Runs after every style (re)load, including theme switches, so our layers always come back.
  map.on("style.load", () => {
    if (map.getSource("cands")) return;
    lit = [];
    addLayers();
    if (state.selected) highlight(state.selected.f.properties.id);
  });
  const clickable = ["cell-dots", "cells", "cand-pts", "sites"];
  clickable.forEach(l => {
    map.on("mouseenter", l, () => map.getCanvas().style.cursor = "pointer");
    map.on("mouseleave", l, () => map.getCanvas().style.cursor = "");
  });
  map.on("click", e => {
    const hits = map.queryRenderedFeatures(e.point, { layers: clickable.filter(l => map.getLayer(l)) });
    if (!hits.length) return;
    const id = hits[0].properties.id;
    const c = state.cands.find(f => f.properties.id === id);
    if (c) return openDossier(c, "cand");
    const s = state.sites.find(f => f.properties.id === id && compareSite(f));
    if (s) openDossier(s, "site");
  });
}

function setTheme(t) {
  pref.set("hc-theme", t);
  if (t === "auto") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = t;
  if (map && map.__style !== basemap(themeNow())) { map.__style = basemap(themeNow()); map.setStyle(map.__style, { diff: false }); }
}

// ---- settings, keys, start --------------------------------------------------------------
function initSettings() {
  const dlg = $("#settings");
  $("#open-settings").addEventListener("click", () => dlg.showModal());
  $("#theme").value = pref.get("hc-theme", "auto");
  $("#theme").addEventListener("change", e => setTheme(e.target.value));
  $("#show-strips").checked = pref.get("hc-strips", "1") === "1";
  $("#show-sites").checked = pref.get("hc-sites", "1") === "1";
  $("#show-strips").addEventListener("change", e => { pref.set("hc-strips", e.target.checked ? "1" : "0"); applyLayerPrefs(); });
  $("#show-sites").addEventListener("change", e => { pref.set("hc-sites", e.target.checked ? "1" : "0"); applyLayerPrefs(); });
  $("#clear-prefs").addEventListener("click", () => {
    pref.clear(); $("#theme").value = "auto"; $("#show-strips").checked = $("#show-sites").checked = true;
    setTheme("auto"); pref.clear(); applyLayerPrefs();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { if (pref.get("hc-theme", "auto") === "auto") setTheme("auto"); });
  document.addEventListener("keydown", e => {
    if ((e.metaKey || e.ctrlKey) && e.key === ",") { e.preventDefault(); dlg.open ? dlg.close() : dlg.showModal(); return; }
    if (dlg.open || /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) return;
    if (e.key === "Escape" && state.selected) closeDossier();
    if (e.key === "ArrowRight" || e.key === "j") step(1);
    if (e.key === "ArrowLeft" || e.key === "k") step(-1);
  });
}

setTimeout(() => document.body.classList.remove("intro"), 1200);
initSettings();
load().then(() => {
  renderList();
  if (window.maplibregl) initMap();
  else $("#map").append(el("p", { class: "empty", text: "The map library didn't load. The list still works; try reloading." }));
}).catch(err => {
  console.error(err);
  $("#lede").textContent = "The results didn't load.";
  $("#sub").textContent = "Check your connection and reload. If you're running this locally, serve the site folder over HTTP (see the instructions).";
});
