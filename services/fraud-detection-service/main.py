import os
import json
import signal
import sys
import time
import logging
from logging import config as logging_config
from datetime import datetime
from typing import Optional

from confluent_kafka import Consumer, Producer, KafkaError, KafkaException
from sklearn.ensemble import IsolationForest
import numpy as np
import joblib  # For model loading
import boto3
from botocore.exceptions import ClientError

# -----------------------------
# Logging Setup (JSON for observability)
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
# Configuration from Env
# -----------------------------
BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'b-1.your-msk-cluster.us-east-1.amazonaws.com:9098')
TOPIC = os.getenv('KAFKA_TOPIC', 'transactions.created')
GROUP_ID = os.getenv('KAFKA_GROUP_ID', 'fraud-detection-group-v1')
MODEL_PATH = os.getenv('MODEL_PATH', '/app/models/isolation_forest_v1.joblib')  # Mount via volume or bake in
ANOMALY_THRESHOLD = float(os.getenv('ANOMALY_THRESHOLD', '-0.5'))  # Isolation Forest: lower = more anomalous
ALERT_THRESHOLD = float(os.getenv('ALERT_THRESHOLD', '500.0'))     # Simple rule: amount > $500

# Fraud alerts configuration
FRAUD_ALERTS_TOPIC = os.getenv('FRAUD_ALERTS_TOPIC', 'fraud.alerts')
SNS_TOPIC_ARN = os.getenv('SNS_TOPIC_ARN', '')  # For high-priority alerts
NOTIFICATION_SERVICE_URL = os.getenv('NOTIFICATION_SERVICE_URL', '')  # Optional: internal notification service
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# -----------------------------
# Load pre-trained model (done once at startup)
# -----------------------------
try:
    model: IsolationForest = joblib.load(MODEL_PATH)
    logger.info("Loaded Isolation Forest model", extra={"model_path": MODEL_PATH})
except Exception as e:
    logger.error("Failed to load model - falling back to rules only", extra={"error": str(e)})
    model = None

# -----------------------------
# Initialize Kafka Producer for fraud alerts
# -----------------------------
producer_conf = {
    'bootstrap.servers': BOOTSTRAP_SERVERS,
    'security.protocol': 'SASL_SSL',
    # 'sasl.mechanism': 'AWS_MSK_IAM',  # Uncomment for IAM auth
    'client.id': 'fraud-detection-producer',
    'acks': 'all',
    'retries': 3,
    'linger.ms': 10,
}

producer = Producer(producer_conf)
logger.info("Initialized Kafka producer for fraud alerts")

# -----------------------------
# Initialize AWS SNS client for high-priority alerts
# -----------------------------
sns_client: Optional[boto3.client] = None
if SNS_TOPIC_ARN:
    try:
        sns_client = boto3.client('sns', region_name=AWS_REGION)
        logger.info("Initialized SNS client", extra={"topic_arn": SNS_TOPIC_ARN})
    except Exception as e:
        logger.error("Failed to initialize SNS client", extra={"error": str(e)})

# -----------------------------
# Kafka Producer delivery callback
# -----------------------------
def delivery_report(err, msg):
    """Callback for Kafka producer delivery reports"""
    if err is not None:
        logger.error("Message delivery failed", extra={"error": str(err), "topic": msg.topic()})
    else:
        logger.debug("Message delivered", extra={"topic": msg.topic(), "partition": msg.partition(), "offset": msg.offset()})

# -----------------------------
# Send fraud alert to Kafka topic
# -----------------------------
def send_fraud_alert_to_kafka(alert_data: dict):
    """Produce fraud alert to 'fraud.alerts' Kafka topic"""
    try:
        alert_message = json.dumps(alert_data).encode('utf-8')
        producer.produce(
            topic=FRAUD_ALERTS_TOPIC,
            value=alert_message,
            key=alert_data.get('tx_id', '').encode('utf-8'),
            callback=delivery_report
        )
        producer.poll(0)  # Trigger delivery reports
        logger.info("Fraud alert sent to Kafka", extra={"tx_id": alert_data.get('tx_id'), "topic": FRAUD_ALERTS_TOPIC})
    except Exception as e:
        logger.error("Failed to send fraud alert to Kafka", extra={"error": str(e), "alert": alert_data})

# -----------------------------
# Send high-priority alert via AWS SNS
# -----------------------------
def send_sns_alert(alert_data: dict):
    """Send high-priority fraud alert via AWS SNS (email/SMS)"""
    if not sns_client or not SNS_TOPIC_ARN:
        return

    try:
        # Format message for SNS
        amount = alert_data.get('amount', 0.0)
        tx_id = alert_data.get('tx_id', 'unknown')
        reasons = alert_data.get('reasons', 'Unknown')
        user_id = alert_data.get('user_id', 'unknown')
        
        message = f"""
🚨 FRAUD ALERT 🚨

Transaction ID: {tx_id}
User ID: {user_id}
Amount: ${amount:,.2f}
Timestamp: {alert_data.get('timestamp')}

Fraud Indicators:
{reasons}

Anomaly Score: {alert_data.get('anomaly_score', 'N/A')}

Action Required: Review transaction immediately.
        """.strip()

        subject = f"⚠️ Fraud Alert: ${amount:,.2f} - TX {tx_id[:8]}"

        response = sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message,
            MessageAttributes={
                'severity': {
                    'DataType': 'String',
                    'StringValue': 'high' if amount > 1000 else 'medium'
                },
                'tx_id': {
                    'DataType': 'String',
                    'StringValue': tx_id
                }
            }
        )
        
        logger.info("SNS alert sent", extra={"message_id": response['MessageId'], "tx_id": tx_id})
    except ClientError as e:
        logger.error("Failed to send SNS alert", extra={"error": str(e), "tx_id": alert_data.get('tx_id')})
    except Exception as e:
        logger.error("Unexpected error sending SNS alert", extra={"error": str(e), "tx_id": alert_data.get('tx_id')})

# -----------------------------
# Send alert to internal Notification Service (optional)
# -----------------------------
def send_notification_service_alert(alert_data: dict):
    """Send fraud alert to internal notification service via HTTP"""
    if not NOTIFICATION_SERVICE_URL:
        return

    try:
        import requests
        
        payload = {
            "type": "fraud_alert",
            "priority": "high" if alert_data.get('amount', 0) > 1000 else "medium",
            "user_id": alert_data.get('user_id'),
            "tx_id": alert_data.get('tx_id'),
            "title": "Potential Fraud Detected",
            "message": f"Transaction of ${alert_data.get('amount', 0):,.2f} flagged as potential fraud.",
            "data": alert_data,
            "channels": ["email", "push", "sms"] if alert_data.get('amount', 0) > 1000 else ["email", "push"]
        }
        
        response = requests.post(
            f"{NOTIFICATION_SERVICE_URL}/api/v1/notifications/send",
            json=payload,
            timeout=5,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            logger.info("Notification service alert sent", extra={"tx_id": alert_data.get('tx_id')})
        else:
            logger.warning("Notification service returned error", extra={
                "status": response.status_code,
                "tx_id": alert_data.get('tx_id'),
                "response": response.text[:200]
            })
    except Exception as e:
        logger.error("Failed to send notification service alert", extra={"error": str(e), "tx_id": alert_data.get('tx_id')})

# -----------------------------
# Main alert dispatcher
# -----------------------------
def dispatch_fraud_alert(event: dict, anomaly_score: float, reasons: str):
    """
    Dispatch fraud alert through multiple channels:
    1. Kafka topic (for downstream services)
    2. AWS SNS (for high-priority real-time alerts)
    3. Internal notification service (for user notifications)
    """
    alert_data = {
        "alert_id": f"fraud-{event.get('tx_id', 'unknown')}-{int(time.time())}",
        "tx_id": event.get('tx_id', 'unknown'),
        "user_id": event.get('user_id', 'unknown'),
        "amount": event.get('amount', 0.0),
        "currency": event.get('currency', 'USD'),
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "anomaly_score": float(anomaly_score),
        "reasons": reasons,
        "severity": "high" if event.get('amount', 0) > 1000 else "medium",
        "event_type": "fraud_detected",
        "metadata": {
            "detection_method": "ml_and_rules" if model else "rules_only",
            "model_version": "isolation_forest_v1" if model else None,
            "detection_service": "fraud-detection-service",
            "environment": os.getenv('ENVIRONMENT', 'production')
        },
        "original_event": event
    }

    # 1. Always send to Kafka (for audit trail and downstream processing)
    send_fraud_alert_to_kafka(alert_data)

    # 2. Send SNS alert for high-value transactions (>$1000)
    if event.get('amount', 0) > 1000:
        send_sns_alert(alert_data)

    # 3. Send to notification service for user alerts
    send_notification_service_alert(alert_data)

# -----------------------------
# Simple feature extraction (expand with real features: velocity, location delta, etc.)
# -----------------------------
def extract_features(event: dict) -> np.ndarray:
    """
    Convert event to feature vector for model.
    In production: pull from feature store (Redis), add velocity, device, geo-risk, etc.
    """
    amount = event.get('amount', 0.0)
    # Placeholder features (expand!)
    features = np.array([[amount, time.time() % 86400]])  # e.g., amount + time-of-day
    return features.reshape(1, -1)

# -----------------------------
# Fraud decision logic
# -----------------------------
def is_fraud(event: dict) -> tuple[bool, float, str]:
    amount = event.get('amount', 0.0)
    tx_id = event.get('tx_id', 'unknown')

    reasons = []

    # Rule-based (fast, explainable)
    if amount > ALERT_THRESHOLD:
        reasons.append(f"High amount ({amount} > {ALERT_THRESHOLD})")

    # ML-based (if model loaded)
    score = 0.0
    if model is not None:
        features = extract_features(event)
        score = model.score_samples(features)[0]  # Lower = more anomalous
        if score < ANOMALY_THRESHOLD:
            reasons.append(f"ML anomaly score {score:.3f} < {ANOMALY_THRESHOLD}")

    is_fraud_flag = len(reasons) > 0
    return is_fraud_flag, score, "; ".join(reasons) or "clean"

# -----------------------------
# Kafka Consumer Loop
# -----------------------------
def run_consumer():
    conf = {
        'bootstrap.servers': BOOTSTRAP_SERVERS,
        'group.id': GROUP_ID,
        'auto.offset.reset': 'earliest',           # or 'latest' depending on needs
        'enable.auto.commit': True,
        'auto.commit.interval.ms': 5000,
        'session.timeout.ms': 10000,
        'max.poll.interval.ms': 300000,            # Allow long processing if needed
        'security.protocol': 'SASL_SSL',           # For AWS MSK IAM → adjust if using IAM auth
        # 'sasl.mechanism': 'AWS_MSK_IAM',        # Uncomment + use aws-msk-iam-auth jar wrapper if IAM
        # 'sasl.jaas.config': '...',
    }

    consumer = Consumer(conf)
    consumer.subscribe([TOPIC])

    logger.info("Starting fraud detection consumer", extra={"topic": TOPIC, "group": GROUP_ID})

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

                logger.debug("Received transaction", extra={"tx_id": tx_id, "event": event})

                fraud_flag, anomaly_score, reasons = is_fraud(event)

                if fraud_flag:
                    logger.warning(
                        "Potential fraud detected",
                        extra={
                            "tx_id": tx_id,
                            "amount": event.get('amount'),
                            "anomaly_score": anomaly_score,
                            "reasons": reasons,
                            "event": event
                        }
                    )
                    
                    # Dispatch fraud alert through multiple channels
                    dispatch_fraud_alert(event, anomaly_score, reasons)
                    
                else:
                    logger.debug("Transaction clean", extra={"tx_id": tx_id, "score": anomaly_score})

            except json.JSONDecodeError as e:
                logger.error("Invalid JSON", extra={"error": str(e), "raw": msg.value()})
            except Exception as e:
                logger.exception("Processing error", extra={"tx_id": event.get('tx_id')})

    except Exception as e:
        logger.critical("Consumer crashed", exc_info=True)
    finally:
        # Flush any pending messages in producer
        logger.info("Flushing producer...")
        producer.flush(timeout=10)
        
        consumer.close()
        logger.info("Consumer closed")

if __name__ == "__main__":
    run_consumer()