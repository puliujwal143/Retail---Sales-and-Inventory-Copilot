"""
RetailIQ Deterministic Sales Forecasting Engine
Calculates 7-day, 14-day, and 30-day demand forecasts using historical daily sales trend weights.
Compares projected demand vs stock to flag potential stock-out risks.
Zero external ML dependencies; pure Python + SQLite.
"""

from typing import Dict, Any, List, Optional
import math
from src.database import query_df, query_all

def calculate_sales_forecast(product_id: str, store_id: Optional[str] = None, target_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes deterministic demand forecast for a product across 7, 14, and 30 days.
    """
    params = [product_id]
    store_filter = ""
    if store_id and store_id != "all":
        store_filter = "AND sales.store_id = ?"
        params.append(store_id)

    date_filter = ""
    if target_date:
        date_filter = "AND sales.date <= ?"
        params.append(target_date)

    # Fetch last 60 days of daily sales for this product
    sql = f"""
        SELECT sales.date, SUM(sales.quantity) as daily_units, SUM(sales.total_revenue) as daily_rev
        FROM sales
        WHERE sales.product_id = ? {store_filter} {date_filter}
        GROUP BY sales.date
        ORDER BY sales.date DESC
        LIMIT 60
    """
    df = query_df(sql, tuple(params))

    if df.empty or len(df) < 5:
        return {
            "status": "insufficient_data",
            "message": "Insufficient historical data to produce a reliable forecast.",
            "forecast_7d": 0,
            "forecast_14d": 0,
            "forecast_30d": 0,
            "stockout_risk": False,
            "confidence": "Low"
        }

    # Sort chronological
    df = df.sort_values("date")
    quantities = df["daily_units"].tolist()
    dates = df["date"].tolist()

    # Calculate weighted moving average (recent 14 days weighted higher)
    recent_14 = quantities[-14:] if len(quantities) >= 14 else quantities
    prior_14 = quantities[-28:-14] if len(quantities) >= 28 else quantities

    avg_recent = sum(recent_14) / max(1, len(recent_14))
    avg_prior = sum(prior_14) / max(1, len(prior_14))

    # Trend multiplier (bounded between 0.75x and 1.35x)
    trend_factor = 1.0
    if avg_prior > 0:
        trend_factor = max(0.75, min(1.35, avg_recent / avg_prior))

    daily_projected = avg_recent * trend_factor
    forecast_7d = math.ceil(daily_projected * 7)
    forecast_14d = math.ceil(daily_projected * 14)
    forecast_30d = math.ceil(daily_projected * 30)

    # Current stock check
    inv_params = [product_id]
    inv_store = ""
    if store_id and store_id != "all":
        inv_store = "AND store_id = ?"
        inv_params.append(store_id)

    inv_sql = f"SELECT SUM(current_stock) as total_stock FROM inventory WHERE product_id = ? {inv_store}"
    inv_res = query_all(inv_sql, tuple(inv_params))
    current_stock = inv_res[0]["total_stock"] if inv_res and inv_res[0]["total_stock"] is not None else 0

    stockout_7d = current_stock < forecast_7d
    stockout_14d = current_stock < forecast_14d

    # Generate Chart Data
    chart_labels = dates[-14:] + [f"Day +{i}" for i in range(1, 8)]
    hist_data = [int(q) for q in quantities[-14:]]
    forecast_data = [None] * len(hist_data) + [round(daily_projected * i, 1) for i in range(1, 8)]
    chart_hist_padded = hist_data + [None] * 7
    # Connect transition
    if hist_data:
        chart_hist_padded[len(hist_data)-1] = hist_data[-1]
        forecast_data[len(hist_data)-1] = hist_data[-1]

    return {
        "status": "success",
        "product_id": product_id,
        "store_id": store_id or "all",
        "current_stock": current_stock,
        "daily_avg_recent": round(avg_recent, 2),
        "trend_factor": round(trend_factor, 2),
        "forecast_7d": forecast_7d,
        "forecast_14d": forecast_14d,
        "forecast_30d": forecast_30d,
        "stockout_7d_risk": stockout_7d,
        "stockout_14d_risk": stockout_14d,
        "recommended_action": f"Reorder +{forecast_7d - current_stock + 10} units immediately to prevent 7-day stock-out" if stockout_7d else "Current stock is sufficient for 7-day projected demand.",
        "chart_spec": {
            "type": "line",
            "title": f"7-Day Demand Forecast (Estimated) vs Historical Sales",
            "labels": chart_labels,
            "datasets": [
                {"label": "Historical Daily Sales", "data": chart_hist_padded, "color": "#087F80"},
                {"label": "Forecasted Demand (Projected)", "data": forecast_data, "color": "#F59E0B"}
            ]
        }
    }
