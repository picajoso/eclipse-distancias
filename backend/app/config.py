"""Configuración central: origen del viaje, proveedores de rutas y puntos de validación."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]  # raíz del proyecto (eclipse2026/)
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"

# --- Origen del viaje (por defecto Madrid) ---------------------------------
ORIGIN_NAME = os.getenv("ECLIPSE_ORIGIN_NAME", "Madrid")
ORIGIN_LAT = float(os.getenv("ECLIPSE_ORIGIN_LAT", "40.4168"))
ORIGIN_LON = float(os.getenv("ECLIPSE_ORIGIN_LON", "-3.7038"))

# --- Rutas ------------------------------------------------------------------
# OSRM público para desarrollo (sin key). ORS con key gratuita para producción.
ORS_API_KEY = os.getenv("ORS_API_KEY", "").strip()
OSRM_BASE = os.getenv("OSRM_BASE", "https://router.project-osrm.org").rstrip("/")
ORS_BASE = os.getenv("ORS_BASE", "https://api.openrouteservice.org").rstrip("/")

# --- Eclipse ---------------------------------------------------------------
ECLIPSE_DATE = "2026-08-12"
# Margen de llegada aconsejado antes del inicio de la totalidad (minutos).
TOTALITY_ARRIVAL_BUFFER_MIN = int(os.getenv("ECLIPSE_BUFFER_MIN", "30"))

# Puntos de validación (verdad de campo de OPALE, en CEST = UTC+2 en agosto).
# Sirven para verificar que el motor calcula igual que la fuente autoritativa.
VALIDATION_POINTS = [
    {"name": "Madrid", "lat": 40.4168, "lon": -3.7038, "is_total": False, "magnitude": 0.99939},
    {"name": "Burgos", "lat": 42.3439, "lon": -3.6969, "is_total": True, "magnitude": 1.0344},
    {"name": "León", "lat": 42.5987, "lon": -5.6671, "is_total": True, "magnitude": 1.0349},
    {"name": "Pamplona", "lat": 42.8125, "lon": -1.6464, "is_total": False, "magnitude": 0.99939},
]
