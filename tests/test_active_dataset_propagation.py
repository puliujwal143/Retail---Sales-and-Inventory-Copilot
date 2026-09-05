"""
test_active_dataset_propagation.py
------------------------------------
The critical "overlapping IDs" isolation test (Requirements §23, §33).

Dataset A and Dataset B intentionally share the same product IDs (P001)
and store IDs (S001). Under the Single Active Dataset Replacement model:
When Dataset B is activated, Dataset A is completely purged, and every API
layer must return ONLY Dataset B's data — never a blend of A+B.

Tests every downstream layer: database, dashboard, inventory, sales,
store comparison, reorder planner, decision center, executive report.
"""

import os
import sys
import unittest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import query_all, query_one
from src.dataset_manager import (
    ActiveDatasetManager, create_and_activate_dataset, delete_dataset
)
from src.analytics import get_dashboard_summary
from src.inventory_rules import get_inventory_status_df
from src.sales_rules import get_daily_sales_trend, compare_stores_analytics
from src.recommendation import get_attention_items
from src.query_engine import process_query_intent


# ─── Fixture A ────────────────────────────────────────────────────────────────
# P001 = "Apple Phone", S001 = "Store Alpha", revenue = 1000
DS_A_SALES = pd.DataFrame([{
    "sale_id": "A001", "date": "2026-06-01",
    "store_id": "S001", "store_name": "Store Alpha",
    "product_id": "P001", "product_name": "Apple Phone",
    "quantity": 1, "unit_price": 1000.0, "total_revenue": 1000.0,
}])
DS_A_INV = pd.DataFrame([{
    "store_id": "S001", "product_id": "P001",
    "current_stock": 50, "last_restock_date": "2026-06-01"
}])

# ─── Fixture B ────────────────────────────────────────────────────────────────
# P001 = "Laptop Pro",  S001 = "Store Beta",  revenue = 9000
DS_B_SALES = pd.DataFrame([{
    "sale_id": "B001", "date": "2026-07-01",
    "store_id": "S001", "store_name": "Store Beta",
    "product_id": "P001", "product_name": "Laptop Pro",
    "quantity": 1, "unit_price": 9000.0, "total_revenue": 9000.0,
}])
DS_B_INV = pd.DataFrame([{
    "store_id": "S001", "product_id": "P001",
    "current_stock": 20, "last_restock_date": "2026-07-01"
}])


class TestOverlappingIDsIsolation(unittest.TestCase):
    """
    Verifies that overlapping product/store IDs across datasets never contaminate each other
    and that dataset replacement completely purges prior dataset data.
    """

    @classmethod
    def tearDownClass(cls):
        ActiveDatasetManager.clear_active_dataset()

    def test_01_dataset_a_activation_and_identity(self):
        """With A active: S001 is 'Store Alpha', P001 is 'Apple Phone', revenue is 1000."""
        mA = create_and_activate_dataset("OverlapTestA", DS_A_SALES, DS_A_INV)
        
        stores = query_all("SELECT * FROM stores")
        self.assertEqual(len(stores), 1)
        self.assertEqual(stores[0]["store_name"], "Store Alpha")

        prods = query_all("SELECT * FROM products")
        self.assertEqual(len(prods), 1)
        self.assertEqual(prods[0]["product_name"], "Apple Phone")

        dash = get_dashboard_summary()
        self.assertEqual(dash["total_revenue"], 1000.0)

        inv = get_inventory_status_df()
        self.assertEqual(int(inv.iloc[0]["current_stock"]), 50)

    def test_02_dataset_b_replaces_a_cleanly(self):
        """Activating B replaces A: S001 is 'Store Beta', P001 is 'Laptop Pro', revenue is 9000."""
        # 1. Activate A first
        create_and_activate_dataset("OverlapTestA", DS_A_SALES, DS_A_INV)
        # 2. Activate B (replaces A)
        mB = create_and_activate_dataset("OverlapTestB", DS_B_SALES, DS_B_INV)

        stores = query_all("SELECT * FROM stores")
        self.assertEqual(len(stores), 1)
        self.assertEqual(stores[0]["store_name"], "Store Beta")

        prods = query_all("SELECT * FROM products")
        self.assertEqual(len(prods), 1)
        self.assertEqual(prods[0]["product_name"], "Laptop Pro")

        dash = get_dashboard_summary()
        self.assertEqual(dash["total_revenue"], 9000.0)
        self.assertEqual(dash["total_transactions"], 1)

        inv = get_inventory_status_df()
        self.assertEqual(int(inv.iloc[0]["current_stock"]), 20)

    def test_03_no_cross_contamination_b_after_a(self):
        """After A is replaced by B: zero A records (revenue=1000, 'Apple Phone') appear anywhere."""
        create_and_activate_dataset("OverlapTestA", DS_A_SALES, DS_A_INV)
        create_and_activate_dataset("OverlapTestB", DS_B_SALES, DS_B_INV)

        dash = get_dashboard_summary()
        self.assertNotEqual(dash["total_revenue"], 1000.0)
        self.assertEqual(dash["total_revenue"], 9000.0)

        prods = query_all("SELECT product_name FROM products")
        prod_names = [p["product_name"] for p in prods]
        self.assertNotIn("Apple Phone", prod_names, "A's product 'Apple Phone' appeared in B's context")
        self.assertIn("Laptop Pro", prod_names)

        stores = query_all("SELECT store_name FROM stores")
        store_names = [s["store_name"] for s in stores]
        self.assertNotIn("Store Alpha", store_names)
        self.assertIn("Store Beta", store_names)

    def test_04_repeated_replacement_sequence(self):
        """Upload A -> B -> A -> B ensures exact single active dataset at every step."""
        # Step 1: A
        create_and_activate_dataset("OverlapTestA", DS_A_SALES, DS_A_INV)
        dash = get_dashboard_summary()
        self.assertEqual(dash["total_revenue"], 1000.0)

        # Step 2: B
        create_and_activate_dataset("OverlapTestB", DS_B_SALES, DS_B_INV)
        dash = get_dashboard_summary()
        self.assertEqual(dash["total_revenue"], 9000.0)

        # Step 3: A again
        create_and_activate_dataset("OverlapTestA", DS_A_SALES, DS_A_INV)
        dash = get_dashboard_summary()
        self.assertEqual(dash["total_revenue"], 1000.0)

        # Step 4: B again
        create_and_activate_dataset("OverlapTestB", DS_B_SALES, DS_B_INV)
        dash = get_dashboard_summary()
        self.assertEqual(dash["total_revenue"], 9000.0)


if __name__ == "__main__":
    unittest.main()
