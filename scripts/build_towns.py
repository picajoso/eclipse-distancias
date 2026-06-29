#!/usr/bin/env python3
"""Construye data/towns_totality.geojson: poblaciones de España (OSM city|town)
dentro de la franja de totalidad (capa IGN), con su población (para priorizar
localidades reconocibles frente a pequeñas pedanías/suburbios).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import geopandas as gpd
import httpx
from shapely.geometry import Point
from shapely.ops import unary_union

DATA = Path(__file__).resolve().parent.parent / "data"
OVERPASS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
UA = "ruta-eclipse-2026/0.1 (eclipse trip planner)"

Q = """[out:json][timeout:90];
area["ISO3166-1"="ES"]->.a;
(node["place"="city"]["name"](area.a); node["place"="town"]["name"](area.a););
out body;"""


def _pop(tags):
    v = (tags or {}).get("population")
    if not v:
        return 0
    digits = re.sub(r"[^0-9]", "", str(v))
    return int(digits) if digits else 0


def fetch_towns():
    last = None
    for u in OVERPASS:
        try:
            r = httpx.post(u, data={"data": Q}, headers={"User-Agent": UA}, timeout=120.0)
            r.raise_for_status()
            return r.json()["elements"]
        except Exception as e:
            last = e
    raise RuntimeError(f"Overpass no disponible: {last}")


def main() -> None:
    els = fetch_towns()
    towns = {}
    for e in els:
        if "lat" not in e:
            continue
        tags = e.get("tags") or {}
        nm = tags.get("name")
        if not nm:
            continue
        key = (round(e["lat"], 4), round(e["lon"], 4))
        towns.setdefault(key, (nm, e["lat"], e["lon"], _pop(tags)))
    print(f"OSM city|town: {len(towns)} únicas, con población: {sum(1 for _,_,_,p in towns.values() if p)}")

    tot = gpd.read_file(DATA / "totality.geojson")
    geoms = list(tot.geometry)
    durs = list(tot["dur_s"])
    band = unary_union(geoms)

    feats = []
    for nm, lat, lon, pop in towns.values():
        p = Point(lon, lat)
        if not band.contains(p):
            continue
        if lon > 1.5 and lat < 40.3:  # Baleares (sin ruta por carretera)
            continue
        dur = 0
        for g, d in zip(geoms, durs):
            if g.contains(p):
                dur = int(d)
                break
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"name": nm, "lat": lat, "lon": lon, "dur": dur, "pop": pop},
        })

    feats.sort(key=lambda f: -f["properties"]["dur"])
    (DATA / "towns_totality.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False)
    )
    withpop = sum(1 for f in feats if f["properties"]["pop"])
    print(f"towns_totality.geojson: {len(feats)} en la franja | con población: {withpop}")
    for thr in (1000, 3000, 5000):
        print(f"  población >= {thr}: {sum(1 for f in feats if f['properties']['pop'] >= thr)}")
    for chk in ["Calatayud", "Calamocha", "Teruel", "Tarragona", "Guadalajara", "San Agustín del Guadalix", "Meco"]:
        hit = next((f for f in feats if f["properties"]["name"] == chk), None)
        print(f"  {chk}: {'SÍ pop='+str(hit['properties']['pop'])+' dur='+str(hit['properties']['dur']) if hit else 'no'}")


if __name__ == "__main__":
    main()
