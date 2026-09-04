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

# API ENDPOINTS
@app.get("/api/dashboard")
def api_dashboard(store_id: Optional[str] = "all"):
    """Returns top-level KPIs, inventory valuation, top products, and store performance."""
    try:
        summary = get_dashboard_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/inventory")
def api_inventory(store_id: Optional[str] = "all", category: Optional[str] = "all"):
    """Returns inventory status table with days remaining, status, and reorder math."""
    try:
        df = get_inventory_status_df(store_id=store_id, category=category)
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
def api_product_detail(product_id: str, store_id: Optional[str] = "all"):
    """Returns detailed product metrics, historical sales trend, stock levels, and reorder calculations for modal."""
    try:
        product_info = query_one("SELECT * FROM products WHERE product_id = ?", (product_id,))
        if not product_info:
            raise HTTPException(status_code=404, detail="Product not found")

        df = get_inventory_status_df(store_id=store_id)
        prod_inv = df[df["product_id"] == product_id] if not df.empty else None
        
        current_stock = int(prod_inv["current_stock"].sum()) if prod_inv is not None and not prod_inv.empty else 0
        units_sold_30d = int(prod_inv["units_sold_30d"].sum()) if prod_inv is not None and not prod_inv.empty else 0
        avg_daily_sales = float(units_sold_30d / 30.0)
        days_remaining = float(current_stock / avg_daily_sales) if avg_daily_sales > 0 else 999.0
        
        status = "HEALTHY"
        if current_stock == 0:
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
        trend_query = """
        SELECT date, COALESCE(SUM(quantity), 0) as units, ROUND(COALESCE(SUM(total_revenue), 0), 2) as revenue
        FROM sales
        WHERE product_id = ? AND date >= date((SELECT MAX(date) FROM sales), '-30 days')
        GROUP BY date ORDER BY date ASC
        """
        trend_rows = query_all(trend_query, (product_id,))

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
            "evidence": {
                "source": "inventory + sales SQLite tables",
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
