import re
import json
from typing import Dict, Any, List, Optional, Tuple
from src.database import query_all, query_one
from src.query_planner import build_query_spec, get_db_date_bounds
from src.analytics_engine import execute_query_spec
from src.response_engine import format_copilot_payload

def get_database_bounds() -> Tuple[Optional[str], Optional[str], int]:
    """Returns MIN(date), MAX(date), and total records count in sales table."""
    from src.dataset_manager import ActiveDatasetManager
    if ActiveDatasetManager.get_active_dataset_id() is None:
        return None, None, 0
    row = query_one("SELECT MIN(date) as min_date, MAX(date) as max_date, COUNT(*) as cnt FROM sales")
    if row and row["min_date"]:
        return str(row["min_date"]), str(row["max_date"]), int(row["cnt"])
    return None, None, 0

def process_query_intent(user_query: str, store_id: Optional[str] = "all", target_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Universal Copilot Engine Entry Point:
    1. Checks if active dataset is present. If None, returns grounded NO_DATA response.
    2. Builds structured QuerySpecification (Intent, Entities, Date Range, Store, Product, Category, Limit).
    3. Executes deterministic SQLite calculations via analytics_engine.
    4. Formats evidence, chart specs, and data scope via response_engine.
    5. Emits detailed QUERY DEBUG trace log.
    """
    from src.dataset_manager import ActiveDatasetManager
    if ActiveDatasetManager.get_active_dataset_id() is None:
        return {
            "intent": "NO_DATA",
            "grounding_state": "NO_DATA",
            "answer": "I don't have an active retail dataset yet. Please upload your sales, inventory, product, and store data in Data Management so I can analyze it.",
            "data_scope": "No Dataset Active (0 stores, 0 SKUs, 0 sales records)",
            "key_metrics": [],
            "recommendations": ["Go to Data Management to upload your retail data or load the demo dataset."],
            "evidence": [],
            "assumptions": ["System is in empty state awaiting user dataset upload."],
            "data_sufficiency": "insufficient",
            "chart": None,
            "confidence": 1.0
        }

    # 1. Build Query Specification via Query Planner
    spec = build_query_spec(user_query, override_store=store_id, override_date=target_date)

    # 2. Execute Deterministic Analytics Engine
    analytics_result = execute_query_spec(spec)

    # 3. Format Payload via Response Engine
    payload = format_copilot_payload(spec, analytics_result)

    # 4. QUERY DEBUG LOGGING (Requirement 16)
    parsed_entities = spec.get("parsed_entities", {})
    grounding_state = spec.get("grounding_state", "DATA_FOUND")
    unresolved = spec.get("unresolved_entities", [])
    missing_reason = spec.get("missing_reason", "")
    
    raw_d = analytics_result.get("raw_data", [])
    if isinstance(raw_d, list):
        record_count = len(raw_d)
    elif isinstance(raw_d, dict):
        record_count = len(raw_d.get("sku_drivers", raw_d.get("growth_skus", [])))
    else:
        record_count = len(analytics_result.get("evidence", []))

    metrics = analytics_result.get("metrics", [])
    context_summary = str(analytics_result.get("context_summary", ""))
    final_response = str(payload.get("answer", ""))

    try:
        print("\n" + "="*60)
        print("RETAILIQ AI GROUNDING PIPELINE TRACE")
        print("="*60)
        print(f"User Query            : {user_query}")
        print(f"-> Parsed Entities    : {parsed_entities}")
        print(f"-> Entity Validation  : State={grounding_state} | Unresolved={unresolved} | Reason={missing_reason}")
        print(f"-> Filtered Records   : {record_count} record(s)")
        print(f"-> Calculated Metrics : {metrics}")
        try:
            print(f"-> AI Context         : {context_summary}")
            print(f"-> Final Response     : {final_response}")
        except UnicodeEncodeError:
            print(f"-> AI Context         : {context_summary.encode('ascii', 'ignore').decode('ascii')}")
            print(f"-> Final Response     : {final_response.encode('ascii', 'ignore').decode('ascii')}")
        print("="*60 + "\n")
    except Exception as log_err:
        pass

    return payload
