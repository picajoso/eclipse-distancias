# Ruta al Eclipse 2026

App web para planificar el viaje al **eclipse solar total del 12 de agosto de 2026**
desde **cualquier origen de España** (península): muestra la franja de totalidad
del IGN, recomienda las poblaciones con **mejor totalidad más cercanas** a tu origen,
y calcula la **ruta en coche** con la hora de salida recomendada para llegar a tiempo
a la totalidad (~20:28 CEST, Sol muy bajo al atardecer).

## Qué hace

- **Mapa interactivo** (Leaflet) con la franja de totalidad y las curvas de
  oscurecimiento (oficial del IGN).
- **Origen seleccionable**: ciudades principales + búsqueda libre vía OpenStreetMap.
- **Recomendaciones por cercanía priorizando la zona de totalidad absoluta**
  (mayor duración de totalidad), no solo la línea recta.
- **Ruta en coche** (OSRM) con distancia, tiempo y **hora de salida recomendada**
  para llegar a la totalidad con margen.
- **Servicios** (miradores, parkings, hoteles) vía Overpass.
- Distingue **totalidad real** de "parcial ~100%": p. ej. Madrid es 97,5%, no totalidad.

## Stack

**FastAPI** (Python) + **Leaflet** (JS vanilla, sin paso de build). Todo con APIs
libres y **sin claves**: OPALE (IMCCE), OSRM, Overpass, Nominatim y datos del IGN.

## Ejecutar

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                                     # tests del motor de eclipse
uvicorn backend.app.main:app --host 0.0.0.0 --port 8123 --reload
# abre http://localhost:8123/app/
```

Para acceder desde otro equipo de tu WiFi, usa `--host 0.0.0.0` y abre
`http://<IP-de-este-equipo>:8123/app/` (permite el cortafuegos si lo pide macOS).
Si el puerto 8000/8080 lo usa Docker u otra app, usa otro libre (ej. 8123).

## Datos

Incluidos en `data/` (generados; pequeños):

- `totality.geojson`, `obscuration.geojson` — curvas del IGN (licencia **CC-BY 4.0**).
- `towns_totality.geojson` — poblaciones de **OpenStreetMap** dentro de la franja (**ODbL**).

Para **regenerarlos**:

1. Descarga *"Eclipse total de Sol de 12 de agosto de 2026. Curvas de nivel"* (GeoPackage)
   de <https://centrodedescargas.cnig.es/CentroDescargas/eclipses> y guárdalo como
   `Eclipses.gpkg` en la raíz del proyecto.
2. `python scripts/build_overlays.py` y `python scripts/build_towns.py`
   (`ingest_ign.py` inspecciona las capas del GeoPackage).

## Estructura

```
backend/app/   FastAPI: eclipse (OPALE), rutas (OSRM), pois (Overpass), overlays, main
frontend/      Leaflet: index.html, app.js, style.css
scripts/       build_overlays, build_towns, ingest_ign
data/          capas GeoJSON (IGN + OSM)
tests/         motor de eclipse validado vs OPALE (Madrid/Burgos/León/Pamplona)
```

## Notas

- El eclipse es al **atardecer** (~20:28 CEST) con el Sol a ~8° sobre el horizonte
  (WNW): busca un punto con **horizonte oeste despejado**.
- OSRM público no incluye tráfico en tiempo real. Para producción, usa OpenRouteService
  con tu clave gratuita (`ORS_API_KEY`).
