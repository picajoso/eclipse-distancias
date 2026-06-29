"""Tests del motor de eclipse contra la tabla de verdad (OPALE, en CEST).

Los unit tests cargan los fixtures crudos de OPALE (sin red). El test de
integración live salta si no hay conexión.
"""
from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from backend.app import eclipse

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text())


# --- Unit tests (sin red) ---------------------------------------------------

def test_madrid_es_parcial_profundo():
    n = eclipse.normalize(load("madrid_opale.json"))
    assert n["is_total"] is False
    assert abs(n["magnitude"] - 0.99939) < 1e-4
    assert n["totality_duration_s"] is None
    # greatest 18:32:24 UTC -> 20:32:24 CEST
    assert n["contacts"]["maximum"].startswith("2026-08-12T20:32:24")


def test_burgos_es_total_con_108s():
    n = eclipse.normalize(load("burgos_opale.json"))
    assert n["is_total"] is True
    assert n["totality_duration_s"] == 108
    # greatest 18:29:18 UTC -> 20:29:18 CEST
    assert n["contacts"]["maximum"].startswith("2026-08-12T20:29:18")
    assert n["contacts"]["total_begin"].startswith("2026-08-12T20:28:24")
    assert n["contacts"]["total_end"].startswith("2026-08-12T20:30:12")


def test_posicion_del_sol_en_maximo():
    n = eclipse.normalize(load("madrid_opale.json"))
    assert abs(n["sun_at_maximum"]["alt"] - 7.19) < 0.1
    assert abs(n["sun_at_maximum"]["az"] - 283.33) < 0.1


def test_obscuration_redondeada_no_confunde_con_totalidad():
    """Madrid y Burgos ambos traen obscuration 100.0; solo Burgos es total."""
    m = eclipse.normalize(load("madrid_opale.json"))
    b = eclipse.normalize(load("burgos_opale.json"))
    assert m["obscuration"] == 100.0 and m["is_total"] is False
    assert b["obscuration"] == 100.0 and b["is_total"] is True


# --- Integración live (OPALE) ----------------------------------------------

def _hay_red() -> bool:
    try:
        socket.gethostbyname("opale.imcce.fr")
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _hay_red(), reason="sin conexión a OPALE")
@pytest.mark.parametrize(
    "lat,lon,is_total,magnitude",
    [
        (42.5987, -5.6671, True, 1.0349),   # León: total
        (42.8125, -1.6464, False, 0.99939),  # Pamplona: parcial
        (40.4168, -3.7038, False, 0.99939),  # Madrid: parcial
    ],
)
def test_live_opale_coincide_con_tabla_verdad(lat, lon, is_total, magnitude):
    n = eclipse.normalize(eclipse.fetch_opale(lat, lon))
    assert n["is_total"] is is_total
    assert abs(n["magnitude"] - magnitude) < 1e-3
