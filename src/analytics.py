import pandas as pd
from typing import Dict, Any, List
from src.database import query_one, query_all, query_df
from src.inventory_rules import get_inventory_status_df, get_low_stock_items
from src.sales_rules import get_store_performance, get_category_performance, get_daily_sales_trend

from src.dataset_manager import ActiveDatasetManager

def get_dashboard_summary(store_id: str = None, target_date: str = None) -> Dict[str, Any]:
    """
    Computes top-level KPIs for store managers, supporting historical date snapshots.
    Validates target_date against database bounds.
    Returns 0/empty values when no dataset is active (NO_DATA state).
    """
    if ActiveDatasetManager.get_active_dataset_id() is None:
        return {
            "target_date": target_date,
            "store_id": store_id or "all",
            "no_data": True,
            "message": "No dataset active. Upload your retail data to get started.",
            "min_date": None,
            "max_date": None,
            "total_revenue": 0.0,
            "total_units_sold": 0,
            "total_transactions": 0,
            "total_inventory_records": 0,
            "total_skus": 0,
            "total_inventory_units": 0,
            "total_inventory_valuation": 0.0,
            "critical_low_stock_count": 0,
            "warning_low_stock_count": 0,
            "slow_moving_count": 0,
            "overstock_count": 0,
            "healthy_stock_count": 0,
            "no_recent_demand_count": 0,
            "sales_growth_pct": 0.0,
            "top_performing_store": "N/A",
            "store_performance": [],
            "category_performance": [],
            "top_products": [],
            "daily_trend": [],
            "sparklines": {
                "revenue": [],
                "units": [],
                "lowstock": [],
                "overstock": [],
                "growth": []
            }
        }

    # Check DB date bounds
    bounds = query_one("SELECT MIN(date) as min_date, MAX(date) as max_date FROM sales")
    min_date = str(bounds["min_date"]) if bounds and bounds.get("min_date") else None
    max_date = str(bounds["max_date"]) if bounds and bounds.get("max_date") else None

    if target_date and min_date and max_date:
        if target_date > max_date and target_date.startswith(max_date[:4]):
            target_date = max_date
        elif target_date < min_date or target_date > max_date:
            return {
                "target_date": target_date,
                "store_id": store_id or "all",
                "no_data": True,
                "message": f"No data available for {target_date}. Supported dataset range: {min_date} to {max_date}.",
                "min_date": min_date,
                "max_date": max_date,
                "total_revenue": 0.0,
                "total_units_sold": 0,
                "total_transactions": 0,
                "total_inventory_records": 0,
                "total_skus": 0,
                "total_inventory_units": 0,
                "total_inventory_valuation": 0.0,
                "critical_low_stock_count": 0,
                "warning_low_stock_count": 0,
                "slow_moving_count": 0,
                "overstock_count": 0,
                "healthy_stock_count": 0,
                "no_recent_demand_count": 0,
                "sales_growth_pct": 0.0,
                "top_performing_store": "N/A",
                "store_performance": [],
                "category_performance": [],
                "top_products": [],
                "daily_trend": [],
                "sparklines": {
                    "revenue": [],
                    "units": [],
                    "lowstock": [],
                    "overstock": [],
                    "growth": []
                }
            }

    where_sales = []
    params_sales = []

    if store_id and store_id != "all":
        where_sales.append("store_id = ?")
        params_sales.append(store_id)

    if target_date:
        where_sales.append("date <= ? AND date >= date(?, '-30 days')")
        params_sales.extend([target_date, target_date])

    clause_str = " WHERE " + " AND ".join(where_sales) if where_sales else ""

    # 1. Total Sales Metrics
    sales_kpi = query_one(f"""
        SELECT 
            COALESCE(SUM(total_revenue), 0) as total_revenue,
            COALESCE(SUM(quantity), 0) as total_units_sold,
            COUNT(DISTINCT sale_id) as total_transactions
        FROM sales
        {clause_str}
    """, tuple(params_sales))

    # 2. Inventory Valuation & Low Stock Count (Reconstructed on target_date)
    inv_df = get_inventory_status_df(store_id=store_id, target_date=target_date)
    total_inventory_records = int(len(inv_df)) if not inv_df.empty else 0
    total_skus = int(inv_df['product_id'].nunique()) if not inv_df.empty else 0
    total_inventory_units = int(inv_df['current_stock'].sum()) if not inv_df.empty else 0
    total_inventory_valuation = float(inv_df['stock_value'].sum()) if not inv_df.empty else 0.0
    
    critical_count = len(inv_df[inv_df['status'].isin(['CRITICAL', 'OUT_OF_STOCK'])]) if not inv_df.empty else 0
    warning_count = len(inv_df[inv_df['status'] == 'WARNING']) if not inv_df.empty else 0
    slow_count = len(inv_df[inv_df['status'] == 'SLOW_MOVING']) if not inv_df.empty else 0
    overstock_count = len(inv_df[inv_df['status'] == 'OVERSTOCK']) if not inv_df.empty else 0
    healthy_count = len(inv_df[inv_df['status'] == 'HEALTHY']) if not inv_df.empty else 0
    no_demand_count = len(inv_df[inv_df['status'] == 'NO_RECENT_DEMAND']) if not inv_df.empty else 0

    # 3. Store Performance
    stores_perf = get_store_performance(store_id=store_id)
    top_store = stores_perf[0]['store_name'] if stores_perf else "N/A"

    # 4. Top Products by Revenue
    top_prod_where = []
    top_prod_params = []
    if store_id and store_id != "all":
        top_prod_where.append("s.store_id = ?")
        top_prod_params.append(store_id)
    if target_date:
        top_prod_where.append("s.date <= ? AND s.date >= date(?, '-30 days')")
        top_prod_params.extend([target_date, target_date])
    
    top_clause = " WHERE " + " AND ".join(top_prod_where) if top_prod_where else ""

    top_products = query_all(f"""
        SELECT 
            p.product_id,
            p.product_name,
            p.category,
            SUM(s.quantity) as units_sold,
            ROUND(SUM(s.total_revenue), 2) as revenue
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        {top_clause}
        GROUP BY p.product_id, p.product_name, p.category
        ORDER BY revenue DESC
        LIMIT 5
    """, tuple(top_prod_params))

    # 5. Sales Trend (Last 30 Days relative to target_date or latest)
    daily_trend = get_daily_sales_trend(30, store_id=store_id, target_date=target_date)
    recent_7d_rev = [d["total_revenue"] for d in daily_trend[-7:]] if len(daily_trend) >= 7 else [d["total_revenue"] for d in daily_trend]
    recent_7d_units = [d["total_units"] for d in daily_trend[-7:]] if len(daily_trend) >= 7 else [d["total_units"] for d in daily_trend]

    # Compute realistic sales growth from daily trend (last 7d vs prior 7d)
    growth_pct = 0.0
    if len(daily_trend) >= 14:
        curr_7d_rev = sum(d["total_revenue"] for d in daily_trend[-7:])
        prev_7d_rev = sum(d["total_revenue"] for d in daily_trend[-14:-7])
        if prev_7d_rev > 0:
            growth_pct = round(((curr_7d_rev - prev_7d_rev) / prev_7d_rev) * 100.0, 1)
    elif len(daily_trend) >= 2:
        first_rev = daily_trend[0]["total_revenue"]
        last_rev = daily_trend[-1]["total_revenue"]
        if first_rev > 0:
            growth_pct = round(((last_rev - first_rev) / first_rev) * 100.0, 1)

    return {
        "target_date": target_date,
        "store_id": store_id or "all",
        "no_data": False,
        "total_revenue": round(sales_kpi["total_revenue"], 2),
        "total_units_sold": sales_kpi["total_units_sold"],
        "total_transactions": sales_kpi["total_transactions"],
        "total_inventory_records": total_inventory_records,
        "total_skus": total_skus,
        "total_inventory_units": total_inventory_units,
        "total_inventory_valuation": round(total_inventory_valuation, 2),
        "critical_low_stock_count": critical_count,
        "warning_low_stock_count": warning_count,
        "slow_moving_count": slow_count,
        "overstock_count": overstock_count,
        "healthy_stock_count": healthy_count,
        "no_recent_demand_count": no_demand_count,
        "sales_growth_pct": growth_pct,
        "top_performing_store": top_store,
        "store_performance": stores_perf,
        "category_performance": get_category_performance(store_id=store_id),
        "top_products": top_products,
        "daily_trend": daily_trend,
        "sparklines": {
            "revenue": recent_7d_rev,
            "units": recent_7d_units,
            "lowstock": [max(0, critical_count + warning_count) for _ in range(len(recent_7d_rev))],
            "overstock": [max(0, overstock_count) for _ in range(len(recent_7d_rev))],
            "growth": [growth_pct] * len(recent_7d_rev) if recent_7d_rev else []
        }
    }
