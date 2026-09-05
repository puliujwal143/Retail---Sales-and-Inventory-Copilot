import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple
from src.database import query_df, query_one, query_all

# Centralized configuration & business rules thresholds
INVENTORY_DEMAND_WINDOW_DAYS = 90  # Demand calculation window in calendar days
TARGET_COVERAGE_DAYS = 7           # Target stock coverage for reordering
CRITICAL_DAYS_THRESHOLD = 2.0      # Days remaining <= 2 is Critical
WARNING_DAYS_THRESHOLD = 7.0       # Days remaining <= 7 is Warning
OVERSTOCK_DAYS_THRESHOLD = 30.0    # Days remaining > 30 is Overstocked
SLOW_MOVING_MAX_SALES = 5          # Sales in 90 days < 5 is Slow Moving
SLOW_MOVING_MIN_STOCK = 20         # Minimum stock to qualify as Slow Moving

def get_recent_demand_period(target_date: str = None) -> Tuple[str, str, int]:
    """
    Returns (recent_start_date, recent_end_date, window_days).
    Dynamically computes available historical days in active dataset:
    - If active dataset has >= 90 days: uses trailing 90 days.
    - If active dataset has < 90 days (e.g. 45 days, 10 days, 5 days): uses all available days.
    - Resolves "today" / "latest" / None to the MAX date in the active dataset.
    Never fabricates missing days.
    """
    bounds = query_one("SELECT MIN(date) as min_d, MAX(date) as max_d FROM sales")
    min_date_str = str(bounds["min_d"]) if bounds and bounds.get("min_d") else "2026-01-01"
    max_date_str = str(bounds["max_d"]) if bounds and bounds.get("max_d") else "2026-01-01"

    if not target_date or target_date in ["today", "latest", "None", "null"]:
        end_date_str = max_date_str
    else:
        end_date_str = target_date
        if end_date_str > max_date_str:
            end_date_str = max_date_str
        if end_date_str < min_date_str:
            end_date_str = min_date_str

    dt_end = pd.to_datetime(end_date_str)
    dt_min = pd.to_datetime(min_date_str)
    
    total_available_days = max(1, (dt_end - dt_min).days + 1)
    window_days = min(INVENTORY_DEMAND_WINDOW_DAYS, total_available_days)

    dt_start = dt_end - pd.Timedelta(days=window_days - 1)
    start_date_str = dt_start.strftime("%Y-%m-%d")
    return start_date_str, end_date_str, window_days

from src.dataset_manager import ActiveDatasetManager

def get_inventory_status_df(store_id: str = None, category: str = None, target_date: str = None) -> pd.DataFrame:
    """
    Computes deterministic inventory status metrics across stores and products.
    Uses the centralized demand window for daily sales & coverage.
    """
    if ActiveDatasetManager.get_active_dataset_id() is None:
        return pd.DataFrame()

    start_date_str, end_date_str, window_days = get_recent_demand_period(target_date)

    # If target_date is not provided, or matches/exceeds the max dataset date, use current_stock directly
    bounds = query_one("SELECT MAX(date) as max_d FROM sales")
    max_dataset_date = str(bounds["max_d"]) if bounds and bounds.get("max_d") else "2026-01-01"
    is_historical_snapshot = bool(target_date and target_date < max_dataset_date)

    if is_historical_snapshot:
        query = """
        WITH date_stock AS (
            SELECT store_id, product_id, COALESCE(SUM(quantity), 0) as stock_on_date
            FROM inventory_movements
            WHERE date <= ?
            GROUP BY store_id, product_id
        ),
        recent_sales AS (
            SELECT 
                product_id, 
                store_id, 
                COALESCE(SUM(quantity), 0) as recent_units_sold,
                COALESCE(SUM(total_revenue), 0) as recent_revenue
            FROM sales
            WHERE date BETWEEN ? AND ?
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
            COALESCE(ds.stock_on_date, i.current_stock) as current_stock,
            i.last_restock_date,
            COALESCE(s.recent_units_sold, 0) as recent_units_sold,
            COALESCE(s.recent_revenue, 0) as recent_revenue
        FROM inventory i
        JOIN products p ON i.product_id = p.product_id
        JOIN stores st ON i.store_id = st.store_id
        LEFT JOIN date_stock ds ON i.product_id = ds.product_id AND i.store_id = ds.store_id
        LEFT JOIN recent_sales s ON i.product_id = s.product_id AND i.store_id = s.store_id
        """
        params = [target_date, start_date_str, end_date_str]
    else:
        query = """
        WITH recent_sales AS (
            SELECT 
                product_id, 
                store_id, 
                COALESCE(SUM(quantity), 0) as recent_units_sold,
                COALESCE(SUM(total_revenue), 0) as recent_revenue
            FROM sales
            WHERE date BETWEEN ? AND ?
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
            COALESCE(s.recent_units_sold, 0) as recent_units_sold,
            COALESCE(s.recent_revenue, 0) as recent_revenue
        FROM inventory i
        JOIN products p ON i.product_id = p.product_id
        JOIN stores st ON i.store_id = st.store_id
        LEFT JOIN recent_sales s ON i.product_id = s.product_id AND i.store_id = s.store_id
        """
        params = [start_date_str, end_date_str]

    where_clauses = []
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
    # 1. Average Daily Sales over available demand window
    df['average_daily_sales'] = df['recent_units_sold'] / float(window_days)

    # 2. Days Remaining / Coverage (Handle zero demand cleanly)
    def calc_days(row):
        stock = row['current_stock']
        ads = row['average_daily_sales']
        if pd.isna(stock) or stock is None or ads <= 0 or pd.isna(ads):
            return 999.0
        return round(float(stock) / float(ads), 1)

    df['days_remaining'] = df.apply(calc_days, axis=1)

    # 3. Status Classification
    def classify_status(row):
        stock = row['current_stock']
        days = row['days_remaining']
        ads = row['average_daily_sales']
        recent_sold = row['recent_units_sold']

        if pd.isna(stock) or stock is None:
            return "NO_STOCK_DATA"
        elif stock <= 0:
            return "OUT_OF_STOCK"
        elif ads <= 0:
            return "NO_RECENT_DEMAND"
        elif days <= CRITICAL_DAYS_THRESHOLD:
            return "CRITICAL"
        elif days <= WARNING_DAYS_THRESHOLD:
            return "WARNING"
        elif days > OVERSTOCK_DAYS_THRESHOLD:
            return "OVERSTOCK"
        elif recent_sold < SLOW_MOVING_MAX_SALES and stock >= SLOW_MOVING_MIN_STOCK:
            return "SLOW_MOVING"
        else:
            return "HEALTHY"

    df['status'] = df.apply(classify_status, axis=1)

    # 4. Recommended Reorder Calculation (Only for items running low)
    def calc_reorder(row):
        status = row['status']
        if status in ['CRITICAL', 'WARNING', 'OUT_OF_STOCK']:
            ads = row['average_daily_sales']
            stock = row['current_stock'] if not pd.isna(row['current_stock']) else 0
            if ads > 0:
                target_stock = ads * TARGET_COVERAGE_DAYS
                reorder_qty = max(0, target_stock - stock)
                return int(np.ceil(reorder_qty))
        return 0

    df['recommended_reorder'] = df.apply(calc_reorder, axis=1)
    df['stock_value'] = np.where(df['current_stock'].notna(), (df['current_stock'] * df['cost_price']).round(2), 0.0)

    # Attach demand period metadata for context traceability
    df['demand_start_date'] = start_date_str
    df['demand_end_date'] = end_date_str
    df['demand_window_days'] = window_days

    # Debug Logging as required by specifications
    try:
        from src.dataset_manager import get_active_dataset_metadata, get_active_dataset_id
        meta = get_active_dataset_metadata()
        ds_id = get_active_dataset_id()
        ds_name = meta.get("dataset_name", "Unknown") if meta else "Unknown"
        print(f"[INVENTORY] dataset_id: {ds_id} | dataset_name: {ds_name} | latest_date: {end_date_str} | inventory_rows_before_filter: {len(df)} | inventory_rows_after_store_filter: {len(df)} | products_joined: {df['product_id'].nunique()} | stores_joined: {df['store_id'].nunique()}")
    except Exception:
        pass

    return df

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
    filtered = df[df['status'] == 'SLOW_MOVING'].sort_values(by='recent_units_sold')
    return filtered.to_dict(orient='records')

def get_overstocked_items() -> List[Dict[str, Any]]:
    """Returns items classified as OVERSTOCK sorted descending by days remaining."""
    df = get_inventory_status_df()
    if df.empty:
        return []
    filtered = df[df['status'] == 'OVERSTOCK'].sort_values(by='days_remaining', ascending=False)
    return filtered.to_dict(orient='records')

def get_interstore_transfer_opportunities(inv_df: pd.DataFrame = None) -> List[Dict[str, Any]]:
    """
    Identifies products overstocked at one store and critical/warning/out of stock at another store.
    Returns structured inter-store transfer recommendations.
    """
    if inv_df is None or inv_df.empty:
        inv_df = get_inventory_status_df()
    if inv_df is None or inv_df.empty:
        return []

    overstocked = inv_df[inv_df['status'] == 'OVERSTOCK']
    needing_stock = inv_df[inv_df['status'].isin(['CRITICAL', 'WARNING', 'OUT_OF_STOCK'])]

    if overstocked.empty or needing_stock.empty:
        return []

    opportunities = []
    for _, low_row in needing_stock.iterrows():
        pid = low_row['product_id']
        p_name = low_row['product_name']
        low_store = low_row['store_name']
        low_stock = int(low_row['current_stock']) if not pd.isna(low_row['current_stock']) else 0
        low_days = float(low_row['days_remaining']) if not pd.isna(low_row['days_remaining']) else 0.0

        # Find matching overstocked store
        matches = overstocked[overstocked['product_id'] == pid]
        for _, over_row in matches.iterrows():
            over_store = over_row['store_name']
            if over_store == low_store:
                continue
            over_stock = int(over_row['current_stock'])
            over_days = float(over_row['days_remaining'])

            opportunities.append({
                "product_id": pid,
                "product_name": p_name,
                "from_store": over_store,
                "from_stock": over_stock,
                "from_days": round(over_days, 1),
                "to_store": low_store,
                "to_stock": low_stock,
                "to_days": round(low_days, 1),
                "recommendation": f"Potential transfer opportunity: '{p_name}' is OVERSTOCKED at {over_store} ({over_stock} units, {over_days:.0f}d coverage) and RUNNING LOW at {low_store} ({low_stock} units, {low_days:.1f}d coverage). Consider transferring stock from {over_store} to {low_store}."
            })
    return opportunities
