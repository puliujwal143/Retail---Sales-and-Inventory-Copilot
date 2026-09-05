"""
Universal Query Specification Planner for RetailIQ.
Transforms natural-language retail questions into structured QuerySpecification objects.
Implements robust Entity Resolution, Product Family Matching, and Accessory Separation.
"""

import re
import datetime
import logging
import html
from typing import Dict, Any, List, Optional, Tuple
from src.database import query_all, query_one
from src.query_context import QueryContext

logger = logging.getLogger("retailiq.planner")

from src.dataset_manager import register_invalidation_callback

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

def clear_conversation_memory():
    """Clears conversation memory on dataset switch."""
    CONVERSATION_MEMORY.clear()
    CONVERSATION_MEMORY.update({
        "last_intent": None,
        "last_metric": "revenue",
        "last_date_range": None,
        "last_store": None,
        "last_product": None,
        "last_product_family": None,
        "last_category": None,
        "last_limit": 5
    })
    logger.info("Cleared conversation memory due to dataset invalidation.")

register_invalidation_callback(clear_conversation_memory)

# Pre-defined Product Family Mappings for RetailIQ Catalog
PRODUCT_FAMILIES = {
    "laptop": {
        "family_name": "Laptop Computers",
        "keywords": ["laptop", "laptops", "notebook", "notebooks"],
        "core_products": ["PRD001", "PRD002"],
        "accessory_products": ["PRD037"],
        "accessory_keywords": ["bag", "bags", "backpack", "backpacks", "sleeve", "sleeves", "case", "cases", "stand", "accessories", "accessory"]
    },
    "smartphone": {
        "family_name": "Smartphones",
        "keywords": ["phone", "phones", "smartphone", "smartphones", "mobile"],
        "core_products": ["PRD016", "PRD017"],
        "accessory_products": ["PRD036"],
        "accessory_keywords": ["case", "charger", "charging", "pad", "cable", "screen protector", "accessories"]
    },
    "desktop": {
        "family_name": "Desktop Computers",
        "keywords": ["desktop", "desktops", "workstation", "pc"],
        "core_products": ["PRD003", "PRD004"],
        "accessory_products": [],
        "accessory_keywords": []
    },
    "smartwatch": {
        "family_name": "Smart Watches",
        "keywords": ["watch", "watches", "smartwatch", "fitness watch"],
        "core_products": ["PRD019"],
        "accessory_products": ["PRD020"],
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
    """Fetches exact products, stores, and categories from active SQLite database."""
    try:
        stores = query_all("SELECT store_id, store_name FROM stores")
        products = query_all("SELECT product_id, product_name, category FROM products")
        categories = list(set(p["category"] for p in products if p.get("category")))
        return stores, products, categories
    except Exception:
        return [], [], []

def get_db_date_bounds():
    """Fetches MIN(date) and MAX(date) from active database."""
    from src.dataset_manager import ActiveDatasetManager
    if ActiveDatasetManager.get_active_dataset_id() is None:
        return None, None
    try:
        row = query_one("SELECT MIN(date) as min_d, MAX(date) as max_d FROM sales")
        if row and row["min_d"] and row["max_d"]:
            return str(row["min_d"]), str(row["max_d"])
    except Exception:
        pass
    return None, None

MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12
}

def parse_date_range(text: str) -> Dict[str, Any]:
    """
    Parses date range expressions into start_date, end_date, granularity, and time_label.
    Uses DB MAX(date) as 'latest'/'today'.
    """
    min_db, max_db = get_db_date_bounds()
    if not min_db or not max_db:
        return {
            "start_date": None,
            "end_date": None,
            "granularity": "daily",
            "time_label": "No Data Available",
            "is_comparison": False
        }
    min_year = int(min_db.split("-")[0])
    max_year = int(max_db.split("-")[0])
    q = text.lower()

    # 1. Explicit date format e.g. "2026-08-02"
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

    # 2. Month name date range: e.g. "between August 1 and August 3", "from Aug 1 to Aug 5", "August 1 to 3"
    m_mrange = re.search(
        r'(?:between|from)\s+([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(?:and|to|-)\s+(?:([a-z]+)\s+)?(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(20\d{2}))?',
        q
    )
    if m_mrange:
        m1_str, d1_str, m2_str, d2_str, y_str = m_mrange.groups()
        if m1_str in MONTH_MAP:
            m1 = MONTH_MAP[m1_str]
            m2 = MONTH_MAP[m2_str] if (m2_str and m2_str in MONTH_MAP) else m1
            d1, d2 = int(d1_str), int(d2_str)
            yr = int(y_str) if y_str else max_year
            s_date = f"{yr:04d}-{m1:02d}-{d1:02d}"
            e_date = f"{yr:04d}-{m2:02d}-{d2:02d}"
            return {
                "start_date": s_date,
                "end_date": e_date,
                "granularity": "daily",
                "time_label": f"{m1_str.title()} {d1} to {m2_str.title() if m2_str else m1_str.title()} {d2}, {yr}",
                "is_comparison": False
            }

    # 3. Single Month + Day: e.g. "on August 2", "sales on Aug 2", "2nd August", "August 2nd"
    m_mday1 = re.search(r'\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(20\d{2}))?\b', q)
    m_mday2 = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)(?:,?\s*(20\d{2}))?\b', q)
    
    if m_mday1 and m_mday1.group(1) in MONTH_MAP:
        m_str, d_str, y_str = m_mday1.groups()
        m_num = MONTH_MAP[m_str]
        d_num = int(d_str)
        yr = int(y_str) if y_str else max_year
        target_d = f"{yr:04d}-{m_num:02d}-{d_num:02d}"
        return {
            "start_date": target_d,
            "end_date": target_d,
            "granularity": "daily",
            "time_label": f"{m_str.title()} {d_num}, {yr}",
            "is_comparison": False
        }
    elif m_mday2 and m_mday2.group(2) in MONTH_MAP:
        d_str, m_str, y_str = m_mday2.groups()
        m_num = MONTH_MAP[m_str]
        d_num = int(d_str)
        yr = int(y_str) if y_str else max_year
        target_d = f"{yr:04d}-{m_num:02d}-{d_num:02d}"
        return {
            "start_date": target_d,
            "end_date": target_d,
            "granularity": "daily",
            "time_label": f"{m_str.title()} {d_num}, {yr}",
            "is_comparison": False
        }

    # 4. Explicit year range: e.g. "2019 to 2024", "2019-2024", "between 2020 and 2025"
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

    # 5. Comparative years: e.g. "compare 2024 and 2025", "2020 vs 2025"
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

    # 6. Single month name: e.g. "in August", "for August 2026"
    for m_name, m_val in MONTH_MAP.items():
        if re.search(r'\b(?:in\s+|for\s+)?' + m_name + r'(?:\s+(20\d{2}))?\b', q):
            m_yr = re.search(r'\b' + m_name + r'\s+(20\d{2})\b', q)
            yr = int(m_yr.group(1)) if m_yr else max_year
            import calendar
            last_day = calendar.monthrange(yr, m_val)[1]
            s_d = f"{yr:04d}-{m_val:02d}-01"
            e_d = f"{yr:04d}-{m_val:02d}-{last_day:02d}"
            if s_d < min_db: s_d = min_db
            if e_d > max_db: e_d = max_db
            return {
                "start_date": s_d,
                "end_date": e_d,
                "granularity": "daily",
                "time_label": f"{m_name.title()} {yr}",
                "is_comparison": False
            }

    # 7. Single year: e.g. "in 2025", "for 2010"
    m_single = re.search(r'\b((?:19|20)\d{2})\b', q)
    if m_single:
        y = int(m_single.group(1))
        is_oob = y < min_year or y > max_year
        end_date = max_db if y >= max_year else f"{y}-12-31"
        return {
            "start_date": f"{y}-01-01",
            "end_date": end_date,
            "granularity": "monthly",
            "time_label": f"Year {y}",
            "is_comparison": False,
            "is_out_of_bounds": is_oob
        }

    # 8. Relative years: e.g. "last 5 years", "last 10 years", "last 3 years"
    m_nyears = re.search(r'last\s+(\d+)\s+years?', q)
    if m_nyears:
        n = int(m_nyears.group(1))
        start_y = max(min_year, max_year - n + 1)
        return {
            "start_date": f"{start_y}-01-01",
            "end_date": max_db,
            "granularity": "yearly" if n >= 3 else "monthly",
            "time_label": f"Last {n} Years ({start_y}-{max_year})",
            "is_comparison": False
        }

    # 9. Relative days/months
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

    if "yesterday" in q:
        max_dt = datetime.datetime.strptime(max_db, "%Y-%m-%d")
        y_dt = max_dt - datetime.timedelta(days=1)
        y_str = y_dt.strftime("%Y-%m-%d")
        return {
            "start_date": y_str,
            "end_date": y_str,
            "granularity": "daily",
            "time_label": f"Snapshot {y_str}",
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

    if any(k in q for k in ["all time", "historical", "entire history", "full period"]):
        return {
            "start_date": min_db,
            "end_date": max_db,
            "granularity": "yearly",
            "time_label": f"Historical Range ({min_db} to {max_db})",
            "is_comparison": False
        }

    # Default fallback date range: Full active dataset
    return {
        "start_date": min_db,
        "end_date": max_db,
        "granularity": "yearly",
        "time_label": f"Full Dataset ({min_db} to {max_db})",
        "is_comparison": False
    }

KNOWN_PRODUCT_KEYWORDS = [
    "laptop", "laptops", "notebook", "notebooks", "macbook", "ultrabook", "chromebook",
    "computer", "computers", "pc", "desktop", "desktops", "workstation",
    "phone", "phones", "smartphone", "smartphones", "mobile", "iphone", "android",
    "tv", "tvs", "television", "televisions", "oled", "smart tv",
    "headphone", "headphones", "headset", "headsets", "earbuds", "earphones", "airpods",
    "keyboard", "keyboards", "mechanical keyboard", "wireless keyboard",
    "mouse", "mice", "ergonomic mouse", "wireless mouse", "gaming mouse",
    "scanner", "scanners", "document scanner",
    "bottle", "bottles", "water bottle", "water bottles", "flask", "tumbler",
    "tablet", "tablets", "ipad", "galaxy tab",
    "camera", "cameras", "dslr", "webcam",
    "watch", "watches", "smartwatch", "fitness tracker",
    "speaker", "speakers", "soundbar", "bluetooth speaker",
    "cable", "cables", "charger", "chargers", "adapter", "power bank",
    "monitor", "monitors", "display", "screen",
    "printer", "printers",
    "shirt", "t-shirt", "dress", "jeans", "pants", "shoes", "sneakers", "jacket",
    "backpack", "bag", "bags", "laptop bag", "sleeve", "case"
]

KNOWN_STORE_TERMS = [
    "downtown flagship", "metro hub store", "metro hub", "westside plaza",
    "north park outlet", "north park", "airport express", "downtown", "metro",
    "westside", "airport", "city store", "mall store", "central store",
    "suburban store", "flagship", "outlet", "london store", "new york store",
    "chicago store", "store 1", "store 2", "store 3", "store 4", "store 5", "store 99"
]

KNOWN_CATEGORY_TERMS = [
    "electronics", "accessories", "home", "computers", "clothing", "apparel",
    "footwear", "groceries", "furniture", "beauty", "toys", "sports", "books", "office"
]

def extract_entities(text: str, override_store: Optional[str] = None) -> Dict[str, Any]:
    """
    Robust Entity Resolution & Data-Grounding Engine:
    Resolves Store, Category, and Exact Products dynamically against active DB.
    Detects explicitly requested but non-existent entities and assigns grounding state:
    - DATA_FOUND
    - NO_DATA
    - PARTIAL_DATA
    - INVALID_QUERY
    """
    q = text.lower()
    stores, products, categories = get_database_entities()
    from src.dataset_manager import get_active_dataset_metadata
    meta = get_active_dataset_metadata() or {}
    dataset_name = meta.get("dataset_name", "Active Dataset")

    prod_names = [p["product_name"] for p in products]
    store_names = [s["store_name"] for s in stores]

    matched_store = None
    unresolved_store = None

    matched_category = None
    unresolved_category = None

    matched_products = []
    excluded_accessories = []
    unresolved_product = None
    entity_type = "ALL_PRODUCTS"

    DATE_WORDS = {
        "january", "february", "march", "april", "may", "june", "july", "august",
        "september", "october", "november", "december", "jan", "feb", "mar", "apr",
        "jun", "jul", "aug", "sep", "oct", "nov", "dec", "today", "yesterday",
        "tomorrow", "recent", "week", "month", "year", "quarter", "days", "months", "years",
        "q1", "q2", "q3", "q4", "2016", "2017", "2018", "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026", "2027",
        "current", "last", "past", "next", "full", "dataset", "period", "range", "annual", "daily", "monthly", "yearly", "august 2026"
    }

    STORE_STOP_WORDS = {
        "store", "stores", "shop", "shops", "outlet", "outlets", "branch", "branches",
        "location", "locations", "the", "and", "or", "in", "at", "for", "all", "each",
        "every", "our", "my", "retail", "which", "what", "top", "best", "worst", "lowest",
        "highest", "this", "that", "one", "any", "some", "a", "an", "doing", "performing",
        "good", "bad", "new", "old", "list", "show", "give", "how", "is", "are", "did", "does"
    }

    # 1. STORE RESOLUTION
    # Check active database stores first (Exact ID, Exact Name, or Distinctive Name Token)
    for st in stores:
        s_name = st["store_name"].lower()
        s_id = st["store_id"].lower()
        if re.search(r'\b' + re.escape(s_id) + r'\b', q) or re.search(r'\b' + re.escape(s_name) + r'\b', q):
            matched_store = st
            break
        # Match distinct store prefix tokens (e.g. "city", "mall", excluding generic words like "store")
        tokens = [t for t in s_name.split() if t not in STORE_STOP_WORDS and len(t) > 2]
        for token in tokens:
            if re.search(r'\b' + re.escape(token) + r'\b', q):
                matched_store = st
                break
        if matched_store:
            break

    # If no store matched, check if user explicitly mentioned a store name/term that is NOT in DB
    if not matched_store:
        # Check explicit store patterns: "in X store", "at X store", "for X store"
        m_store_pat = re.search(r'\b(?:in|at|for|across)\s+([a-zA-Z0-9\s\-]+?)\s+(?:store|branch|outlet|location|shop)\b', q)
        if m_store_pat:
            candidate_st = m_store_pat.group(1).strip()
            candidate_st_clean = " ".join([w for w in candidate_st.split() if w not in STORE_STOP_WORDS])
            if candidate_st_clean and candidate_st_clean not in ["sales", "performance", "inventory", "stock"]:
                active_match = any(candidate_st_clean in s.lower() for s in store_names)
                if not active_match:
                    unresolved_store = candidate_st_clean.title() + " Store"
        else:
            m_store_pat2 = re.search(r'\b([a-zA-Z0-9\-]+)\s+(?:store|branch|outlet|location|shop)\b', q)
            if m_store_pat2:
                candidate_st2 = m_store_pat2.group(1).strip()
                if candidate_st2.lower() not in STORE_STOP_WORDS and len(candidate_st2) > 2 and candidate_st2.lower() not in ["sales", "performance", "inventory", "stock", "the"]:
                    active_match2 = any(candidate_st2 in s.lower() for s in store_names)
                    if not active_match2:
                        unresolved_store = candidate_st2.title() + " Store"
        
        if not unresolved_store:
            for known_st in KNOWN_STORE_TERMS:
                if re.search(r'\b' + re.escape(known_st) + r'\b', q):
                    if not any(known_st in s.lower() for s in store_names):
                        unresolved_store = known_st.title() + " Store"
                        break

    # 2. CATEGORY RESOLUTION
    # Check active database categories first
    for cat in categories:
        cat_l = cat.lower()
        if re.search(r'\b' + re.escape(cat_l) + r'\b', q):
            matched_category = cat
            entity_type = "CATEGORY"
            break

    # If no category matched, check if user mentioned a category term NOT in active DB
    if not matched_category:
        m_cat_pat = re.search(r'\b(?:in|for|of)\s+([a-zA-Z0-9\s\-]+?)\s+category\b', q)
        if m_cat_pat:
            candidate_cat = m_cat_pat.group(1).strip()
            if not any(candidate_cat == c.lower() for c in categories):
                unresolved_category = candidate_cat.title()
        else:
            for known_cat in KNOWN_CATEGORY_TERMS:
                if re.search(r'\b' + re.escape(known_cat) + r'\b', q):
                    if not any(known_cat == c.lower() for c in categories):
                        if known_cat in ["clothing", "apparel", "footwear", "groceries", "furniture", "beauty", "toys", "sports", "books"]:
                            unresolved_category = known_cat.title()
                            break

    # 3. PRODUCT RESOLUTION (Exact & Token Matching against Active DB)
    # Match active DB products first
    for p in products:
        p_name_l = p["product_name"].lower()
        p_id_l = p["product_id"].lower()
        if re.search(r'\b' + re.escape(p_id_l) + r'\b', q) or re.search(r'\b' + re.escape(p_name_l) + r'\b', q):
            matched_products.append(p)
            entity_type = "PRODUCT"
            break

    if not matched_products:
        # Match product multi-word or distinct keywords in DB
        for p in products:
            p_name_l = p["product_name"].lower()
            # Check key noun tokens (e.g., "phone", "tv", "headphones", "keyboard", "bottle")
            for token in p_name_l.split():
                if len(token) > 2 and re.search(r'\b' + re.escape(token) + r'\b', q):
                    # Avoid generic words
                    if token not in ["fast", "slow", "old", "selling", "popular", "pro", "wireless", "smart"]:
                        matched_products.append(p)
                        entity_type = "PRODUCT"
                        break
            if matched_products:
                break

    # If still no product matched, check if user asked about a product noun NOT in active DB
    if not matched_products and entity_type != "CATEGORY" and not unresolved_category:
        # Check explicit question patterns: "how did X sales perform", "how did X perform", "sales of X"
        m_prod_pat = re.search(r'\b(?:how did|how does|how is|performance of|sales of|sales for|revenue of|stock of|inventory of|tell me about|info on|what about)\s+([a-zA-Z0-9\s\-]+?)\s*(?:sales\s+)?(?:perform|do|doing|look|trend|revenue|inventory|stock)?\b', q)
        if m_prod_pat:
            candidate_p = m_prod_pat.group(1).strip()
            # Clean stop words from candidate
            candidate_words = [w for w in candidate_p.split() if w not in ["the", "a", "an", "my", "our", "all", "in", "at", "for", "across", "to", "from", "and", "of"]]
            candidate_p_clean = " ".join(candidate_words).strip()
            
            # Check if candidate is pure date/time or generic query word
            is_date_only = all((w in DATE_WORDS or w.isdigit()) for w in candidate_words) if candidate_words else True
            is_store_reference = matched_store is not None or any(s in candidate_p_clean.lower() for s in store_names) or any(w in candidate_p_clean.lower().split() for w in STORE_STOP_WORDS)
            is_generic = candidate_p_clean in ["sales", "business", "company", "store", "stores", "everything", "products", "performance", "numbers", "records", "data", ""]

            if candidate_p_clean and not is_date_only and not is_generic and not is_store_reference:
                # Check if it matches any active product
                if not any(candidate_p_clean in p.lower() for p in prod_names):
                    unresolved_product = candidate_p_clean.title()
        
        # Check known product keywords if still unresolved
        if not unresolved_product:
            for known_kw in KNOWN_PRODUCT_KEYWORDS:
                if re.search(r'\b' + re.escape(known_kw) + r'\b', q):
                    if not any(known_kw in p.lower() for p in prod_names):
                        unresolved_product = known_kw.title()
                        break

    matched_product = matched_products[0] if (matched_products and len(matched_products) == 1) else None

    # 4. GROUNDING STATE DECISION
    grounding_state = "DATA_FOUND"
    missing_reason = None
    suggested_actions = []

    if unresolved_product:
        grounding_state = "NO_DATA"
        safe_p = html.escape(str(unresolved_product))
        safe_p_clean = html.escape(str(unresolved_product.lower()))
        if matched_store:
            missing_reason = f"'{safe_p}' data was not found in the current dataset ('{dataset_name}'). {matched_store['store_name']} is active, but there are no {safe_p_clean} products in the catalog. Available products are: {', '.join(prod_names)}."
        else:
            missing_reason = f"'{safe_p}' data was not found in the current dataset ('{dataset_name}'). I cannot provide {safe_p_clean}-specific sales performance. Available products in the current dataset are: {', '.join(prod_names)}."
        suggested_actions = [f"Try querying one of the available products: {', '.join(prod_names[:3])}"]
    elif unresolved_store:
        grounding_state = "NO_DATA"
        safe_st = html.escape(str(unresolved_store))
        missing_reason = f"Store '{safe_st}' was not found in the current dataset ('{dataset_name}'). Available stores are: {', '.join(store_names)}. I cannot provide store-specific sales performance."
        suggested_actions = [f"Try querying one of the available stores: {', '.join(store_names)}"]
    elif unresolved_category:
        grounding_state = "NO_DATA"
        safe_cat = html.escape(str(unresolved_category))
        missing_reason = f"Category '{safe_cat}' was not found in the current dataset ('{dataset_name}'). Available categories are: {', '.join(categories)}."
        suggested_actions = [f"Try querying one of the available categories: {', '.join(categories)}"]

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

    return {
        "entity_type": entity_type,
        "grounding_state": grounding_state,
        "missing_reason": missing_reason,
        "suggested_actions": suggested_actions,
        "unresolved_product": unresolved_product,
        "unresolved_store": unresolved_store,
        "unresolved_category": unresolved_category,
        "store": matched_store,
        "product": matched_product,
        "matched_products": matched_products,
        "excluded_accessories": excluded_accessories,
        "category": matched_category,
        "metric": metric,
        "limit": limit
    }

def classify_intent(text: str, entities: Dict[str, Any], date_info: Dict[str, Any]) -> str:
    """Classifies user query into canonical retail query intent."""
    q = text.lower().strip()

    # 1. Greetings, Conversational Tokens & Help
    conversational_tokens = [
        "hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening", "howdy",
        "thank you", "thanks", "thx", "thank u", "many thanks", "thank you so much", "thanks a lot",
        "ok", "okay", "great", "nice", "got it", "cool", "perfect", "awesome", "sure", "alright",
        "bye", "goodbye", "see you", "see ya"
    ]
    if q in conversational_tokens or any(q.startswith(t + " ") or q.endswith(" " + t) for t in ["thank you", "thanks", "thx", "bye", "goodbye"]):
        return "GREETING"
    if q in ["help", "what can you do", "commands", "how to use", "options", "features", "capabilities"]:
        return "HELP"

    has_store_word = any(w in q for w in [
        "store", "stores", "branch", "branches", "location", "locations", "shop", "shops", "outlet", "outlets"
    ]) or bool(entities.get("store") or entities.get("unresolved_store"))

    # 2. Store Comparison
    if has_store_word and ("compare" in q or "vs" in q or "comparison" in q or "compared to" in q or "difference between" in q):
        return "STORE_COMPARISON"

    # 3. Store Performance by Revenue
    if has_store_word and any(k in q for k in [
        "most revenue", "highest revenue", "made the most revenue", "generated the most revenue",
        "highest sales revenue", "top revenue store", "top store by revenue", "store made the most revenue",
        "store generated the most revenue", "store made the most money", "store has the highest revenue"
    ]):
        return "STORE_PERFORMANCE_BY_REVENUE"

    # 4. Store Performance by Units
    if has_store_word and any(k in q for k in [
        "sold the most units", "sold most units", "most units sold", "highest units", "most units",
        "highest quantity sold", "sold the most items", "sold the most products", "most volume", "highest volume",
        "store sold the most", "store sold the most units", "location sold the most", "branch sold the most"
    ]):
        return "STORE_PERFORMANCE_BY_UNITS"

    # 5. Store Performance (Rankings / General / Single Store / Best / Worst)
    is_store_performance_kw = any(k in q for k in [
        "performing best", "performing worst", "performing well", "performing poorly",
        "doing best", "doing worst", "doing well", "doing poorly",
        "best performing", "worst performing", "top performing", "bottom performing",
        "highest performing", "lowest performing", "underperforming",
        "performing", "performance", "strongest", "weakest", "successful",
        "highest sales", "highest selling", "best store", "best stores",
        "top store", "top stores", "worst store", "worst stores",
        "store performance", "branch performance", "location performance",
        "how is", "how are", "how did"
    ])
    if has_store_word and is_store_performance_kw:
        return "STORE_PERFORMANCE"

    if has_store_word and any(k in q for k in [
        "sales by store", "by store", "stores performed", "store sales", "sales across stores",
        "which store has the highest", "which store is", "which location is", "which branch is"
    ]):
        return "STORE_PERFORMANCE"

    # 6. Direct Store Count Query
    if any(k in q for k in [
        "how many stores", "how many store", "number of stores", "count of stores", "how many locations", "number of locations", "how many branches", "count of locations"
    ]):
        return "STORE_COUNT"

    # 7. Direct Store List Query (Informational Catalogue Listing ONLY)
    if any(k in q for k in [
        "what stores do i have", "which stores do i have", "what stores i have", "which stores i have",
        "list my stores", "show my stores", "list stores", "show stores", "what stores are available",
        "what are my stores", "stores do i have", "stores i have", "all stores", "all my stores", "our stores",
        "list the stores", "show the stores", "stores list", "store list", "list all my stores", "list all stores",
        "what stores do we have", "give me list of stores", "give me a list of stores"
    ]) or (has_store_word and any(w in q for w in ["list", "show", "what", "which", "available"]) and not any(w in q for w in ["perform", "sales", "revenue", "rank", "best", "worst", "top", "unit", "doing", "vs", "compare"])):
        return "STORE_LIST"

    # 8. Direct Product Count Query
    if any(k in q for k in [
        "how many products", "how many product", "how many skus", "how many sku", "how many items", "how many item",
        "number of products", "number of skus", "number of items", "count of products", "count of items", "count of skus"
    ]):
        return "PRODUCT_COUNT"

    # 9. Direct Inventory Summary / Stock Count Query
    if any(k in q for k in [
        "how much stock", "how much inventory", "what is my total stock", "what is total stock",
        "total stock on hand", "total inventory", "total stock", "stock do i have", "inventory do i have",
        "how many stock units", "how many units in stock", "stock on hand", "total units on hand"
    ]):
        return "INVENTORY_SUMMARY"

    # Specific negative words that indicate a ranking/performance/operational/sales query rather than an informational catalogue list
    is_ranking_or_perf = any(k in q for k in [
        "sold the most", "sold most", "sells the most", "sells most", "most sold", "highest revenue",
        "most revenue", "best seller", "best-seller", "best selling", "top seller", "top performing",
        "worst performing", "sold least", "revenue of", "sales of", "sales at", "sales in", "sales for",
        "revenue at", "revenue in", "revenue for", "sales", "revenue", "reorder", "replenish", "overstock",
        "overstocked", "attention", "grow", "growth", "why", "performance of", "how did", "how does",
        "how many", "count", "number of", "how much", "how are", "trend", "trajectory"
    ])

    # 10. Direct Product / Item List Query (PRODUCT_LIST)
    if (
        any(k in q for k in [
            "what items do i have", "what items do we have", "what items i have", "what items are available",
            "what products do i have", "what products do we have", "what products i have", "which products do i have",
            "which items do i have", "which products do we have", "products do i have", "items do i have",
            "products i have", "items i have", "list my products", "list my items", "show my products",
            "show my items", "show all products", "show all items", "show all my products", "show all my items",
            "list products", "list items", "list all products", "list all items", "products are available",
            "items are available", "products in my catalogue", "products in my catalog", "items in my catalogue",
            "items in my catalog", "products in catalogue", "products in catalog", "give me list if items",
            "give me list of items", "give me a list of items", "give me list of products", "give me a list of products",
            "give me products", "give me items", "products available", "items available",
            "show my products with stock", "show products with stock", "products with stock", "items with stock",
            "what products are in stock", "what items are in stock", "which products are in stock", "which items are in stock",
            "what items do you have", "what products do you have", "list catalogue", "show catalogue", "product catalogue",
            "product list", "items list", "list of items", "list if items"
        ])
        or (
            any(w in q for w in ["list", "show", "give", "display", "what", "which", "view", "available"])
            and any(w in q for w in ["item", "items", "product", "products", "sku", "skus", "catalogue", "catalog"])
            and not is_ranking_or_perf
        )
    ):
        return "PRODUCT_LIST"

    # 11. Top Product by Units vs Revenue
    if any(k in q for k in [
        "sold the most", "sold most", "sells the most", "sells most", "most sold", "most units",
        "highest units", "highest quantity", "most volume", "which product sold the most", "which item sold the most",
        "which one sells the most", "what product sold the most", "what item sold the most", "most sold product",
        "most sold item", "best selling product by units"
    ]):
        return "TOP_PRODUCT_BY_UNITS"

    if any(k in q for k in [
        "most revenue", "highest revenue", "generated the most revenue", "generated most revenue",
        "made the most revenue", "made the most money", "highest sales amount", "which product generated the most revenue",
        "which item generated the most revenue", "which product made the most", "which item made the most",
        "highest revenue product", "highest revenue item", "top product by revenue"
    ]):
        return "TOP_PRODUCT_BY_REVENUE"

    # 12. Reorder, Low Stock, Overstock, Slow Moving, Attention Today
    if any(k in q for k in ["attention", "priority", "urgent", "problems", "issues", "what needs my attention", "attention today", "what needs attention"]):
        return "ATTENTION_TODAY"
    if any(k in q for k in ["reorder", "replenish", "purchase order", "buy more", "which products should i reorder", "which ones should i reorder", "what should i reorder", "products should i reorder", "items should i reorder"]):
        return "REORDER"
    if any(k in q for k in ["low stock", "running out", "running low", "critical stock", "stockout risk"]):
        return "LOW_STOCK"
    if any(k in q for k in ["overstock", "overstocked", "excess inventory", "too much stock", "which are overstocked", "which products are overstocked", "products are overstocked", "items are overstocked"]):
        return "OVERSTOCK"
    if any(k in q for k in ["slow moving", "slow-moving", "slowest moving", "dead inventory"]):
        return "SLOW_MOVING"
    if any(k in q for k in ["inventory level", "stock level", "stock coverage", "days of stock", "today's inventory"]):
        return "INVENTORY_SNAPSHOT"

    # 13. Sales Improvement & Opportunity
    if any(k in q for k in [
        "improve sales", "improve the sales", "increase sales", "increase revenue", "improve revenue",
        "what can i do", "what should i do", "what should i focus", "where should i focus",
        "how to sell more", "sell more", "sales opportunities", "biggest opportunities", "biggest sales",
        "hurting sales", "losing sales", "products are declining", "declining products",
        "stores are underperforming", "underperforming stores", "focus on today", "what to do today",
        "recommendations to improve", "how can we increase", "how can i improve", "improve performance"
    ]):
        return "SALES_IMPROVEMENT"

    # 14. Causal / Why Analysis
    if any(k in q for k in ["why did", "why has", "why is", "reason for", "cause of", "what caused", "what is driving", "driving sales", "driving revenue", "why are", "what explains"]):
        return "CAUSAL_ANALYSIS"

    # 15. Seasonality
    if any(k in q for k in ["seasonality", "seasonal", "monthly pattern", "best month", "demand pattern"]):
        return "SEASONALITY"

    # 16. Comparisons
    if date_info.get("is_comparison") or "vs" in q or "compare" in q or "comparison" in q:
        if entities.get("matched_products"):
            return "PRODUCT_COMPARISON"
        if entities.get("store") or "store" in q or "stores" in q:
            return "STORE_COMPARISON"
        return "YEAR_COMPARISON"

    # 17. Top Categories
    if any(k in q for k in ["top category", "best category", "category performance", "categories", "which category", "sales by category", "by category"]):
        return "TOP_CATEGORIES"

    # 18. Store Performance Fallback
    if any(k in q for k in ["top store", "best store", "store performance", "which store", "which location", "sales by store", "by store", "stores performed"]):
        return "STORE_PERFORMANCE"

    # 19. Top Products (General Rankings)
    if any(k in q for k in [
        "top product", "best product", "best performer", "top performer", "best seller", "best-selling",
        "top skus", "worst performer", "worst product", "top 5 products", "top 10 products", "best sku",
        "performing product", "performing item", "best performing item", "best performing product"
    ]):
        return "TOP_PRODUCTS"

    # 20. Specific Product or Store Performance
    if entities.get("product") or entities.get("matched_products") or entities.get("unresolved_product"):
        if any(k in q for k in ["best", "top", "lead", "highest", "winner"]):
            return "TOP_PRODUCTS"
        if any(k in q for k in ["store", "stores", "which store"]):
            return "STORE_PERFORMANCE"
        return "PRODUCT_PERFORMANCE"

    # 21. Sales Trend
    if any(k in q for k in ["trend", "trajectory", "over time", "history", "historical", "last 10 years", "last 5 years", "grew", "changed"]):
        return "SALES_TREND"

    # 22. Dataset Metadata & Details
    if any(k in q for k in [
        "how many sales records", "how many sales transactions", "how many sales rows", "how many transactions",
        "how many sales records do i have", "how many sales do i have", "total sales records",
        "how many inventory records", "how many inventory rows", "how many inventory items", "number of inventory records",
        "total inventory records", "inventory records do i have", "what dataset", "which dataset", "active dataset",
        "active dataset name", "dataset metadata", "dataset details"
    ]):
        return "DATASET_METADATA"

    # 23. General Summary
    if any(k in q for k in ["summary", "overview", "business performing", "how are we doing", "general status"]):
        return "GENERAL_SUMMARY"

    # 24. Retail Intent Guard - verify presence of retail domain terms or resolved entities
    has_retail_intent = any(k in q for k in [
        "sale", "sales", "revenue", "unit", "units", "quantity", "inventory", "stock", "reorder",
        "store", "stores", "product", "products", "item", "items", "sku", "category", "categories",
        "performance", "performing", "growth", "trend", "spike", "drop", "critical", "warning",
        "overstock", "slow", "summary", "overview", "kpi", "metrics", "catalog", "catalogue", "today",
        "yesterday", "month", "year", "date", "money", "earned", "cost", "profit"
    ]) or bool(entities.get("matched_products") or entities.get("matched_store") or entities.get("matched_category"))

    if not has_retail_intent:
        return "CLARIFICATION_NEEDED"

    # 25. Default Sales Summary (only when retail context is present)
    return "SALES_SUMMARY"

def build_query_spec(question: str, override_store: Optional[str] = None, override_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Main Entrypoint: Builds validated QuerySpecification dictionary using QueryContext.
    Includes Entity Resolution, Data Grounding, and Diagnostic Logging.
    """
    global CONVERSATION_MEMORY

    q_clean = question.strip()
    date_info = parse_date_range(q_clean)
    entities = extract_entities(q_clean, override_store=override_store)

    # Store selector override from UI header (only if user did not explicitly mention a different store in query)
    if override_store and override_store.upper() != "ALL" and not entities.get("unresolved_store"):
        stores, _, _ = get_database_entities()
        for st in stores:
            if st["store_id"].lower() == override_store.lower():
                entities["store"] = st
                break

    intent = classify_intent(q_clean, entities, date_info)
    requires_cause = intent == "CAUSAL_ANALYSIS" or any(k in q_clean.lower() for k in ["why", "reason", "cause", "what caused", "what is driving", "what explains"])
    if requires_cause:
        intent = "CAUSAL_ANALYSIS"

    store_id = entities["store"]["store_id"] if entities.get("store") else "all"
    store_name = entities["store"]["store_name"] if entities.get("store") else "All Stores"

    # Check Date Range Records count for explicit date ranges
    grounding_state = entities["grounding_state"]
    missing_reason = entities["missing_reason"]
    suggested_actions = entities["suggested_actions"]

    if grounding_state == "DATA_FOUND":
        # Check if date range is completely empty
        s_date = date_info.get("start_date", get_db_date_bounds()[0])
        e_date = date_info.get("end_date", get_db_date_bounds()[1])
        cnt_row = query_one("SELECT COUNT(*) as cnt FROM sales WHERE date BETWEEN ? AND ?", (s_date, e_date))
        if cnt_row and cnt_row["cnt"] == 0:
            min_db, max_db = get_db_date_bounds()
            grounding_state = "NO_DATA"
            missing_reason = f"No sales records exist for the requested period ({s_date} to {e_date}) in the active dataset (supported range: {min_db} to {max_db})."
            suggested_actions = [f"Select a date range within {min_db} to {max_db}"]

    # Construct parsed_entities summary
    parsed_entities = {
        "matched_products": [p["product_name"] for p in entities.get("matched_products", [])],
        "unresolved_product": entities.get("unresolved_product"),
        "matched_store": entities.get("store", {}).get("store_name") if entities.get("store") else None,
        "unresolved_store": entities.get("unresolved_store"),
        "matched_category": entities.get("category"),
        "unresolved_category": entities.get("unresolved_category"),
        "date_range": f"{date_info.get('start_date')} to {date_info.get('end_date')} ({date_info.get('time_label')})"
    }

    # Construct canonical QueryContext
    ctx = QueryContext(
        raw_question=q_clean,
        intent=intent,
        metric=entities["metric"],
        entity_type=entities["entity_type"],
        grounding_state=grounding_state,
        unresolved_entities=[{"type": "product", "term": entities["unresolved_product"]}] if entities.get("unresolved_product") else ([] if not entities.get("unresolved_store") else [{"type": "store", "term": entities["unresolved_store"]}]),
        missing_reason=missing_reason,
        suggested_actions=suggested_actions,
        parsed_entities=parsed_entities,
        matched_products=entities["matched_products"],
        excluded_accessories=entities["excluded_accessories"],
        product=entities["product"],
        category=entities["category"],
        store_id=store_id,
        store_name=store_name,
        start_date=date_info.get("start_date", get_db_date_bounds()[0]),
        end_date=date_info.get("end_date", get_db_date_bounds()[1]),
        comparison_label=date_info.get("time_label"),
        limit=entities["limit"],
        requires_cause_analysis=requires_cause,
        chart_required=(grounding_state == "DATA_FOUND")
    )

    spec = ctx.to_dict()
    spec["raw_date_info"] = date_info
    spec["store"] = entities["store"]

    logger.info(f"[QUERY CONTEXT] Query: '{q_clean}' | Intent: {intent} | Grounding: {grounding_state} | Store: {store_name} | Scope: {date_info.get('time_label')}")

    return spec
