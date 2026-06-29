"""Puntos de interés (servicios) vía Overpass (OpenStreetMap), sin API key.

Devuelve miradores, aparcamientos y alojamiento alrededor de un punto como
GeoJSON, con caché en memoria por celda aproximada (las mismas coordenadas +
radio no vuelven a golpear Overpass durante el TTL).
"""
from __future__ import annotations

import time
from typing import Any

from .config import DATA_DIR  # noqa: F401  (DATA_DIR reservado para caché en disco futura)
from .httpclient import get_client

OVERPASS_URLS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",  # estable en pruebas
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
USER_AGENT = "ruta-eclipse-2026/0.1 (planificador de viaje al eclipse; +https://www.openstreetmap.org)"
CACHE_TTL_S = 3600
MAX_CACHE_SIZE = 500  # #3: la caché no crece sin límite (FIFO)
_cache: dict[tuple, tuple[float, dict]] = {}


def _kind(tags: dict[str, str]) -> str | None:
    if tags.get("tourism") == "viewpoint":
        return "viewpoint"
    if tags.get("amenity") == "parking":
        return "parking"
    if tags.get("tourism") in {
        "hotel", "hostel", "guest_house", "apartment", "motel",
        "camp_site", "alpine_hut", "chalet", "apartment",
    }:
        return "lodging"
    return None


def _build_query(lat: float, lon: float, radius_m: int) -> str:
    # Exigimos 'name' en parking/alojamiento: corta el ruido (miles de nodos)
    # y queda lo realmente útil para planificar el viaje. Miradores sin nombre se conservan.
    return f"""[out:json][timeout:40];
(
  node["tourism"="viewpoint"](around:{radius_m},{lat},{lon});
  node["amenity"="parking"]["name"](around:{radius_m},{lat},{lon});
  node["tourism"~"^(hotel|hostel|guest_house|apartment|motel|camp_site|alpine_hut|chalet)$"]["name"](around:{radius_m},{lat},{lon});
);
out center 150;"""


def _post(query: str) -> dict:
    last_exc: Exception | None = None
    for url in OVERPASS_URLS:
        try:
            r = get_client().post(url, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=60.0)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # prueba el siguiente endpoint
            last_exc = exc
    raise RuntimeError(f"Overpass no disponible: {last_exc}")


def get_pois(lat: float, lon: float, radius_m: int = 8000) -> dict[str, Any]:
    """GeoJSON FeatureCollection de servicios alrededor de (lat, lon)."""
    key = (round(lat, 3), round(lon, 3), radius_m)
    cached = _cache.get(key)
    if cached and time.monotonic() - cached[0] < CACHE_TTL_S:
        return cached[1]

    raw = _post(_build_query(lat, lon, radius_m))
    features = []
    for el in raw.get("elements", []):
        tags = el.get("tags", {}) or {}
        kind = _kind(tags)
        if not kind:
            continue
        if el.get("type") == "node":
            lat_e, lon_e = el.get("lat"), el.get("lon")
        else:
            c = el.get("center") or {}
            lat_e, lon_e = c.get("lat"), c.get("lon")
        if lat_e is None or lon_e is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon_e, lat_e]},
            "properties": {
                "name": tags.get("name") or {"viewpoint": "Mirador", "parking": "Aparcamiento", "lodging": "Alojamiento"}[kind],
                "kind": kind,
            },
        })

    geojson = {
        "type": "FeatureCollection",
        "query": {"lat": lat, "lon": lon, "radius_m": radius_m},
        "features": features,
    }
    if len(_cache) >= MAX_CACHE_SIZE:
        _cache.pop(next(iter(_cache)))  # FIFO: descarta la entrada más antigua
    _cache[key] = (time.monotonic(), geojson)
    return geojson
