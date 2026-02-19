from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

LAG_FEATURES = [1, 2, 3, 7, 14, 28]
P10_Z = -1.2815515655446004
P90_Z = 1.2815515655446004


@dataclass
class ForecastResult:
    method: str
    holdout_wape: float | None
    history: list[dict[str, float | str]]
    forecast: list[dict[str, float | date]]
    daily_mean: float
    daily_std: float


def demand_series_from_transactions(
    transactions: list[object], days_lookback: int = 365
) -> pd.Series:
    if not transactions:
        return pd.Series(dtype=float)

    records: list[tuple[pd.Timestamp, float]] = []
    for tx in transactions:
        tx_type = str(getattr(tx, "transaction_type", "")).upper()
        # Demand should only include outbound fulfillment, not adjustments.
        if tx_type == "OUTBOUND" and getattr(tx, "quantity_delta", 0) < 0:
            tx_date = pd.Timestamp(getattr(tx, "created_at").date())
            records.append((tx_date, float(abs(getattr(tx, "quantity_delta")))))

    if not records:
        return pd.Series(dtype=float)

    frame = pd.DataFrame(records, columns=["date", "demand"])
    grouped = frame.groupby("date", as_index=True)["demand"].sum().sort_index()

    end_date = pd.Timestamp.today().normalize()
    start_date = max(grouped.index.min(), end_date - pd.Timedelta(days=days_lookback))
    full_range = pd.date_range(start=start_date, end=end_date, freq="D")

    return grouped.reindex(full_range, fill_value=0.0).astype(float)


def generate_forecast(
    series: pd.Series,
    horizon_days: int = 30,
    allow_ml: bool = True,
) -> ForecastResult:
    horizon_days = max(1, int(horizon_days))
    if series.empty or float(series.sum()) == 0.0:
        forecast = []
        start = pd.Timestamp.today().normalize()
        for i in range(1, horizon_days + 1):
            current_date = (start + timedelta(days=i)).date()
            forecast.append({"date": current_date, "p10": 0.0, "p50": 0.0, "p90": 0.0})
        return ForecastResult(
            method="zero-demand-baseline",
            holdout_wape=None,
            history=[],
            forecast=forecast,
            daily_mean=0.0,
            daily_std=0.0,
        )

    model_ready, feature_frame = _build_feature_frame(series)

    if allow_ml and model_ready and len(feature_frame) >= 50:
        return _gradient_boosted_forecast(series, feature_frame, horizon_days)
    return _weighted_average_forecast(series, horizon_days)


def _build_feature_frame(series: pd.Series) -> tuple[bool, pd.DataFrame]:
    frame = pd.DataFrame(index=series.index)
    frame["y"] = series.values

    for lag in LAG_FEATURES:
        frame[f"lag_{lag}"] = frame["y"].shift(lag)

    frame["rolling_mean_7"] = frame["y"].shift(1).rolling(window=7).mean()
    frame["rolling_std_7"] = frame["y"].shift(1).rolling(window=7).std().fillna(0.0)
    frame["dow"] = frame.index.dayofweek
    frame["month"] = frame.index.month
    frame["trend"] = np.arange(len(frame), dtype=float)

    frame = frame.dropna()
    return not frame.empty, frame


def _gradient_boosted_forecast(
    series: pd.Series,
    feature_frame: pd.DataFrame,
    horizon_days: int,
) -> ForecastResult:
    target = feature_frame["y"]
    features = feature_frame.drop(columns=["y"])

    holdout = max(7, min(14, len(features) // 5))
    if len(features) <= holdout + 10:
        return _weighted_average_forecast(series, horizon_days)

    x_train, x_test = features.iloc[:-holdout], features.iloc[-holdout:]
    y_train, y_test = target.iloc[:-holdout], target.iloc[-holdout:]

    model = GradientBoostingRegressor(
        random_state=42,
        n_estimators=300,
        learning_rate=0.05,
        max_depth=3,
        loss="squared_error",
    )
    model.fit(x_train, y_train)

    y_test_pred = np.maximum(model.predict(x_test), 0.0)
    denominator = float(np.maximum(y_test.sum(), 1.0))
    holdout_wape = float(np.abs(y_test - y_test_pred).sum() / denominator)

    residuals = y_test - y_test_pred
    sigma = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else float(series.std())
    sigma = max(sigma, 0.1)

    history_series = series.copy()
    forecast_rows: list[dict[str, float | date]] = []

    for step in range(1, horizon_days + 1):
        next_date = history_series.index[-1] + timedelta(days=1)
        feature_row = _feature_row_from_history(history_series, next_date)
        point_forecast = float(max(model.predict(feature_row)[0], 0.0))

        uncertainty = sigma * np.sqrt(step)
        p10 = max(0.0, point_forecast + P10_Z * uncertainty)
        p90 = max(point_forecast, point_forecast + P90_Z * uncertainty)

        forecast_rows.append(
            {
                "date": next_date.date(),
                "p10": round(p10, 3),
                "p50": round(point_forecast, 3),
                "p90": round(p90, 3),
            }
        )

        history_series.loc[next_date] = point_forecast

    history = [
        {"date": idx.date().isoformat(), "demand": float(value)}
        for idx, value in series.tail(90).items()
    ]

    return ForecastResult(
        method="gradient-boosted-lag-model",
        holdout_wape=round(holdout_wape, 4),
        history=history,
        forecast=forecast_rows,
        daily_mean=float(np.mean([row["p50"] for row in forecast_rows])),
        daily_std=sigma,
    )


def _feature_row_from_history(history: pd.Series, next_date: pd.Timestamp) -> pd.DataFrame:
    features: dict[str, float] = {}

    history_mean = float(history.mean()) if len(history) > 0 else 0.0
    for lag in LAG_FEATURES:
        if len(history) >= lag:
            features[f"lag_{lag}"] = float(history.iloc[-lag])
        else:
            features[f"lag_{lag}"] = history_mean

    window = history.tail(7)
    features["rolling_mean_7"] = float(window.mean()) if not window.empty else history_mean
    features["rolling_std_7"] = float(window.std(ddof=0)) if len(window) > 1 else 0.0
    features["dow"] = float(next_date.dayofweek)
    features["month"] = float(next_date.month)
    features["trend"] = float(len(history))

    return pd.DataFrame([features])


def _weighted_average_forecast(series: pd.Series, horizon_days: int) -> ForecastResult:
    window_size = min(28, len(series))
    recent = series.tail(window_size).values

    weights = np.arange(1, window_size + 1)
    weighted_mean = float(np.dot(recent, weights) / weights.sum())

    weekday_mean = series.groupby(series.index.dayofweek).mean()
    overall_mean = float(series.mean()) if float(series.mean()) > 0 else 1.0
    sigma = max(float(series.std(ddof=1)) if len(series) > 1 else 0.0, 0.1)

    forecast_rows: list[dict[str, float | date]] = []
    last_date = series.index[-1]

    for step in range(1, horizon_days + 1):
        future_date = last_date + timedelta(days=step)
        weekday_factor = float(weekday_mean.get(future_date.dayofweek, overall_mean) / overall_mean)
        point_forecast = max(weighted_mean * weekday_factor, 0.0)

        uncertainty = sigma * np.sqrt(step)
        p10 = max(0.0, point_forecast + P10_Z * uncertainty)
        p90 = max(point_forecast, point_forecast + P90_Z * uncertainty)

        forecast_rows.append(
            {
                "date": future_date.date(),
                "p10": round(float(p10), 3),
                "p50": round(float(point_forecast), 3),
                "p90": round(float(p90), 3),
            }
        )

    history = [
        {"date": idx.date().isoformat(), "demand": float(value)}
        for idx, value in series.tail(90).items()
    ]

    return ForecastResult(
        method="weighted-moving-average",
        holdout_wape=None,
        history=history,
        forecast=forecast_rows,
        daily_mean=float(np.mean([row["p50"] for row in forecast_rows])),
        daily_std=sigma,
    )
