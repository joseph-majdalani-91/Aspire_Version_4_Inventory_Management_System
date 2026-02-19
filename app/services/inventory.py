from __future__ import annotations

from math import ceil, sqrt
from statistics import NormalDist


def calculate_reorder_policy(
    on_hand: int,
    lead_time_days: int,
    service_level: float,
    daily_forecast_p50: float,
    daily_std: float,
    review_period_days: int = 7,
    min_order_qty: int = 0,
    safety_stock_override: int | None = None,
) -> dict[str, int | float | str]:
    lead_time_days = max(1, lead_time_days)
    review_period_days = max(1, review_period_days)
    service_level = min(max(service_level, 0.5), 0.999)

    z_value = NormalDist().inv_cdf(service_level)
    model_safety_stock = z_value * daily_std * sqrt(lead_time_days)

    if safety_stock_override is not None:
        safety_stock = max(float(safety_stock_override), model_safety_stock)
    else:
        safety_stock = model_safety_stock

    lead_time_demand = daily_forecast_p50 * lead_time_days
    reorder_point = lead_time_demand + safety_stock
    target_stock = reorder_point + (daily_forecast_p50 * review_period_days)

    recommended_order_qty = max(0, int(ceil(target_stock - on_hand)))
    if recommended_order_qty > 0 and min_order_qty > 0:
        recommended_order_qty = int(ceil(recommended_order_qty / min_order_qty) * min_order_qty)

    if on_hand <= reorder_point * 0.5:
        stockout_risk = "HIGH"
    elif on_hand <= reorder_point:
        stockout_risk = "MEDIUM"
    else:
        stockout_risk = "LOW"

    return {
        "on_hand": int(on_hand),
        "lead_time_days": int(lead_time_days),
        "forecast_daily_p50": round(float(daily_forecast_p50), 3),
        "safety_stock": int(round(safety_stock)),
        "reorder_point": int(round(reorder_point)),
        "target_stock": int(round(target_stock)),
        "recommended_order_qty": int(recommended_order_qty),
        "stockout_risk": stockout_risk,
    }
