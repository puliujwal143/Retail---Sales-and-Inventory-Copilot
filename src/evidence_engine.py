"""
Evidence Classification Engine for RetailIQ AI Copilot.
Categorizes analytics outputs into FACTS, OBSERVATIONS, HYPOTHESES, and UNKNOWNS.
"""

from typing import Dict, Any, List

def build_structured_evidence(analytics_result: Dict[str, Any], query_spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Structures analytics findings into FACTS, OBSERVATIONS, HYPOTHESES (POSSIBLE DRIVERS), and UNKNOWNS.
    """
    intent = analytics_result.get("intent", query_spec.get("intent", "SALES_SUMMARY"))
    requires_cause = query_spec.get("requires_cause_analysis", False) or intent in ["WHY_SALES_CHANGED", "CAUSAL_ANALYSIS"]
    metrics = analytics_result.get("metrics", [])
    raw_data = analytics_result.get("raw_data", [])
    raw_evidence = analytics_result.get("evidence", [])

    facts = []
    observations = []
    hypotheses = []
    unknowns = []

    # Check if raw_data is a dict containing structured taxonomy from run_driver_analysis
    if isinstance(raw_data, dict) and "confirmed_facts" in raw_data:
        facts = raw_data.get("confirmed_facts", [])
        observations = raw_data.get("observed_patterns", [])
        hypotheses = raw_data.get("possible_drivers", [])
        unknowns = raw_data.get("unknowns", [])
        return {
            "facts": facts,
            "observations": observations,
            "hypotheses": hypotheses,
            "unknowns": unknowns
        }

    # 1. FACTS (Calculated numbers directly from SQLite)
    for m in metrics:
        if isinstance(m, dict) and "label" in m and "value" in m:
            facts.append(f"{m['label']}: {m['value']}")

    if not facts and raw_evidence:
        for item in raw_evidence[:4]:
            if isinstance(item, dict) and "revenue" in item and "units_sold" in item:
                facts.append(f"{item.get('product_name', 'Item')}: ${item['revenue']:,.2f} ({item['units_sold']:,} units)")

    # 2. OBSERVATIONS (Identified co-occurring patterns in dataset)
    if isinstance(raw_data, list) and len(raw_data) >= 2:
        if "revenue" in raw_data[0] and "revenue" in raw_data[-1]:
            rev_start = raw_data[0]["revenue"]
            rev_end = raw_data[-1]["revenue"]
            if isinstance(rev_start, (int, float)) and isinstance(rev_end, (int, float)) and rev_start > 0:
                pct = ((rev_end - rev_start) / rev_start) * 100.0
                observations.append(f"Revenue changed by {pct:+.1f}% from initial period (${rev_start:,.2f}) to final period (${rev_end:,.2f}).")
        if len(raw_data) > 3:
            observations.append(f"Sales trajectory evaluated across {len(raw_data)} consecutive recording periods.")

    # 3. HYPOTHESES & UNKNOWNS (Triggered for Causal / Why Queries)
    if requires_cause:
        hypotheses.append("Potential co-occurring drivers may include stock availability, velocity shifts, or store demand changes.")
        unknowns.append("The database contains transaction sales history and stock levels, but does NOT contain marketing campaigns, advertisements, pricing changes, or competitor datasets.")
        unknowns.append("External root causes cannot be established without inventing unverified facts.")

    return {
        "facts": facts,
        "observations": observations,
        "hypotheses": hypotheses,
        "unknowns": unknowns
    }
