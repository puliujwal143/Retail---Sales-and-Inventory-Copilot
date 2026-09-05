import calendar
import datetime
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from src.database import query_df, query_all, query_one

SPIKE_THRESHOLD_PCT = 30.0  # >= +30% change is a sales spike
DROP_THRESHOLD_PCT = -30.0   # <= -30% change is a sales drop

def resolve_store_id(store_input: Optional[str]) -> Optional[str]:
    """Resolves store name or store ID to canonical store_id string."""
    if not store_input or str(store_input).lower() == "all":
        return None
    if str(store_input).startswith("STR"):
        return str(store_input)
    row = query_one("SELECT store_id FROM stores WHERE store_name LIKE ? OR store_id = ?", (f"%{store_input}%", store_input))
    if row:
        return row["store_id"]
    return store_input

def get_product_sales_trends(time_days: int = 30, store_id: Optional[str] = None) -> pd.DataFrame:
    """
    Compares sales in recent N-day period vs previous N-day period per product.
    Calculates exact percentage change and flags sales spikes / drops.
    """
    from src.dataset_manager import ActiveDatasetManager
    if ActiveDatasetManager.get_active_dataset_id() is None:
        return pd.DataFrame()

    resolved_store = resolve_store_id(store_id)
    where_clause = ""
    params = [time_days, time_days, 2 * time_days]
    if resolved_store:
        where_clause = "AND s.store_id = ?"
        params = [time_days, resolved_store, time_days, 2 * time_days, resolved_store]

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
    from src.dataset_manager import ActiveDatasetManager
    if ActiveDatasetManager.get_active_dataset_id() is None:
        return []

    resolved_store = resolve_store_id(store_id)
    where_clause = ""
    params = ()
    if resolved_store:
        where_clause = "WHERE st.store_id = ?"
        params = (resolved_store,)

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

def get_category_performance(store_id: Optional[str] = None, target_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns sales performance broken down by product category."""
    from src.dataset_manager import ActiveDatasetManager
    if ActiveDatasetManager.get_active_dataset_id() is None:
        return []

    resolved_store = resolve_store_id(store_id)
    where_parts = []
    params = []
    if resolved_store:
        where_parts.append("s.store_id = ?")
        params.append(resolved_store)
    if target_date:
        where_parts.append("s.date <= ?")
        params.append(target_date)

    where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""

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
    return query_all(query, tuple(params))

def get_daily_sales_trend(days: int = 30, store_id: Optional[str] = None, target_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns aggregate daily/monthly revenue, volume, and period metadata relative to target_date."""
    from src.dataset_manager import ActiveDatasetManager
    if ActiveDatasetManager.get_active_dataset_id() is None:
        return []

    resolved_store = resolve_store_id(store_id)
    where_parts = []
    params = []
    
    # Normalize target_date if > max_date
    bounds = query_one("SELECT MAX(date) as max_date FROM sales")
    max_db_date = bounds["max_date"] if bounds and bounds.get("max_date") else None
    if not max_db_date:
        return []
    
    effective_target = target_date
    if effective_target and effective_target > max_db_date:
        effective_target = max_db_date

    if resolved_store:
        where_parts.append("s.store_id = ?")
        params.append(resolved_store)
        
    if effective_target:
        where_parts.append("s.date <= ? AND s.date >= date(?, '-' || ? || ' days')")
        params.extend([effective_target, effective_target, days])
    else:
        where_parts.append("s.date >= date((SELECT MAX(date) FROM sales), '-' || ? || ' days')")
        params.append(days)

    where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""

    month_abbr = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    month_full = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

    # Aggregation mode: daily for <= 90 days, monthly for > 90 days
    if days > 90:
        query = f"""
        SELECT 
            strftime('%Y-%m', s.date) as ym,
            MIN(s.date) as start_date,
            MAX(s.date) as end_date,
            COUNT(DISTINCT s.date) as num_days,
            SUM(s.quantity) as total_units,
            ROUND(SUM(s.total_revenue), 2) as total_revenue,
            ROUND(SUM(s.total_revenue) / COUNT(DISTINCT s.date), 2) as avg_daily_revenue,
            ROUND(CAST(SUM(s.quantity) AS FLOAT) / COUNT(DISTINCT s.date), 2) as avg_daily_units
        FROM sales s
        {where_clause}
        GROUP BY ym
        ORDER BY ym ASC
        """
        rows = query_all(query, tuple(params))
        result = []
        for r in rows:
            ym = r["ym"]
            start_d = r["start_date"]
            end_d = r["end_date"]
            num_days = r["num_days"]
            total_units = r["total_units"]
            total_rev = r["total_revenue"]
            avg_daily_rev = r["avg_daily_revenue"]
            avg_daily_units = r["avg_daily_units"]

            y, m = int(ym.split('-')[0]), int(ym.split('-')[1])
            cal_days = calendar.monthrange(y, m)[1]
            start_day = int(start_d.split('-')[2])
            end_day = int(end_d.split('-')[2])

            is_partial = (num_days < cal_days or start_day > 1 or end_day < cal_days)

            if is_partial:
                display_label = f"{month_abbr[m]} {start_day}–{end_day}"
                period_title = f"{month_full[m]} {start_day}–{end_day}, {y} (Partial — {num_days} Days)"
            else:
                display_label = f"{month_abbr[m]} {y}" if len(rows) > 12 else month_abbr[m]
                period_title = f"{month_full[m]} {y} (Full Month — {num_days} Days)"

            result.append({
                "date": ym,
                "label": display_label,
                "period_title": period_title,
                "start_date": start_d,
                "end_date": end_d,
                "days_covered": num_days,
                "is_partial": is_partial,
                "total_units": total_units,
                "total_revenue": total_rev,
                "avg_daily_revenue": avg_daily_rev,
                "avg_daily_units": avg_daily_units
            })
        return result
    else:
        query = f"""
        SELECT 
            s.date as date,
            s.date as start_date,
            s.date as end_date,
            1 as num_days,
            SUM(s.quantity) as total_units,
            ROUND(SUM(s.total_revenue), 2) as total_revenue,
            ROUND(SUM(s.total_revenue), 2) as avg_daily_revenue,
            SUM(s.quantity) as avg_daily_units
        FROM sales s
        {where_clause}
        GROUP BY s.date
        ORDER BY s.date ASC
        """
        rows = query_all(query, tuple(params))
        result = []
        for r in rows:
            d_str = r["date"]
            dt = datetime.datetime.strptime(d_str, "%Y-%m-%d")
            display_label = f"{month_abbr[dt.month]} {dt.day}"
            period_title = f"{month_abbr[dt.month]} {dt.day}, {dt.year}"
            result.append({
                "date": d_str,
                "label": display_label,
                "period_title": period_title,
                "start_date": d_str,
                "end_date": d_str,
                "days_covered": 1,
                "is_partial": False,
                "total_units": r["total_units"],
                "total_revenue": r["total_revenue"],
                "avg_daily_revenue": r["avg_daily_revenue"],
                "avg_daily_units": r["avg_daily_units"]
            })
        return result

def get_sales_analytics_charts(days: int = 30, store_id: Optional[str] = "all", category: Optional[str] = "all", target_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Generates structured chart specs and deterministic insights for the Sales Analytics Workspace.
    Safely handles empty datasets (NO_DATA state) without throwing 500 errors.
    """
    from src.dataset_manager import ActiveDatasetManager
    timeframe_str = "6 Months" if days == 180 else f"{days} Days"
    granularity_str = "Monthly" if days > 90 else "Daily"

    if ActiveDatasetManager.get_active_dataset_id() is None:
        return {
            "time_days": days,
            "combined_trend": {
                "type": "dual_axis",
                "title": f"Revenue & Sales Volume ({timeframe_str})",
                "subtitle": "No retail data available",
                "labels": [],
                "periods": [],
                "is_monthly": False,
                "is_partial": [],
                "avg_daily_revenue": [],
                "avg_daily_units": [],
                "datasets": [
                    {"label": "Revenue (₹)", "data": [], "color": "#087F80", "type": "line", "y_axis": "left", "unit": "₹"},
                    {"label": "Units Sold", "data": [], "color": "#3B82F6", "type": "bar", "y_axis": "right", "unit": "units"}
                ]
            },
            "revenue_trend": {
                "type": "line",
                "title": f"Revenue Movement ({timeframe_str})",
                "subtitle": "No retail data available",
                "labels": [],
                "periods": [],
                "is_monthly": False,
                "is_partial": [],
                "avg_daily_revenue": [],
                "avg_daily_units": [],
                "datasets": [{"label": "Revenue (₹)", "data": [], "color": "#087F80"}]
            },
            "units_trend": {
                "type": "area",
                "title": f"Units Sold Over Time ({timeframe_str})",
                "subtitle": "No retail data available",
                "labels": [],
                "periods": [],
                "is_monthly": False,
                "is_partial": [],
                "avg_daily_revenue": [],
                "avg_daily_units": [],
                "datasets": [{"label": "Units Sold", "data": [], "color": "#10b981"}]
            },
            "category_chart": {
                "type": "bar",
                "title": "Revenue by Product Category",
                "subtitle": "No category data available",
                "labels": [],
                "datasets": [{"label": "Category Revenue (₹)", "data": [], "color": "#8b5cf6"}]
            },
            "top_products_chart": {
                "type": "horizontal_bar",
                "title": "Top 5 Products by Revenue",
                "subtitle": "No product data available",
                "labels": [],
                "datasets": [{"label": "Revenue (₹)", "data": [], "color": "#06b6d4"}]
            },
            "store_chart": {
                "type": "bar",
                "title": "Store Performance Comparison",
                "subtitle": "No store data available",
                "labels": [],
                "datasets": [{"label": "Store Revenue (₹)", "data": [], "color": "#f59e0b"}]
            },
            "spikes": [],
            "drops": [],
            "insights": ["No sales data available. Upload a dataset to view sales trends and analytics."]
        }

    resolved_store = resolve_store_id(store_id)
    
    # Normalize target_date
    bounds = query_one("SELECT MAX(date) as max_date FROM sales")
    max_db_date = bounds["max_date"] if bounds and bounds.get("max_date") else None
    effective_target = target_date
    if effective_target and max_db_date and effective_target > max_db_date:
        effective_target = max_db_date

    # 1. Trend (Revenue & Units)
    daily = get_daily_sales_trend(days=days, store_id=resolved_store, target_date=effective_target)
    labels = [d["label"] for d in daily]
    revenues = [d["total_revenue"] for d in daily]
    units = [d["total_units"] for d in daily]

    is_partial_flags = [d.get("is_partial", False) for d in daily]
    avg_daily_revs = [d.get("avg_daily_revenue", d.get("total_revenue", 0)) for d in daily]
    avg_daily_units_list = [d.get("avg_daily_units", d.get("total_units", 0)) for d in daily]

    combined_trend_chart = {
        "type": "dual_axis",
        "title": f"Revenue & Sales Volume ({timeframe_str})",
        "subtitle": f"{granularity_str} revenue and units sold over time" if daily else "No sales recorded in this period",
        "labels": labels,
        "periods": daily,
        "is_monthly": (days > 90),
        "is_partial": is_partial_flags,
        "avg_daily_revenue": avg_daily_revs,
        "avg_daily_units": avg_daily_units_list,
        "datasets": [
            {
                "label": "Revenue (₹)",
                "data": revenues,
                "color": "#087F80",
                "type": "line",
                "y_axis": "left",
                "unit": "₹"
            },
            {
                "label": "Units Sold",
                "data": units,
                "color": "#3B82F6",
                "type": "bar",
                "y_axis": "right",
                "unit": "units"
            }
        ]
    }

    revenue_trend_chart = {
        "type": "line",
        "title": f"Revenue Movement ({timeframe_str})",
        "subtitle": f"{granularity_str} revenue trajectory" if daily else "No sales recorded in this period",
        "labels": labels,
        "periods": daily,
        "is_monthly": (days > 90),
        "is_partial": is_partial_flags,
        "avg_daily_revenue": avg_daily_revs,
        "avg_daily_units": avg_daily_units_list,
        "datasets": [{"label": "Revenue (₹)", "data": revenues, "color": "#087F80"}]
    }

    units_trend_chart = {
        "type": "area",
        "title": f"Units Sold Over Time ({timeframe_str})",
        "subtitle": f"{granularity_str} unit demand volume" if daily else "No sales recorded in this period",
        "labels": labels,
        "periods": daily,
        "is_monthly": (days > 90),
        "is_partial": is_partial_flags,
        "avg_daily_revenue": avg_daily_revs,
        "avg_daily_units": avg_daily_units_list,
        "datasets": [{"label": "Units Sold", "data": units, "color": "#10b981"}]
    }

    # 2. Category Performance Chart
    categories = get_category_performance(store_id=resolved_store, target_date=effective_target)
    cat_names = [c["category"] for c in categories]
    cat_revs = [c["total_revenue"] for c in categories]

    category_chart = {
        "type": "bar",
        "title": "Revenue by Product Category",
        "subtitle": "Total revenue per category" if categories else "No categories available",
        "labels": cat_names,
        "datasets": [{"label": "Category Revenue (₹)", "data": cat_revs, "color": "#8b5cf6"}]
    }

    # 3. Top Products Horizontal Bar Chart
    where_parts = []
    params = []
    if resolved_store:
        where_parts.append("s.store_id = ?")
        params.append(resolved_store)
    if effective_target:
        where_parts.append("s.date <= ? AND s.date >= date(?, '-' || ? || ' days')")
        params.extend([effective_target, effective_target, days])
    elif max_db_date:
        where_parts.append("s.date >= date((SELECT MAX(date) FROM sales), '-' || ? || ' days')")
        params.append(days)

    where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""

    top_p_data = []
    if max_db_date or effective_target:
        top_p_query = f"""
        SELECT p.product_name, COALESCE(SUM(s.quantity), 0) as units, ROUND(COALESCE(SUM(s.total_revenue), 0), 2) as revenue
        FROM sales s JOIN products p ON s.product_id = p.product_id
        {where_clause}
        GROUP BY p.product_id, p.product_name
        ORDER BY revenue DESC LIMIT 5
        """
        top_p_data = query_all(top_p_query, tuple(params))
        
    top_p_names = [p["product_name"] for p in top_p_data]
    top_p_revs = [p["revenue"] for p in top_p_data]

    top_products_chart = {
        "type": "horizontal_bar",
        "title": "Top 5 Products by Revenue",
        "subtitle": f"Highest revenue items in last {days} days" if top_p_data else "No product sales in this period",
        "labels": top_p_names,
        "datasets": [{"label": "Revenue (₹)", "data": top_p_revs, "color": "#06b6d4"}]
    }

    # 4. Store Performance Chart
    stores = get_store_performance(store_id=resolved_store)
    st_names = [s["store_name"] for s in stores]
    st_revs = [s["total_revenue"] for s in stores]

    store_chart = {
        "type": "bar",
        "title": "Store Performance Comparison",
        "subtitle": "Revenue breakdown across retail store locations" if stores else "No store performance data available",
        "labels": st_names,
        "datasets": [{"label": "Store Revenue (₹)", "data": st_revs, "color": "#f59e0b"}]
    }

    # 5. Deterministic AI Insights
    spikes = get_sales_spikes(time_days=days)
    drops = get_sales_drops(time_days=days)

    total_revenue_val = sum(revenues)
    total_units_val = sum(units)
    top_cat = categories[0]["category"] if categories else "N/A"
    top_st = stores[0]["store_name"] if stores else "N/A"

    insights = []
    if daily:
        insights.append(f"Total revenue reached ₹{total_revenue_val:,.2f} with {total_units_val:,} units sold over the last {days} days.")
    else:
        insights.append(f"No sales transactions recorded over the last {days} days.")

    if categories:
        insights.append(f"Category '{top_cat}' is the primary revenue driver at ₹{categories[0]['total_revenue']:,.2f}.")
    if stores:
        insights.append(f"Top performing store location is '{top_st}' generating ₹{stores[0]['total_revenue']:,.2f} total revenue.")

    if spikes:
        s0 = spikes[0]
        insights.append(f"Product '{s0['product_name']}' experienced a +{s0['pct_change_units']}% sales surge ({s0['prev_units_30d']} -> {s0['curr_units_30d']} units).")
    if drops:
        d0 = drops[0]
        insights.append(f"Product '{d0['product_name']}' experienced a {d0['pct_change_units']}% sales drop ({d0['prev_units_30d']} -> {d0['curr_units_30d']} units).")

    return {
        "time_days": days,
        "combined_trend": combined_trend_chart,
        "revenue_trend": revenue_trend_chart,
        "units_trend": units_trend_chart,
        "category_chart": category_chart,
        "top_products_chart": top_products_chart,
        "store_chart": store_chart,
        "spikes": spikes,
        "drops": drops,
        "insights": insights
    }

def compare_stores_analytics(store_ids: Optional[List[str]] = None, time_days: int = 30, target_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Compares selected stores side-by-side across revenue, units, growth, stock risks, and trend specs.
    Dynamically loads and compares all stores in the active dataset by default.
    """
    from src.dataset_manager import ActiveDatasetManager
    if ActiveDatasetManager.get_active_dataset_id() is None:
        return {
            "stores_count": 0,
            "comparison_table": [],
            "comparison_chart": {
                "type": "line",
                "title": "Store Revenue Trajectory",
                "labels": [],
                "datasets": []
            },
            "insights": []
        }

    all_db_stores = query_all("SELECT store_id, store_name, location FROM stores ORDER BY store_id")
    available_ids = [s["store_id"] for s in all_db_stores]
    
    if not available_ids:
        return {
            "stores_count": 0,
            "comparison_table": [],
            "comparison_chart": {
                "type": "line",
                "title": "Store Revenue Trajectory",
                "labels": [],
                "datasets": []
            },
            "insights": []
        }

    if not store_ids or len(store_ids) == 0 or "all" in [str(s).lower() for s in store_ids if s]:
        selected_ids = available_ids
    else:
        valid_ids = [s for s in store_ids if s in available_ids]
        selected_ids = valid_ids if valid_ids else available_ids

    date_filter = ""
    params = [time_days]
    if target_date:
        date_filter = "AND s.date <= ?"
        params.append(target_date)

    placeholders = ",".join(["?"] * len(selected_ids))

    # 1. Total Revenue & Units per Store
    sql_stores = f"""
        WITH max_date_cte AS (
            SELECT COALESCE(?, MAX(date)) as ref_date FROM sales
        )
        SELECT 
            st.store_id,
            st.store_name,
            st.location,
            COALESCE(SUM(s.quantity), 0) as units_sold,
            ROUND(COALESCE(SUM(s.total_revenue), 0), 2) as total_revenue
        FROM stores st
        LEFT JOIN sales s ON st.store_id = s.store_id 
            AND s.date >= date((SELECT ref_date FROM max_date_cte), '-' || ? || ' days')
            {date_filter}
        WHERE st.store_id IN ({placeholders})
        GROUP BY st.store_id, st.store_name, st.location
        ORDER BY total_revenue DESC
    """

    sql_params = [target_date, time_days]
    if target_date:
        sql_params.append(target_date)
    sql_params.extend(selected_ids)

    df_comp = query_df(sql_stores, tuple(sql_params))
    
    # 2. Inventory Health per Store
    from src.inventory_rules import get_inventory_status_df
    inv_df = get_inventory_status_df(target_date=target_date)

    comparison_results = []
    datasets_trend = []

    # Dynamic color palette for comparative charts
    colors = ["#087F80", "#2563EB", "#D97706", "#8B5CF6", "#EC4899", "#10B981", "#6366F1", "#F97316"]
    dates_list = []

    for idx, s_id in enumerate(selected_ids):
        s_row = df_comp[df_comp["store_id"] == s_id] if not df_comp.empty else pd.DataFrame()
        if s_row.empty:
            continue
        s_data = s_row.iloc[0].to_dict()

        # Filter inventory for store
        s_inv = inv_df[inv_df["store_id"] == s_id] if not inv_df.empty else pd.DataFrame()
        crit_count = len(s_inv[s_inv["status"].isin(["CRITICAL", "OUT_OF_STOCK"])]) if not s_inv.empty else 0
        warn_count = len(s_inv[s_inv["status"] == "WARNING"]) if not s_inv.empty else 0
        overstock_count = len(s_inv[s_inv["status"] == "OVERSTOCK"]) if not s_inv.empty else 0
        healthy_count = len(s_inv[s_inv["status"] == "HEALTHY"]) if not s_inv.empty else 0

        # Daily trend
        daily_sql = f"""
            SELECT date, ROUND(SUM(total_revenue), 2) as daily_rev
            FROM sales
            WHERE store_id = ? AND date >= date((SELECT COALESCE(?, MAX(date)) FROM sales), '-' || ? || ' days')
            GROUP BY date ORDER BY date ASC
        """
        daily_params = [s_id, target_date, time_days]
        df_daily = query_df(daily_sql, tuple(daily_params))
        
        cur_dates = df_daily["date"].tolist() if not df_daily.empty else []
        cur_revs = df_daily["daily_rev"].tolist() if not df_daily.empty else []

        if len(cur_dates) > len(dates_list):
            dates_list = cur_dates

        s_data["critical_items"] = crit_count
        s_data["warning_items"] = warn_count
        s_data["overstock_items"] = overstock_count
        s_data["healthy_items"] = healthy_count
        s_data["avg_daily_revenue"] = round(s_data["total_revenue"] / max(1, time_days), 2)

        comparison_results.append(s_data)

        if cur_dates:
            datasets_trend.append({
                "label": s_data["store_name"],
                "data": cur_revs,
                "color": colors[idx % len(colors)]
            })

    # Sort comparison results by revenue
    comparison_results.sort(key=lambda x: x["total_revenue"], reverse=True)

    return {
        "timeframe_days": time_days,
        "target_date": target_date,
        "stores_count": len(comparison_results),
        "comparison_table": comparison_results,
        "top_store": comparison_results[0]["store_name"] if comparison_results else "N/A",
        "highest_risk_store": max(comparison_results, key=lambda x: x["critical_items"])["store_name"] if comparison_results else "N/A",
        "comparison_chart": {
            "type": "line",
            "title": f"Store Revenue Comparison ({time_days} Days)",
            "subtitle": f"Comparing {len(comparison_results)} stores side-by-side",
            "labels": dates_list,
            "datasets": datasets_trend
        }
    }

def get_yearly_performance(store_id: Optional[str] = "all") -> Dict[str, Any]:
    """
    Computes yearly sales performance breakdown, YoY growth %, and highlights dynamically based on active dataset.
    """
    from src.dataset_manager import ActiveDatasetManager
    if ActiveDatasetManager.get_active_dataset_id() is None:
        return {
            "yearly_table": [],
            "best_year": "N/A",
            "fastest_growth_year": "N/A",
            "lowest_year": "N/A",
            "yearly_chart": {
                "type": "bar",
                "title": "Annual Revenue by Year",
                "labels": [],
                "datasets": [{"label": "Annual Revenue (₹)", "data": [], "color": "#087F80"}]
            },
            "growth_chart": {
                "type": "line",
                "title": "YoY Revenue Growth Rate (%)",
                "labels": [],
                "datasets": [{"label": "YoY Growth (%)", "data": [], "color": "#2563EB"}]
            }
        }

    resolved_store = resolve_store_id(store_id)
    where_parts = []
    params = []
    if resolved_store:
        where_parts.append("store_id = ?")
        params.append(resolved_store)

    where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""

    sql = f"""
        SELECT 
            strftime('%Y', date) as year,
            COALESCE(SUM(quantity), 0) as total_units,
            ROUND(COALESCE(SUM(total_revenue), 0), 2) as total_revenue,
            COUNT(DISTINCT sale_id) as transaction_count
        FROM sales
        {where_clause}
        GROUP BY strftime('%Y', date)
        ORDER BY year ASC
    """
    rows = query_all(sql, tuple(params))
    if not rows:
        return {
            "yearly_table": [],
            "best_year": "N/A",
            "fastest_growth_year": "N/A",
            "lowest_year": "N/A",
            "yearly_chart": {
                "type": "bar",
                "title": "Annual Revenue by Year",
                "labels": [],
                "datasets": [{"label": "Annual Revenue (₹)", "data": [], "color": "#087F80"}]
            },
            "growth_chart": {
                "type": "line",
                "title": "YoY Revenue Growth Rate (%)",
                "labels": [],
                "datasets": [{"label": "YoY Growth (%)", "data": [], "color": "#2563EB"}]
            }
        }

    yearly_data = []
    prev_rev = None
    prev_units = None

    for r in rows:
        rev = r["total_revenue"]
        units = r["total_units"]
        
        yoy_rev_pct = round(((rev - prev_rev) / prev_rev) * 100, 1) if prev_rev and prev_rev > 0 else 0.0
        yoy_units_pct = round(((units - prev_units) / prev_units) * 100, 1) if prev_units and prev_units > 0 else 0.0

        r["yoy_revenue_growth"] = yoy_rev_pct
        r["yoy_units_growth"] = yoy_units_pct
        yearly_data.append(r)

        prev_rev = rev
        prev_units = units

    best_year = max(yearly_data, key=lambda x: x["total_revenue"])["year"] if yearly_data else "N/A"
    lowest_year = min(yearly_data, key=lambda x: x["total_revenue"])["year"] if yearly_data else "N/A"
    fastest_growth = max(yearly_data[1:], key=lambda x: x["yoy_revenue_growth"])["year"] if len(yearly_data) > 1 else best_year

    years = [y["year"] for y in yearly_data if y.get("year")]
    revs = [y["total_revenue"] for y in yearly_data if y.get("year")]
    growth_rates = [y["yoy_revenue_growth"] for y in yearly_data if y.get("year")]

    if len(years) > 1:
        chart_title = f"Annual Revenue by Year ({years[0]} - {years[-1]})"
    elif len(years) == 1:
        chart_title = f"Annual Revenue ({years[0]})"
    else:
        chart_title = "Annual Revenue by Year"

    return {
        "yearly_table": yearly_data,
        "best_year": best_year,
        "fastest_growth_year": fastest_growth,
        "lowest_year": lowest_year,
        "yearly_chart": {
            "type": "bar",
            "title": chart_title,
            "labels": years,
            "datasets": [{"label": "Annual Revenue (₹)", "data": revs, "color": "#087F80"}]
        },
        "growth_chart": {
            "type": "line",
            "title": "YoY Revenue Growth Rate (%)",
            "labels": years,
            "datasets": [{"label": "YoY Growth (%)", "data": growth_rates, "color": "#2563EB"}]
        }
    }

def get_seasonality_analysis(store_id: Optional[str] = "all") -> Dict[str, Any]:
    """
    Computes average monthly revenue and units across all recorded periods in active dataset.
    Validates date coverage and safely flags INSUFFICIENT_HISTORY when data span < 3 distinct months.
    """
    from src.dataset_manager import ActiveDatasetManager
    ds_id = ActiveDatasetManager.get_active_dataset_id()
    if ds_id is None:
        return {
            "status": "NO_DATA",
            "message": "No dataset active. Upload your retail data to calculate seasonality.",
            "seasonality_table": [],
            "peak_month": "N/A",
            "unique_months": 0,
            "seasonality_chart": {
                "type": "bar",
                "title": "Monthly Demand Seasonality Profile",
                "subtitle": "No monthly data available",
                "labels": [],
                "datasets": [{"label": "Avg Monthly Revenue (₹)", "data": [], "color": "#D97706"}]
            }
        }
    
    resolved_store = resolve_store_id(store_id)
    where_parts = []
    params = []
    if resolved_store:
        where_parts.append("store_id = ?")
        params.append(resolved_store)

    where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""

    # Check date bounds and historical coverage
    stats_query = f"""
        SELECT 
            MIN(date) as min_d,
            MAX(date) as max_d,
            COUNT(DISTINCT date) as unique_dates,
            COUNT(DISTINCT strftime('%Y-%m', date)) as unique_months
        FROM sales
        {where_clause}
    """
    stats_row = query_one(stats_query, tuple(params))
    min_date = str(stats_row["min_d"]) if stats_row and stats_row.get("min_d") else "N/A"
    max_date = str(stats_row["max_d"]) if stats_row and stats_row.get("max_d") else "N/A"
    unique_dates = int(stats_row["unique_dates"]) if stats_row and stats_row.get("unique_dates") is not None else 0
    unique_months = int(stats_row["unique_months"]) if stats_row and stats_row.get("unique_months") is not None else 0

    print(f"[SEASONALITY] dataset_id: {ds_id} | date_min: {min_date} | date_max: {max_date} | unique_dates: {unique_dates} | unique_months: {unique_months} | store_scope: {store_id or 'all'}")

    # Seasonality requires at least 3 distinct calendar months to show meaningful seasonal patterns
    if unique_months < 3:
        return {
            "status": "INSUFFICIENT_HISTORY",
            "message": "Not enough historical data in the active dataset to calculate a reliable seasonal pattern.",
            "unique_months": unique_months,
            "date_min": min_date,
            "date_max": max_date,
            "seasonality_table": [],
            "peak_month": "N/A",
            "seasonality_chart": {
                "type": "bar",
                "title": "Monthly Demand Seasonality Profile",
                "subtitle": "Insufficient historical data for seasonality",
                "labels": [],
                "datasets": [{"label": "Avg Monthly Revenue (₹)", "data": [], "color": "#D97706"}]
            }
        }

    sql = f"""
        SELECT 
            m as month_num,
            COUNT(DISTINCT y) as years_count,
            ROUND(AVG(monthly_rev), 2) as avg_revenue,
            ROUND(AVG(monthly_units), 2) as avg_units
        FROM (
            SELECT 
                strftime('%Y', date) as y,
                strftime('%m', date) as m,
                SUM(total_revenue) as monthly_rev,
                SUM(quantity) as monthly_units
            FROM sales
            {where_clause}
            GROUP BY y, m
        )
        GROUP BY m
        ORDER BY CAST(m AS INTEGER) ASC
    """
    rows = query_all(sql, tuple(params))
    if not rows:
        return {
            "status": "INSUFFICIENT_HISTORY",
            "message": "No sales records available to compute seasonality.",
            "unique_months": 0,
            "date_min": min_date,
            "date_max": max_date,
            "seasonality_table": [],
            "peak_month": "N/A",
            "seasonality_chart": {
                "type": "bar",
                "title": "Monthly Demand Seasonality Profile",
                "subtitle": "No monthly data available",
                "labels": [],
                "datasets": [{"label": "Avg Monthly Revenue (₹)", "data": [], "color": "#D97706"}]
            }
        }
    
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    labels = []
    avg_revs = []

    for r in rows:
        m_val = r.get("month_num")
        m_idx = int(m_val) - 1 if (m_val and str(m_val).isdigit()) else 0
        m_name = month_names[m_idx] if 0 <= m_idx < 12 else str(m_val or "Unknown")
        r["month_name"] = m_name
        labels.append(m_name)
        avg_revs.append(r.get("avg_revenue", 0.0))

    if len(labels) == 12:
        title = "Monthly Demand Seasonality Profile (Jan - Dec)"
        subtitle = "Average monthly revenue across recorded years"
    elif len(labels) > 1:
        title = f"Monthly Demand Distribution ({labels[0]} - {labels[-1]})"
        subtitle = f"Monthly revenue across {len(labels)} recorded months"
    elif len(labels) == 1:
        title = f"Monthly Demand Profile ({labels[0]})"
        subtitle = f"Monthly revenue for {labels[0]}"
    else:
        title = "Monthly Demand Seasonality Profile"
        subtitle = "No monthly data available"

    peak_month = max(rows, key=lambda x: x.get("avg_revenue", 0))["month_name"] if rows else "N/A"

    return {
        "status": "SUCCESS",
        "message": f"Seasonality computed across {len(labels)} months.",
        "unique_months": unique_months,
        "date_min": min_date,
        "date_max": max_date,
        "seasonality_table": rows,
        "peak_month": peak_month,
        "seasonality_chart": {
            "type": "bar",
            "title": title,
            "subtitle": subtitle,
            "labels": labels,
            "datasets": [{"label": "Avg Monthly Revenue (₹)", "data": avg_revs, "color": "#D97706"}]
        }
    }
