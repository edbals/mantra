"""
Isolation Forest anomaly detection for watchlist broker flow.

Fits on historical broker data, scores a signal period, and returns
a per-broker anomaly score alongside direction.

Features per (broker, day):
  - net_volume        : raw net lots (buy - sell)
  - buy_volume        : raw buy lots
  - sell_volume       : raw sell lots
  - buy_ratio         : buy / (buy + sell)  [0, 1]
  - net_ratio         : net / (buy + sell)  [-1, 1]

IsolationForest.decision_function returns lower values for anomalies.
We invert and normalise to an anomaly_score in [0, 100] for display.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

_FEATURES = ["net_volume", "buy_volume", "sell_volume", "buy_ratio", "net_ratio"]
MIN_HISTORY_ROWS = 10   # minimum rows per broker to fit


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    total = out["buy_volume"].fillna(0) + out["sell_volume"].fillna(0)
    eps = 1e-9
    out["buy_ratio"] = out["buy_volume"].fillna(0) / (total + eps)
    out["net_ratio"] = out["net_volume"].fillna(0) / (total + eps)
    for col in ["net_volume", "buy_volume", "sell_volume"]:
        out[col] = out[col].fillna(0)
    return out


def score_brokers(
    hist_df: pd.DataFrame,
    signal_df: pd.DataFrame,
    contamination: float = 0.05,
) -> pd.DataFrame:
    """
    Fit one IsolationForest per broker on hist_df, score signal_df.

    Parameters
    ----------
    hist_df   : historical rows — columns [code, date, buy_volume, sell_volume, net_volume]
    signal_df : rows to score — same columns, one row per broker (or avg over signal period)
    contamination : expected fraction of anomalies in history (default 5%)

    Returns
    -------
    DataFrame with columns [code, anomaly_score, direction, if_label]
      anomaly_score : 0–100, higher = more anomalous
      direction     : "buying" | "selling" | "neutral"
      if_label      : -1 (anomaly) or 1 (normal) per IsolationForest
    """
    if hist_df.empty or signal_df.empty:
        return pd.DataFrame(columns=["code", "anomaly_score", "direction", "if_label"])

    hist  = _build_features(hist_df)
    sig   = _build_features(signal_df)

    results = []
    for code in sig["code"].unique():
        h = hist[hist["code"] == code][_FEATURES].dropna()
        s = sig[sig["code"] == code][_FEATURES].dropna()

        if len(h) < MIN_HISTORY_ROWS or s.empty:
            continue

        scaler = StandardScaler()
        X_hist = scaler.fit_transform(h)
        X_sig  = scaler.transform(s)

        model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=42,
        )
        model.fit(X_hist)

        raw_score = float(model.decision_function(X_sig).mean())
        label     = int(model.predict(X_sig)[0])

        # Normalise: decision_function typical range ~[-0.5, 0.5]
        # Lower raw = more anomalous → invert to anomaly_score
        anomaly_score = float(np.clip((-raw_score + 0.5) / 1.0 * 100, 0, 100))

        net = float(sig[sig["code"] == code]["net_volume"].mean())
        if net > 0:
            direction = "buying"
        elif net < 0:
            direction = "selling"
        else:
            direction = "neutral"

        results.append({
            "code":          code,
            "anomaly_score": round(anomaly_score, 1),
            "direction":     direction,
            "if_label":      label,   # -1 = anomaly, 1 = normal
        })

    return pd.DataFrame(results)
