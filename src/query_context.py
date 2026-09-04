"""
Canonical QueryContext Data Structure for RetailIQ.
Encapsulates resolved query intent, entities, stores, date bounds, and comparison windows.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

@dataclass
class QueryContext:
    raw_question: str
    intent: str
    metric: str = "revenue"
    entity_type: str = "ALL_PRODUCTS"
    matched_products: List[Dict[str, Any]] = field(default_factory=list)
    excluded_accessories: List[Dict[str, Any]] = field(default_factory=list)
    product_family: Optional[str] = None
    product: Optional[Dict[str, Any]] = None
    category: Optional[str] = None
    store_id: str = "all"
    store_name: str = "All Stores"
    start_date: str = "2016-01-01"
    end_date: str = "2026-09-03"
    comparison_start_date: Optional[str] = None
    comparison_end_date: Optional[str] = None
    comparison_label: Optional[str] = None
    limit: int = 5
    requires_cause_analysis: bool = False
    chart_required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_question": self.raw_question,
            "intent": self.intent,
            "metric": self.metric,
            "entity_type": self.entity_type,
            "matched_products": self.matched_products,
            "excluded_accessories": self.excluded_accessories,
            "product_family": self.product_family,
            "product": self.product,
            "category": self.category,
            "store": {"store_id": self.store_id, "store_name": self.store_name} if self.store_id != "all" else None,
            "store_id": self.store_id,
            "store_name": self.store_name,
            "date_range": {
                "start_date": self.start_date,
                "end_date": self.end_date,
                "time_label": self.comparison_label or f"{self.start_date} to {self.end_date}",
                "comparison_start_date": self.comparison_start_date,
                "comparison_end_date": self.comparison_end_date,
                "comparison_label": self.comparison_label
            },
            "limit": self.limit,
            "requires_cause_analysis": self.requires_cause_analysis,
            "chart_required": self.chart_required
        }
