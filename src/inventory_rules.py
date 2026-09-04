import pandas as pd
import numpy as np
from typing import Dict, List, Any
from src.database import query_df, query_all

# Configurable system assumptions & business rules thresholds
TARGET_COVERAGE_DAYS = 7        # Default target stock coverage in days
CRITICAL_DAYS_THRESHOLD = 2.0  # Days remaining <= 2 is Critical
WARNING_DAYS_THRESHOLD = 7.0   # Days remaining <= 7 is Warning
OVERSTOCK_DAYS_THRESHOLD = 30.0 # Days remaining > 30 is Overstock
OVERSTOCK_MIN_UNITS = 50       # Minimum stock to qualify as Overstock
SLOW_MOVING_MAX_SALES = 5      # Sales in 30 days < 5 is Slow Moving
SLOW_MOVING_MIN_STOCK = 20     # Minimum stock to qualify as Slow Moving

def get_inventory_status_df(store_id: str = None, category: str = None) -> pd.DataFrame:
    """
    Computes deterministic inventory status metrics across stores and products.
    Calculates average daily sales (last 30 days), days remaining, status, and recommended reorder.
    """
    # SQL query joining inventory, products, stores, and 30-day sales
    query = """
    WITH sales_30d AS (
        SELECT 
            product_id, 
            store_id, 
            COALESCE(SUM(quantity), 0) as units_sold_30d,
            COALESCE(SUM(total_revenue), 0) as revenue_30d
        FROM sales
        WHERE date >= date((SELECT MAX(date) FROM sales), '-30 days')
        GROUP BY product_id, store_id
    )
    SELECT 
        i.store_id,
        st.store_name,
        i.product_id,
        p.product_name,
        p.category,
        p.unit_price,
        p.cost_price,
        p.reorder_point,
        i.current_stock,
        i.last_restock_date,
        COALESCE(s.units_sold_30d, 0) as units_sold_30d,
        COALESCE(s.revenue_30d, 0) as revenue_30d
    FROM inventory i
    JOIN products p ON i.product_id = p.product_id
    JOIN stores st ON i.store_id = st.store_id
    LEFT JOIN sales_30d s ON i.product_id = s.product_id AND i.store_id = s.store_id
    """
    
    where_clauses = []
    params = []
    if store_id and store_id != "all":
        where_clauses.append("i.store_id = ?")
        params.append(store_id)
    if category and category != "all":
        where_clauses.append("p.category = ?")
        params.append(category)
        
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
        
    df = query_df(query, tuple(params))
    if df.empty:
        return df

    # Deterministic Business Rule Calculations
    # 1. Average Daily Sales over 30 days
    df['average_daily_sales'] = df['units_sold_30d'] / 30.0

    # 2. Days Remaining (Handling division by zero)
    # If ADS > 0, stock / ADS. If ADS == 0 and stock > 0, 999.0 (Infinite coverage). If stock == 0 and ADS == 0, 0.0.
    df['days_remaining'] = np.where(
        df['average_daily_sales'] > 0,
        df['current_stock'] / df['average_daily_sales'],
        np.where(df['current_stock'] > 0, 999.0, 0.0)
    )
    df['days_remaining'] = df['days_remaining'].round(1)

    # 3. Status Classification
    def classify_status(row):
        days = row['days_remaining']
        stock = row['current_stock']
        sold_30d = row['units_sold_30d']
        
        if stock == 0:
            return "OUT_OF_STOCK"
        elif days <= CRITICAL_DAYS_THRESHOLD:
            return "CRITICAL"
        elif days <= WARNING_DAYS_THRESHOLD:
            return "WARNING"
        elif sold_30d < SLOW_MOVING_MAX_SALES and stock >= SLOW_MOVING_MIN_STOCK:
            return "SLOW_MOVING"
        elif days > OVERSTOCK_DAYS_THRESHOLD and stock >= OVERSTOCK_MIN_UNITS:
            return "OVERSTOCK"
        else:
            return "HEALTHY"

    df['status'] = df.apply(classify_status, axis=1)

    # 4. Recommended Reorder Calculation
    # Target stock = ADS * TARGET_COVERAGE_DAYS
    # Recommended reorder = max(0, target_stock - current_stock)
    def calc_reorder(row):
        ads = row['average_daily_sales']
        stock = row['current_stock']
        target_stock = ads * TARGET_COVERAGE_DAYS
        reorder_qty = max(0, target_stock - stock)
        return int(np.ceil(reorder_qty))

    df['recommended_reorder'] = df.apply(calc_reorder, axis=1)
    df['stock_value'] = (df['current_stock'] * df['cost_price']).round(2)

    return df

def get_low_stock_items() -> List[Dict[str, Any]]:
    """Returns all items in CRITICAL or WARNING status sorted by days remaining."""
    df = get_inventory_status_df()
    if df.empty:
        return []
    filtered = df[df['status'].isin(['CRITICAL', 'WARNING', 'OUT_OF_STOCK'])].sort_values(by='days_remaining')
    return filtered.to_dict(orient='records')

def get_slow_moving_items() -> List[Dict[str, Any]]:
    """Returns items classified as SLOW_MOVING."""
    df = get_inventory_status_df()
    if df.empty:
        return []
    filtered = df[df['status'] == 'SLOW_MOVING'].sort_values(by='units_sold_30d')
    return filtered.to_dict(orient='records')

def get_overstocked_items() -> List[Dict[str, Any]]:
    """Returns items classified as OVERSTOCK."""
    df = get_inventory_status_df()
    if df.empty:
        return []
    filtered = df[df['status'] == 'OVERSTOCK'].sort_values(by='days_remaining', ascending=False)
    return filtered.to_dict(orient='records')
