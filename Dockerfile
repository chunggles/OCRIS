# OCRIS in one container for a cloud host (Render: see render.yaml and docs/DEPLOYMENT.md).
# The React app is built to static files and served by Django from the same address as the API,
# so the sign-in cookie never has to cross sites. Everything OCRIS writes goes to DATA_DIR, which
# must be a persistent disk.

# ── 1. Build the site ─────────────────────────────────────────────────────────
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# The API is on the same address as the site
RUN VITE_API_URL=/api npm run build

# ── 2. The server ─────────────────────────────────────────────────────────────
FROM python:3.12-slim-trixie

# Tesseract 5.5 and the English model the OCR was tuned and measured with (tessdata_fast 4.1.0, the
# same file as the Windows installer's). The build stops if Debian ever ships a different model.
ARG ENG_MODEL_SHA256=7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/* \
 && model="$(find /usr/share/tesseract-ocr -name eng.traineddata | head -n 1)" \
 && echo "${ENG_MODEL_SHA256}  ${model}" | sha256sum -c - \
 && tesseract --version

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_THREAD_LIMIT=1 \
    DATA_DIR=/var/data \
    FRONTEND_DIST=/app/frontend/dist
# OMP_THREAD_LIMIT=1: one thread per Tesseract run, so several uploads share the CPU instead of
# fighting over it

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend /frontend/dist /app/frontend/dist
# Static files of Django's own pages; DEBUG only so that settings load without the real secrets
RUN DEBUG=True DATA_DIR=/tmp/build-data python manage.py collectstatic --noinput

EXPOSE 10000
CMD ["sh", "start.sh"]
