import pandas as pd
import numpy as np
from typing import Dict, List, Any
from src.database import query_df, query_all

SPIKE_THRESHOLD_PCT = 30.0  # >= +30% change is a sales spike
DROP_THRESHOLD_PCT = -30.0   # <= -30% change is a sales drop

def get_product_sales_trends() -> pd.DataFrame:
    """
    Compares sales in the recent 30-day period vs the previous 30-day period per product.
    Calculates exact percentage change and flags sales spikes / drops.
    """
    query = """
    WITH max_date_cte AS (
        SELECT MAX(date) as max_date FROM sales
    ),
    curr_30d AS (
        SELECT 
            s.product_id,
            COALESCE(SUM(s.quantity), 0) as curr_units,
            COALESCE(SUM(s.total_revenue), 0) as curr_revenue
        FROM sales s, max_date_cte m
        WHERE s.date >= date(m.max_date, '-30 days')
        GROUP BY s.product_id
    ),
    prev_30d AS (
        SELECT 
            s.product_id,
            COALESCE(SUM(s.quantity), 0) as prev_units,
            COALESCE(SUM(s.total_revenue), 0) as prev_revenue
        FROM sales s, max_date_cte m
        WHERE s.date < date(m.max_date, '-30 days') 
          AND s.date >= date(m.max_date, '-60 days')
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
    LEFT JOIN curr_30d c ON p.product_id = c.product_id
    LEFT JOIN prev_30d pr ON p.product_id = pr.product_id
    """
    
    df = query_df(query)
    if df.empty:
        return df

    # Percentage change in unit sales
    def calc_pct_change(row):
        curr = row['curr_units_30d']
        prev = row['prev_units_30d']
        if prev == 0:
            return 100.0 if curr > 0 else 0.0
        return round(((curr - prev) / prev) * 100.0, 1)

    df['pct_change_units'] = df.apply(calc_pct_change, axis=1)

    # Flag spikes & drops
    def flag_trend(pct):
        if pct >= SPIKE_THRESHOLD_PCT:
            return "SALES_SPIKE"
        elif pct <= DROP_THRESHOLD_PCT:
            return "SALES_DROP"
        else:
            return "STEADY"

    df['trend_flag'] = df['pct_change_units'].apply(flag_trend)
    return df

def get_sales_spikes() -> List[Dict[str, Any]]:
    """Returns products experiencing a sales spike (>= +30%)."""
    df = get_product_sales_trends()
    if df.empty:
        return []
    spikes = df[df['trend_flag'] == 'SALES_SPIKE'].sort_values(by='pct_change_units', ascending=False)
    return spikes.to_dict(orient='records')

def get_sales_drops() -> List[Dict[str, Any]]:
    """Returns products experiencing a sales drop (<= -30%)."""
    df = get_product_sales_trends()
    if df.empty:
        return []
    drops = df[df['trend_flag'] == 'SALES_DROP'].sort_values(by='pct_change_units')
    return drops.to_dict(orient='records')

def get_store_performance() -> List[Dict[str, Any]]:
    """Returns total revenue and total units sold per store."""
    query = """
    SELECT 
        st.store_id,
        st.store_name,
        st.location,
        COALESCE(SUM(s.quantity), 0) as total_units_sold,
        COALESCE(SUM(s.total_revenue), 0) as total_revenue
    FROM stores st
    LEFT JOIN sales s ON st.store_id = s.store_id
    GROUP BY st.store_id, st.store_name, st.location
    ORDER BY total_revenue DESC
    """
    return query_all(query)

def get_category_performance() -> List[Dict[str, Any]]:
    """Returns sales performance broken down by product category."""
    query = """
    SELECT 
        p.category,
        COUNT(DISTINCT p.product_id) as product_count,
        COALESCE(SUM(s.quantity), 0) as total_units_sold,
        COALESCE(SUM(s.total_revenue), 0) as total_revenue
    FROM products p
    LEFT JOIN sales s ON p.product_id = s.product_id
    GROUP BY p.category
    ORDER BY total_revenue DESC
    """
    return query_all(query)

def get_daily_sales_trend(days: int = 30) -> List[Dict[str, Any]]:
    """Returns aggregate daily revenue and volume for the last N days."""
    query = """
    WITH max_date_cte AS (
        SELECT MAX(date) as max_date FROM sales
    )
    SELECT 
        s.date,
        SUM(s.quantity) as total_units,
        ROUND(SUM(s.total_revenue), 2) as total_revenue
    FROM sales s, max_date_cte m
    WHERE s.date >= date(m.max_date, '-' || ? || ' days')
    GROUP BY s.date
    ORDER BY s.date ASC
    """
    return query_all(query, (days,))
