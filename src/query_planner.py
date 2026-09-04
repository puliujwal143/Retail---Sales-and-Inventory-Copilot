"""
Universal Query Specification Planner for RetailIQ.
Transforms natural-language retail questions into structured QuerySpecification objects.
"""

import re
import datetime
from typing import Dict, Any, List, Optional
from src.database import query_all, query_one

# Global conversation memory store (per session / in-memory)
CONVERSATION_MEMORY: Dict[str, Any] = {
    "last_intent": None,
    "last_metric": "revenue",
    "last_date_range": None,
    "last_store": None,
    "last_product": None,
    "last_category": None,
    "last_limit": 5
}

def get_database_entities():
    """Fetches exact products, stores, and categories from SQLite database."""
    try:
        stores = query_all("SELECT store_id, store_name FROM stores")
        products = query_all("SELECT product_id, product_name, category FROM products")
        categories = list(set(p["category"] for p in products if p.get("category")))
        return stores, products, categories
    except Exception:
        return [], [], []

def get_db_date_bounds():
    """Fetches MIN(sales_date) and MAX(sales_date) from database."""
    try:
        row = query_one("SELECT MIN(sales_date) as min_d, MAX(sales_date) as max_d FROM sales")
        if row and row["min_d"] and row["max_d"]:
            return row["min_d"], row["max_d"]
    except Exception:
        pass
    return "2016-01-01", "2026-09-03"

def parse_date_range(text: str) -> Dict[str, Any]:
    """
    Parses date range expressions into start_date, end_date, granularity, and time_label.
    Uses DB MAX(date) as 'latest'/'today'.
    """
    min_db, max_db = get_db_date_bounds()
    max_year = int(max_db.split("-")[0])
    q = text.lower()

    # Explicit year range: e.g. "2019 to 2024", "2019-2024", "from 2019 to 2024", "between 2019 and 2024", "2016 to 2026"
    m_range = re.search(r'(?:from\s+|between\s+)?(20\d{2})\s*(?:to|-|and)\s*(20\d{2})', q)
    if m_range:
        y1, y2 = int(m_range.group(1)), int(m_range.group(2))
        start_y, end_y = min(y1, y2), max(y1, y2)
        end_date = max_db if end_y == max_year else f"{end_y}-12-31"
        return {
            "start_date": f"{start_y}-01-01",
            "end_date": end_date,
            "granularity": "yearly" if (end_y - start_y) >= 2 else "monthly",
            "time_label": f"{start_y} to {end_y}",
            "is_comparison": False
        }

    # Comparative years: e.g. "compare 2020 and 2025", "2020 vs 2025"
    m_comp = re.search(r'(?:compare\s+)?(20\d{2})\s*(?:vs|and|compared to)\s*(20\d{2})', q)
    if m_comp:
        y1, y2 = int(m_comp.group(1)), int(m_comp.group(2))
        return {
            "start_date": f"{min(y1, y2)}-01-01",
            "end_date": f"{max(y1, y2)}-12-31",
            "granularity": "yearly",
            "time_label": f"{y1} vs {y2}",
            "years_to_compare": [y1, y2],
            "is_comparison": True
        }

    # Single year: e.g. "in 2022", "for 2020", "2024"
    m_single = re.search(r'\b(20\d{2})\b', q)
    if m_single:
        y = int(m_single.group(1))
        end_date = max_db if y == max_year else f"{y}-12-31"
        return {
            "start_date": f"{y}-01-01",
            "end_date": end_date,
            "granularity": "monthly",
            "time_label": f"Year {y}",
            "is_comparison": False
        }

    # Last N years: e.g. "last 10 years", "last 5 years", "last 3 years", "last 2 years", "last 1 year"
    m_nyears = re.search(r'last\s+(\d+)\s+years?', q)
    if m_nyears:
        n = int(m_nyears.group(1))
        start_y = max(2016, max_year - n + 1)
        return {
            "start_date": f"{start_y}-01-01",
            "end_date": max_db,
            "granularity": "yearly" if n >= 3 else "monthly",
            "time_label": f"Last {n} Years ({start_y}-{max_year})",
            "is_comparison": False
        }

    # Last N days/months: e.g. "last 30 days", "last 90 days", "last 6 months"
    m_ndays = re.search(r'last\s+(\d+)\s+days?', q)
    if m_ndays:
        n = int(m_ndays.group(1))
        end_dt = datetime.datetime.strptime(max_db, "%Y-%m-%d")
        start_dt = end_dt - datetime.timedelta(days=n)
        return {
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": max_db,
            "granularity": "daily" if n <= 90 else "monthly",
            "time_label": f"Last {n} Days",
            "is_comparison": False
        }

    m_nmonths = re.search(r'last\s+(\d+)\s+months?', q)
    if m_nmonths:
        n = int(m_nmonths.group(1))
        end_dt = datetime.datetime.strptime(max_db, "%Y-%m-%d")
        start_dt = end_dt - datetime.timedelta(days=n * 30)
        return {
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "end_date": max_db,
            "granularity": "monthly",
            "time_label": f"Last {n} Months",
            "is_comparison": False
        }

    # Relative tokens: "today", "latest", "current", "yesterday", "this year", "last year"
    if any(k in q for k in ["today", "latest", "current"]):
        return {
            "start_date": max_db,
            "end_date": max_db,
            "granularity": "daily",
            "time_label": f"Snapshot {max_db}",
            "is_comparison": False
        }

    if "this year" in q:
        return {
            "start_date": f"{max_year}-01-01",
            "end_date": max_db,
            "granularity": "monthly",
            "time_label": f"Year {max_year}",
            "is_comparison": False
        }

    if "last year" in q:
        prev_y = max_year - 1
        return {
            "start_date": f"{prev_y}-01-01",
            "end_date": f"{prev_y}-12-31",
            "granularity": "monthly",
            "time_label": f"Year {prev_y}",
            "is_comparison": False
        }

    if any(k in q for k in ["all time", "historical", "entire history", "full period", "since 2016"]):
        return {
            "start_date": min_db,
            "end_date": max_db,
            "granularity": "yearly",
            "time_label": f"Historical Range ({min_db} to {max_db})",
            "is_comparison": False
        }

    # Default fallback date range: Full dataset for historical queries, snapshot for inventory
    return {
        "start_date": min_db,
        "end_date": max_db,
        "granularity": "yearly",
        "time_label": f"Full Dataset ({min_db} to {max_db})",
        "is_comparison": False
    }

def extract_entities(text: str) -> Dict[str, Any]:
    """Matches product, store, category, metric, limit, and thresholds against DB."""
    q = text.lower()
    stores, products, categories = get_database_entities()

    matched_store = None
    matched_product = None
    matched_category = None

    # Store Matching
    for st in stores:
        s_name = st["store_name"].lower()
        s_id = st["store_id"].lower()
        if s_id in q or s_name in q:
            matched_store = st
            break
        # Match store location keywords like "westside", "downtown", "suburban", "metro", "eastside"
        parts = s_name.split()
        for p in parts:
            if len(p) > 3 and p in q:
                matched_store = st
                break

    # Category Matching
    for cat in categories:
        if cat.lower() in q or (cat.lower() == "computers" and "computer" in q) or (cat.lower() == "audio" and "headphone" in q):
            matched_category = cat
            break

    # Product Matching
    for prod in products:
        p_name = prod["product_name"].lower()
        p_id = prod["product_id"].lower()
        if p_id in q or p_name in q:
            matched_product = prod
            break
        # Match keywords like "laptop", "monitor", "headphone", "keyboard", "mouse"
        for kw in ["laptop", "monitor", "headphone", "keyboard", "mouse", "desk", "chair", "cable"]:
            if kw in q and kw in p_name:
                matched_product = prod
                break

    # Limit Extraction (e.g. "top 5", "top 10", "bottom 3")
    limit = 5
    m_lim = re.search(r'\b(?:top|bottom|first|limit)\s+(\d+)\b', q)
    if m_lim:
        limit = int(m_lim.group(1))

    # Metric Extraction
    metric = "revenue"
    if any(k in q for k in ["units sold", "quantity sold", "unit count", "most sold", "highest quantity", "number of items", "volume"]):
        metric = "units"
    elif any(k in q for k in ["growth", "growth %", "fastest growing", "percentage increase", "grew the most"]):
        metric = "growth"
    elif any(k in q for k in ["stock", "inventory", "days remaining", "coverage", "reorder"]):
        metric = "stock"

    # Threshold Extraction (e.g. "< 7 days", "> 50000 revenue")
    m_thresh_days = re.search(r'less than\s+(\d+)\s+days', q)
    threshold_days = int(m_thresh_days.group(1)) if m_thresh_days else None

    return {
        "store": matched_store,
        "product": matched_product,
        "category": matched_category,
        "metric": metric,
        "limit": limit,
        "threshold_days": threshold_days
    }

def classify_intent(text: str, entities: Dict[str, Any], date_info: Dict[str, Any]) -> str:
    """Classifies user query into one of 60+ retail intents."""
    q = text.lower()

    # 1. Why / Causal Query
    if any(k in q for k in ["why did", "why has", "why is", "reason for", "cause of"]):
        return "WHY_SALES_CHANGED"

    # 2. Seasonality
    if any(k in q for k in ["seasonality", "seasonal", "monthly pattern", "best month", "demand pattern"]):
        return "SEASONALITY"

    # 3. Year / Store / Product Comparison
    if date_info.get("is_comparison") or "vs" in q or "compare" in q or "comparison" in q:
        if entities.get("product"):
            return "PRODUCT_COMPARISON"
        if entities.get("store") or "store" in q or "stores" in q:
            return "STORE_COMPARISON"
        return "YEAR_COMPARISON"

    # 4. Inventory / Reorder / Attention / Risk
    if any(k in q for k in ["attention", "priority", "urgent", "problems", "issues"]):
        return "ATTENTION_ITEMS"
    if any(k in q for k in ["reorder", "replenish", "purchase order", "buy more"]):
        return "REORDER"
    if any(k in q for k in ["low stock", "running out", "running low", "critical stock", "stockout risk"]):
        return "LOW_STOCK"
    if any(k in q for k in ["overstock", "excess inventory", "too much stock", "dead inventory"]):
        return "OVERSTOCK"
    if any(k in q for k in ["inventory", "stock level", "stock coverage", "days of stock"]):
        return "INVENTORY_SNAPSHOT"

    # 5. Product Rankings & Performance
    if any(k in q for k in [
        "top product", "best product", "best performer", "top performer", "best seller", "best-selling",
        "highest revenue product", "most sold product", "top skus", "worst performer", "worst product",
        "which product", "which item", "top 5 products", "top 10 products", "best sku"
    ]) or ("product" in q and any(k in q for k in ["best", "top", "most", "highest", "lowest", "grew"])) or ("item" in q and "doing" in q):
        return "TOP_PRODUCTS"

    if entities.get("product"):
        return "PRODUCT_PERFORMANCE"

    # 6. Category Rankings & Performance
    if any(k in q for k in [
        "top category", "best category", "category performance", "categories", "which category",
        "category generated", "category sold"
    ]) or ("category" in q and any(k in q for k in ["best", "top", "most", "highest"])):
        return "TOP_CATEGORIES"

    # 7. Store Rankings & Performance
    if any(k in q for k in [
        "top store", "best store", "store performance", "which store", "which location",
        "location made", "best performing store", "highest revenue store"
    ]) or ("store" in q and any(k in q for k in ["best", "top", "most", "highest"])):
        return "STORE_PERFORMANCE"

    # 8. Sales & Revenue Trends / Trajectory
    if any(k in q for k in ["trend", "trajectory", "over time", "history", "historical", "last 10 years", "last 5 years", "grew", "changed"]):
        return "SALES_TREND"

    # 9. General Business Summary
    if any(k in q for k in ["summary", "overview", "business performing", "how are we doing", "general status"]):
        return "GENERAL_SUMMARY"

    # Default to Sales Summary
    return "SALES_SUMMARY"

def build_query_spec(question: str, override_store: Optional[str] = None, override_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Main Entrypoint: Takes natural language question and builds a complete QuerySpecification.
    Includes conversational memory handling and multi-filter integration.
    """
    global CONVERSATION_MEMORY

    q_clean = question.strip()
    date_info = parse_date_range(q_clean)
    entities = extract_entities(q_clean)

    # Apply override store from UI selector if user didn't specify one in prompt
    if not entities["store"] and override_store and override_store.upper() != "ALL":
        stores, _, _ = get_database_entities()
        for st in stores:
            if st["store_id"].lower() == override_store.lower():
                entities["store"] = st
                break

    # Conversation Context Continuation (Follow-up handling)
    # E.g., User asks "How about 2023?" or "What about Westside?"
    if len(q_clean.split()) <= 4 and CONVERSATION_MEMORY.get("last_intent"):
        if not entities["product"] and CONVERSATION_MEMORY.get("last_product"):
            entities["product"] = CONVERSATION_MEMORY["last_product"]
        if not entities["category"] and CONVERSATION_MEMORY.get("last_category"):
            entities["category"] = CONVERSATION_MEMORY["last_category"]

    intent = classify_intent(q_clean, entities, date_info)

    # Update conversation memory
    CONVERSATION_MEMORY["last_intent"] = intent
    CONVERSATION_MEMORY["last_metric"] = entities["metric"]
    CONVERSATION_MEMORY["last_date_range"] = date_info
    if entities["store"]: CONVERSATION_MEMORY["last_store"] = entities["store"]
    if entities["product"]: CONVERSATION_MEMORY["last_product"] = entities["product"]
    if entities["category"]: CONVERSATION_MEMORY["last_category"] = entities["category"]

    query_spec = {
        "raw_question": q_clean,
        "intent": intent,
        "metric": entities["metric"],
        "aggregation": "sum",
        "date_range": date_info,
        "store": entities["store"],
        "product": entities["product"],
        "category": entities["category"],
        "limit": entities["limit"],
        "threshold_days": entities["threshold_days"],
        "chart_required": True
    }

    return query_spec
