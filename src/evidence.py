from typing import Dict, List, Any

def create_evidence_item(
    product_name: str,
    store_name: str,
    current_stock: int,
    avg_daily_sales: float,
    days_remaining: float,
    sales_period: str = "Last 30 Days",
    units_sold: int = 0,
    source: str = "inventory + sales records"
) -> Dict[str, Any]:
    """Generates structured evidence dictionary for supporting figures."""
    return {
        "product_name": product_name,
        "store_name": store_name,
        "current_stock": current_stock,
        "avg_daily_sales": round(avg_daily_sales, 2),
        "days_remaining": round(days_remaining, 1),
        "units_sold": units_sold,
        "sales_period": sales_period,
        "source": source
    }

def format_evidence_summary(evidence_list: List[Dict[str, Any]]) -> str:
    """Formats evidence items into readable string block for prompt context."""
    if not evidence_list:
        return "No specific inventory/sales evidence items supplied."
    
    lines = []
    for idx, item in enumerate(evidence_list, 1):
        line = (
            f"Evidence Item #{idx}:\n"
            f"  - Product: {item.get('product_name')}\n"
            f"  - Store: {item.get('store_name')}\n"
            f"  - Current Stock: {item.get('current_stock')} units\n"
            f"  - Average Daily Sales: {item.get('avg_daily_sales')} units/day\n"
            f"  - Days Remaining: {item.get('days_remaining')} days\n"
            f"  - Sales (Period: {item.get('sales_period')}): {item.get('units_sold')} units\n"
            f"  - Data Source: {item.get('source')}"
        )
        lines.append(line)
    return "\n\n".join(lines)
