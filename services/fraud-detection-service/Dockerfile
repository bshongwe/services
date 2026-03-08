# Multi-stage Dockerfile for Fraud Detection Service
# Supports both IsolationForest and XGBoost models

# Stage 1: Model builder (optional - if you want to bake in models)
FROM python:3.11-slim AS model-builder

WORKDIR /build

# Copy training script and data
COPY train.py .
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optionally run training (if you have data in the image)
# COPY data/ ./data/
# RUN python train.py --model isolation-forest --data data/transactions.csv --version v1

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main_production.py main.py
COPY train.py .

# Create directories for models
RUN mkdir -p /app/models /app/data

# Copy pre-trained models (if available)
# Option 1: Bake models into image (faster startup)
COPY models/ /app/models/

# Option 2: Mount models as volume at runtime (more flexible)
# docker run -v /path/to/models:/app/models fraud-detection:latest

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:9090/metrics || exit 1

# Environment variables (can be overridden)
ENV KAFKA_BOOTSTRAP_SERVERS=b-1.msk-cluster.us-east-1.amazonaws.com:9098 \
    KAFKA_TOPIC=transactions.created \
    FRAUD_ALERTS_TOPIC=fraud.alerts \
    DLQ_TOPIC=fraud.dlq \
    MODEL_TYPE=isolation_forest \
    MODEL_PATH=/app/models/isolation_forest_v1.joblib \
    SCALER_PATH=/app/models/scaler_v1.joblib \
    ANOMALY_THRESHOLD=-0.5 \
    XGBOOST_THRESHOLD=0.85 \
    ALERT_THRESHOLD=500.0 \
    METRICS_PORT=9090 \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

# Expose Prometheus metrics port
EXPOSE 9090

# Run with non-root user
RUN useradd -m -u 1000 fraud && chown -R fraud:fraud /app
USER fraud

CMD ["python", "main.py"]
