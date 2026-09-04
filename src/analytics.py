import pandas as pd
from typing import Dict, Any, List
from src.database import query_one, query_all, query_df
from src.inventory_rules import get_inventory_status_df, get_low_stock_items
from src.sales_rules import get_store_performance, get_category_performance, get_daily_sales_trend

def get_dashboard_summary() -> Dict[str, Any]:
    """
    Computes top-level KPIs for store managers:
    - Total Revenue
    - Total Units Sold
    - Total Inventory Valuation
    - Low Stock Count
    - Store count
    - Top Store
    - Store Performance list
    - Sales Trend
    """
    # 1. Total Sales Metrics
    sales_kpi = query_one("""
        SELECT 
            COALESCE(SUM(total_revenue), 0) as total_revenue,
            COALESCE(SUM(quantity), 0) as total_units_sold,
            COUNT(DISTINCT sale_id) as total_transactions
        FROM sales
    """)

    # 2. Inventory Valuation & Low Stock Count
    inv_df = get_inventory_status_df()
    total_inventory_units = int(inv_df['current_stock'].sum()) if not inv_df.empty else 0
    total_inventory_valuation = float(inv_df['stock_value'].sum()) if not inv_df.empty else 0.0
    
    critical_count = len(inv_df[inv_df['status'] == 'CRITICAL']) if not inv_df.empty else 0
    warning_count = len(inv_df[inv_df['status'] == 'WARNING']) if not inv_df.empty else 0
    slow_count = len(inv_df[inv_df['status'] == 'SLOW_MOVING']) if not inv_df.empty else 0
    overstock_count = len(inv_df[inv_df['status'] == 'OVERSTOCK']) if not inv_df.empty else 0

    # 3. Store Performance & Top Store
    stores_perf = get_store_performance()
    top_store = stores_perf[0]['store_name'] if stores_perf else "N/A"

    # 4. Top Products by Revenue
    top_products = query_all("""
        SELECT 
            p.product_id,
            p.product_name,
            p.category,
            SUM(s.quantity) as units_sold,
            ROUND(SUM(s.total_revenue), 2) as revenue
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        GROUP BY p.product_id, p.product_name, p.category
        ORDER BY revenue DESC
        LIMIT 5
    """)

    # 5. Sales Trend (Last 30 Days)
    daily_trend = get_daily_sales_trend(30)

    return {
        "total_revenue": round(sales_kpi["total_revenue"], 2),
        "total_units_sold": sales_kpi["total_units_sold"],
        "total_transactions": sales_kpi["total_transactions"],
        "total_inventory_units": total_inventory_units,
        "total_inventory_valuation": round(total_inventory_valuation, 2),
        "critical_low_stock_count": critical_count,
        "warning_low_stock_count": warning_count,
        "slow_moving_count": slow_count,
        "overstock_count": overstock_count,
        "top_performing_store": top_store,
        "store_performance": stores_perf,
        "category_performance": get_category_performance(),
        "top_products": top_products,
        "daily_trend": daily_trend
    }
