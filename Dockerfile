# Container image for IBM Cloud Code Engine (or any container platform).
# Build:  docker build -t haq .
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-hin tesseract-ocr-kan \
    && rm -rf /var/lib/apt/lists/* && useradd --create-home --uid 10001 haq
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=web /web/dist frontend/dist
ENV APP_ENV=production HAQ_DATA_DIR=/data OCR_LANGUAGES=eng+hin+kan PORT=8080
RUN mkdir -p /data && chown haq /data
USER haq
WORKDIR /app/backend
EXPOSE 8080
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
