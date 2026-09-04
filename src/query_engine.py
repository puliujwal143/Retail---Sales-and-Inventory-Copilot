import re
import json
from typing import Dict, Any, List, Optional, Tuple
from src.database import query_all, query_one
from src.query_planner import build_query_spec, get_db_date_bounds
from src.analytics_engine import execute_query_spec
from src.response_engine import format_copilot_payload

def get_database_bounds() -> Tuple[str, str, int]:
    """Returns MIN(date), MAX(date), and total records count in sales table."""
    row = query_one("SELECT MIN(sales_date) as min_date, MAX(sales_date) as max_date, COUNT(*) as cnt FROM sales")
    if row and row["min_date"]:
        return row["min_date"], row["max_date"], row["cnt"]
    return "2016-01-01", "2026-09-03", 114515

def process_query_intent(user_query: str, store_id: Optional[str] = "all", target_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Universal Copilot Engine Entry Point:
    1. Builds structured QuerySpecification (Intent, Entities, Date Range, Store, Product, Category, Limit).
    2. Executes deterministic SQLite calculations via analytics_engine.
    3. Formats evidence, chart specs, and data scope via response_engine.
    """
    # 1. Build Query Specification via Query Planner
    spec = build_query_spec(user_query, override_store=store_id, override_date=target_date)

    # 2. Execute Deterministic Analytics Engine
    analytics_result = execute_query_spec(spec)

    # 3. Format Payload via Response Engine
    payload = format_copilot_payload(spec, analytics_result)
    return payload
