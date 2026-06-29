"""Tests del motor de rutas (OSRM público en vivo). Saltan si no hay red."""
from __future__ import annotations

import socket

import pytest

from backend.app import routes


def _hay_red() -> bool:
    try:
        socket.gethostbyname("router.project-osrm.org")
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _hay_red(), reason="sin conexión a OSRM")
def test_ruta_madrid_burgos_es_plausible():
    r = routes.get_route(40.4168, -3.7038, 42.3439, -3.6969)  # Madrid -> Burgos
    assert r["provider"] in ("osrm", "ors")
    assert 4000 < r["duration_s"] < 20000      # ~1h10m .. ~5h30m
    assert 150_000 < r["distance_m"] < 400_000  # ~150 .. ~400 km
    geom = r["geometry"]
    assert geom["type"] == "LineString"
    assert len(geom["coordinates"]) > 10


@pytest.mark.skipif(not _hay_red(), reason="sin conexión a OPALE/OSRM")
def test_plan_llegada_sugiere_salida_antes_de_totalidad():
    travel = routes.get_route(40.4168, -3.7038, 42.3439, -3.7038)  # Madrid -> Burgos
    plan = routes.plan_arrival(42.3439, -3.6969, travel["duration_s"], buffer_min=30)
    assert plan["is_total"] is True
    assert plan["key_event"] == "total_begin"
    # totalidad empieza 20:28:24 CEST; con viaje+30' debe salir bastante antes
    assert plan["suggested_departure"].startswith("2026-08-12T")
    assert plan["suggested_departure"] < plan["key_event_at"]
    assert plan["low_sun_warning"] is True  # Sol ~8° -> aviso de sol bajo
