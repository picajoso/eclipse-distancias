#!/usr/bin/env python3
"""Construye las capas de overlay web a partir del GeoPackage del IGN.

Salida (en data/):
  - obscuration.geojson : bandas de % de oscurecimiento (>= 50%), campo 'pct' (0-100)
  - totality.geojson    : bandas de duración de totalidad (>= 10s), campo 'dur_s'

Las bandas EMBALDOSAN (cada punto en una sola), así que pintan un gradiente
limpio. Se recortan a la Península+Baleares y se simplifican para aligerar.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pyogrio
from shapely.geometry import box

ROOT = Path(__file__).resolve().parent.parent
GPKG = ROOT / "Eclipses.gpkg"
DATA = ROOT / "data"
IBERIA = box(-11.0, 35.0, 4.7, 44.8)  # lon/lat; incluye Atlántico gallego y Baleares
SIMPLIFY = 0.004  # grados (~400 m)


def layer_name(prefix: str) -> str:
    for n, _ in pyogrio.list_layers(str(GPKG)):
        if n.startswith(prefix):
            return n
    raise SystemExit(f"Capa '{prefix}…' no encontrada en {GPKG}")


def prep(gdf) -> gpd.GeoDataFrame:
    gdf = gdf.to_crs(4326)
    gdf = gpd.clip(gdf, IBERIA)
    gdf["geometry"] = gdf["geometry"].simplify(SIMPLIFY, preserve_topology=True)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    return gdf


def main() -> None:
    if not GPKG.exists():
        raise SystemExit(f"Falta {GPKG}. Coloca el GeoPackage del IGN en la raíz.")

    # --- Oscurecimiento ---
    obs = prep(gpd.read_file(str(GPKG), layer=layer_name("oscurez")))
    obs = obs.rename(columns={"Oscurecimiento": "obsc"})
    obs["pct"] = (obs["obsc"] * 100).round(1)
    obs = obs[obs["pct"] >= 50.0][["pct", "geometry"]].sort_values("pct")
    out_obs = DATA / "obscuration.geojson"
    obs.to_file(out_obs, driver="GeoJSON")

    # --- Duración de totalidad (descartamos la banda 0 = exterior sin totalidad) ---
    dur = prep(gpd.read_file(str(GPKG), layer=layer_name("durtot")))
    dur = dur.rename(columns={"DuracionTotalSeg": "dur_s"})
    dur["dur_s"] = dur["dur_s"].astype(int)
    dur = dur[dur["dur_s"] >= 10][["dur_s", "geometry"]].sort_values("dur_s")
    out_dur = DATA / "totality.geojson"
    dur.to_file(out_dur, driver="GeoJSON")

    # --- Diagnóstico ---
    print(f"obscuration.geojson: {len(obs)} bandas, pct={sorted(obs['pct'].unique())}  "
          f"({out_obs.stat().st_size/1024:.0f} KB)")
    print(f"totality.geojson:    {len(dur)} bandas, dur_s={sorted(dur['dur_s'].unique())}  "
          f"({out_dur.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
