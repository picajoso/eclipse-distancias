"""Motor de circunstancias del eclipse del 12-08-2026.

Dos capas:
  * ``fetch_opale`` llama a la API OPALE del IMCCE (autoritativa, sin key).
  * ``normalize`` convierte la respuesta cruda en un diccionario normalizado:
    distingue TOTALIDAD real de "parcial ~100%", pasa tiempos a CEST y
    calcula duración, altitud/azimut del Sol en el máximo.

La normalización es una función pura (testeable sin red usando los fixtures
de ``tests/fixtures``).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .config import ECLIPSE_DATE
from .httpclient import get_client

OPALE_URL = "https://opale.imcce.fr/api/v1/phenomena/eclipses/10/2026-08-12"
UTC = ZoneInfo("UTC")
MADRID_TZ = ZoneInfo("Europe/Madrid")  # CEST (UTC+2) en agosto


def fetch_opale(lat: float, lon: float, *, timeout: float = 25.0) -> dict[str, Any]:
    """Llamada cruda a OPALE para un observador en (lat, lon)."""
    r = get_client().get(OPALE_URL, params={"observer": f"{lat},{lon}"}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def get_circumstances(lat: float, lon: float) -> dict[str, Any]:
    """Conveniencia: fetch + normalize (lo que usa el endpoint)."""
    return normalize(fetch_opale(lat, lon))


# --- Helpers privados -------------------------------------------------------

def _parse_hms(s: str | None) -> int | None:
    """'00:01:48.0' -> 108 segundos."""
    if not s:
        return None
    h, m, rest = s.split(":")
    return int(h) * 3600 + int(m) * 60 + round(float(rest))


def _evt_dt(events: dict[str, Any], key: str) -> datetime | None:
    """Instanto (UTC) de un evento OPALE, o None si no existe."""
    e = events.get(key)
    if not e or not e.get("date"):
        return None
    return datetime.fromisoformat(e["date"]).replace(tzinfo=UTC)


def _to_cest(dt: datetime | None) -> str | None:
    """ISO 8601 en hora de Madrid (CEST en agosto)."""
    return dt.astimezone(MADRID_TZ).isoformat() if dt else None


def _totality_seconds(data: dict[str, Any], events: dict[str, Any]) -> int | None:
    """Duración de la totalidad: preferimos U4-U1 (robusto) sobre el campo de OPALE."""
    u1, u4 = _evt_dt(events, "U1"), _evt_dt(events, "U4")
    if u1 and u4:
        return int((u4 - u1).total_seconds())
    return _parse_hms(data.get("duration", {}).get("umbral"))


# --- Normalización ----------------------------------------------------------

def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Convierte una respuesta OPALE en circunstancias normalizadas.

    Nota sobre ``obscuration``: OPALE lo redondea a entero, por lo que un
    parcial profundísimo (magnitud 0.99939) sale como 100.0 igual que una
    totalidad. Por eso exponemos ``magnitude`` (precisa) y ``is_total`` como
    señales fiables; el % exacto se calculará por solape de discos en la fase
    skyfield. No mostrar "100%" sin comprobar ``is_total``.
    """
    data = raw["response"]["data"][0]
    events = data.get("events", {}) or {}

    is_total = bool(
        ("U1" in events and "U4" in events)
        or data.get("type") == "ObserverTotalEclipse"
    )

    begin = _evt_dt(events, "P1")
    maximum = _evt_dt(events, "greatest")
    end = _evt_dt(events, "P4")
    total_begin = _evt_dt(events, "U1")
    total_end = _evt_dt(events, "U4")

    greatest = events.get("greatest", {})
    sun = greatest.get("Sun") or {}
    sun_at_max = {
        "alt": round(sun.get("elevation"), 2) if "elevation" in sun else None,
        "az": round(sun.get("azimuth"), 2) if "azimuth" in sun else None,
    }

    return {
        "date": ECLIPSE_DATE,
        "type": data.get("type"),
        "is_total": is_total,
        # Para parcial, 'obscuration' viene redondeada; 'magnitude' es precisa.
        "obscuration": data.get("obscuration"),
        "magnitude": data.get("magnitude"),
        "totality_duration_s": _totality_seconds(data, events),
        "contacts": {
            "begin": _to_cest(begin),
            "maximum": _to_cest(maximum),
            "end": _to_cest(end),
            "total_begin": _to_cest(total_begin),
            "total_end": _to_cest(total_end),
        },
        "sun_at_maximum": sun_at_max,
    }
