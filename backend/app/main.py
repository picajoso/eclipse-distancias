"""API FastAPI para 'Ruta al Eclipse 2026'.

Endpoints (MVP):
  GET /                       -> health
  GET /eclipse/circumstances  -> circunstancias en un punto (motor OPALE)
  GET /eclipse/validation     -> los 4 puntos de verdad de campo, ya calculados

Los endpoints /contours, /destinations, /route y /pois se añaden en fases
posteriores.
"""
from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import eclipse, overlays, pois, routes
from .config import DATA_DIR, FRONTEND_DIR, ORIGIN_LAT, ORIGIN_LON, ORIGIN_NAME, VALIDATION_POINTS
from .httpclient import get_client

app = FastAPI(title="Ruta al Eclipse 2026", version="0.1.0")

# CORS abierto para desarrollo (frontend estático en otro origen).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health() -> dict:
    return {"status": "ok", "service": "ruta-eclipse-2026"}


@app.get("/eclipse/circumstances")
def circumstances(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """Circunstancias del eclipse en (lat, lon): totalidad, %, horarios CEST."""
    try:
        return eclipse.get_circumstances(lat, lon)
    except Exception as exc:  # OPALE caído / error de red
        raise HTTPException(status_code=502, detail=f"Error consultando OPALE: {exc}")


@app.get("/route")
def route(
    to_lat: float = Query(..., ge=-90, le=90),
    to_lon: float = Query(..., ge=-180, le=180),
    from_lat: float = Query(ORIGIN_LAT, ge=-90, le=90),
    from_lon: float = Query(ORIGIN_LON, ge=-180, le=180),
    profile: str = Query("driving"),
):
    """Ruta más rápida origen->destino + hora de salida para llegar a la totalidad."""
    try:
        travel = routes.get_route(from_lat, from_lon, to_lat, to_lon, profile)
        plan = routes.plan_arrival(to_lat, to_lon, travel["duration_s"])
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error calculando ruta: {exc}")
    return {
        "origin": {"name": ORIGIN_NAME, "lat": from_lat, "lon": from_lon},
        "destination": {"lat": to_lat, "lon": to_lon},
        **travel,
        "plan": plan,
    }


@app.get("/pois")
def pois_around(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius: int = Query(8000, ge=500, le=50000),
):
    """Servicios (miradores/aparcamientos/alojamiento) cerca de un punto (Overpass)."""
    try:
        return pois.get_pois(lat, lon, radius)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error consultando Overpass: {exc}")


@app.get("/eclipse/overlays")
def eclipse_overlays() -> dict:
    """Capas del IGN: bandas de oscurecimiento y de duración de totalidad (GeoJSON)."""
    return overlays.load()


@app.get("/destinations")
def destinations(from_lat: float = ORIGIN_LAT, from_lon: float = ORIGIN_LON) -> list:
    """Poblaciones de la franja MÁS CERCANAS al origen (por carretera)."""
    try:
        return routes.destinations_from(from_lat, from_lon)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error en matriz OSRM: {exc}")


@app.get("/geocode")
def geocode(q: str = Query(..., min_length=2)):
    """Geocodifica una localidad de España (Nominatim / OpenStreetMap)."""
    try:
        r = get_client().get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "countrycodes": "es", "limit": 5},
            headers={"User-Agent": "ruta-eclipse-2026/0.1 (eclipse trip planner)"},
            timeout=15.0,
        )
        r.raise_for_status()
        return [
            {"name": h["display_name"].split(",")[0], "lat": float(h["lat"]), "lon": float(h["lon"])}
            for h in r.json()
        ]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Error en geocodificación: {exc}")


@app.get("/eclipse/validation")
def validation() -> list[dict]:
    """Puntos de validación con sus circunstancias (verdad de campo)."""
    out = []
    for p in VALIDATION_POINTS:
        try:
            c = eclipse.get_circumstances(p["lat"], p["lon"])
        except Exception as exc:  # pragma: no cover - depende de red
            c = {"error": str(exc)}
        out.append({**p, "circumstances": c})
    return out


# Servir el frontend estático si existe (montado al final para no tapar rutas).
if FRONTEND_DIR.is_dir():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="app")
