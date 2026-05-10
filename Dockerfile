# ── Mini EDC — Phase F: Docker Image ─────────────────────────────────────────
# Multi-stage build: keeps final image lean (~150 MB vs ~1 GB)

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build deps
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="Mini EDC Project"
LABEL description="CDISC-compliant Electronic Data Capture REST API"
LABEL version="1.0.0"

# Security: run as non-root user
RUN groupadd -r edcuser && useradd -r -g edcuser edcuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY python/api_phase_e.py         ./api_phase_e.py
COPY python/api_phase_f.py         ./api_phase_f.py
COPY python/cdisc_validation_engine.py ./cdisc_validation_engine.py
COPY python/sdtm_generator.py      ./sdtm_generator.py
COPY python/part11_audit.py        ./part11_audit.py
COPY data/                         ./data/

# Create output directories
RUN mkdir -p /app/reports/sdtm /app/logs && \
    chown -R edcuser:edcuser /app

# Switch to non-root
USER edcuser

# Expose API port
EXPOSE 8000

# Health check — Docker will restart if API goes down
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start the API
CMD ["python", "-m", "uvicorn", "api_phase_f:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--access-log"]
