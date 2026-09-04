"""
Universal Query Specification Planner for RetailIQ.
Transforms natural-language retail questions into structured QuerySpecification objects.
Implements robust Entity Resolution, Product Family Matching, and Accessory Separation.
"""

import re
import datetime
import logging
from typing import Dict, Any, List, Optional, Tuple
from src.database import query_all, query_one

logger = logging.getLogger("retailiq.planner")

# Global conversation memory store
CONVERSATION_MEMORY: Dict[str, Any] = {
    "last_intent": None,
    "last_metric": "revenue",
    "last_date_range": None,
    "last_store": None,
    "last_product": None,
    "last_product_family": None,
    "last_category": None,
    "last_limit": 5
}

# Pre-defined Product Family Mappings for RetailIQ Catalog
PRODUCT_FAMILIES = {
    "laptop": {
        "family_name": "Laptop Computers",
        "keywords": ["laptop", "laptops", "notebook", "notebooks"],
        "core_products": ["PRD001", "PRD002"],  # Pro Laptop 15-inch, Ultra Slim Notebook 13
        "accessory_products": ["PRD037"],       # Laptop Backpack Water Resistant
        "accessory_keywords": ["bag", "bags", "backpack", "backpacks", "sleeve", "sleeves", "case", "cases", "stand", "accessories", "accessory"]
    },
    "smartphone": {
        "family_name": "Smartphones",
        "keywords": ["phone", "phones", "smartphone", "smartphones", "mobile"],
        "core_products": ["PRD016", "PRD017"],  # Flagship Smartphone 128GB, Budget Smartphone 64GB
        "accessory_products": ["PRD036"],       # Wireless Charging Pad
        "accessory_keywords": ["case", "charger", "charging", "pad", "cable", "screen protector", "accessories"]
    },
    "desktop": {
        "family_name": "Desktop Computers",
        "keywords": ["desktop", "desktops", "workstation", "pc"],
        "core_products": ["PRD003", "PRD004"],  # Desktop Workstation i7, Gaming Desktop RTX
        "accessory_products": [],
        "accessory_keywords": []
    },
    "smartwatch": {
        "family_name": "Smart Watches",
        "keywords": ["watch", "watches", "smartwatch", "fitness watch"],
        "core_products": ["PRD019"],            # Smart Fitness Watch
        "accessory_products": ["PRD020"],       # Smart Watch Replacement Band
        "accessory_keywords": ["band", "bands", "strap", "replacement"]
    },
    "audio": {
        "family_name": "Audio Equipment",
        "keywords": ["audio", "headphone", "headphones", "earbuds", "speaker", "speakers", "soundbar", "mic"],
        "core_products": ["PRD011", "PRD012", "PRD013", "PRD014", "PRD015"],
        "accessory_products": [],
        "accessory_keywords": []
    },
    "gaming": {
        "family_name": "Gaming Hardware",
        "keywords": ["gaming", "console", "vr", "controller", "headset"],
        "core_products": ["PRD004", "PRD031", "PRD032", "PRD033", "PRD034", "PRD035"],
        "accessory_products": [],
        "accessory_keywords": []
    }
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
    """Fetches MIN(date) and MAX(date) from database."""
    try:
        row = query_one("SELECT MIN(date) as min_d, MAX(date) as max_d FROM sales")
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

    # Explicit date format e.g. "2025-06-15"
    m_date = re.search(r'\b(20\d{2}-\d{2}-\d{2})\b', q)
    if m_date:
        target_d = m_date.group(1)
        return {
            "start_date": target_d,
            "end_date": target_d,
            "granularity": "daily",
            "time_label": f"Date Snapshot {target_d}",
            "is_comparison": False
        }

    # Explicit year range: e.g. "2019 to 2024", "2019-2024", "between 2020 and 2025"
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

    # Comparative years: e.g. "compare 2024 and 2025", "2020 vs 2025"
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

    # Single year: e.g. "in 2025", "for 2024"
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

    # Relative years: e.g. "last 5 years", "last 10 years", "last 3 years"
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

    # Relative days/months
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

    # Default fallback date range: Full dataset (2016-2026)
    return {
        "start_date": min_db,
        "end_date": max_db,
        "granularity": "yearly",
        "time_label": f"Full Dataset ({min_db} to {max_db})",
        "is_comparison": False
    }

def extract_entities(text: str) -> Dict[str, Any]:
    """
    Robust Entity Resolution Engine:
    Resolves Store, Category, Product Family, and Exact Products.
    Separates Core Products from Accessory SKUs deterministically.
    """
    q = text.lower()
    stores, products, categories = get_database_entities()
    prod_dict = {p["product_id"]: p for p in products}

    matched_store = None
    matched_category = None
    matched_product_family = None
    matched_products = []
    excluded_accessories = []
    entity_type = "ALL_PRODUCTS"  # ALL_PRODUCTS, CATEGORY, PRODUCT_FAMILY, PRODUCT, STORE

    # 1. STORE RESOLUTION
    for st in stores:
        s_name = st["store_name"].lower()
        s_id = st["store_id"].lower()
        if s_id in q or s_name in q:
            matched_store = st
            break
        for p in s_name.split():
            if len(p) > 3 and p in q:
                matched_store = st
                break

    # 2. CATEGORY RESOLUTION
    for cat in categories:
        cat_l = cat.lower()
        if cat_l in q:
            matched_category = cat
            entity_type = "CATEGORY"
            break
        elif cat_l == "computers" and any(k in q for k in ["computer", "computers", "pc"]):
            matched_category = cat
            entity_type = "CATEGORY"
            break
        elif cat_l == "mobile" and any(k in q for k in ["mobile", "phone", "phones", "smartphone"]):
            matched_category = cat
            entity_type = "CATEGORY"
            break

    # 3. PRODUCT FAMILY & ACCESSORY SEPARATION
    for fam_key, fam_info in PRODUCT_FAMILIES.items():
        if any(kw in q for kw in fam_info["keywords"]):
            # Check if user explicitly asked for an accessory term (e.g., "laptop bag", "laptop sleeve")
            user_asked_accessory = any(akw in q for akw in fam_info["accessory_keywords"])

            if user_asked_accessory:
                # User specifically asked for accessory e.g. "laptop bag"
                for acc_id in fam_info["accessory_products"]:
                    if acc_id in prod_dict:
                        matched_products.append(prod_dict[acc_id])
                entity_type = "PRODUCT"
                matched_product_family = f"{fam_info['family_name']} Accessories"
            else:
                # User asked for core product family e.g. "laptop sales", "how did laptops perform"
                for core_id in fam_info["core_products"]:
                    if core_id in prod_dict:
                        matched_products.append(prod_dict[core_id])
                for acc_id in fam_info["accessory_products"]:
                    if acc_id in prod_dict:
                        excluded_accessories.append(prod_dict[acc_id])
                entity_type = "PRODUCT_FAMILY"
                matched_product_family = fam_info["family_name"]
            break

    # 4. EXACT PRODUCT MATCHING (If no product family was matched)
    if not matched_products and entity_type not in ["CATEGORY", "PRODUCT_FAMILY"]:
        for p in products:
            p_name_l = p["product_name"].lower()
            p_id_l = p["product_id"].lower()
            if p_id_l in q or p_name_l in q:
                matched_products.append(p)
                entity_type = "PRODUCT"
                break

    # If single exact product was matched
    matched_product = matched_products[0] if (matched_products and len(matched_products) == 1) else None

    # 5. METRIC & LIMIT EXTRACTION
    metric = "revenue"
    if any(k in q for k in ["units sold", "quantity sold", "unit count", "most sold", "highest quantity", "number of items", "volume"]):
        metric = "units"
    elif any(k in q for k in ["growth", "growth %", "fastest growing", "percentage increase", "grew the most"]):
        metric = "growth"
    elif any(k in q for k in ["stock", "inventory", "days remaining", "coverage", "reorder"]):
        metric = "stock"

    limit = 5
    m_lim = re.search(r'\b(?:top|bottom|first|limit)\s+(\d+)\b', q)
    if m_lim:
        limit = int(m_lim.group(1))

    m_thresh_days = re.search(r'less than\s+(\d+)\s+days', q)
    threshold_days = int(m_thresh_days.group(1)) if m_thresh_days else None

    return {
        "entity_type": entity_type,
        "store": matched_store,
        "product": matched_product,
        "product_family": matched_product_family,
        "matched_products": matched_products,
        "excluded_accessories": excluded_accessories,
        "category": matched_category,
        "metric": metric,
        "limit": limit,
        "threshold_days": threshold_days
    }

def classify_intent(text: str, entities: Dict[str, Any], date_info: Dict[str, Any]) -> str:
    """Classifies user query into canonical retail query intent."""
    q = text.lower()

    # 1. Why / Causal Query
    if any(k in q for k in ["why did", "why has", "why is", "reason for", "cause of", "what caused"]):
        return "WHY_SALES_CHANGED"

    # 2. Seasonality
    if any(k in q for k in ["seasonality", "seasonal", "monthly pattern", "best month", "demand pattern"]):
        return "SEASONALITY"

    # 3. Comparisons
    if date_info.get("is_comparison") or "vs" in q or "compare" in q or "comparison" in q:
        if entities.get("matched_products"):
            return "PRODUCT_COMPARISON"
        if entities.get("store") or "store" in q or "stores" in q:
            return "STORE_COMPARISON"
        return "YEAR_COMPARISON"

    # 4. Inventory / Reorder / Risk / Attention
    if any(k in q for k in ["attention", "priority", "urgent", "problems", "issues"]):
        return "ATTENTION_ITEMS"
    if any(k in q for k in ["reorder", "replenish", "purchase order", "buy more"]):
        return "REORDER"
    if any(k in q for k in ["low stock", "running out", "running low", "critical stock", "stockout risk"]):
        return "LOW_STOCK"
    if any(k in q for k in ["overstock", "excess inventory", "too much stock", "dead inventory"]):
        return "OVERSTOCK"
    if any(k in q for k in ["inventory", "stock level", "stock coverage", "days of stock", "today's inventory"]):
        return "INVENTORY_SNAPSHOT"

    # 5. Category Performance
    if any(k in q for k in ["top category", "best category", "category performance", "categories", "which category", "sales by category", "by category"]):
        return "TOP_CATEGORIES"

    # 6. Store Performance
    if any(k in q for k in ["top store", "best store", "store performance", "which store", "which location", "sales by store", "by store"]):
        return "STORE_PERFORMANCE"

    # 7. Product Rankings & Sales Performance
    if any(k in q for k in [
        "top product", "best product", "best performer", "top performer", "best seller", "best-selling",
        "highest revenue product", "most sold product", "top skus", "worst performer", "worst product",
        "top 5 products", "top 10 products", "best sku"
    ]):
        return "TOP_PRODUCTS"

    if entities.get("product_family") or entities.get("product") or entities.get("matched_products"):
        if any(k in q for k in ["best", "top", "lead", "highest", "winner"]):
            return "TOP_PRODUCTS"
        return "PRODUCT_PERFORMANCE"

    # 8. Sales Trend
    if any(k in q for k in ["trend", "trajectory", "over time", "history", "historical", "last 10 years", "last 5 years", "grew", "changed"]):
        return "SALES_TREND"

    # 9. General Summary
    if any(k in q for k in ["summary", "overview", "business performing", "how are we doing", "general status"]):
        return "GENERAL_SUMMARY"

    return "SALES_SUMMARY"

def build_query_spec(question: str, override_store: Optional[str] = None, override_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Main Entrypoint: Builds validated QuerySpecification dictionary.
    Includes Entity Resolution, Product Family Identification, and Diagnostic Logging.
    """
    global CONVERSATION_MEMORY

    q_clean = question.strip()
    date_info = parse_date_range(q_clean)
    entities = extract_entities(q_clean)

    # Store selector override from UI header
    if not entities["store"] and override_store and override_store.upper() != "ALL":
        stores, _, _ = get_database_entities()
        for st in stores:
            if st["store_id"].lower() == override_store.lower():
                entities["store"] = st
                break

    # Follow-up Memory Context
    if len(q_clean.split()) <= 4 and CONVERSATION_MEMORY.get("last_intent"):
        if not entities["matched_products"] and CONVERSATION_MEMORY.get("last_product"):
            entities["product"] = CONVERSATION_MEMORY["last_product"]
            entities["matched_products"] = [CONVERSATION_MEMORY["last_product"]]
            entities["entity_type"] = "PRODUCT"
        if not entities["category"] and CONVERSATION_MEMORY.get("last_category"):
            entities["category"] = CONVERSATION_MEMORY["last_category"]

    intent = classify_intent(q_clean, entities, date_info)

    # Diagnostic Development Logging
    logger.info(f"[ENTITY RESOLUTION] Query: '{q_clean}' | Intent: {intent} | Entity Type: {entities['entity_type']} | Family: {entities['product_family']} | Matched SKUs: {[p['product_name'] for p in entities['matched_products']]} | Excluded: {[p['product_name'] for p in entities['excluded_accessories']]}")

    # Memory state update
    CONVERSATION_MEMORY["last_intent"] = intent
    CONVERSATION_MEMORY["last_metric"] = entities["metric"]
    CONVERSATION_MEMORY["last_date_range"] = date_info
    if entities["store"]: CONVERSATION_MEMORY["last_store"] = entities["store"]
    if entities["product"]: CONVERSATION_MEMORY["last_product"] = entities["product"]
    if entities["category"]: CONVERSATION_MEMORY["last_category"] = entities["category"]

    return {
        "raw_question": q_clean,
        "intent": intent,
        "metric": entities["metric"],
        "entity_type": entities["entity_type"],
        "date_range": date_info,
        "store": entities["store"],
        "product": entities["product"],
        "product_family": entities["product_family"],
        "matched_products": entities["matched_products"],
        "excluded_accessories": entities["excluded_accessories"],
        "category": entities["category"],
        "limit": entities["limit"],
        "threshold_days": entities["threshold_days"],
        "chart_required": True
    }
