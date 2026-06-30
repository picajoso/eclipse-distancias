FROM python:3.11-slim

# Evitar archivos .pyc y habilitar salida de logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Filtrar las dependencias de compilación pesadas (GIS) que no se usan en runtime
COPY requirements.txt .
RUN sed -i '/geopandas\|pyogrio\|shapely\|skyfield/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente y las capas de datos pre-calculadas
COPY backend/ ./backend/
COPY data/ ./data/
COPY frontend/ ./frontend/

# Crear un usuario del sistema sin privilegios y ajustar permisos de lectura/ejecución
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8123

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8123"]
