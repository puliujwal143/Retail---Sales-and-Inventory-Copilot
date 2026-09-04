import os
import json
import logging
from typing import Dict, Any

logger = logging.getLogger("retailiq.gemini")

SYSTEM_PROMPT = """You are a retail analytics assistant for a store manager running a small retail operation.

CRITICAL GROUNDING RULES:
1. Use ONLY the evidence supplied in the prompt context.
2. NEVER replace requested product family items with accessories (e.g., do NOT mention 'Laptop Bag' when explaining 'Laptop Computers' unless specifically asked).
3. Never invent sales, inventory, prices, products, stores, causes, or recommendations.
4. Do NOT perform business calculations if calculated values are already supplied by the system.
5. If the supplied evidence does not contain enough information to answer the question (e.g. asking why sales increased when no promotional or marketing data is in the evidence), EXPLICITLY state that the available data is insufficient to answer the cause.
6. Do NOT infer causes or external factors (promotions, weather, ads, competitors) that are not supported by the evidence.
7. Every factual statement must be supported by supplied figures.
8. Mention relevant system assumptions (e.g., 7-day target inventory coverage, 2-day critical threshold).
9. You are an explanation layer over a deterministic retail analytics system, NOT the source of truth.

You MUST respond strictly in valid JSON format with the following keys:
{
  "answer": "Clear, professional, natural-language explanation grounded in the evidence.",
  "key_metrics": [
    {"label": "Metric Name", "value": "Metric Value"}
  ],
  "recommendations": [
    "Actionable recommendation 1",
    "Actionable recommendation 2"
  ],
  "evidence": [
    {
      "product_name": "Product",
      "store_name": "Store",
      "revenue": 1000.0,
      "units_sold": 50,
      "source": "sales ledger"
    }
  ],
  "assumptions": [
    "Assumption 1"
  ],
  "data_sufficiency": "sufficient" or "insufficient"
}
"""

def generate_copilot_response(processed_query: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sends structured query payload to Gemini for natural-language explanation.
    Falls back gracefully to deterministic python response if Gemini key is absent or request fails.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    # If API key missing, immediately return deterministic fallback
    if not api_key:
        logger.info("GEMINI_API_KEY not found in environment. Using deterministic fallback engine.")
        return create_deterministic_fallback(processed_query, "Operating in Offline Deterministic Mode")

    # Prepare prompt context
    user_query = processed_query.get("user_query", "")
    intent = processed_query.get("intent", "")
    data_scope = processed_query.get("data_scope", "")
    data_sufficiency = processed_query.get("data_sufficiency", "sufficient")
    context_summary = processed_query.get("context_summary", "")
    evidence = processed_query.get("evidence", [])
    assumptions = processed_query.get("assumptions", [])
    metrics = processed_query.get("metrics", [])
    recommendations = processed_query.get("recommendations", [])
    chart = processed_query.get("chart", None)

    structured_ev = processed_query.get("structured_evidence", {})

    prompt_content = f"""USER QUESTION: "{user_query}"

CLASSIFIED INTENT: {intent}
DATA SCOPE: {data_scope}
SYSTEM DATA SUFFICIENCY: {data_sufficiency}
ANALYTICS SUMMARY: {context_summary}

STRUCTURED EVIDENCE TAXONOMY:
- FACTS: {json.dumps(structured_ev.get('facts', []), indent=2)}
- OBSERVATIONS: {json.dumps(structured_ev.get('observations', []), indent=2)}
- HYPOTHESES: {json.dumps(structured_ev.get('hypotheses', []), indent=2)}
- UNKNOWNS: {json.dumps(structured_ev.get('unknowns', []), indent=2)}

SUPPLIED CALCULATED METRICS:
{json.dumps(metrics, indent=2)}

SUPPLIED EVIDENCE:
{json.dumps(evidence, indent=2)}

SYSTEM ASSUMPTIONS:
{json.dumps(assumptions, indent=2)}

SUPPLIED DETERMINISTIC RECOMMENDATIONS:
{json.dumps(recommendations, indent=2)}

Remember: Respond ONLY with valid JSON following the schema. Directly answer the user's question first. Ground every statement in supplied numbers. If data sufficiency is 'insufficient', explicitly state what the data DOES show, what is UNKNOWN, and present hypotheses only as hypotheses, NOT facts.
"""

    # Attempt to call Gemini via google-genai SDK
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        # Try primary flash model, with fallbacks for lite model
        model_names = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-2.5-flash']
        raw_text = None
        last_err = None

        for model_name in model_names:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt_content,
                    config={
                        'system_instruction': SYSTEM_PROMPT,
                        'temperature': 0.1,
                        'response_mime_type': 'application/json'
                    }
                )
                raw_text = response.text
                if raw_text:
                    break
            except Exception as m_err:
                last_err = m_err
                continue

        if not raw_text:
            raise Exception(f"All Gemini model attempts failed. Last error: {last_err}")

        # Parse JSON output
        parsed_json = clean_and_parse_json(raw_text)
        if parsed_json:
            parsed_json.setdefault("data_sufficiency", data_sufficiency)
            parsed_json.setdefault("assumptions", assumptions)
            parsed_json.setdefault("evidence", evidence)
            parsed_json["data_scope"] = data_scope
            parsed_json["intent"] = intent
            parsed_json["chart"] = chart
            return parsed_json
        else:
            logger.warning("Gemini returned non-JSON string. Falling back to deterministic output.")
            return create_deterministic_fallback(processed_query, "Malformed LLM output received.")

    except Exception as e:
        logger.error(f"Gemini API request failed: {e}")
        return create_deterministic_fallback(processed_query, f"Gemini fallback mode ({str(e)})")

def clean_and_parse_json(text: str) -> Dict[str, Any]:
    """Cleans markdown code blocks and parses JSON safely."""
    try:
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"JSON parse error: {e}")
        return None

def create_deterministic_fallback(processed_query: Dict[str, Any], note: str = "") -> Dict[str, Any]:
    """
    Generates a 100% reliable, data-grounded answer when Gemini API is unavailable or returns invalid format.
    Ensures app NEVER crashes.
    """
    user_query = processed_query.get("user_query", "")
    intent = processed_query.get("intent", "")
    data_scope = processed_query.get("data_scope", "")
    data_sufficiency = processed_query.get("data_sufficiency", "sufficient")
    context_summary = processed_query.get("context_summary", "")
    evidence = processed_query.get("evidence", [])
    assumptions = processed_query.get("assumptions", [])
    metrics = processed_query.get("metrics", [])
    recommendations = processed_query.get("recommendations", [])
    chart = processed_query.get("chart", None)

    if processed_query.get("is_out_of_bounds") or "No sales records exist" in context_summary or "NO DATA" in context_summary:
        answer = context_summary
    elif data_sufficiency == "insufficient":
        answer = (
            f"Regarding '{user_query}': {context_summary} "
            f"The dataset contains sales transaction history and inventory stock levels, but does NOT contain "
            f"marketing campaigns, advertisements, price changes, or competitor data. Therefore, the specific root cause cannot be determined without inventing unverified facts."
        )
    else:
        answer = f"Analysis for query '{user_query}': {context_summary}"
        if recommendations:
            answer += f" Key action: {recommendations[0]}"

    if note:
        answer += f" ({note})"

    return {
        "intent": intent,
        "answer": answer,
        "data_scope": data_scope,
        "key_metrics": metrics,
        "recommendations": recommendations,
        "evidence": evidence,
        "assumptions": assumptions,
        "data_sufficiency": data_sufficiency,
        "chart": chart
    }
