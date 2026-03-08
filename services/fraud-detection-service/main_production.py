"""
Production-Hardened Fraud Detection Service
============================================

Features:
- Prometheus metrics for observability
- Dead Letter Queue (DLQ) for failed messages
- Support for both IsolationForest and XGBoost models
- Avro schema support with Schema Registry
- Horizontal scaling with Kafka consumer groups
- Circuit breaker for external services
- Graceful shutdown and backpressure handling
"""

import os
import json
import signal
import sys
import time
import logging
from logging import config as logging_config
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from confluent_kafka import Consumer, Producer, KafkaError, KafkaException
from confluent_kafka.avro import AvroConsumer, AvroProducer
from confluent_kafka.avro.cached_schema_registry_client import CachedSchemaRegistryClient
from sklearn.ensemble import IsolationForest
import xgboost as xgb
import numpy as np
import joblib
import boto3
from botocore.exceptions import ClientError
from prometheus_client import start_http_server, Counter, Histogram, Gauge, Summary
import requests

# -----------------------------
# Prometheus Metrics
# -----------------------------
MESSAGES_PROCESSED = Counter('fraud_detection_messages_processed_total', 'Total messages processed', ['status'])
FRAUD_DETECTED = Counter('fraud_detection_fraud_detected_total', 'Total fraud cases detected', ['severity'])
PROCESSING_TIME = Histogram('fraud_detection_processing_seconds', 'Time spent processing messages')
MODEL_SCORE = Histogram('fraud_detection_model_score', 'Model anomaly scores', buckets=[-1, -0.8, -0.6, -0.4, -0.2, 0])
KAFKA_LAG = Gauge('fraud_detection_kafka_lag', 'Kafka consumer lag', ['partition'])
ACTIVE_CONSUMERS = Gauge('fraud_detection_active_consumers', 'Number of active consumers')
DLQ_MESSAGES = Counter('fraud_detection_dlq_messages_total', 'Messages sent to DLQ', ['reason'])
ALERT_DELIVERY = Counter('fraud_detection_alert_delivery_total', 'Alert delivery attempts', ['channel', 'status'])
CIRCUIT_BREAKER_STATE = Gauge('fraud_detection_circuit_breaker_state', 'Circuit breaker state', ['service'])

# -----------------------------
# Logging Setup
# -----------------------------
logging_config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json'
        }
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': os.getenv('LOG_LEVEL', 'INFO')
        }
    }
})

logger = logging.getLogger(__name__)

# -----------------------------
# Configuration
# -----------------------------
BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'b-1.your-msk-cluster.us-east-1.amazonaws.com:9098')
TOPIC = os.getenv('KAFKA_TOPIC', 'transactions.created')
GROUP_ID = os.getenv('KAFKA_GROUP_ID', 'fraud-detection-group-v1')
FRAUD_ALERTS_TOPIC = os.getenv('FRAUD_ALERTS_TOPIC', 'fraud.alerts')
DLQ_TOPIC = os.getenv('DLQ_TOPIC', 'fraud.dlq')

# Model configuration
MODEL_TYPE = os.getenv('MODEL_TYPE', 'isolation_forest')  # or 'xgboost'
MODEL_PATH = os.getenv('MODEL_PATH', '/app/models/isolation_forest_v1.joblib')
SCALER_PATH = os.getenv('SCALER_PATH', '/app/models/scaler_v1.joblib')
ANOMALY_THRESHOLD = float(os.getenv('ANOMALY_THRESHOLD', '-0.5'))
XGBOOST_THRESHOLD = float(os.getenv('XGBOOST_THRESHOLD', '0.85'))
ALERT_THRESHOLD = float(os.getenv('ALERT_THRESHOLD', '500.0'))

# Schema Registry (optional)
SCHEMA_REGISTRY_URL = os.getenv('SCHEMA_REGISTRY_URL', '')
USE_AVRO = os.getenv('USE_AVRO', 'false').lower() == 'true'

# Alert configuration
SNS_TOPIC_ARN = os.getenv('SNS_TOPIC_ARN', '')
NOTIFICATION_SERVICE_URL = os.getenv('NOTIFICATION_SERVICE_URL', '')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Monitoring
METRICS_PORT = int(os.getenv('METRICS_PORT', '9090'))
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv('CIRCUIT_BREAKER_THRESHOLD', '5'))
CIRCUIT_BREAKER_TIMEOUT = int(os.getenv('CIRCUIT_BREAKER_TIMEOUT', '60'))

# -----------------------------
# Circuit Breaker
# -----------------------------
class CircuitState(Enum):
    CLOSED = 0   # Normal operation
    OPEN = 1     # Failing, reject requests
    HALF_OPEN = 2  # Testing if service recovered

class CircuitBreaker:
    """Circuit breaker for external service calls"""
    
    def __init__(self, service_name: str, threshold: int = 5, timeout: int = 60):
        self.service_name = service_name
        self.threshold = threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = CircuitState.CLOSED
        
        CIRCUIT_BREAKER_STATE.labels(service=service_name).set(self.state.value)
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = CircuitState.HALF_OPEN
                CIRCUIT_BREAKER_STATE.labels(service=self.service_name).set(self.state.value)
                logger.info(f"Circuit breaker {self.service_name}: HALF_OPEN")
            else:
                logger.warning(f"Circuit breaker {self.service_name}: OPEN, rejecting call")
                return None
        
        try:
            result = func(*args, **kwargs)
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                CIRCUIT_BREAKER_STATE.labels(service=self.service_name).set(self.state.value)
                logger.info(f"Circuit breaker {self.service_name}: CLOSED")
            
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.threshold:
                self.state = CircuitState.OPEN
                CIRCUIT_BREAKER_STATE.labels(service=self.service_name).set(self.state.value)
                logger.error(f"Circuit breaker {self.service_name}: OPEN after {self.failure_count} failures")
            
            logger.error(f"Circuit breaker {self.service_name}: call failed", extra={"error": str(e)})
            raise

# Initialize circuit breakers
sns_circuit_breaker = CircuitBreaker('sns', CIRCUIT_BREAKER_THRESHOLD, CIRCUIT_BREAKER_TIMEOUT)
notification_circuit_breaker = CircuitBreaker('notification_service', CIRCUIT_BREAKER_THRESHOLD, CIRCUIT_BREAKER_TIMEOUT)

# -----------------------------
# Load Models
# -----------------------------
model = None
scaler = None

try:
    logger.info(f"Loading {MODEL_TYPE} model from {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
    
    if os.path.exists(SCALER_PATH):
        scaler = joblib.load(SCALER_PATH)
        logger.info(f"Loaded scaler from {SCALER_PATH}")
    
    logger.info(f"{MODEL_TYPE} model loaded successfully")
except Exception as e:
    logger.error("Failed to load model", extra={"error": str(e)})
    model = None

# -----------------------------
# Initialize Kafka Producers
# -----------------------------
producer_conf = {
    'bootstrap.servers': BOOTSTRAP_SERVERS,
    'security.protocol': 'SASL_SSL',
    'client.id': 'fraud-detection-producer',
    'acks': 'all',
    'retries': 3,
    'linger.ms': 10,
    'compression.type': 'snappy',
}

if USE_AVRO and SCHEMA_REGISTRY_URL:
    schema_registry = CachedSchemaRegistryClient({'url': SCHEMA_REGISTRY_URL})
    producer = AvroProducer(producer_conf, schema_registry=schema_registry)
    logger.info("Initialized Avro producer with Schema Registry")
else:
    producer = Producer(producer_conf)
    logger.info("Initialized standard Kafka producer")

# DLQ producer
dlq_producer = Producer(producer_conf)

# -----------------------------
# AWS SNS Client
# -----------------------------
sns_client: Optional[boto3.client] = None
if SNS_TOPIC_ARN:
    try:
        sns_client = boto3.client('sns', region_name=AWS_REGION)
        logger.info("Initialized SNS client", extra={"topic_arn": SNS_TOPIC_ARN})
    except Exception as e:
        logger.error("Failed to initialize SNS client", extra={"error": str(e)})

# -----------------------------
# Feature Extraction
# -----------------------------
def extract_features(event: dict) -> np.ndarray:
    """Extract features from transaction event"""
    amount = event.get('amount', 0.0)
    hour = datetime.fromisoformat(event.get('timestamp', datetime.now().isoformat())).hour
    day_of_week = datetime.fromisoformat(event.get('timestamp', datetime.now().isoformat())).weekday()
    
    # Basic features (expand based on training features)
    features = np.array([[
        amount,
        np.log1p(amount),
        hour,
        day_of_week,
        int(day_of_week >= 5),  # is_weekend
        int(22 <= hour or hour <= 6),  # is_night
        event.get('tx_count_1h', 0),
        event.get('time_since_last_tx', 24),
    ]])
    
    # Apply scaler if available
    if scaler is not None:
        features = scaler.transform(features)
    
    return features

# -----------------------------
# Fraud Detection Logic
# -----------------------------
@PROCESSING_TIME.time()
def detect_fraud(event: dict) -> tuple[bool, float, str]:
    """
    Detect fraud using ML model and rules.
    Returns: (is_fraud, score/probability, reasons)
    """
    amount = event.get('amount', 0.0)
    reasons = []
    score = 0.0
    
    # Rule-based checks
    if amount > ALERT_THRESHOLD:
        reasons.append(f"High amount ({amount} > {ALERT_THRESHOLD})")
    
    # ML-based detection
    if model is not None:
        features = extract_features(event)
        
        if MODEL_TYPE == 'isolation_forest':
            # Anomaly detection
            score = model.score_samples(features)[0]
            MODEL_SCORE.observe(score)
            
            if score < ANOMALY_THRESHOLD:
                reasons.append(f"ML anomaly score {score:.3f} < {ANOMALY_THRESHOLD}")
        
        elif MODEL_TYPE == 'xgboost':
            # Supervised classification
            fraud_probability = model.predict_proba(features)[0][1]
            score = fraud_probability
            MODEL_SCORE.observe(fraud_probability)
            
            if fraud_probability >= XGBOOST_THRESHOLD:
                reasons.append(f"XGBoost fraud probability {fraud_probability:.3f} >= {XGBOOST_THRESHOLD}")
    
    is_fraud = len(reasons) > 0
    
    if is_fraud:
        severity = "high" if amount > 1000 else "medium"
        FRAUD_DETECTED.labels(severity=severity).inc()
    
    return is_fraud, score, "; ".join(reasons) or "clean"

# -----------------------------
# Dead Letter Queue
# -----------------------------
def send_to_dlq(message_value: bytes, error_reason: str, original_topic: str):
    """Send failed message to Dead Letter Queue"""
    try:
        dlq_message = {
            "original_topic": original_topic,
            "error_reason": error_reason,
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "message": message_value.decode('utf-8') if isinstance(message_value, bytes) else str(message_value)
        }
        
        dlq_producer.produce(
            topic=DLQ_TOPIC,
            value=json.dumps(dlq_message).encode('utf-8'),
            callback=lambda err, msg: logger.error(f"DLQ delivery failed: {err}") if err else None
        )
        dlq_producer.poll(0)
        
        DLQ_MESSAGES.labels(reason=error_reason).inc()
        logger.warning("Message sent to DLQ", extra={"reason": error_reason})
        
    except Exception as e:
        logger.error("Failed to send message to DLQ", extra={"error": str(e)})

# -----------------------------
# Alert Delivery Functions
# -----------------------------
def delivery_report(err, msg):
    """Kafka producer delivery callback"""
    if err is not None:
        logger.error("Alert delivery failed", extra={"error": str(err), "topic": msg.topic()})
        ALERT_DELIVERY.labels(channel='kafka', status='failed').inc()
    else:
        ALERT_DELIVERY.labels(channel='kafka', status='success').inc()

def send_fraud_alert_to_kafka(alert_data: dict):
    """Send fraud alert to Kafka topic"""
    try:
        alert_message = json.dumps(alert_data).encode('utf-8')
        producer.produce(
            topic=FRAUD_ALERTS_TOPIC,
            value=alert_message,
            key=alert_data.get('tx_id', '').encode('utf-8'),
            callback=delivery_report
        )
        producer.poll(0)
        logger.info("Fraud alert sent to Kafka", extra={"tx_id": alert_data.get('tx_id')})
    except Exception as e:
        logger.error("Failed to send fraud alert to Kafka", extra={"error": str(e)})
        ALERT_DELIVERY.labels(channel='kafka', status='error').inc()

def send_sns_alert_with_circuit_breaker(alert_data: dict):
    """Send SNS alert with circuit breaker protection"""
    if not sns_client or not SNS_TOPIC_ARN:
        return
    
    def _send_sns():
        amount = alert_data.get('amount', 0.0)
        tx_id = alert_data.get('tx_id', 'unknown')
        
        message = f"""
🚨 FRAUD ALERT 🚨

Transaction ID: {tx_id}
Amount: ${amount:,.2f}
Anomaly Score: {alert_data.get('anomaly_score', 'N/A')}
Reasons: {alert_data.get('reasons', 'Unknown')}
        """.strip()
        
        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"⚠️ Fraud Alert: ${amount:,.2f}",
            Message=message
        )
        
        logger.info("SNS alert sent", extra={"message_id": response['MessageId']})
        ALERT_DELIVERY.labels(channel='sns', status='success').inc()
        return response
    
    try:
        sns_circuit_breaker.call(_send_sns)
    except Exception as e:
        logger.error("SNS alert failed", extra={"error": str(e)})
        ALERT_DELIVERY.labels(channel='sns', status='failed').inc()

def send_notification_service_alert_with_circuit_breaker(alert_data: dict):
    """Send notification with circuit breaker protection"""
    if not NOTIFICATION_SERVICE_URL:
        return
    
    def _send_notification():
        payload = {
            "type": "fraud_alert",
            "priority": "high" if alert_data.get('amount', 0) > 1000 else "medium",
            "user_id": alert_data.get('user_id'),
            "title": "Potential Fraud Detected",
            "message": f"Transaction of ${alert_data.get('amount', 0):,.2f} flagged.",
            "data": alert_data
        }
        
        response = requests.post(
            f"{NOTIFICATION_SERVICE_URL}/api/v1/notifications/send",
            json=payload,
            timeout=5
        )
        response.raise_for_status()
        
        logger.info("Notification service alert sent")
        ALERT_DELIVERY.labels(channel='notification_service', status='success').inc()
        return response
    
    try:
        notification_circuit_breaker.call(_send_notification)
    except Exception as e:
        logger.error("Notification service alert failed", extra={"error": str(e)})
        ALERT_DELIVERY.labels(channel='notification_service', status='failed').inc()

def dispatch_fraud_alert(event: dict, score: float, reasons: str):
    """Dispatch fraud alert through all channels"""
    alert_data = {
        "alert_id": f"fraud-{event.get('tx_id', 'unknown')}-{int(time.time())}",
        "tx_id": event.get('tx_id', 'unknown'),
        "user_id": event.get('user_id', 'unknown'),
        "amount": event.get('amount', 0.0),
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "anomaly_score": float(score),
        "reasons": reasons,
        "severity": "high" if event.get('amount', 0) > 1000 else "medium",
        "model_type": MODEL_TYPE,
        "original_event": event
    }
    
    send_fraud_alert_to_kafka(alert_data)
    
    if event.get('amount', 0) > 1000:
        send_sns_alert_with_circuit_breaker(alert_data)
    
    send_notification_service_alert_with_circuit_breaker(alert_data)

# -----------------------------
# Main Consumer Loop
# -----------------------------
def run_consumer():
    consumer_conf = {
        'bootstrap.servers': BOOTSTRAP_SERVERS,
        'group.id': GROUP_ID,
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': True,
        'auto.commit.interval.ms': 5000,
        'session.timeout.ms': 10000,
        'max.poll.interval.ms': 300000,
        'security.protocol': 'SASL_SSL',
    }
    
    consumer = Consumer(consumer_conf)
    consumer.subscribe([TOPIC])
    
    ACTIVE_CONSUMERS.inc()
    logger.info("Fraud detection consumer started", extra={"topic": TOPIC, "group": GROUP_ID})
    
    running = True
    
    def shutdown(sig=None, frame=None):
        nonlocal running
        running = False
        logger.info("Shutdown signal received")
    
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    try:
        while running:
            msg = consumer.poll(timeout=1.0)
            
            if msg is None:
                continue
            
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    raise KafkaException(msg.error())
            
            try:
                event = json.loads(msg.value().decode('utf-8'))
                tx_id = event.get('tx_id', 'unknown')
                
                logger.debug("Processing transaction", extra={"tx_id": tx_id})
                
                # Detect fraud
                is_fraud, score, reasons = detect_fraud(event)
                
                if is_fraud:
                    logger.warning("Fraud detected", extra={
                        "tx_id": tx_id,
                        "amount": event.get('amount'),
                        "score": score,
                        "reasons": reasons
                    })
                    dispatch_fraud_alert(event, score, reasons)
                    MESSAGES_PROCESSED.labels(status='fraud').inc()
                else:
                    logger.debug("Transaction clean", extra={"tx_id": tx_id, "score": score})
                    MESSAGES_PROCESSED.labels(status='clean').inc()
                
            except json.JSONDecodeError as e:
                logger.error("Invalid JSON", extra={"error": str(e)})
                send_to_dlq(msg.value(), "json_decode_error", TOPIC)
                MESSAGES_PROCESSED.labels(status='error').inc()
                
            except Exception as e:
                logger.exception("Processing error", extra={"tx_id": event.get('tx_id', 'unknown')})
                send_to_dlq(msg.value(), str(e), TOPIC)
                MESSAGES_PROCESSED.labels(status='error').inc()
    
    except Exception as e:
        logger.critical("Consumer crashed", exc_info=True)
    
    finally:
        ACTIVE_CONSUMERS.dec()
        logger.info("Flushing producers...")
        producer.flush(timeout=10)
        dlq_producer.flush(timeout=10)
        
        consumer.close()
        logger.info("Consumer closed")

# -----------------------------
# Main Entry Point
# -----------------------------
if __name__ == "__main__":
    # Start Prometheus metrics server
    start_http_server(METRICS_PORT)
    logger.info(f"Prometheus metrics server started on port {METRICS_PORT}")
    
    # Run consumer
    run_consumer()
