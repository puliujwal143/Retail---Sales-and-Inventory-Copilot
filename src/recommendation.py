from typing import List, Dict, Any
from src.inventory_rules import (
    get_inventory_status_df, 
    get_low_stock_items, 
    get_slow_moving_items, 
    get_overstocked_items,
    TARGET_COVERAGE_DAYS
)
from src.sales_rules import get_sales_spikes, get_sales_drops

from src.dataset_manager import ActiveDatasetManager

def get_attention_items() -> List[Dict[str, Any]]:
    """
    Attention Engine: Collects critical stock risks, slow-moving items, overstock,
    sales spikes, and sales drops, ranking them by severity.
    Returns empty list when no dataset is active.
    """
    if ActiveDatasetManager.get_active_dataset_id() is None:
        return []

    attention_list = []

    # 1. Critical & Out of Stock (HIGH Severity)
    inv_df = get_inventory_status_df()
    if not inv_df.empty:
        critical_df = inv_df[inv_df['status'].isin(['CRITICAL', 'OUT_OF_STOCK'])].sort_values(by='days_remaining')
        for _, row in critical_df.iterrows():
            days = row['days_remaining']
            p_name = row['product_name']
            s_name = row['store_name']
            stock = row['current_stock']
            reorder = row['recommended_reorder']
            ads = row['average_daily_sales']

            msg = f"{p_name} ({s_name}) has only {stock} units remaining (est. {days} days of demand)."
            action = f"Reorder {reorder} units immediately to reach {TARGET_COVERAGE_DAYS}-day target coverage."
            reason = f"Current inventory covers approximately {days} days of demand, below the {TARGET_COVERAGE_DAYS}-day target safety threshold."

            attention_list.append({
                "id": f"ATT_CRIT_{row['store_id']}_{row['product_id']}",
                "severity": "HIGH",
                "type": "STOCK_OUT_RISK",
                "product_name": p_name,
                "store_name": s_name,
                "summary": msg,
                "current_stock": stock,
                "avg_daily_sales": ads,
                "days_remaining": days,
                "recommended_action": action,
                "reason": reason,
                "assumption": f"{TARGET_COVERAGE_DAYS}-day target inventory coverage."
            })

        # 2. Warning Stock (HIGH / MEDIUM Severity)
        warning_df = inv_df[inv_df['status'] == 'WARNING'].sort_values(by='days_remaining')
        for _, row in warning_df.iterrows():
            days = row['days_remaining']
            p_name = row['product_name']
            s_name = row['store_name']
            stock = row['current_stock']
            reorder = row['recommended_reorder']
            ads = row['average_daily_sales']

            msg = f"{p_name} ({s_name}) stock is low ({stock} units remaining, est. {days} days)."
            action = f"Schedule reorder of {reorder} units within 48 hours."
            reason = f"Stock level has reached warning threshold ({days} days remaining vs {TARGET_COVERAGE_DAYS}-day coverage target)."

            attention_list.append({
                "id": f"ATT_WARN_{row['store_id']}_{row['product_id']}",
                "severity": "HIGH",
                "type": "LOW_STOCK_WARNING",
                "product_name": p_name,
                "store_name": s_name,
                "summary": msg,
                "current_stock": stock,
                "avg_daily_sales": ads,
                "days_remaining": days,
                "recommended_action": action,
                "reason": reason,
                "assumption": f"{TARGET_COVERAGE_DAYS}-day target inventory coverage."
            })

    # 3. Sales Spikes (OPPORTUNITY Severity)
    spikes = get_sales_spikes()
    for spike in spikes[:3]:
        p_name = spike['product_name']
        pct = spike['pct_change_units']
        curr_u = spike['curr_units_30d']
        prev_u = spike['prev_units_30d']

        msg = f"{p_name} sales surged by +{pct}% (from {prev_u} to {curr_u} units in 30 days)."
        action = "Ensure sufficient safety stock and review store display placement to sustain momentum."
        reason = f"Significant demand surge (+{pct}%) detected over previous 30-day period."

        attention_list.append({
            "id": f"ATT_SPIKE_{spike['product_id']}",
            "severity": "OPPORTUNITY",
            "type": "SALES_SPIKE",
            "product_name": p_name,
            "store_name": "All Stores",
            "summary": msg,
            "current_stock": "N/A",
            "avg_daily_sales": round(curr_u / 30.0, 2),
            "days_remaining": "N/A",
            "recommended_action": action,
            "reason": reason,
            "assumption": "Comparing last 30 days volume against previous 30-day baseline."
        })

    # 4. Sales Drops (MEDIUM Severity)
    drops = get_sales_drops()
    for drop in drops[:3]:
        p_name = drop['product_name']
        pct = drop['pct_change_units']
        curr_u = drop['curr_units_30d']
        prev_u = drop['prev_units_30d']

        msg = f"{p_name} sales dropped by {pct}% (from {prev_u} to {curr_u} units in 30 days)."
        action = "Consider promotional pricing or Bundling with fast-moving accessories."
        reason = f"Sales velocity declined sharply ({pct}%) over recent 30-day window."

        attention_list.append({
            "id": f"ATT_DROP_{drop['product_id']}",
            "severity": "MEDIUM",
            "type": "SALES_DROP",
            "product_name": p_name,
            "store_name": "All Stores",
            "summary": msg,
            "current_stock": "N/A",
            "avg_daily_sales": round(curr_u / 30.0, 2),
            "days_remaining": "N/A",
            "recommended_action": action,
            "reason": reason,
            "assumption": "Comparing last 30 days volume against previous 30-day baseline."
        })

    # 5. Slow Moving Inventory (MEDIUM Severity)
    slow = get_slow_moving_items()
    for s_item in slow[:3]:
        p_name = s_item['product_name']
        s_name = s_item['store_name']
        stock = s_item['current_stock']
        sold = s_item['units_sold_30d']

        msg = f"{p_name} ({s_name}) has {stock} units in stock but sold only {sold} units in the last 30 days."
        action = "Initiate clearance discount or transfer stock to high-traffic store location."
        reason = f"Inventory holding costs accumulate when 30-day sales volume is under 5 units with stock >= 20."

        attention_list.append({
            "id": f"ATT_SLOW_{s_item['store_id']}_{s_item['product_id']}",
            "severity": "MEDIUM",
            "type": "SLOW_MOVING",
            "product_name": p_name,
            "store_name": s_name,
            "summary": msg,
            "current_stock": stock,
            "avg_daily_sales": round(sold / 30.0, 2),
            "days_remaining": s_item['days_remaining'],
            "recommended_action": action,
            "reason": reason,
            "assumption": "Threshold: < 5 units sold in 30 days with >= 20 units stock."
        })

    return attention_list
