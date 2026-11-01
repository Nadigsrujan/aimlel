FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend/src NEURAL_CARTOGRAPHER_HOME=/app
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-ml.txt requirements-api.txt requirements-ingest.txt ./
RUN python -m pip install --no-cache-dir torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir -r requirements-ml.txt
COPY backend/src/ backend/src/
COPY scripts/ scripts/
COPY configs/ configs/
COPY data/manifests/ data/manifests/
COPY --from=frontend /frontend/dist/ frontend/dist/
RUN useradd --create-home --uid 10001 cartographer \
    && mkdir -p artifacts data/raw data/processed data/interim \
    && chown -R cartographer:cartographer /app
USER cartographer
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=4)"
CMD ["python", "-m", "uvicorn", "api:app", "--app-dir", "scripts", "--host", "0.0.0.0", "--port", "8080"]
