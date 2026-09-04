"""
Chart Engine for RetailIQ AI Copilot.
Constructs structured JSON chart specifications from deterministic analytics outputs.
"""

from typing import Dict, Any, List

def build_chart_spec(chart_type: str, title: str, labels: List[str], datasets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Constructs a clean, safe chart specification dictionary.
    Guarantees no NaN, null, or undefined values in dataset arrays.
    """
    clean_labels = [str(lbl) for lbl in labels] if labels else []
    clean_datasets = []

    palette = ["#087F80", "#2B6CB0", "#f59e0b", "#ef4444", "#805AD5", "#319795", "#DD6B20"]

    for idx, ds in enumerate(datasets):
        raw_data = ds.get("data", [])
        clean_data = []
        for val in raw_data:
            if val is None or val != val:  # NaN check
                clean_data.append(0.0)
            elif isinstance(val, (int, float)):
                clean_data.append(float(val))
            else:
                try:
                    clean_data.append(float(val))
                except (ValueError, TypeError):
                    clean_data.append(0.0)

        clean_datasets.append({
            "label": ds.get("label", f"Series {idx+1}"),
            "data": clean_data,
            "color": ds.get("color", palette[idx % len(palette)])
        })

    return {
        "type": chart_type or "line",
        "title": title or "Analytics Chart",
        "labels": clean_labels,
        "datasets": clean_datasets
    }
