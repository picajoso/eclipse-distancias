"""Cliente HTTP persistente compartido por toda la app.

Reutiliza el pool de conexiones TCP/TLS entre llamadas a OPALE, OSRM y Overpass,
evitando repetir el handshake en cada petición (ahorro típico de ~100-300 ms por
llamada). ``httpx.Client`` es seguro entre hilos, así que se puede compartir con
el threadpool de FastAPI sin problemas.
"""
from __future__ import annotations

import threading

import httpx

_lock = threading.Lock()
_client: httpx.Client | None = None


def get_client() -> httpx.Client:
    """Devuelve el cliente HTTP singleton (lo crea bajo cerrojo la primera vez)."""
    global _client
    if _client is None:
        with _lock:
            if _client is None:  # double-checked locking
                _client = httpx.Client(timeout=30.0)
    return _client
