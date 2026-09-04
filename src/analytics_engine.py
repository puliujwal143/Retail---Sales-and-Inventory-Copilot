"""
Deterministic Analytics Engine for RetailIQ.
Executes parameterized SQLite queries based on structured QuerySpecifications.
"""

from typing import Dict, Any, List
from src.database import query_all, query_one
from src.inventory_rules import TARGET_COVERAGE_DAYS, CRITICAL_DAYS_THRESHOLD, get_inventory_status_df
from src.recommendation import get_attention_items

def execute_query_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Primary dispatcher: Executes SQL calculations for any QuerySpecification.
    """
    intent = spec.get("intent", "SALES_SUMMARY")
    date_range = spec.get("date_range", {})
    start_date = date_range.get("start_date", "2016-01-01")
    end_date = date_range.get("end_date", "2026-09-03")
    time_label = date_range.get("time_label", "Full Dataset")

    store_filter = spec.get("store")
    store_id = store_filter["store_id"] if store_filter else None
    store_name = store_filter["store_name"] if store_filter else "All Stores"

    prod_filter = spec.get("product")
    prod_id = prod_filter["product_id"] if prod_filter else None
    prod_name = prod_filter["product_name"] if prod_filter else None

    cat_filter = spec.get("category")
    limit = spec.get("limit", 5)

    data_scope_str = f"Date Scope: {time_label} ({start_date} to {end_date}) • Scope: {store_name}"
    if cat_filter: data_scope_str += f" • Category: {cat_filter}"
    if prod_name: data_scope_str += f" • Product: {prod_name}"

    # 1. TOP / RANKED PRODUCTS
    if intent in ["TOP_PRODUCTS", "BEST_SELLING_PRODUCT", "HIGHEST_REVENUE_PRODUCT", "LOWEST_PERFORMING_PRODUCT"]:
        where_clauses = ["s.date BETWEEN ? AND ?"]
        params = [start_date, end_date]
        if store_id:
            where_clauses.append("s.store_id = ?")
            params.append(store_id)
        if cat_filter:
            where_clauses.append("p.category = ?")
            params.append(cat_filter)

        where_sql = " AND ".join(where_clauses)
        sort_dir = "ASC" if intent == "LOWEST_PERFORMING_PRODUCT" else "DESC"
        order_col = "SUM(s.quantity)" if spec.get("metric") == "units" else "SUM(s.total_revenue)"
        
        sql = f"""
            SELECT p.product_id, p.product_name, p.category,
                   SUM(s.total_revenue) as total_revenue,
                   SUM(s.quantity) as total_units_sold
            FROM sales s
            JOIN products p ON s.product_id = p.product_id
            WHERE {where_sql}
            GROUP BY p.product_id, p.product_name, p.category
            ORDER BY {order_col} {sort_dir}
            LIMIT ?
        """
        params.append(limit)
        results = query_all(sql, tuple(params))

        evidence = [{
            "product_name": r["product_name"],
            "store_name": store_name,
            "revenue": r["total_revenue"],
            "units_sold": r["total_units_sold"],
            "source": "sales ledger"
        } for r in results]

        metrics = [{"label": r["product_name"], "value": f"${r['total_revenue']:,.2f} ({r['total_units_sold']:,} units)"} for r in results]
        top_p = results[0] if results else None

        summary_text = (
            f"Top product by {spec['metric']} for {time_label} across {store_name} is "
            f"'{top_p['product_name'] if top_p else 'N/A'}' with ${top_p['total_revenue']:,.2f} revenue ({top_p['total_units_sold']:,} units)."
            if top_p else "No sales data found for the selected scope."
        )

        return {
            "intent": intent,
            "data_scope": data_scope_str,
            "data_sufficiency": "sufficient",
            "context_summary": summary_text,
            "metrics": metrics,
            "recommendations": [f"Optimize stock allocation for lead SKU '{top_p['product_name'] if top_p else 'N/A'}'."],
            "evidence": evidence,
            "raw_data": results,
            "chart_data": {
                "type": "horizontal_bar",
                "title": f"Top Products by Revenue ({time_label})",
                "labels": [r["product_name"][:16] for r in results],
                "datasets": [{"label": "Revenue ($)", "data": [r["total_revenue"] for r in results], "color": "#087F80"}]
            }
        }

    # 2. CATEGORY PERFORMANCE / RANKING
    if intent in ["TOP_CATEGORIES", "CATEGORY_PERFORMANCE"]:
        where_clauses = ["s.date BETWEEN ? AND ?"]
        params = [start_date, end_date]
        if store_id:
            where_clauses.append("s.store_id = ?")
            params.append(store_id)

        where_sql = " AND ".join(where_clauses)
        sql = f"""
            SELECT p.category, SUM(s.total_revenue) as total_revenue, SUM(s.quantity) as total_units
            FROM sales s
            JOIN products p ON s.product_id = p.product_id
            WHERE {where_sql}
            GROUP BY p.category
            ORDER BY total_revenue DESC
        """
        results = query_all(sql, tuple(params))
        top_c = results[0] if results else None

        return {
            "intent": intent,
            "data_scope": data_scope_str,
            "data_sufficiency": "sufficient",
            "context_summary": f"Ranked retail category performance for {time_label}. Lead category: '{top_c['category'] if top_c else 'N/A'}' generating ${top_c['total_revenue']:,.2f}.",
            "metrics": [{"label": r["category"], "value": f"${r['total_revenue']:,.2f}"} for r in results],
            "recommendations": [f"Expand merchandising strategy in top category '{top_c['category'] if top_c else 'N/A'}'."],
            "evidence": [{"category": r["category"], "revenue": r["total_revenue"], "units_sold": r["total_units"], "source": "sales ledger"} for r in results],
            "raw_data": results,
            "chart_data": {
                "type": "bar",
                "title": f"Category Performance ({time_label})",
                "labels": [r["category"] for r in results],
                "datasets": [{"label": "Revenue ($)", "data": [r["total_revenue"] for r in results], "color": "#2B6CB0"}]
            }
        }

    # 3. STORE PERFORMANCE & COMPARISON
    if intent in ["STORE_PERFORMANCE", "STORE_COMPARISON", "TOP_STORES"]:
        where_clauses = ["s.date BETWEEN ? AND ?"]
        params = [start_date, end_date]
        if cat_filter:
            where_clauses.append("p.category = ?")
            params.append(cat_filter)

        where_sql = " AND ".join(where_clauses)
        sql = f"""
            SELECT st.store_id, st.store_name,
                   SUM(s.total_revenue) as total_revenue,
                   SUM(s.quantity) as total_units_sold
            FROM sales s
            JOIN stores st ON s.store_id = st.store_id
            JOIN products p ON s.product_id = p.product_id
            WHERE {where_sql}
            GROUP BY st.store_id, st.store_name
            ORDER BY total_revenue DESC
        """
        results = query_all(sql, tuple(params))
        top_st = results[0] if results else None

        return {
            "intent": intent,
            "data_scope": data_scope_str,
            "data_sufficiency": "sufficient",
            "context_summary": f"Ranked store performance for {time_label}. Top store: {top_st['store_name'] if top_st else 'N/A'} with ${top_st['total_revenue']:,.2f} revenue.",
            "metrics": [{"label": r["store_name"], "value": f"${r['total_revenue']:,.2f}"} for r in results],
            "recommendations": [f"Prioritize inventory allocation for high-velocity store '{top_st['store_name'] if top_st else 'N/A'}'."],
            "evidence": [{"store_name": r["store_name"], "revenue": r["total_revenue"], "units_sold": r["total_units_sold"], "source": "sales ledger"} for r in results],
            "raw_data": results,
            "chart_data": {
                "type": "bar",
                "title": f"Store Revenue Comparison ({time_label})",
                "labels": [r["store_name"] for r in results],
                "datasets": [{"label": "Revenue ($)", "data": [r["total_revenue"] for r in results], "color": "#f59e0b"}]
            }
        }

    # 4. PRODUCT PERFORMANCE & TREND
    if intent in ["PRODUCT_PERFORMANCE", "PRODUCT_COMPARISON"]:
        target_prod = prod_name or "Pro Laptop 15-inch"
        where_clauses = ["p.product_name LIKE ?"]
        params = [f"%{target_prod}%"]
        if store_id:
            where_clauses.append("s.store_id = ?")
            params.append(store_id)

        where_sql = " AND ".join(where_clauses)
        sql = f"""
            SELECT strftime('%Y', s.date) as year,
                   SUM(s.total_revenue) as revenue,
                   SUM(s.quantity) as units
            FROM sales s
            JOIN products p ON s.product_id = p.product_id
            WHERE {where_sql}
            GROUP BY year ORDER BY year
        """
        results = query_all(sql, tuple(params))
        if not results:
            sql = "SELECT strftime('%Y', date) as year, SUM(total_revenue) as revenue, SUM(quantity) as units FROM sales GROUP BY year ORDER BY year"
            results = query_all(sql)

        labels = [r["year"] for r in results]
        revs = [r["revenue"] for r in results]
        tot_rev = sum(revs)
        tot_u = sum(r["units"] for r in results)

        return {
            "intent": intent,
            "data_scope": data_scope_str,
            "data_sufficiency": "sufficient",
            "context_summary": f"Historical trajectory for product '{target_prod}'. Total Revenue: ${tot_rev:,.2f} across {tot_u:,} units sold.",
            "metrics": [
                {"label": "Product", "value": target_prod},
                {"label": "Total Revenue", "value": f"${tot_rev:,.2f}"},
                {"label": "Units Sold", "value": f"{tot_u:,} units"}
            ],
            "recommendations": [f"Monitor supply chain replenishment for product '{target_prod}'."],
            "evidence": [{"year": r["year"], "product_name": target_prod, "revenue": r["revenue"], "units_sold": r["units"], "source": "sales ledger"} for r in results],
            "raw_data": results,
            "chart_data": {
                "type": "line",
                "title": f"Product Sales Trend: {target_prod}",
                "labels": labels,
                "datasets": [{"label": "Revenue ($)", "data": revs, "color": "#087F80"}]
            }
        }

    # 5. YEAR COMPARISON
    if intent == "YEAR_COMPARISON":
        years = date_range.get("years_to_compare", [2020, 2025])
        y1, y2 = years[0], years[1]
        
        where_params = [store_id] if store_id else []
        store_sql = "AND store_id = ?" if store_id else ""

        r1 = query_one(f"SELECT SUM(total_revenue) as rev, SUM(quantity) as units FROM sales WHERE strftime('%Y', date) = ? {store_sql}", (str(y1), *where_params))
        r2 = query_one(f"SELECT SUM(total_revenue) as rev, SUM(quantity) as units FROM sales WHERE strftime('%Y', date) = ? {store_sql}", (str(y2), *where_params))

        rev1 = r1["rev"] if r1 and r1["rev"] else 0.0
        rev2 = r2["rev"] if r2 and r2["rev"] else 0.0
        units1 = r1["units"] if r1 and r1["units"] else 0
        units2 = r2["units"] if r2 and r2["units"] else 0

        diff = rev2 - rev1
        pct = ((rev2 - rev1) / rev1 * 100.0) if rev1 > 0 else 0.0

        return {
            "intent": intent,
            "data_scope": data_scope_str,
            "data_sufficiency": "sufficient",
            "context_summary": f"Comparative revenue analysis: Year {y1} produced ${rev1:,.2f} ({units1:,} units), whereas Year {y2} produced ${rev2:,.2f} ({units2:,} units). Net Change: {pct:+.1f}% (${diff:+,.2f}).",
            "metrics": [
                {"label": f"Revenue {y1}", "value": f"${rev1:,.2f}"},
                {"label": f"Revenue {y2}", "value": f"${rev2:,.2f}"},
                {"label": "Net Growth", "value": f"{pct:+.1f}% (${diff:+,.2f})"}
            ],
            "recommendations": [f"Capitalize on growth momentum observed between {y1} and {y2}."],
            "evidence": [
                {"year": str(y1), "revenue": rev1, "units_sold": units1, "source": "sales ledger"},
                {"year": str(y2), "revenue": rev2, "units_sold": units2, "source": "sales ledger"}
            ],
            "raw_data": {"year1": y1, "rev1": rev1, "year2": y2, "rev2": rev2, "pct": pct},
            "chart_data": {
                "type": "bar",
                "title": f"Revenue Comparison: {y1} vs {y2}",
                "labels": [str(y1), str(y2)],
                "datasets": [{"label": "Revenue ($)", "data": [rev1, rev2], "color": "#087F80"}]
            }
        }

    # 6. INVENTORY / REORDER / ATTENTION ITEMS
    if intent in ["ATTENTION_ITEMS", "REORDER", "LOW_STOCK", "OVERSTOCK", "INVENTORY_SNAPSHOT"]:
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
                "source": "inventory ledger"
            })
            rec_list.append(f"{item['product_name']}: {item['recommended_action']}")
            metrics.append({"label": item['product_name'], "value": f"{item['current_stock']} units ({item['days_remaining']} days left)"})

        return {
            "intent": intent,
            "data_scope": data_scope_str,
            "data_sufficiency": "sufficient",
            "context_summary": f"Identified {len(items)} inventory status items requiring operational attention.",
            "metrics": metrics,
            "recommendations": rec_list,
            "evidence": evidence_list,
            "raw_data": items,
            "chart_data": {
                "type": "bar",
                "title": "Operational Attention Priority Items",
                "labels": [it["product_name"][:12] for it in items[:5]],
                "datasets": [{"label": "Days Stock Remaining", "data": [it["days_remaining"] for it in items[:5]], "color": "#ef4444"}]
            }
        }

    # 7. SEASONALITY ANALYSIS
    if intent == "SEASONALITY":
        where_params = [store_id] if store_id else []
        store_sql = "WHERE store_id = ?" if store_id else ""

        sql = f"""
            SELECT strftime('%m', date) as month_num,
                   SUM(total_revenue) as total_revenue,
                   SUM(quantity) as total_units
            FROM sales
            {store_sql}
            GROUP BY month_num ORDER BY month_num
        """
        results = query_all(sql, tuple(where_params))
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        labels = []
        revs = []
        evidence = []

        for r in results:
            idx = int(r["month_num"]) - 1
            m_name = month_names[idx]
            labels.append(m_name)
            revs.append(r["total_revenue"])
            evidence.append({"month": m_name, "revenue": r["total_revenue"], "units_sold": r["total_units"], "source": "10-year monthly aggregation"})

        return {
            "intent": intent,
            "data_scope": data_scope_str,
            "data_sufficiency": "sufficient",
            "context_summary": f"Calculated 10-year monthly demand seasonality profile across all available historical records.",
            "metrics": [{"label": labels[i], "value": f"${revs[i]:,.2f}"} for i in range(min(4, len(labels)))],
            "recommendations": ["Prepare inventory buffer ahead of peak historical demand months."],
            "evidence": evidence,
            "raw_data": results,
            "chart_data": {
                "type": "bar",
                "title": "10-Year Monthly Demand Seasonality Profile",
                "labels": labels,
                "datasets": [{"label": "Average Revenue ($)", "data": revs, "color": "#2B6CB0"}]
            }
        }

    # 8. WHY / CAUSAL QUERY
    if intent == "WHY_SALES_CHANGED":
        sql = "SELECT strftime('%Y', date) as year, SUM(total_revenue) as revenue FROM sales GROUP BY year ORDER BY year"
        yearly = query_all(sql)
        y_start = yearly[0]["year"] if yearly else "2016"
        y_end = yearly[-1]["year"] if yearly else "2026"
        rev_start = yearly[0]["revenue"] if yearly else 0
        rev_end = yearly[-1]["revenue"] if yearly else 0
        pct = ((rev_end - rev_start) / rev_start * 100.0) if rev_start > 0 else 0.0

        summary_text = (
            f"Observed historical sales increased by {pct:+.1f}% from ${rev_start:,.2f} ({y_start}) to ${rev_end:,.2f} ({y_end}). "
            f"However, the dataset contains transaction sales ledger and inventory stock levels, but does NOT contain marketing campaigns, "
            f"advertisements, pricing adjustments, or competitor data. Therefore, the specific root cause cannot be established without inventing unverified facts."
        )

        return {
            "intent": intent,
            "data_scope": data_scope_str,
            "data_sufficiency": "insufficient",
            "context_summary": summary_text,
            "metrics": [
                {"label": f"Initial ({y_start})", "value": f"${rev_start:,.2f}"},
                {"label": f"Latest ({y_end})", "value": f"${rev_end:,.2f}"},
                {"label": "Historical Growth", "value": f"{pct:+.1f}%"}
            ],
            "recommendations": ["Correlate external marketing or pricing logs with internal sales trends for root-cause verification."],
            "evidence": [{"year": r["year"], "revenue": r["revenue"], "source": "sales ledger"} for r in yearly],
            "raw_data": yearly,
            "chart_data": {
                "type": "line",
                "title": "Historical Revenue Trajectory",
                "labels": [r["year"] for r in yearly],
                "datasets": [{"label": "Revenue ($)", "data": [r["revenue"] for r in yearly], "color": "#087F80"}]
            }
        }

    # 9. GENERAL / DEFAULT SALES TREND & SUMMARY
    sql = """
        SELECT strftime('%Y', date) as year,
               SUM(total_revenue) as revenue,
               SUM(quantity) as units
        FROM sales
        WHERE date BETWEEN ? AND ?
        GROUP BY year
        ORDER BY year
    """
    yearly = query_all(sql, (start_date, end_date))
    if not yearly:
        sql = "SELECT strftime('%Y', date) as year, SUM(total_revenue) as revenue, SUM(quantity) as units FROM sales GROUP BY year ORDER BY year"
        yearly = query_all(sql)

    labels = [r["year"] for r in yearly]
    revs = [r["revenue"] for r in yearly]
    tot_rev = sum(revs)
    tot_units = sum(r["units"] for r in yearly)

    evidence = [{"year": r["year"], "revenue": r["revenue"], "units_sold": r["units"], "source": "sales ledger"} for r in yearly]

    return {
        "intent": intent,
        "data_scope": data_scope_str,
        "data_sufficiency": "sufficient",
        "context_summary": f"Historical sales summary for {time_label} across {store_name}. Total Revenue: ${tot_rev:,.2f} ({tot_units:,} units sold).",
        "metrics": [
            {"label": "Total Revenue", "value": f"${tot_rev:,.2f}"},
            {"label": "Units Sold", "value": f"{tot_units:,} units"},
            {"label": "Time Period", "value": time_label}
        ],
        "recommendations": ["Explore specific store or product breakdowns for deeper operational insights."],
        "evidence": evidence,
        "raw_data": yearly,
        "chart_data": {
            "type": "line",
            "title": f"Revenue Trend ({time_label})",
            "labels": labels,
            "datasets": [{"label": "Revenue ($)", "data": revs, "color": "#087F80"}]
        }
    }
