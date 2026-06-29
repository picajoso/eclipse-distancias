"""Motor de rutas: trayecto más rápido desde el origen hasta un destino.

Usa OpenRouteService si hay ``ORS_API_KEY`` (mejor perfiles), si no cae al
OSRM público (sin key, solo 'driving'). Devuelve tiempo/distancia/geometría
GeoJSON y, combinado con el motor de eclipse, la **hora de salida recomendada**
para llegar a la totalidad (o al máximo) con margen.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import json
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt

import httpx

from . import eclipse
from .config import (
    DATA_DIR,
    ORS_API_KEY,
    ORS_BASE,
    ORIGIN_LAT,
    ORIGIN_LON,
    OSRM_BASE,
    TOTALITY_ARRIVAL_BUFFER_MIN,
)

MADRID_TZ = ZoneInfo("Europe/Madrid")


# --- Proveedores ------------------------------------------------------------

def _osrm(
    olat: float, olon: float, dlat: float, dlon: float, profile: str, timeout: float = 25.0
) -> dict[str, Any]:
    """OSRM público (lon,lat;lon,lat). El servidor público solo soporta 'driving'."""
    if profile != "driving":
        profile = "driving"
    url = f"{OSRM_BASE}/route/v1/{profile}/{olon},{olat};{dlon},{dlat}"
    r = httpx.get(url, params={"overview": "full", "geometries": "geojson"}, timeout=timeout)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "Ok" or not j.get("routes"):
        raise RuntimeError(f"OSRM sin ruta: {j.get('message') or j.get('code')}")
    rt = j["routes"][0]
    return {
        "duration_s": round(rt["duration"]),
        "distance_m": round(rt["distance"]),
        "geometry": rt["geometry"],  # GeoJSON LineString [lon,lat]
        "provider": "osrm",
    }


def _ors(
    olat: float, olon: float, dlat: float, dlon: float, profile: str, timeout: float = 25.0
) -> dict[str, Any]:
    """OpenRouteService (requiere API key). profiles: driving-car, foot-walk, cycling-regular..."""
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
    url = f"{ORS_BASE}/v2/directions/{profile}"
    body = {"coordinates": [[olon, olat], [dlon, dlat]], "geometry": "true"}
    r = httpx.post(url, headers=headers, json=body, timeout=timeout)
    r.raise_for_status()
    j = r.json()
    rt = j["routes"][0]
    seg = rt.get("segments", [{}])[0]
    return {
        "duration_s": round(seg.get("duration", rt.get("summary", {}).get("duration", 0))),
        "distance_m": round(seg.get("distance", rt.get("summary", {}).get("distance", 0))),
        "geometry": rt["geometry"],
        "provider": "ors",
    }


def get_route(
    olat: float,
    olon: float,
    dlat: float,
    dlon: float,
    profile: str = "driving",
) -> dict[str, Any]:
    """Ruta más rápida entre origen y destino. Elige proveedor por configuración."""
    if ORS_API_KEY:
        return _ors(olat, olon, dlat, dlon, profile)
    return _osrm(olat, olon, dlat, dlon, profile)


# --- Integración con el eclipse --------------------------------------------

def plan_arrival(
    dest_lat: float,
    dest_lon: float,
    travel_duration_s: float,
    buffer_min: int = TOTALITY_ARRIVAL_BUFFER_MIN,
) -> dict[str, Any]:
    """Hora de salida recomendada para llegar al evento clave con margen.

    El evento clave es el inicio de la totalidad si el destino está dentro de
    la franja; si no, el momento del máximo (parcial). Si ni eso (punto sin
    eclipse visible), no hay plan.
    """
    circ = eclipse.get_circumstances(dest_lat, dest_lon)
    if circ["is_total"]:
        key_iso = circ["contacts"]["total_begin"]
        key_event = "total_begin"
    else:
        key_iso = circ["contacts"]["maximum"]
        key_event = "maximum"

    plan: dict[str, Any] = {
        "is_total": circ["is_total"],
        "key_event": key_event,
        "key_event_at": key_iso,
        "buffer_min": buffer_min,
    }
    if not key_iso:
        plan["suggested_departure"] = None
        return plan

    key_dt = datetime.fromisoformat(key_iso)
    depart = key_dt - timedelta(seconds=travel_duration_s) - timedelta(minutes=buffer_min)
    plan["suggested_departure"] = depart.isoformat()
    # ¿El evento clave ocurre con el Sol sobre el horizonte?
    sun_alt = circ.get("sun_at_maximum", {}).get("alt")
    plan["sun_alt_at_maximum"] = sun_alt
    plan["low_sun_warning"] = sun_alt is not None and sun_alt < 10
    return plan


@lru_cache(maxsize=1)
def totality_towns() -> tuple:
    """Todas las poblaciones (OSM city|town) dentro de la franja de totalidad."""
    fc = json.loads((DATA_DIR / "towns_totality.geojson").read_text())
    return tuple(
        (f["properties"]["name"], f["properties"]["lat"], f["properties"]["lon"], f["properties"]["dur"], f["properties"].get("pop", 0))
        for f in fc["features"]
    )


def _haversine(la1: float, lo1: float, la2: float, lo2: float) -> float:
    dla, dlo = radians(la2 - la1), radians(lo2 - lo1)
    a = sin(dla / 2) ** 2 + cos(radians(la1)) * cos(radians(la2)) * sin(dlo / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def destinations_from(lat: float, lon: float, max_km: float = 450.0, min_found: int = 18) -> list[dict]:
    """Poblaciones de totalidad RECONOCIBLES (>=3000 hab, >=50s) dentro de un radio
    creciente (max_km en línea recta). Sin recorte por count (eso cortaba pueblos
    interiores como Calatayud cuando el origen tiene mucha densidad alrededor).
    Ordenadas por distancia en coche. Garantiza un mínimo si el origen está lejos.
    """
    towns = totality_towns()
    towns = tuple(t for t in towns if t[3] >= 50 and t[4] >= 3000)
    hav = sorted(((_haversine(lat, lon, t[1], t[2]), t) for t in towns), key=lambda x: x[0])
    ranked = [t for h, t in hav if h <= max_km][:50]
    if len(ranked) < min_found:
        ranked = [t for _, t in hav[:min_found]]
    coords = ";".join([f"{lon},{lat}"] + [f"{t[2]},{t[1]}" for t in ranked])
    url = f"{OSRM_BASE}/table/v1/driving/{coords}?sources=0&annotations=distance,duration"
    r = httpx.get(url, timeout=60.0)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != "Ok" or "distances" not in j:
        raise RuntimeError(f"OSRM table: {j.get('message') or j.get('code')}")
    dists, durs = j["distances"][0], j["durations"][0]
    out = []
    for i, (nm, tlat, tlon, dur, pop) in enumerate(ranked):
        out.append({
            "name": nm, "lat": tlat, "lon": tlon, "dur": int(dur), "pop": int(pop),
            "driving_km": round(dists[i + 1] / 1000), "driving_min": round(durs[i + 1] / 60),
        })
    # Puntuación: PRIORIDA la zona de totalidad absoluta (duración) y, dentro de ella,
    # la cercanía. Así un pueblo con totalidad profunda (p.ej. 100s) se antepone a uno
    # de borde (50-60s) aunque este esté más cerca, sin caer en sitios lejanísimos
    # (ya estamos dentro del radio de los más cercanos).
    dvals = [d["dur"] for d in out]
    kvals = [d["driving_km"] for d in out]
    dmin, dmax = min(dvals), max(dvals)
    kmin, kmax = min(kvals), max(kvals)
    W = 0.6  # peso de la duración de totalidad; (1-W) para la cercanía
    for d in out:
        dn = (d["dur"] - dmin) / (dmax - dmin) if dmax > dmin else 1
        kn = 1 - (d["driving_km"] - kmin) / (kmax - kmin) if kmax > kmin else 1
        d["score"] = round(W * dn + (1 - W) * kn, 3)
    out.sort(key=lambda d: -d["score"])
    return out
