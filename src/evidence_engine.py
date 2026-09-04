"""
Evidence Classification Engine for RetailIQ AI Copilot.
Categorizes analytics outputs into FACTS, OBSERVATIONS, HYPOTHESES, and UNKNOWNS.
"""

from typing import Dict, Any, List

def build_structured_evidence(analytics_result: Dict[str, Any], query_spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Structures analytics findings into facts, observations, hypotheses, and unknowns.
    """
    intent = analytics_result.get("intent", query_spec.get("intent", "SALES_SUMMARY"))
    requires_cause = query_spec.get("requires_cause_analysis", False) or intent == "WHY_SALES_CHANGED"
    metrics = analytics_result.get("metrics", [])
    raw_data = analytics_result.get("raw_data", [])
    raw_evidence = analytics_result.get("evidence", [])

    facts = []
    observations = []
    hypotheses = []
    unknowns = []

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
        hypotheses.append("Potential unconfirmed drivers may include promotional campaigns, pricing adjustments, or external market demand.")
        unknowns.append("The database contains transaction sales history and stock levels, but does NOT contain marketing, advertisement, price-change, or competitor datasets.")
        unknowns.append("Root cause cannot be established without inventing unverified facts.")

    return {
        "facts": facts,
        "observations": observations,
        "hypotheses": hypotheses,
        "unknowns": unknowns
    }
