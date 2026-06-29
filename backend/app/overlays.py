"""Carga (con caché) las capas de overlay generadas desde el GeoPackage del IGN."""
from __future__ import annotations

import json
from functools import lru_cache

from .config import DATA_DIR


@lru_cache(maxsize=1)
def load() -> dict:
    """Devuelve {obscuration, totality} como GeoJSON, o None si falta el fichero."""
    def _read(name: str):
        p = DATA_DIR / name
        return json.loads(p.read_text()) if p.exists() else None

    return {"obscuration": _read("obscuration.geojson"), "totality": _read("totality.geojson")}
