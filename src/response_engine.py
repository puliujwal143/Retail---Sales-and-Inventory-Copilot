"""
Universal Response Engine for RetailIQ AI Copilot.
Formats deterministic analytics, query specs, evidence, and chart objects into standardized responses.
Integrates Evidence Engine taxonomy and Self-Checking Validation.
"""

from typing import Dict, Any, List
from src.chart_engine import build_chart_spec
from src.evidence_engine import build_structured_evidence
from src.validation import validate_and_enrich_payload

def format_copilot_payload(spec: Dict[str, Any], analytics_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Combines QuerySpecification, Deterministic Analytics, Structured Evidence, and Validation into response format.
    """
    chart_raw = analytics_result.get("chart_data", None)
    chart_spec = None
    if chart_raw and isinstance(chart_raw, dict):
        chart_spec = build_chart_spec(
            chart_type=chart_raw.get("type", "line"),
            title=chart_raw.get("title", "Analytics Chart"),
            labels=chart_raw.get("labels", []),
            datasets=chart_raw.get("datasets", [])
        )

    evidence_items = analytics_result.get("evidence", [])
    formatted_evidence = []
    for e in evidence_items:
        if isinstance(e, dict):
            formatted_evidence.append(e)
        else:
            formatted_evidence.append({"description": str(e), "source": "system ledger"})

    structured_evidence = build_structured_evidence(analytics_result, spec)

    raw_payload = {
        "intent": analytics_result.get("intent", spec.get("intent", "SALES_SUMMARY")),
        "user_query": spec.get("raw_question", ""),
        "grounding_state": analytics_result.get("grounding_state") or spec.get("grounding_state", "DATA_FOUND"),
        "data_scope": analytics_result.get("data_scope", "Date Scope: Full Dataset • Scope: All Stores"),
        "data_sufficiency": analytics_result.get("data_sufficiency", "sufficient"),
        "context_summary": analytics_result.get("context_summary", ""),
        "metrics": analytics_result.get("metrics", []),
        "recommendations": analytics_result.get("recommendations", []),
        "evidence": formatted_evidence,
        "structured_evidence": structured_evidence,
        "assumptions": analytics_result.get("assumptions", [
            "Target inventory coverage = 7 days",
            "Critical stockout threshold = 2 days"
        ]),
        "chart": chart_spec,
        "raw_data": analytics_result.get("raw_data", [])
    }

    # Execute self-checking validation & enrichment
    final_payload = validate_and_enrich_payload(spec, analytics_result, raw_payload)
    return final_payload
