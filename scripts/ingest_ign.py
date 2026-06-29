#!/usr/bin/env python3
"""Ingesta del GeoPackage del IGN (Trío de eclipses) -> GeoJSON por capa.

Uso:
    python scripts/ingest_ign.py [ruta/al/eclipse2026.gpkg]

Si no se pasa ruta, usa el primer .gpkg en data/.
Convierte cada capa a EPSG:4326 (lon,lat) y escribe data/ign_<capa>.geojson,
imprimiendo un resumen para identificar la franja de totalidad y las curvas de
ocultación/duración. Tras ejecutarlo, cableamos las capas elegidas al mapa.
"""
from __future__ import annotations

import glob
import sys
from pathlib import Path

import geopandas as gpd
import pyogrio

DATA = Path(__file__).resolve().parent.parent / "data"


def find_gpkg(arg: str | None) -> Path:
    if arg:
        p = Path(arg)
        if p.exists():
            return p
    for f in sorted(glob.glob(str(DATA / "*.gpkg"))):
        return Path(f)
    sys.exit(
        "No encuentro ningún .gpkg. Descarga el GeoPackage del IGN en data/ "
        "(centrodedescargas.cnig.es/CentroDescargas/eclipses -> "
        "'Eclipse total de Sol de 12 de agosto de 2026. Curvas de nivel') y reejecuta."
    )


def main() -> None:
    gpkg = find_gpkg(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"== GeoPackage: {gpkg} ({gpkg.stat().st_size / 1e6:.1f} MB) ==\n")

    layers = pyogrio.list_layers(str(gpkg))  # [(name, geom_type), ...]
    print(f"Capas ({len(layers)}):")
    for name, gtype in layers:
        print(f"  - {name}  [{gtype}]")
    print()

    for name, gtype in layers:
        try:
            gdf = gpd.read_file(str(gpkg), layer=name)
        except Exception as exc:
            print(f"!! leyendo {name}: {exc}")
            continue

        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        safe = "".join(c if c.isalnum() else "_" for c in name)[:40]
        out = DATA / f"ign_{safe}.geojson"
        gdf.to_file(out, driver="GeoJSON")

        cols = [c for c in gdf.columns if c != "geometry"]
        bounds = [round(b, 3) for b in gdf.total_bounds]
        print(f"[{name}] -> {out.name}")
        print(f"   geom={gtype}  features={len(gdf)}  crs={gdf.crs.to_epsg() if gdf.crs else '?'}")
        print(f"   cols={cols}")
        print(f"   bounds(lon/lat)={bounds}")
        if cols:
            print(f"   sample={gdf[cols].head(3).to_dict('records')}")
        print()


if __name__ == "__main__":
    main()
