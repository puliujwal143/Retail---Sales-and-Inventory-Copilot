import re
from typing import Dict, Any, List
from src.inventory_rules import get_inventory_status_df, get_low_stock_items, get_slow_moving_items, get_overstocked_items, TARGET_COVERAGE_DAYS
from src.sales_rules import get_product_sales_trends, get_sales_spikes, get_sales_drops, get_store_performance, get_category_performance
from src.recommendation import get_attention_items
from src.evidence import create_evidence_item

def process_query_intent(user_query: str) -> Dict[str, Any]:
    """
    Classifies natural language user intent deterministically, executes Python queries,
    and returns a compact structured payload containing exact figures, evidence, and assumptions.
    """
    q_lower = user_query.strip().lower()

    # 1. ATTENTION / TODAY'S ALERTS
    if any(k in q_lower for k in ["attention", "today", "alert", "urgent", "priority", "issue"]):
        items = get_attention_items()
        evidence_list = []
        rec_list = []
        metrics = []

        for item in items[:5]:
            evidence_list.append({
                "product_name": item["product_name"],
                "store_name": item["store_name"],
                "current_stock": item["current_stock"],
                "avg_daily_sales": item["avg_daily_sales"],
                "days_remaining": item["days_remaining"],
                "units_sold": item.get("units_sold", "N/A"),
                "sales_period": "Last 30 Days",
                "source": "inventory + sales records"
            })
            rec_list.append(f"{item['product_name']}: {item['recommended_action']}")
            metrics.append({"label": item['product_name'], "value": f"{item['current_stock']} units ({item['days_remaining']} days)"})

        return {
            "intent": "ATTENTION_TODAY",
            "user_query": user_query,
            "data_sufficiency": "sufficient",
            "context_summary": f"Identified {len(items)} items requiring operational attention.",
            "metrics": metrics,
            "recommendations": rec_list,
            "evidence": evidence_list,
            "assumptions": [f"Target inventory coverage = {TARGET_COVERAGE_DAYS} days", "Critical stock threshold <= 2 days", "Sales trend period = 30 days"],
            "raw_data": items
        }

    # 2. RUNNING OUT / REORDER
    elif any(k in q_lower for k in ["running out", "reorder", "restock", "low stock", "critical stock", "stockout", "stock-out"]):
        low_items = get_low_stock_items()
        evidence_list = []
        rec_list = []
        metrics = []

        for item in low_items:
            evidence_list.append({
                "product_name": item["product_name"],
                "store_name": item["store_name"],
                "current_stock": item["current_stock"],
                "avg_daily_sales": round(item["average_daily_sales"], 2),
                "days_remaining": item["days_remaining"],
                "units_sold": item["units_sold_30d"],
                "sales_period": "Last 30 Days",
                "source": "inventory + sales"
            })
            rec_list.append(f"Reorder {item['recommended_reorder']} units of {item['product_name']} at {item['store_name']}.")
            metrics.append({
                "label": f"{item['product_name']} ({item['store_name']})", 
                "value": f"Stock: {item['current_stock']} | ADS: {round(item['average_daily_sales'],1)} | Reorder: {item['recommended_reorder']}"
            })

        return {
            "intent": "REORDER_STOCKOUT",
            "user_query": user_query,
            "data_sufficiency": "sufficient",
            "context_summary": f"Found {len(low_items)} products at or below the warning threshold.",
            "metrics": metrics,
            "recommendations": rec_list,
            "evidence": evidence_list,
            "assumptions": [f"Target inventory coverage = {TARGET_COVERAGE_DAYS} days", "Critical threshold <= 2 days, Warning threshold <= 7 days"],
            "raw_data": low_items
        }

    # 3. OVERSTOCKED
    elif any(k in q_lower for k in ["overstock", "overstocked", "too much stock", "excess stock"]):
        over_items = get_overstocked_items()
        evidence_list = []
        rec_list = []
        metrics = []

        for item in over_items:
            evidence_list.append({
                "product_name": item["product_name"],
                "store_name": item["store_name"],
                "current_stock": item["current_stock"],
                "avg_daily_sales": round(item["average_daily_sales"], 2),
                "days_remaining": item["days_remaining"],
                "units_sold": item["units_sold_30d"],
                "sales_period": "Last 30 Days",
                "source": "inventory + sales"
            })
            rec_list.append(f"Pause procurement for {item['product_name']} at {item['store_name']}. Implement promotional discount or store re-allocation.")
            metrics.append({"label": item['product_name'], "value": f"Stock: {item['current_stock']} units | Coverage: {item['days_remaining']} days"})

        return {
            "intent": "OVERSTOCK",
            "user_query": user_query,
            "data_sufficiency": "sufficient",
            "context_summary": f"Identified {len(over_items)} overstocked product-store combinations.",
            "metrics": metrics,
            "recommendations": rec_list,
            "evidence": evidence_list,
            "assumptions": ["Overstock threshold = Coverage > 30 days and current stock >= 50 units"],
            "raw_data": over_items
        }

    # 4. SLOW MOVING INVENTORY
    elif any(k in q_lower for k in ["slow", "slow moving", "slowly", "sluggish", "stagnant"]):
        slow_items = get_slow_moving_items()
        evidence_list = []
        rec_list = []
        metrics = []

        for item in slow_items:
            evidence_list.append({
                "product_name": item["product_name"],
                "store_name": item["store_name"],
                "current_stock": item["current_stock"],
                "avg_daily_sales": round(item["average_daily_sales"], 2),
                "days_remaining": item["days_remaining"],
                "units_sold": item["units_sold_30d"],
                "sales_period": "Last 30 Days",
                "source": "inventory + sales"
            })
            rec_list.append(f"Discount or cross-promote {item['product_name']} ({item['store_name']}) - 30d sales: {item['units_sold_30d']} units.")
            metrics.append({"label": item['product_name'], "value": f"Stock: {item['current_stock']} units | 30d Sales: {item['units_sold_30d']}"})

        return {
            "intent": "SLOW_MOVING",
            "user_query": user_query,
            "data_sufficiency": "sufficient",
            "context_summary": f"Found {len(slow_items)} slow-moving products.",
            "metrics": metrics,
            "recommendations": rec_list,
            "evidence": evidence_list,
            "assumptions": ["Slow-moving threshold = < 5 units sold in 30 days with stock >= 20 units"],
            "raw_data": slow_items
        }

    # 5. CAUSAL QUESTIONS ("WHY DID ... INCREASE / DECREASE?") -> EXPLICIT DATA INSUFFICIENT
    elif any(k in q_lower for k in ["why", "reason for", "what caused", "why did"]):
        # Retrieve facts about sales change first
        trends_df = get_product_sales_trends()
        
        # Check if a specific product or category is mentioned
        matching_rows = []
        if not trends_df.empty:
            for _, row in trends_df.iterrows():
                p_name = row['product_name'].lower()
                cat = row['category'].lower()
                if any(w in p_name or w in cat for w in q_lower.split()):
                    matching_rows.append(row)

        evidence_list = []
        metrics = []
        if matching_rows:
            for r in matching_rows[:3]:
                evidence_list.append({
                    "product_name": r["product_name"],
                    "store_name": "All Stores",
                    "current_stock": "N/A",
                    "avg_daily_sales": round(r["curr_units_30d"] / 30.0, 2),
                    "days_remaining": "N/A",
                    "units_sold": f"Current: {r['curr_units_30d']} | Prev: {r['prev_units_30d']}",
                    "sales_period": "30d vs Previous 30d",
                    "source": "sales records"
                })
                metrics.append({
                    "label": r["product_name"],
                    "value": f"Change: {r['pct_change_units']}% ({r['prev_units_30d']} → {r['curr_units_30d']} units)"
                })
        else:
            # Default to top spike product
            spikes = get_sales_spikes()
            if spikes:
                top_s = spikes[0]
                evidence_list.append({
                    "product_name": top_s["product_name"],
                    "store_name": "All Stores",
                    "current_stock": "N/A",
                    "avg_daily_sales": round(top_s["curr_units_30d"] / 30.0, 2),
                    "days_remaining": "N/A",
                    "units_sold": f"Current: {top_s['curr_units_30d']} | Prev: {top_s['prev_units_30d']}",
                    "sales_period": "30d vs Previous 30d",
                    "source": "sales records"
                })
                metrics.append({
                    "label": top_s["product_name"],
                    "value": f"Change: +{top_s['pct_change_units']}% ({top_s['prev_units_30d']} → {top_s['curr_units_30d']} units)"
                })

        return {
            "intent": "CAUSAL_WHY_QUERY",
            "user_query": user_query,
            "data_sufficiency": "insufficient",
            "context_summary": "The sales figures demonstrate the volume change, but marketing, pricing, advertisement, competitor, or external causal data is NOT available in the database.",
            "metrics": metrics,
            "recommendations": ["Incorporate marketing campaign logs or promotion tracking into the system to capture causal factors."],
            "evidence": evidence_list,
            "assumptions": ["Sales transaction records contain quantity and revenue, but lack marketing/campaign meta-attributes."],
            "raw_data": matching_rows if matching_rows else []
        }

    # 6. SALES SPIKES / DROPS / TRENDS
    elif any(k in q_lower for k in ["spike", "drop", "surge", "decline", "increase", "decrease", "unusual", "trend"]):
        spikes = get_sales_spikes()
        drops = get_sales_drops()
        evidence_list = []
        rec_list = []
        metrics = []

        for s in spikes:
            evidence_list.append({
                "product_name": s["product_name"],
                "store_name": "All Stores",
                "current_stock": "N/A",
                "avg_daily_sales": round(s["curr_units_30d"] / 30.0, 2),
                "days_remaining": "N/A",
                "units_sold": f"{s['prev_units_30d']} → {s['curr_units_30d']}",
                "sales_period": "30d vs Previous 30d",
                "source": "sales records"
            })
            metrics.append({"label": f"SPIKE: {s['product_name']}", "value": f"+{s['pct_change_units']}% growth"})
            rec_list.append(f"Capitalize on {s['product_name']} demand surge (+{s['pct_change_units']}%).")

        for d in drops:
            evidence_list.append({
                "product_name": d["product_name"],
                "store_name": "All Stores",
                "current_stock": "N/A",
                "avg_daily_sales": round(d["curr_units_30d"] / 30.0, 2),
                "days_remaining": "N/A",
                "units_sold": f"{d['prev_units_30d']} → {d['curr_units_30d']}",
                "sales_period": "30d vs Previous 30d",
                "source": "sales records"
            })
            metrics.append({"label": f"DROP: {d['product_name']}", "value": f"{d['pct_change_units']}% decline"})
            rec_list.append(f"Investigate demand decline for {d['product_name']} ({d['pct_change_units']}%).")

        return {
            "intent": "SALES_TRENDS_ANOMALIES",
            "user_query": user_query,
            "data_sufficiency": "sufficient",
            "context_summary": f"Detected {len(spikes)} sales spikes (>= +30%) and {len(drops)} sales drops (<= -30%).",
            "metrics": metrics,
            "recommendations": rec_list,
            "evidence": evidence_list,
            "assumptions": ["Spike threshold >= +30% change, Drop threshold <= -30% change over 30 days"],
            "raw_data": {"spikes": spikes, "drops": drops}
        }

    # 7. STORE PERFORMANCE
    elif any(k in q_lower for k in ["store", "best store", "performing store", "top store"]):
        stores_perf = get_store_performance()
        evidence_list = []
        metrics = []

        for st in stores_perf:
            evidence_list.append({
                "product_name": "All Products",
                "store_name": st["store_name"],
                "current_stock": "N/A",
                "avg_daily_sales": round(st["total_units_sold"] / 90.0, 2),
                "days_remaining": "N/A",
                "units_sold": st["total_units_sold"],
                "sales_period": "90 Days History",
                "source": "sales records"
            })
            metrics.append({"label": st["store_name"], "value": f"${st['total_revenue']:,.2f} ({st['total_units_sold']} units)"})

        top_store = stores_perf[0] if stores_perf else None
        rec = f"Maintain strong inventory allocation for top store '{top_store['store_name'] if top_store else 'N/A'}'."

        return {
            "intent": "STORE_PERFORMANCE",
            "user_query": user_query,
            "data_sufficiency": "sufficient",
            "context_summary": f"Ranked {len(stores_perf)} stores by total revenue.",
            "metrics": metrics,
            "recommendations": [rec],
            "evidence": evidence_list,
            "assumptions": ["Store ranking based on total revenue across 90 days"],
            "raw_data": stores_perf
        }

    # 8. PRODUCT SPECIFIC PERFORMANCE (e.g. "How did laptops perform this month?")
    else:
        trends_df = get_product_sales_trends()
        matching_rows = []
        
        if not trends_df.empty:
            for _, row in trends_df.iterrows():
                p_name = row['product_name'].lower()
                cat = row['category'].lower()
                # Check for word match
                tokens = q_lower.replace("?", "").split()
                if any(token in p_name or token in cat for token in tokens if len(token) > 3):
                    matching_rows.append(row)

        if matching_rows:
            evidence_list = []
            metrics = []
            rec_list = []

            for r in matching_rows:
                evidence_list.append({
                    "product_name": r["product_name"],
                    "store_name": "All Stores",
                    "current_stock": "N/A",
                    "avg_daily_sales": round(r["curr_units_30d"] / 30.0, 2),
                    "days_remaining": "N/A",
                    "units_sold": r["curr_units_30d"],
                    "sales_period": "Last 30 Days",
                    "source": "sales + product catalog"
                })
                metrics.append({
                    "label": r["product_name"],
                    "value": f"${r['curr_revenue_30d']:,.2f} revenue | {r['curr_units_30d']} units ({r['pct_change_units']}% YoY/MoM)"
                })
                if r['pct_change_units'] > 0:
                    rec_list.append(f"Maintain inventory momentum for {r['product_name']}.")
                else:
                    rec_list.append(f"Review pricing strategy for {r['product_name']}.")

            return {
                "intent": "PRODUCT_PERFORMANCE",
                "user_query": user_query,
                "data_sufficiency": "sufficient",
                "context_summary": f"Found {len(matching_rows)} matching products in catalog.",
                "metrics": metrics,
                "recommendations": rec_list,
                "evidence": evidence_list,
                "assumptions": ["Comparison based on last 30 days vs previous 30 days"],
                "raw_data": matching_rows
            }
        
        # General Fallback Intent
        inv_df = get_inventory_status_df()
        top_items = inv_df.head(5).to_dict(orient='records') if not inv_df.empty else []
        evidence_list = [{
            "product_name": it["product_name"],
            "store_name": it["store_name"],
            "current_stock": it["current_stock"],
            "avg_daily_sales": round(it["average_daily_sales"], 2),
            "days_remaining": it["days_remaining"],
            "units_sold": it["units_sold_30d"],
            "sales_period": "Last 30 Days",
            "source": "inventory"
        } for it in top_items]

        return {
            "intent": "GENERAL_SUMMARY",
            "user_query": user_query,
            "data_sufficiency": "sufficient",
            "context_summary": "Extracted high-level inventory and sales catalog summary.",
            "metrics": [{"label": it["product_name"], "value": f"Stock: {it['current_stock']}"} for it in top_items],
            "recommendations": ["Use specific questions like 'What is running out?' or 'Which store performed best?' for targeted insights."],
            "evidence": evidence_list,
            "assumptions": ["Showing top items from overall store catalog"],
            "raw_data": top_items
        }
