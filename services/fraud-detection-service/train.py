"""
Offline Model Training for Fraud Detection
============================================

This script trains machine learning models on historical transaction data.
Supports both IsolationForest (unsupervised) and XGBoost (supervised).

Usage:
    python train.py --model isolation-forest --data data/transactions.csv
    python train.py --model xgboost --data data/labeled_transactions.csv --labels data/labels.csv
"""

import os
import argparse
import logging
from datetime import datetime
from typing import Tuple, Optional
import json

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.metrics import (
    classification_report, 
    confusion_matrix, 
    roc_auc_score,
    precision_recall_curve,
    average_precision_score
)
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import matplotlib.pyplot as plt
import seaborn as sns

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
MODEL_DIR = os.getenv('MODEL_DIR', './models')
DATA_DIR = os.getenv('DATA_DIR', './data')
RANDOM_STATE = 42


class FeatureEngineering:
    """Feature engineering for fraud detection"""
    
    @staticmethod
    def extract_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract features from raw transaction data.
        
        Features:
        - Transaction amount (log-scaled)
        - Hour of day
        - Day of week
        - Velocity features (transactions per hour/day)
        - Amount deviation from user average
        - Geographic distance from last transaction
        - Time since last transaction
        - Card age
        """
        features = pd.DataFrame()
        
        # Basic features
        features['amount'] = df['amount']
        features['amount_log'] = np.log1p(df['amount'])
        
        # Temporal features
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        features['hour'] = df['timestamp'].dt.hour
        features['day_of_week'] = df['timestamp'].dt.dayofweek
        features['is_weekend'] = (df['timestamp'].dt.dayofweek >= 5).astype(int)
        features['is_night'] = ((df['timestamp'].dt.hour >= 22) | (df['timestamp'].dt.hour <= 6)).astype(int)
        
        # User-based features (requires grouping)
        if 'user_id' in df.columns:
            user_stats = df.groupby('user_id').agg({
                'amount': ['mean', 'std', 'count'],
                'timestamp': 'min'
            }).reset_index()
            user_stats.columns = ['user_id', 'user_avg_amount', 'user_std_amount', 'user_tx_count', 'user_first_tx']
            
            df = df.merge(user_stats, on='user_id', how='left')
            
            features['amount_vs_user_avg'] = (df['amount'] - df['user_avg_amount']) / (df['user_std_amount'] + 1e-5)
            features['user_tx_count'] = df['user_tx_count']
            features['account_age_days'] = (df['timestamp'] - df['user_first_tx']).dt.days
        
        # Velocity features (transactions per time window)
        if 'user_id' in df.columns:
            df = df.sort_values(['user_id', 'timestamp'])
            df['time_since_last_tx'] = df.groupby('user_id')['timestamp'].diff().dt.total_seconds() / 3600  # hours
            features['time_since_last_tx'] = df['time_since_last_tx'].fillna(24)  # Default 24h if first tx
            
            # Transactions in last hour/day
            df['tx_count_1h'] = df.groupby('user_id')['timestamp'].rolling('1H', on='timestamp').count().values
            df['tx_count_24h'] = df.groupby('user_id')['timestamp'].rolling('24H', on='timestamp').count().values
            features['tx_count_1h'] = df['tx_count_1h'].fillna(0)
            features['tx_count_24h'] = df['tx_count_24h'].fillna(0)
        
        # Merchant/category features
        if 'merchant_category' in df.columns:
            features['merchant_category'] = pd.Categorical(df['merchant_category']).codes
        
        if 'merchant_id' in df.columns:
            merchant_fraud_rate = df.groupby('merchant_id')['is_fraud'].mean() if 'is_fraud' in df.columns else None
            if merchant_fraud_rate is not None:
                df['merchant_fraud_rate'] = df['merchant_id'].map(merchant_fraud_rate)
                features['merchant_fraud_rate'] = df['merchant_fraud_rate'].fillna(0)
        
        # Geographic features
        if 'latitude' in df.columns and 'longitude' in df.columns:
            df = df.sort_values(['user_id', 'timestamp'])
            df['lat_prev'] = df.groupby('user_id')['latitude'].shift(1)
            df['lon_prev'] = df.groupby('user_id')['longitude'].shift(1)
            
            # Haversine distance
            df['distance_km'] = FeatureEngineering._haversine_distance(
                df['latitude'], df['longitude'],
                df['lat_prev'], df['lon_prev']
            )
            features['distance_from_last_tx'] = df['distance_km'].fillna(0)
            features['is_foreign'] = (df.get('country_code', 'US') != 'US').astype(int)
        
        # Device/channel features
        if 'device_type' in df.columns:
            features['device_type'] = pd.Categorical(df['device_type']).codes
        
        if 'channel' in df.columns:
            features['channel'] = pd.Categorical(df['channel']).codes
        
        return features
    
    @staticmethod
    def _haversine_distance(lat1, lon1, lat2, lon2):
        """Calculate haversine distance between two points"""
        R = 6371  # Earth radius in km
        
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        
        return R * c


class IsolationForestTrainer:
    """Train IsolationForest for anomaly detection (unsupervised)"""
    
    def __init__(self, contamination: float = 0.001, n_estimators: int = 100):
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.model = None
        self.scaler = StandardScaler()
    
    def train(self, X: np.ndarray) -> dict:
        """Train IsolationForest on normal transactions"""
        logger.info(f"Training IsolationForest with contamination={self.contamination}, n_estimators={self.n_estimators}")
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            max_samples='auto',
            random_state=RANDOM_STATE,
            n_jobs=-1,
            verbose=1
        )
        
        self.model.fit(X_scaled)
        
        # Get anomaly scores
        scores = self.model.score_samples(X_scaled)
        
        # Calculate metrics
        metrics = {
            'model_type': 'isolation_forest',
            'n_samples': X.shape[0],
            'n_features': X.shape[1],
            'contamination': self.contamination,
            'n_estimators': self.n_estimators,
            'score_mean': float(np.mean(scores)),
            'score_std': float(np.std(scores)),
            'score_min': float(np.min(scores)),
            'score_max': float(np.max(scores)),
            'threshold': float(np.percentile(scores, self.contamination * 100))
        }
        
        logger.info(f"Training complete. Metrics: {metrics}")
        return metrics
    
    def evaluate(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> dict:
        """Evaluate model (if labels available)"""
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)  # -1 for anomaly, 1 for normal
        scores = self.model.score_samples(X_scaled)
        
        # Convert predictions: -1 (anomaly) -> 1 (fraud), 1 (normal) -> 0 (not fraud)
        predictions_binary = (predictions == -1).astype(int)
        
        metrics = {
            'n_samples': X.shape[0],
            'n_anomalies_detected': int(np.sum(predictions_binary)),
            'anomaly_rate': float(np.mean(predictions_binary))
        }
        
        if y is not None:
            metrics.update({
                'accuracy': float(np.mean(predictions_binary == y)),
                'precision': float(np.sum((predictions_binary == 1) & (y == 1)) / (np.sum(predictions_binary == 1) + 1e-5)),
                'recall': float(np.sum((predictions_binary == 1) & (y == 1)) / (np.sum(y == 1) + 1e-5)),
                'confusion_matrix': confusion_matrix(y, predictions_binary).tolist()
            })
            logger.info(f"Evaluation metrics: {metrics}")
        
        return metrics
    
    def save(self, version: str):
        """Save model and scaler"""
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        os.makedirs(MODEL_DIR, exist_ok=True)
        
        model_path = f"{MODEL_DIR}/isolation_forest_{version}.joblib"
        scaler_path = f"{MODEL_DIR}/scaler_{version}.joblib"
        
        joblib.dump(self.model, model_path)
        joblib.dump(self.scaler, scaler_path)
        
        logger.info(f"Model saved to {model_path}")
        logger.info(f"Scaler saved to {scaler_path}")
        
        return model_path, scaler_path


class XGBoostTrainer:
    """Train XGBoost for supervised fraud detection"""
    
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold
        self.model = None
        self.scaler = StandardScaler()
    
    def train(self, X: np.ndarray, y: np.ndarray, tune_hyperparams: bool = False) -> dict:
        """Train XGBoost classifier"""
        logger.info(f"Training XGBoost with {X.shape[0]} samples, {X.shape[1]} features")
        
        # Check class imbalance
        fraud_rate = np.mean(y)
        logger.info(f"Fraud rate: {fraud_rate:.4f} ({np.sum(y)} fraud, {len(y) - np.sum(y)} legitimate)")
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X_scaled, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
        )
        
        # Calculate scale_pos_weight for imbalanced data
        scale_pos_weight = (len(y_train) - np.sum(y_train)) / np.sum(y_train)
        
        if tune_hyperparams:
            logger.info("Tuning hyperparameters with GridSearchCV...")
            param_grid = {
                'max_depth': [3, 5, 7],
                'learning_rate': [0.01, 0.1, 0.3],
                'n_estimators': [100, 200, 300],
                'min_child_weight': [1, 3, 5],
                'subsample': [0.8, 1.0],
                'colsample_bytree': [0.8, 1.0]
            }
            
            base_model = xgb.XGBClassifier(
                scale_pos_weight=scale_pos_weight,
                random_state=RANDOM_STATE,
                n_jobs=-1
            )
            
            grid_search = GridSearchCV(
                base_model,
                param_grid,
                cv=3,
                scoring='average_precision',
                n_jobs=-1,
                verbose=2
            )
            
            grid_search.fit(X_train, y_train)
            self.model = grid_search.best_estimator_
            logger.info(f"Best parameters: {grid_search.best_params_}")
        else:
            # Use reasonable default parameters
            self.model = xgb.XGBClassifier(
                max_depth=5,
                learning_rate=0.1,
                n_estimators=200,
                min_child_weight=3,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=scale_pos_weight,
                random_state=RANDOM_STATE,
                n_jobs=-1,
                eval_metric='aucpr'
            )
            
            # Train with early stopping
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                early_stopping_rounds=20,
                verbose=False
            )
        
        # Evaluate on validation set
        metrics = self.evaluate(X_val, y_val)
        
        # Feature importance
        feature_importance = self.model.feature_importances_
        metrics['feature_importance_mean'] = float(np.mean(feature_importance))
        
        logger.info(f"Training complete. Validation metrics: {metrics}")
        return metrics
    
    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Evaluate XGBoost model"""
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        X_scaled = self.scaler.transform(X)
        
        # Predict probabilities
        y_proba = self.model.predict_proba(X_scaled)[:, 1]
        y_pred = (y_proba >= self.threshold).astype(int)
        
        # Calculate metrics
        tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()
        
        metrics = {
            'accuracy': float(np.mean(y_pred == y)),
            'precision': float(tp / (tp + fp + 1e-5)),
            'recall': float(tp / (tp + fn + 1e-5)),
            'f1_score': float(2 * tp / (2 * tp + fp + fn + 1e-5)),
            'roc_auc': float(roc_auc_score(y, y_proba)),
            'avg_precision': float(average_precision_score(y, y_proba)),
            'true_positives': int(tp),
            'false_positives': int(fp),
            'true_negatives': int(tn),
            'false_negatives': int(fn),
            'fraud_detection_rate': float(tp / (tp + fn + 1e-5)),
            'false_alarm_rate': float(fp / (fp + tn + 1e-5)),
            'threshold': self.threshold
        }
        
        logger.info(f"Evaluation metrics: {metrics}")
        return metrics
    
    def save(self, version: str):
        """Save XGBoost model and scaler"""
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        os.makedirs(MODEL_DIR, exist_ok=True)
        
        model_path = f"{MODEL_DIR}/xgboost_{version}.joblib"
        scaler_path = f"{MODEL_DIR}/scaler_{version}.joblib"
        
        joblib.dump(self.model, model_path)
        joblib.dump(self.scaler, scaler_path)
        
        logger.info(f"Model saved to {model_path}")
        logger.info(f"Scaler saved to {scaler_path}")
        
        return model_path, scaler_path
    
    def plot_feature_importance(self, feature_names: list, top_n: int = 20):
        """Plot feature importance"""
        if self.model is None:
            raise ValueError("Model not trained yet")
        
        importance = self.model.feature_importances_
        indices = np.argsort(importance)[::-1][:top_n]
        
        plt.figure(figsize=(10, 8))
        plt.title('Top Feature Importances')
        plt.barh(range(top_n), importance[indices])
        plt.yticks(range(top_n), [feature_names[i] for i in indices])
        plt.xlabel('Importance')
        plt.tight_layout()
        plt.savefig(f"{MODEL_DIR}/feature_importance.png")
        logger.info(f"Feature importance plot saved to {MODEL_DIR}/feature_importance.png")


def load_data(data_path: str, labels_path: Optional[str] = None) -> Tuple[pd.DataFrame, Optional[np.ndarray]]:
    """Load transaction data and labels"""
    logger.info(f"Loading data from {data_path}")
    
    df = pd.read_csv(data_path)
    logger.info(f"Loaded {len(df)} transactions")
    
    labels = None
    if labels_path:
        logger.info(f"Loading labels from {labels_path}")
        labels = pd.read_csv(labels_path)['is_fraud'].values
        logger.info(f"Loaded {len(labels)} labels ({np.sum(labels)} fraud)")
    elif 'is_fraud' in df.columns:
        labels = df['is_fraud'].values
        df = df.drop('is_fraud', axis=1)
        logger.info(f"Found labels in data ({np.sum(labels)} fraud)")
    
    return df, labels


def save_metadata(model_type: str, version: str, metrics: dict, feature_names: list):
    """Save model metadata"""
    metadata = {
        'model_type': model_type,
        'version': version,
        'timestamp': datetime.now().isoformat(),
        'metrics': metrics,
        'feature_names': feature_names,
        'training_config': {
            'random_state': RANDOM_STATE,
        }
    }
    
    metadata_path = f"{MODEL_DIR}/metadata_{version}.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"Metadata saved to {metadata_path}")


def main():
    parser = argparse.ArgumentParser(description='Train fraud detection models')
    parser.add_argument('--model', type=str, required=True, choices=['isolation-forest', 'xgboost'],
                        help='Model type to train')
    parser.add_argument('--data', type=str, required=True, help='Path to training data CSV')
    parser.add_argument('--labels', type=str, default=None, help='Path to labels CSV (for XGBoost)')
    parser.add_argument('--version', type=str, default=None, help='Model version (default: v{timestamp})')
    parser.add_argument('--contamination', type=float, default=0.001, help='Contamination rate for IsolationForest')
    parser.add_argument('--n-estimators', type=int, default=100, help='Number of estimators')
    parser.add_argument('--threshold', type=float, default=0.85, help='Classification threshold for XGBoost')
    parser.add_argument('--tune', action='store_true', help='Tune hyperparameters (XGBoost only)')
    
    args = parser.parse_args()
    
    # Set version
    version = args.version or f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Load data
    df, labels = load_data(args.data, args.labels)
    
    # Feature engineering
    logger.info("Extracting features...")
    features_df = FeatureEngineering.extract_features(df)
    X = features_df.values
    feature_names = features_df.columns.tolist()
    
    logger.info(f"Feature matrix shape: {X.shape}")
    logger.info(f"Features: {feature_names}")
    
    # Train model
    if args.model == 'isolation-forest':
        trainer = IsolationForestTrainer(contamination=args.contamination, n_estimators=args.n_estimators)
        metrics = trainer.train(X)
        
        if labels is not None:
            eval_metrics = trainer.evaluate(X, labels)
            metrics.update(eval_metrics)
        
        model_path, scaler_path = trainer.save(version)
        
    elif args.model == 'xgboost':
        if labels is None:
            raise ValueError("XGBoost requires labels. Provide --labels or include 'is_fraud' column in data.")
        
        trainer = XGBoostTrainer(threshold=args.threshold)
        metrics = trainer.train(X, labels, tune_hyperparams=args.tune)
        model_path, scaler_path = trainer.save(version)
        
        # Plot feature importance
        trainer.plot_feature_importance(feature_names)
    
    # Save metadata
    save_metadata(args.model, version, metrics, feature_names)
    
    logger.info("=" * 80)
    logger.info(f"Training complete!")
    logger.info(f"Model: {args.model}")
    logger.info(f"Version: {version}")
    logger.info(f"Model path: {model_path}")
    logger.info(f"Scaler path: {scaler_path}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
