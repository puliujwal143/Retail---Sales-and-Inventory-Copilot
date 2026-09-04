import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from src.database import query_df, query_all

SPIKE_THRESHOLD_PCT = 30.0  # >= +30% change is a sales spike
DROP_THRESHOLD_PCT = -30.0   # <= -30% change is a sales drop

def get_product_sales_trends(time_days: int = 30, store_id: Optional[str] = None) -> pd.DataFrame:
    """
    Compares sales in recent N-day period vs previous N-day period per product.
    Calculates exact percentage change and flags sales spikes / drops.
    """
    where_clause = ""
    params = [time_days, time_days, 2 * time_days]
    if store_id and store_id != "all":
        where_clause = "AND s.store_id = ?"
        params = [time_days, store_id, time_days, 2 * time_days, store_id]

    query = f"""
    WITH max_date_cte AS (
        SELECT MAX(date) as max_date FROM sales
    ),
    curr_period AS (
        SELECT 
            s.product_id,
            COALESCE(SUM(s.quantity), 0) as curr_units,
            COALESCE(SUM(s.total_revenue), 0) as curr_revenue
        FROM sales s, max_date_cte m
        WHERE s.date >= date(m.max_date, '-' || ? || ' days') {where_clause}
        GROUP BY s.product_id
    ),
    prev_period AS (
        SELECT 
            s.product_id,
            COALESCE(SUM(s.quantity), 0) as prev_units,
            COALESCE(SUM(s.total_revenue), 0) as prev_revenue
        FROM sales s, max_date_cte m
        WHERE s.date < date(m.max_date, '-' || ? || ' days') 
          AND s.date >= date(m.max_date, '-' || ? || ' days') {where_clause}
        GROUP BY s.product_id
    )
    SELECT 
        p.product_id,
        p.product_name,
        p.category,
        p.unit_price,
        COALESCE(c.curr_units, 0) as curr_units_30d,
        COALESCE(c.curr_revenue, 0) as curr_revenue_30d,
        COALESCE(pr.prev_units, 0) as prev_units_30d,
        COALESCE(pr.prev_revenue, 0) as prev_revenue_30d
    FROM products p
    LEFT JOIN curr_period c ON p.product_id = c.product_id
    LEFT JOIN prev_period pr ON p.product_id = pr.product_id
    """
    
    df = query_df(query, tuple(params))
    if df.empty:
        return df

    def calc_pct_change(row):
        curr = row['curr_units_30d']
        prev = row['prev_units_30d']
        if prev == 0:
            return 100.0 if curr > 0 else 0.0
        return round(((curr - prev) / prev) * 100.0, 1)

    df['pct_change_units'] = df.apply(calc_pct_change, axis=1)

    def flag_trend(pct):
        if pct >= SPIKE_THRESHOLD_PCT:
            return "SALES_SPIKE"
        elif pct <= DROP_THRESHOLD_PCT:
            return "SALES_DROP"
        else:
            return "STEADY"

    df['trend_flag'] = df['pct_change_units'].apply(flag_trend)
    return df

def get_sales_spikes(time_days: int = 30) -> List[Dict[str, Any]]:
    """Returns products experiencing a sales spike (>= +30%)."""
    df = get_product_sales_trends(time_days)
    if df.empty:
        return []
    spikes = df[df['trend_flag'] == 'SALES_SPIKE'].sort_values(by='pct_change_units', ascending=False)
    return spikes.to_dict(orient='records')

def get_sales_drops(time_days: int = 30) -> List[Dict[str, Any]]:
    """Returns products experiencing a sales drop (<= -30%)."""
    df = get_product_sales_trends(time_days)
    if df.empty:
        return []
    drops = df[df['trend_flag'] == 'SALES_DROP'].sort_values(by='pct_change_units')
    return drops.to_dict(orient='records')

def get_store_performance(store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns total revenue and total units sold per store."""
    where_clause = ""
    params = ()
    if store_id and store_id != "all":
        where_clause = "WHERE st.store_id = ?"
        params = (store_id,)

    query = f"""
    SELECT 
        st.store_id,
        st.store_name,
        st.location,
        COALESCE(SUM(s.quantity), 0) as total_units_sold,
        ROUND(COALESCE(SUM(s.total_revenue), 0), 2) as total_revenue
    FROM stores st
    LEFT JOIN sales s ON st.store_id = s.store_id
    {where_clause}
    GROUP BY st.store_id, st.store_name, st.location
    ORDER BY total_revenue DESC
    """
    return query_all(query, params)

def get_category_performance(store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns sales performance broken down by product category."""
    where_clause = ""
    params = ()
    if store_id and store_id != "all":
        where_clause = "WHERE s.store_id = ?"
        params = (store_id,)

    query = f"""
    SELECT 
        p.category,
        COUNT(DISTINCT p.product_id) as product_count,
        COALESCE(SUM(s.quantity), 0) as total_units_sold,
        ROUND(COALESCE(SUM(s.total_revenue), 0), 2) as total_revenue
    FROM products p
    LEFT JOIN sales s ON p.product_id = s.product_id {where_clause}
    GROUP BY p.category
    ORDER BY total_revenue DESC
    """
    return query_all(query, params)

def get_daily_sales_trend(days: int = 30, store_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns aggregate daily revenue and volume for the last N days."""
    where_clause = ""
    params = [days]
    if store_id and store_id != "all":
        where_clause = "AND s.store_id = ?"
        params = [days, store_id]

    query = f"""
    WITH max_date_cte AS (
        SELECT MAX(date) as max_date FROM sales
    )
    SELECT 
        s.date,
        SUM(s.quantity) as total_units,
        ROUND(SUM(s.total_revenue), 2) as total_revenue
    FROM sales s, max_date_cte m
    WHERE s.date >= date(m.max_date, '-' || ? || ' days') {where_clause}
    GROUP BY s.date
    ORDER BY s.date ASC
    """
    return query_all(query, tuple(params))

def get_sales_analytics_charts(days: int = 30, store_id: Optional[str] = "all", category: Optional[str] = "all") -> Dict[str, Any]:
    """
    Generates structured chart specs and deterministic insights for the Sales Analytics Workspace.
    """
    # 1. Daily Trend (Revenue & Units)
    daily = get_daily_sales_trend(days=days, store_id=store_id)
    dates = [d["date"] for d in daily]
    revenues = [d["total_revenue"] for d in daily]
    units = [d["total_units"] for d in daily]

    revenue_trend_chart = {
        "type": "line",
        "title": f"Revenue Movement ({days} Days)",
        "subtitle": "Daily revenue trajectory",
        "labels": dates,
        "datasets": [{"label": "Revenue ($)", "data": revenues, "color": "#3b82f6"}]
    }

    units_trend_chart = {
        "type": "area",
        "title": f"Units Sold Over Time ({days} Days)",
        "subtitle": "Daily unit demand volume",
        "labels": dates,
        "datasets": [{"label": "Units Sold", "data": units, "color": "#10b981"}]
    }

    # 2. Category Performance Chart
    categories = get_category_performance(store_id=store_id)
    cat_names = [c["category"] for c in categories]
    cat_revs = [c["total_revenue"] for c in categories]

    category_chart = {
        "type": "bar",
        "title": "Revenue by Product Category",
        "subtitle": "Total revenue per category",
        "labels": cat_names,
        "datasets": [{"label": "Category Revenue ($)", "data": cat_revs, "color": "#8b5cf6"}]
    }

    # 3. Top Products Horizontal Bar Chart
    top_p_query = """
    SELECT p.product_name, COALESCE(SUM(s.quantity), 0) as units, ROUND(COALESCE(SUM(s.total_revenue), 0), 2) as revenue
    FROM sales s JOIN products p ON s.product_id = p.product_id
    WHERE s.date >= date((SELECT MAX(date) FROM sales), '-' || ? || ' days')
    GROUP BY p.product_id, p.product_name
    ORDER BY revenue DESC LIMIT 5
    """
    top_p_data = query_all(top_p_query, (days,))
    top_p_names = [p["product_name"] for p in top_p_data]
    top_p_revs = [p["revenue"] for p in top_p_data]

    top_products_chart = {
        "type": "horizontal_bar",
        "title": "Top 5 Products by Revenue",
        "subtitle": f"Highest revenue items in last {days} days",
        "labels": top_p_names,
        "datasets": [{"label": "Revenue ($)", "data": top_p_revs, "color": "#06b6d4"}]
    }

    # 4. Store Performance Chart
    stores = get_store_performance()
    st_names = [s["store_name"] for s in stores]
    st_revs = [s["total_revenue"] for s in stores]

    store_chart = {
        "type": "bar",
        "title": "Store Performance Comparison",
        "subtitle": "Revenue breakdown across retail store locations",
        "labels": st_names,
        "datasets": [{"label": "Store Revenue ($)", "data": st_revs, "color": "#f59e0b"}]
    }

    # 5. Deterministic AI Insights
    spikes = get_sales_spikes(time_days=days)
    drops = get_sales_drops(time_days=days)

    total_revenue_val = sum(revenues)
    total_units_val = sum(units)
    top_cat = categories[0]["category"] if categories else "N/A"
    top_st = stores[0]["store_name"] if stores else "N/A"

    insights = [
        f"Total revenue reached ${total_revenue_val:,.2f} with {total_units_val:,} units sold over the last {days} days.",
        f"Category '{top_cat}' is the primary revenue driver at ${categories[0]['total_revenue']:,.2f}.",
        f"Top performing store location is '{top_st}' generating ${stores[0]['total_revenue']:,.2f} total revenue.",
    ]

    if spikes:
        s0 = spikes[0]
        insights.append(f"Product '{s0['product_name']}' experienced a +{s0['pct_change_units']}% sales surge ({s0['prev_units_30d']} -> {s0['curr_units_30d']} units).")
    if drops:
        d0 = drops[0]
        insights.append(f"Product '{d0['product_name']}' experienced a {d0['pct_change_units']}% sales drop ({d0['prev_units_30d']} -> {d0['curr_units_30d']} units).")

    return {
        "time_days": days,
        "revenue_trend": revenue_trend_chart,
        "units_trend": units_trend_chart,
        "category_chart": category_chart,
        "top_products_chart": top_products_chart,
        "store_chart": store_chart,
        "spikes": spikes,
        "drops": drops,
        "insights": insights
    }
