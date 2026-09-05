"""
test_dataset_lifecycle.py
--------------------------
Tests the full lifecycle of datasets in the Single Active Dataset Replacement Model:
- Fresh NO_DATA state produces zero analytics
- Every upload creates a distinct UUID-based dataset_id
- Previous dataset is removed from storage when a new dataset is uploaded and activated
- Deletion works correctly (file + metadata removed)
- Deleting the active dataset transitions to NO_DATA (never auto-activates demo)
- Demo cannot be deleted
- NO_DATA never auto-falls back to Demo
"""

import os
import sys
import unittest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import query_all, query_one
from src.dataset_manager import (
    ActiveDatasetManager, create_and_activate_dataset, delete_dataset,
    DATASETS_DIR
)
from src.analytics import get_dashboard_summary
from src.inventory_rules import get_inventory_status_df


def _minimal_sales(n_stores=1, n_products=1, prefix="T"):
    """Builds a tiny but valid sales DataFrame for testing."""
    rows = []
    for s in range(n_stores):
        for p in range(n_products):
            rows.append({
                "sale_id":      f"{prefix}_{s}_{p}",
                "date":         "2026-07-01",
                "store_id":     f"TS{s+1:02d}",
                "store_name":   f"Test Store {s+1}",
                "product_id":   f"TP{p+1:02d}",
                "product_name": f"Test Product {p+1}",
                "quantity":     10,
                "unit_price":   100.0,
                "total_revenue":1000.0,
            })
    return pd.DataFrame(rows)


class TestDatasetLifecycle(unittest.TestCase):

    def setUp(self):
        ActiveDatasetManager.clear_active_dataset()

    def tearDown(self):
        ActiveDatasetManager.clear_active_dataset()

    # ─── NO_DATA state ──────────────────────────────────────────────────────
    def test_fresh_state_is_no_data(self):
        """After clear_active_dataset(), all analytics must return empty/zero."""
        ActiveDatasetManager.clear_active_dataset()
        self.assertIsNone(ActiveDatasetManager.get_active_dataset_id())

        active = ActiveDatasetManager.get_active_dataset()
        self.assertEqual(active["status"], "NO_DATA")
        self.assertEqual(active["store_count"], 0)
        self.assertEqual(active["product_count"], 0)

        # Dashboard must return zeros
        dash = get_dashboard_summary()
        self.assertEqual(dash["total_revenue"], 0.0)
        self.assertEqual(dash["total_transactions"], 0)

        # Inventory must return empty
        inv_df = get_inventory_status_df()
        self.assertTrue(inv_df.empty)

        # /api/stores equivalent
        stores = query_all("SELECT * FROM stores")
        self.assertEqual(stores, [])

    # ─── Unique dataset IDs ──────────────────────────────────────────────────
    def test_upload_creates_unique_dataset(self):
        """Two uploads must produce two distinct ds_ UUIDs."""
        df = _minimal_sales(1, 2, "UQ")
        m1 = create_and_activate_dataset("UniqueTest1", df)
        m2 = create_and_activate_dataset("UniqueTest2", df)

        self.assertNotEqual(m1["dataset_id"], m2["dataset_id"])
        self.assertTrue(m1["dataset_id"].startswith("ds_"))
        self.assertTrue(m2["dataset_id"].startswith("ds_"))

    # ─── Previous dataset removed on new upload ─────────────────────────────
    def test_previous_dataset_removed_on_new_upload(self):
        """Under the Single Active Dataset Replacement Model, uploading B deletes A."""
        dfA = _minimal_sales(2, 3, "A")
        mA  = create_and_activate_dataset("DatasetA_lifecycle", dfA)
        pathA = os.path.join(DATASETS_DIR, f"{mA['dataset_id']}.sqlite")
        self.assertTrue(os.path.exists(pathA))

        # Now upload B (this activates B and removes A)
        dfB = _minimal_sales(4, 5, "B")
        mB  = create_and_activate_dataset("DatasetB_lifecycle", dfB)
        pathB = os.path.join(DATASETS_DIR, f"{mB['dataset_id']}.sqlite")

        # A's file must be deleted from storage
        self.assertFalse(os.path.exists(pathA), "Dataset A SQLite file must be removed when B is activated")
        # B's file must exist and be active
        self.assertTrue(os.path.exists(pathB))
        self.assertEqual(ActiveDatasetManager.get_active_dataset_id(), mB["dataset_id"])

    # ─── Repeated replacement A -> B -> C ───────────────────────────────────
    def test_repeated_replacement_lifecycle(self):
        """Repeated uploads ensure only the current active dataset is retained."""
        dfA = _minimal_sales(1, 1, "SA")
        dfB = _minimal_sales(2, 2, "SB")
        dfC = _minimal_sales(3, 3, "SC")

        mA = create_and_activate_dataset("DatasetA", dfA)
        pathA = os.path.join(DATASETS_DIR, f"{mA['dataset_id']}.sqlite")
        self.assertTrue(os.path.exists(pathA))

        mB = create_and_activate_dataset("DatasetB", dfB)
        pathB = os.path.join(DATASETS_DIR, f"{mB['dataset_id']}.sqlite")
        self.assertFalse(os.path.exists(pathA))
        self.assertTrue(os.path.exists(pathB))

        mC = create_and_activate_dataset("DatasetC", dfC)
        pathC = os.path.join(DATASETS_DIR, f"{mC['dataset_id']}.sqlite")
        self.assertFalse(os.path.exists(pathB))
        self.assertTrue(os.path.exists(pathC))
        self.assertEqual(ActiveDatasetManager.get_active_dataset_id(), mC["dataset_id"])

    # ─── Delete active dataset → NO_DATA ─────────────────────────────────────
    def test_delete_active_dataset_goes_to_no_data(self):
        """Deleting the currently active dataset must transition to NO_DATA, never Demo."""
        df = _minimal_sales(1, 1, "DAD")
        m  = create_and_activate_dataset("DeleteActiveTest", df)
        self.assertEqual(ActiveDatasetManager.get_active_dataset_id(), m["dataset_id"])

        delete_dataset(m["dataset_id"])

        active_id = ActiveDatasetManager.get_active_dataset_id()
        self.assertIsNone(active_id, f"Expected NO_DATA (None) after deleting active dataset, got '{active_id}'")

        active_meta = ActiveDatasetManager.get_active_dataset()
        self.assertEqual(active_meta["status"], "NO_DATA")
        self.assertNotEqual(active_id, "demo")

    # ─── Demo cannot be deleted ──────────────────────────────────────────────
    def test_demo_cannot_be_deleted(self):
        """Attempting to delete 'demo' must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            delete_dataset("demo")
        self.assertIn("demo", str(ctx.exception).lower())

    # ─── NO_DATA never auto-activates Demo ──────────────────────────────────
    def test_no_demo_fallback(self):
        """NO_DATA state must never automatically activate the demo dataset."""
        ActiveDatasetManager.clear_active_dataset()

        active_id = ActiveDatasetManager.get_active_dataset_id()
        self.assertIsNone(active_id, "NO_DATA state auto-activated a dataset (expected None)")

        # Query stores — must return empty list (from empty.sqlite), not demo data
        stores = query_all("SELECT * FROM stores")
        self.assertEqual(stores, [], f"NO_DATA returned stores from another dataset: {stores[:3]}")

        # Dashboard must not contain demo revenue
        dash = get_dashboard_summary()
        self.assertEqual(dash["total_revenue"], 0.0)


if __name__ == "__main__":
    unittest.main()
