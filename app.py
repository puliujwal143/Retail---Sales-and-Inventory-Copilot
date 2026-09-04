import os
import sys
import uvicorn
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database import init_db, query_all, query_one
from src.analytics import get_dashboard_summary
from src.inventory_rules import get_inventory_status_df, get_low_stock_items, get_slow_moving_items, get_overstocked_items, TARGET_COVERAGE_DAYS
from src.sales_rules import get_sales_spikes, get_sales_drops, get_category_performance, get_store_performance, get_sales_analytics_charts, get_daily_sales_trend
from src.recommendation import get_attention_items
from src.query_engine import process_query_intent
from src.gemini import generate_copilot_response
from src.forecasting import calculate_sales_forecast
from src.sales_rules import compare_stores_analytics

# Initialize FastAPI App
app = FastAPI(
    title="RetailIQ - Sales & Inventory Copilot",
    description="Evidence-First AI Retail Operations Assistant (PS03)",
    version="1.0.0"
)

# Startup Handler to automatically populate SQLite data
@app.on_event("startup")
def startup_db_init():
    try:
        init_db(force=False)
    except Exception as e:
        print(f"Error initializing SQLite database on startup: {e}")

# Request model for chat
class ChatRequest(BaseModel):
    question: str
    store_id: Optional[str] = "all"
    target_date: Optional[str] = None

# API ENDPOINTS
@app.get("/api/dashboard")
def api_dashboard(store_id: Optional[str] = "all", date: Optional[str] = None):
    """Returns top-level KPIs, inventory valuation, top products, and store performance."""
    try:
        summary = get_dashboard_summary(store_id=store_id, target_date=date)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/snapshot")
def api_snapshot(date: str, store_id: Optional[str] = "all"):
    """Returns full historical retail snapshot as of target_date."""
    try:
        summary = get_dashboard_summary(store_id=store_id, target_date=date)
        inv_df = get_inventory_status_df(store_id=store_id, target_date=date)
        inv_records = inv_df.to_dict(orient="records") if not inv_df.empty else []
        alerts = get_attention_items()
        
        return {
            "snapshot_date": date,
            "store_id": store_id,
            "summary": summary,
            "inventory": inv_records,
            "alerts": alerts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/reorder-plan")
def api_reorder_plan(store_id: Optional[str] = "all", category: Optional[str] = "all", priority: Optional[str] = "all", date: Optional[str] = None):
    """Returns dedicated intelligent reorder planner data with target coverage math."""
    try:
        df = get_inventory_status_df(store_id=store_id, category=category, target_date=date)
        if df.empty:
            return []

        # Filter items requiring reorder or matching priority
        df["reorder_priority"] = df["status"].apply(lambda s: "CRITICAL" if s in ["CRITICAL", "OUT_OF_STOCK"] else ("HIGH" if s == "WARNING" else "NORMAL"))
        
        if priority and priority != "all":
            df = df[df["reorder_priority"] == priority]
        
        # Sort by reorder priority and units needed
        df = df.sort_values(by=["recommended_reorder", "days_remaining"], ascending=[False, True])
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/forecast")
def api_forecast(product_id: str, store_id: Optional[str] = "all", date: Optional[str] = None):
    """Returns 7-day, 14-day, and 30-day deterministic demand forecast with stockout risk flags."""
    try:
        return calculate_sales_forecast(product_id=product_id, store_id=store_id, target_date=date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/compare-stores")
def api_compare_stores(store_ids: str = "STR001,STR002,STR003", days: int = 30, date: Optional[str] = None):
    """Returns side-by-side store comparison matrix, stock health, and trend charts."""
    try:
        s_list = [s.strip() for s in store_ids.split(",") if s.strip()]
        return compare_stores_analytics(store_ids=s_list, time_days=days, target_date=date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/decision-center")
def api_decision_center(date: Optional[str] = None):
    """Returns prioritized operational decision items ranked by urgency and impact."""
    try:
        df = get_inventory_status_df(target_date=date)
        if df.empty:
            return []

        decisions = []
        # 1. Critical & Out of Stock Reorders
        crit_df = df[df["status"].isin(["CRITICAL", "OUT_OF_STOCK"])]
        for _, row in crit_df.iterrows():
            decisions.append({
                "priority": "CRITICAL",
                "category": "Inventory Replenishment",
                "title": f"Reorder Required: {row['product_name']}",
                "store_name": row["store_name"],
                "store_id": row["store_id"],
                "product_id": row["product_id"],
                "issue": f"Stock of {row['current_stock']} units covers only {row['days_remaining']} days of demand.",
                "impact": f"High risk of immediate stock-out and loss of sales.",
                "action": f"Reorder +{row['recommended_reorder']} units immediately.",
                "evidence": f"Current Stock: {row['current_stock']} | Avg Daily: {row['average_daily_sales']:.1f}/day | Target: 7 Days"
            })

        # 2. High Priority Warnings & Sales Drops
        warn_df = df[df["status"] == "WARNING"]
        for _, row in warn_df.iterrows():
            decisions.append({
                "priority": "HIGH",
                "category": "Stock Warning",
                "title": f"Low Stock Warning: {row['product_name']}",
                "store_name": row["store_name"],
                "store_id": row["store_id"],
                "product_id": row["product_id"],
                "issue": f"Stock covers {row['days_remaining']} days (below 7-day target threshold).",
                "impact": f"Potential stock depletion within the coming week.",
                "action": f"Schedule purchase order for +{row['recommended_reorder']} units.",
                "evidence": f"Stock: {row['current_stock']} | Days Left: {row['days_remaining']}d"
            })

        # 3. Medium Priority Overstock & Slow Moving
        over_df = df[df["status"] == "OVERSTOCK"]
        for _, row in over_df.iterrows():
            decisions.append({
                "priority": "MEDIUM",
                "category": "Capital Optimization",
                "title": f"Overstock Reduction: {row['product_name']}",
                "store_name": row["store_name"],
                "store_id": row["store_id"],
                "product_id": row["product_id"],
                "issue": f"High inventory of {row['current_stock']} units covers {row['days_remaining']} days.",
                "impact": f"Capital lock of ${row['stock_value']} in excess stock.",
                "action": "Pause upcoming replenishment orders and consider cross-promotions.",
                "evidence": f"Stock: {row['current_stock']} units (${row['stock_value']}) | Coverage: {row['days_remaining']}d"
            })

        return decisions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/executive-report")
def api_executive_report(store_id: Optional[str] = "all", date: Optional[str] = None):
    """Returns comprehensive BI Executive Summary Report for export & printing."""
    try:
        summary = get_dashboard_summary(store_id=store_id, target_date=date)
        spikes = get_sales_spikes()
        drops = get_sales_drops()
        inv_df = get_inventory_status_df(store_id=store_id, target_date=date)
        
        crit_items = inv_df[inv_df["status"].isin(["CRITICAL", "OUT_OF_STOCK"])].to_dict(orient="records") if not inv_df.empty else []
        reorder_items = inv_df[inv_df["recommended_reorder"] > 0].to_dict(orient="records") if not inv_df.empty else []
        
        return {
            "report_title": "RetailIQ Executive Operations Report",
            "generated_date": date or "Current Real-Time",
            "store_scope": store_id,
            "kpis": summary,
            "sales_anomalies": {"spikes": spikes, "drops": drops},
            "critical_stock_items": crit_items,
            "recommended_reorders": reorder_items,
            "top_products": summary.get("top_products", []),
            "store_performance": summary.get("store_performance", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/inventory")
def api_inventory(store_id: Optional[str] = "all", category: Optional[str] = "all", date: Optional[str] = None):
    """Returns inventory status table with days remaining, status, and reorder math."""
    try:
        df = get_inventory_status_df(store_id=store_id, category=category, target_date=date)
        if df.empty:
            return []
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sales")
def api_sales():
    """Returns period-over-period sales trends, sales spikes, sales drops, and category breakdown."""
    try:
        spikes = get_sales_spikes()
        drops = get_sales_drops()
        category_perf = get_category_performance()
        store_perf = get_store_performance()
        return {
            "spikes": spikes,
            "drops": drops,
            "category_performance": category_perf,
            "store_performance": store_perf
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/charts")
def api_analytics_charts(days: int = 30, store_id: Optional[str] = "all", category: Optional[str] = "all"):
    """Returns multi-chart datasets and deterministic insights for the Sales Analytics Workspace."""
    try:
        return get_sales_analytics_charts(days=days, store_id=store_id, category=category)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/{product_id}")
def api_product_detail(product_id: str, store_id: Optional[str] = "all", date: Optional[str] = None):
    """Returns detailed product metrics, historical sales trend, stock levels, and reorder calculations for modal."""
    try:
        product_info = query_one("SELECT * FROM products WHERE product_id = ?", (product_id,))
        if not product_info:
            raise HTTPException(status_code=404, detail="Product not found")

        df = get_inventory_status_df(store_id=store_id, target_date=date)
        prod_inv = df[df["product_id"] == product_id] if not df.empty else None
        
        current_stock = int(prod_inv["current_stock"].sum()) if prod_inv is not None and not prod_inv.empty else 0
        units_sold_30d = int(prod_inv["units_sold_30d"].sum()) if prod_inv is not None and not prod_inv.empty else 0
        avg_daily_sales = float(units_sold_30d / 30.0)
        days_remaining = float(current_stock / avg_daily_sales) if avg_daily_sales > 0 else 999.0
        
        status = "HEALTHY"
        if current_stock <= 0:
            status = "OUT_OF_STOCK"
        elif days_remaining <= 2.0:
            status = "CRITICAL"
        elif days_remaining <= 7.0:
            status = "WARNING"
        elif units_sold_30d < 5 and current_stock >= 20:
            status = "SLOW_MOVING"
        elif days_remaining > 30 and current_stock >= 50:
            status = "OVERSTOCK"

        target_stock = avg_daily_sales * TARGET_COVERAGE_DAYS
        reorder_qty = max(0, int(round(target_stock - current_stock)))

        # Product daily trend (30 days)
        if date:
            trend_query = """
            SELECT date, COALESCE(SUM(quantity), 0) as units, ROUND(COALESCE(SUM(total_revenue), 0), 2) as revenue
            FROM sales
            WHERE product_id = ? AND date <= ? AND date >= date(?, '-30 days')
            GROUP BY date ORDER BY date ASC
            """
            trend_rows = query_all(trend_query, (product_id, date, date))
        else:
            trend_query = """
            SELECT date, COALESCE(SUM(quantity), 0) as units, ROUND(COALESCE(SUM(total_revenue), 0), 2) as revenue
            FROM sales
            WHERE product_id = ? AND date >= date((SELECT MAX(date) FROM sales), '-30 days')
            GROUP BY date ORDER BY date ASC
            """
            trend_rows = query_all(trend_query, (product_id,))

        # Store breakdown for this product
        store_breakdown_sql = """
            SELECT st.store_name, COALESCE(SUM(s.quantity), 0) as units_sold, ROUND(COALESCE(SUM(s.total_revenue), 0), 2) as revenue
            FROM stores st
            LEFT JOIN sales s ON st.store_id = s.store_id AND s.product_id = ?
            GROUP BY st.store_id, st.store_name
            ORDER BY revenue DESC
        """
        store_matrix = query_all(store_breakdown_sql, (product_id,))

        return {
            "product": product_info,
            "metrics": {
                "current_stock": current_stock,
                "units_sold_30d": units_sold_30d,
                "avg_daily_sales": round(avg_daily_sales, 2),
                "days_remaining": round(days_remaining, 1),
                "status": status,
                "recommended_reorder": reorder_qty,
                "target_coverage_days": TARGET_COVERAGE_DAYS,
                "30d_revenue": round(units_sold_30d * product_info["unit_price"], 2)
            },
            "sales_trend": trend_rows,
            "store_matrix": store_matrix,
            "evidence": {
                "source": "inventory_movements + sales SQLite tables",
                "calculation": f"{current_stock} stock / {round(avg_daily_sales, 2)} avg daily sales = {round(days_remaining, 1)} days coverage",
                "assumptions": [f"{TARGET_COVERAGE_DAYS}-day target inventory coverage", "30-day historical sales window"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/alerts")
def api_alerts():
    """Returns severity-ranked attention items detected by the rules engine."""
    try:
        return get_attention_items()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stores")
def api_stores():
    """Returns list of retail stores."""
    try:
        return query_all("SELECT * FROM stores ORDER BY store_id")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products")
def api_products():
    """Returns product catalogue."""
    try:
        return query_all("SELECT * FROM products ORDER BY product_id")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
def api_chat(req: ChatRequest):
    """
    AI Copilot Chat Endpoint:
    1. Classifies intent & runs deterministic Python logic.
    2. Packages structured evidence, assumptions, and SVG chart specs.
    3. Calls Gemini for explanation (or deterministic fallback if API fails).
    """
    try:
        if not req.question or not req.question.strip():
            raise HTTPException(status_code=400, detail="Question cannot be empty.")
        
        # 1. Deterministic query processing & evidence gathering
        processed = process_query_intent(req.question.strip())
        
        # 2. Gemini explanation generation
        grounded_response = generate_copilot_response(processed)
        return grounded_response

    except Exception as e:
        return JSONResponse(
            status_code=200,  # Return fallback JSON gracefully without breaking frontend
            content={
                "answer": f"An error occurred while processing your request: {str(e)}",
                "key_metrics": [],
                "recommendations": ["Try rephrasing your question or check database logs."],
                "evidence": [],
                "assumptions": [],
                "data_sufficiency": "insufficient",
                "chart": None
            }
        )

# Static Files Mounting
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    """Serves the single-page web app."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "RetailIQ API active. Please place index.html in static directory."}

if __name__ == "__main__":
    # Ensure database is initialized before server starts
    init_db(force=False)
    
    print("\n" + "="*60)
    print("RetailIQ Sales & Inventory Copilot (PS03)")
    print("Listening on: http://0.0.0.0:8000")
    print("Open in Browser: http://localhost:8000")
    print("="*60 + "\n")

    # Serve directly using uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
