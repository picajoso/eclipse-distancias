"""Tests de POIs (Overpass en vivo). Saltan si no hay red."""
from __future__ import annotations

import socket

import pytest

from backend.app import pois


def _hay_red() -> bool:
    try:
        socket.gethostbyname("overpass-api.de")
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _hay_red(), reason="sin conexión a Overpass")
def test_hay_servicios_cerca_de_burgos():
    fc = pois.get_pois(42.3439, -3.6969, radius_m=8000)
    assert fc["type"] == "FeatureCollection"
    kinds = {f["properties"]["kind"] for f in fc["features"]}
    # Al menos parking o lodging debería aparecer en una capital de provincia.
    assert kinds & {"viewpoint", "parking", "lodging"}
    for f in fc["features"]:
        assert f["properties"]["kind"] in {"viewpoint", "parking", "lodging"}
        assert f["geometry"]["type"] == "Point"


def test_cache_evita_segunda_llamada(monkeypatch):
    """La segunda llamada con la misma celda usa caché (no llama a Overpass)."""
    pois._cache.clear()
    calls = {"n": 0}
    orig = pois._post

    def fake_post(query):
        calls["n"] += 1
        return {"elements": [
            {"type": "node", "lat": 42.0, "lon": -3.0, "tags": {"tourism": "viewpoint", "name": "X"}}
        ]}

    monkeypatch.setattr(pois, "_post", fake_post)
    pois.get_pois(42.3439, -3.6969)
    pois.get_pois(42.3439, -3.6969)  # misma celda -> caché
    assert calls["n"] == 1
    orig  # silencia "no usado"
