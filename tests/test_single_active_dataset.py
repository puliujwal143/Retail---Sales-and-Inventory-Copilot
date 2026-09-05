"""
RetailIQ — Comprehensive Single Active Dataset Replacement Model Test Suite.
Verifies all 21 core requirements specified in the Single Active Dataset Replacement specification.
"""

import os
import unittest
import pandas as pd
import sqlite3
from fastapi.testclient import TestClient

from app import app
from src.dataset_manager import (
    ActiveDatasetManager,
    create_and_activate_dataset,
    get_active_dataset_id,
    get_active_dataset_db_path,
    DATASETS_DIR
)
from src.database import query_all, query_one
from src.analytics import get_dashboard_summary
from src.inventory_rules import get_inventory_status_df
from src.query_planner import CONVERSATION_MEMORY


class TestSingleActiveDatasetReplacement(unittest.TestCase):
    """
    Automated Test Suite for RetailIQ Single Active Dataset Replacement Model.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Fixture A: 1 Store, 2 Products, 2 Sales (Revenue: 1,111)
        cls.sales_a = pd.DataFrame([
            {"sale_id": "SA1", "date": "2026-08-01", "store_id": "STA", "product_id": "PA1", "quantity": 1, "unit_price": 1000.0, "total_revenue": 1000.0},
            {"sale_id": "SA2", "date": "2026-08-02", "store_id": "STA", "product_id": "PA2", "quantity": 1, "unit_price": 111.0, "total_revenue": 111.0}
        ])
        cls.inv_a = pd.DataFrame([
            {"store_id": "STA", "product_id": "PA1", "current_stock": 50, "last_restock_date": "2026-08-02"},
            {"store_id": "STA", "product_id": "PA2", "current_stock": 20, "last_restock_date": "2026-08-02"}
        ])
        cls.prods_a = pd.DataFrame([
            {"product_id": "PA1", "product_name": "Product Alpha One", "category": "Computers", "unit_price": 1000.0, "cost_price": 600.0, "reorder_point": 10},
            {"product_id": "PA2", "product_name": "Product Alpha Two", "category": "Audio", "unit_price": 111.0, "cost_price": 60.0, "reorder_point": 5}
        ])
        cls.stores_a = pd.DataFrame([
            {"store_id": "STA", "store_name": "Alpha Flagship Store", "location": "Sector Alpha", "square_feet": 10000, "opening_date": "2020-01-01"}
        ])

        # Fixture B: 2 Stores, 3 Products, 3 Sales (Revenue: 9,999)
        cls.sales_b = pd.DataFrame([
            {"sale_id": "SB1", "date": "2026-09-01", "store_id": "STB1", "product_id": "PB1", "quantity": 2, "unit_price": 4000.0, "total_revenue": 8000.0},
            {"sale_id": "SB2", "date": "2026-09-02", "store_id": "STB1", "product_id": "PB2", "quantity": 1, "unit_price": 1000.0, "total_revenue": 1000.0},
            {"sale_id": "SB3", "date": "2026-09-03", "store_id": "STB2", "product_id": "PB3", "quantity": 1, "unit_price": 999.0, "total_revenue": 999.0}
        ])
        cls.inv_b = pd.DataFrame([
            {"store_id": "STB1", "product_id": "PB1", "current_stock": 100, "last_restock_date": "2026-09-03"},
            {"store_id": "STB1", "product_id": "PB2", "current_stock": 40, "last_restock_date": "2026-09-03"},
            {"store_id": "STB2", "product_id": "PB3", "current_stock": 30, "last_restock_date": "2026-09-03"}
        ])
        cls.prods_b = pd.DataFrame([
            {"product_id": "PB1", "product_name": "Beta Premium Laptop", "category": "Computers", "unit_price": 4000.0, "cost_price": 2500.0, "reorder_point": 20},
            {"product_id": "PB2", "product_name": "Beta Noise Headphones", "category": "Audio", "unit_price": 1000.0, "cost_price": 500.0, "reorder_point": 10},
            {"product_id": "PB3", "product_name": "Beta Smart Watch", "category": "Wearables", "unit_price": 999.0, "cost_price": 500.0, "reorder_point": 10}
        ])
        cls.stores_b = pd.DataFrame([
            {"store_id": "STB1", "store_name": "Beta Downtown Store", "location": "Sector Beta 1", "square_feet": 12000, "opening_date": "2021-01-01"},
            {"store_id": "STB2", "store_name": "Beta Uptown Mall", "location": "Sector Beta 2", "square_feet": 8000, "opening_date": "2022-01-01"}
        ])

        # Fixture C: 1 Store, 1 Product, 1 Sale (Revenue: 555)
        cls.sales_c = pd.DataFrame([
            {"sale_id": "SC1", "date": "2026-09-05", "store_id": "STC", "product_id": "PC1", "quantity": 1, "unit_price": 555.0, "total_revenue": 555.0}
        ])
        cls.inv_c = pd.DataFrame([
            {"store_id": "STC", "product_id": "PC1", "current_stock": 15, "last_restock_date": "2026-09-05"}
        ])
        cls.prods_c = pd.DataFrame([
            {"product_id": "PC1", "product_name": "Gamma Smart Speaker", "category": "Audio", "unit_price": 555.0, "cost_price": 300.0, "reorder_point": 5}
        ])
        cls.stores_c = pd.DataFrame([
            {"store_id": "STC", "store_name": "Gamma Express", "location": "Sector Gamma", "square_feet": 5000, "opening_date": "2023-01-01"}
        ])

    def setUp(self):
        # Reset to NO_DATA state before each test
        ActiveDatasetManager.clear_active_dataset()

    def tearDown(self):
        # Clean up after test
        ActiveDatasetManager.clear_active_dataset()

    def test_first_start_no_data(self):
        """1. Fresh start must be NO_DATA with active_dataset_id = None."""
        ActiveDatasetManager.clear_active_dataset()
        active_id = get_active_dataset_id()
        self.assertIsNone(active_id)

        meta = ActiveDatasetManager.get_active_dataset()
        self.assertEqual(meta["status"], "NO_DATA")
        self.assertEqual(meta["store_count"], 0)
        self.assertEqual(meta["product_count"], 0)
        self.assertEqual(meta["sales_count"], 0)

        # Verify dashboard API returns 0 / no_data
        res = self.client.get("/api/dashboard")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("total_revenue", 0), 0.0)

    def test_upload_a(self):
        """2. Upload Dataset A makes Dataset A active."""
        meta_a = create_and_activate_dataset("Dataset A", self.sales_a, self.inv_a, self.prods_a, self.stores_a)
        active_id = get_active_dataset_id()
        self.assertEqual(active_id, meta_a["dataset_id"])
        self.assertEqual(meta_a["store_count"], 1)
        self.assertEqual(meta_a["product_count"], 2)
        self.assertEqual(meta_a["total_revenue"], 1111.0)

        # File exists
        db_path = get_active_dataset_db_path()
        self.assertTrue(os.path.exists(db_path))

    def test_upload_b_replaces_a(self):
        """3. Upload Dataset B removes Dataset A and activates B."""
        meta_a = create_and_activate_dataset("Dataset A", self.sales_a, self.inv_a, self.prods_a, self.stores_a)
        id_a = meta_a["dataset_id"]
        file_a = os.path.join(DATASETS_DIR, f"{id_a}.sqlite")
        self.assertTrue(os.path.exists(file_a))

        # Upload B
        meta_b = create_and_activate_dataset("Dataset B", self.sales_b, self.inv_b, self.prods_b, self.stores_b)
        id_b = meta_b["dataset_id"]
        file_b = os.path.join(DATASETS_DIR, f"{id_b}.sqlite")

        # Dataset A must be removed from disk
        self.assertFalse(os.path.exists(file_a), "Old dataset A SQLite file was not removed upon B activation")
        # Dataset B must be active
        self.assertTrue(os.path.exists(file_b))
        self.assertEqual(get_active_dataset_id(), id_b)

    def test_upload_c_replaces_b(self):
        """4. Upload Dataset C removes Dataset B and activates C."""
        meta_b = create_and_activate_dataset("Dataset B", self.sales_b, self.inv_b, self.prods_b, self.stores_b)
        id_b = meta_b["dataset_id"]
        file_b = os.path.join(DATASETS_DIR, f"{id_b}.sqlite")
        self.assertTrue(os.path.exists(file_b))

        # Upload C
        meta_c = create_and_activate_dataset("Dataset C", self.sales_c, self.inv_c, self.prods_c, self.stores_c)
        id_c = meta_c["dataset_id"]
        file_c = os.path.join(DATASETS_DIR, f"{id_c}.sqlite")

        self.assertFalse(os.path.exists(file_b))
        self.assertTrue(os.path.exists(file_c))
        self.assertEqual(get_active_dataset_id(), id_c)

    def test_old_database_removed(self):
        """5. Verify old active SQLite database file is purged upon replacement."""
        meta_a = create_and_activate_dataset("Dataset A", self.sales_a, self.inv_a, self.prods_a, self.stores_a)
        file_a = os.path.join(DATASETS_DIR, f"{meta_a['dataset_id']}.sqlite")
        self.assertTrue(os.path.exists(file_a))

        create_and_activate_dataset("Dataset B", self.sales_b, self.inv_b, self.prods_b, self.stores_b)
        self.assertFalse(os.path.exists(file_a))

    def test_old_data_not_visible(self):
        """6. After B activation, old data A (names, products, stores, revenue) must not be visible anywhere."""
        create_and_activate_dataset("Dataset A", self.sales_a, self.inv_a, self.prods_a, self.stores_a)
        create_and_activate_dataset("Dataset B", self.sales_b, self.inv_b, self.prods_b, self.stores_b)

        # Check products in active DB
        products = query_all("SELECT product_name FROM products")
        product_names = [p["product_name"] for p in products]
        self.assertNotIn("Product Alpha One", product_names)
        self.assertNotIn("Product Alpha Two", product_names)
        self.assertIn("Beta Premium Laptop", product_names)

        # Check stores in active DB
        stores = query_all("SELECT store_name FROM stores")
        store_names = [s["store_name"] for s in stores]
        self.assertNotIn("Alpha Flagship Store", store_names)
        self.assertIn("Beta Downtown Store", store_names)

        # Check revenue
        sales_row = query_one("SELECT SUM(total_revenue) as rev FROM sales")
        self.assertEqual(sales_row["rev"], 9999.0)

    def test_invalid_upload_preserves_current(self):
        """7. Invalid upload preserves currently active dataset intact."""
        meta_a = create_and_activate_dataset("Dataset A", self.sales_a, self.inv_a, self.prods_a, self.stores_a)
        id_a = meta_a["dataset_id"]
        file_a = os.path.join(DATASETS_DIR, f"{id_a}.sqlite")

        # Invalid upload: empty sales DataFrame
        empty_sales = pd.DataFrame()
        with self.assertRaises(Exception):
            create_and_activate_dataset("Invalid B", empty_sales)

        # A must remain intact and active
        self.assertTrue(os.path.exists(file_a))
        self.assertEqual(get_active_dataset_id(), id_a)

        dashboard = get_dashboard_summary()
        self.assertEqual(dashboard["total_revenue"], 1111.0)

    def test_dashboard_uses_current_dataset(self):
        """8. Dashboard endpoint returns metrics strictly from the active dataset."""
        create_and_activate_dataset("Dataset B", self.sales_b, self.inv_b, self.prods_b, self.stores_b)
        res = self.client.get("/api/dashboard")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_revenue"], 9999.0)
        self.assertEqual(data["total_units_sold"], 4)

    def test_inventory_uses_current_dataset(self):
        """9. Inventory endpoint returns inventory strictly from the active dataset."""
        create_and_activate_dataset("Dataset B", self.sales_b, self.inv_b, self.prods_b, self.stores_b)
        res = self.client.get("/api/inventory")
        self.assertEqual(res.status_code, 200)
        items = res.json()
        self.assertEqual(len(items), 6)  # 2 stores * 3 products = 6 inventory entries
        product_names = [i["product_name"] for i in items]
        self.assertIn("Beta Premium Laptop", product_names)
        self.assertNotIn("Product Alpha One", product_names)

    def test_reorder_uses_current_dataset(self):
        """10. Reorder planner calculates only from current active dataset."""
        create_and_activate_dataset("Dataset B", self.sales_b, self.inv_b, self.prods_b, self.stores_b)
        res = self.client.get("/api/reorder-plan")
        self.assertEqual(res.status_code, 200)
        plan = res.json()
        for item in plan:
            self.assertIn("Beta", item["product_name"])
            self.assertNotIn("Alpha", item["product_name"])

    def test_sales_uses_current_dataset(self):
        """11. Sales analytics charts use current active dataset."""
        create_and_activate_dataset("Dataset B", self.sales_b, self.inv_b, self.prods_b, self.stores_b)
        res = self.client.get("/api/analytics/charts")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("revenue_trend", data)

    def test_store_comparison_uses_current_dataset(self):
        """12. Store comparison matrix only displays stores in the active dataset."""
        create_and_activate_dataset("Dataset B", self.sales_b, self.inv_b, self.prods_b, self.stores_b)
        res = self.client.get("/api/compare-stores")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["stores_count"], 2)
        store_names = [s["store_name"] for s in data["comparison_table"]]
        self.assertIn("Beta Downtown Store", store_names)
        self.assertNotIn("Alpha Flagship Store", store_names)

    def test_reports_use_current_dataset(self):
        """13. Executive report generates entirely from current active dataset."""
        create_and_activate_dataset("Dataset B", self.sales_b, self.inv_b, self.prods_b, self.stores_b)
        res = self.client.get("/api/executive-report")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        kpis = data["kpis"]
        self.assertEqual(kpis["total_revenue"], 9999.0)
        self.assertEqual(kpis["total_units_sold"], 4)

    def test_copilot_uses_current_dataset(self):
        """14. AI Copilot reasoning answers from active dataset B."""
        create_and_activate_dataset("Dataset B", self.sales_b, self.inv_b, self.prods_b, self.stores_b)
        res = self.client.post("/api/chat", json={"question": "What is my total revenue?"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("9,999", data["answer"])
        self.assertNotIn("1,111", data["answer"])

    def test_copilot_context_cleared(self):
        """15. Conversation memory and context are wiped on dataset replacement."""
        create_and_activate_dataset("Dataset A", self.sales_a, self.inv_a, self.prods_a, self.stores_a)
        self.client.post("/api/chat", json={"question": "How many stores do I have?"})

        # Replace with Dataset B
        create_and_activate_dataset("Dataset B", self.sales_b, self.inv_b, self.prods_b, self.stores_b)

        # Conversation memory must be reset
        self.assertIsNone(CONVERSATION_MEMORY["last_intent"])

        # Query revenue on B
        res = self.client.post("/api/chat", json={"question": "What is my total revenue?"})
        data = res.json()
        self.assertIn("9,999", data["answer"])
        self.assertNotIn("1,111", data["answer"])

    def test_overlapping_ids(self):
        """16. Datasets with identical IDs (P001, S001) do not leak or persist old values."""
        overlap_sales_a = pd.DataFrame([
            {"sale_id": "SAL01", "date": "2026-08-01", "store_id": "S001", "product_id": "P001", "quantity": 1, "unit_price": 1000.0, "total_revenue": 1000.0}
        ])
        overlap_prods_a = pd.DataFrame([
            {"product_id": "P001", "product_name": "Apple", "category": "Fruit", "unit_price": 1000.0, "cost_price": 500.0, "reorder_point": 10}
        ])
        overlap_stores_a = pd.DataFrame([
            {"store_id": "S001", "store_name": "Store Alpha", "location": "Zone A", "square_feet": 5000, "opening_date": "2020-01-01"}
        ])

        create_and_activate_dataset("Overlap A", overlap_sales_a, products_df=overlap_prods_a, stores_df=overlap_stores_a)

        p_row = query_one("SELECT product_name FROM products WHERE product_id = 'P001'")
        self.assertEqual(p_row["product_name"], "Apple")

        # Replace with Overlap B having SAME P001 & S001 IDs
        overlap_sales_b = pd.DataFrame([
            {"sale_id": "SAL01", "date": "2026-08-01", "store_id": "S001", "product_id": "P001", "quantity": 1, "unit_price": 9000.0, "total_revenue": 9000.0}
        ])
        overlap_prods_b = pd.DataFrame([
            {"product_id": "P001", "product_name": "Laptop", "category": "Computers", "unit_price": 9000.0, "cost_price": 6000.0, "reorder_point": 10}
        ])
        overlap_stores_b = pd.DataFrame([
            {"store_id": "S001", "store_name": "Store Beta", "location": "Zone B", "square_feet": 8000, "opening_date": "2021-01-01"}
        ])

        create_and_activate_dataset("Overlap B", overlap_sales_b, products_df=overlap_prods_b, stores_df=overlap_stores_b)

        p_row = query_one("SELECT product_name FROM products WHERE product_id = 'P001'")
        self.assertEqual(p_row["product_name"], "Laptop")

        s_row = query_one("SELECT store_name FROM stores WHERE store_id = 'S001'")
        self.assertEqual(s_row["store_name"], "Store Beta")

    def test_cache_invalidation(self):
        """17. Invalidation triggers cleanly on dataset activation."""
        create_and_activate_dataset("Dataset A", self.sales_a, self.inv_a, self.prods_a, self.stores_a)
        dash_a = get_dashboard_summary()
        self.assertEqual(dash_a["total_revenue"], 1111.0)

        create_and_activate_dataset("Dataset B", self.sales_b, self.inv_b, self.prods_b, self.stores_b)
        dash_b = get_dashboard_summary()
        self.assertEqual(dash_b["total_revenue"], 9999.0)

    def test_no_demo_fallback(self):
        """18. NO_DATA or dataset replacement never silently falls back to Demo."""
        ActiveDatasetManager.clear_active_dataset()
        self.assertIsNone(get_active_dataset_id())

        res = self.client.get("/api/dashboard")
        self.assertEqual(res.json().get("total_revenue", 0), 0.0)

    def test_clear_returns_no_data(self):
        """19. Clear Active Dataset explicitly sets state to NO_DATA."""
        create_and_activate_dataset("Dataset A", self.sales_a, self.inv_a, self.prods_a, self.stores_a)
        self.assertIsNotNone(get_active_dataset_id())

        res = self.client.post("/api/datasets/clear")
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(get_active_dataset_id())

        meta = ActiveDatasetManager.get_active_dataset()
        self.assertEqual(meta["status"], "NO_DATA")

    def test_explicit_demo_activation(self):
        """20. Demo dataset is active ONLY when explicitly activated."""
        ActiveDatasetManager.clear_active_dataset()
        self.assertIsNone(get_active_dataset_id())

        res = self.client.post("/api/datasets/reset")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(get_active_dataset_id(), "demo")
        meta = ActiveDatasetManager.get_active_dataset()
        self.assertTrue(meta["is_demo"])
        self.assertEqual(meta["status"], "DEMO_ACTIVE")

    def test_source_database_api_ui_counts(self):
        """21. Mandatory verification: SOURCE = DATABASE = API metrics match 100%."""
        meta = create_and_activate_dataset("Dataset B", self.sales_b, self.inv_b, self.prods_b, self.stores_b)

        # 1. Source Truth
        src_store_cnt = len(self.stores_b)
        src_prod_cnt = len(self.prods_b)
        src_sales_cnt = len(self.sales_b)
        src_rev = float(self.sales_b["total_revenue"].sum())
        src_units = int(self.sales_b["quantity"].sum())

        # 2. Database Truth
        db_store_cnt = query_one("SELECT COUNT(*) as cnt FROM stores")["cnt"]
        db_prod_cnt = query_one("SELECT COUNT(*) as cnt FROM products")["cnt"]
        db_sales_cnt = query_one("SELECT COUNT(*) as cnt FROM sales")["cnt"]
        db_sales_agg = query_one("SELECT SUM(total_revenue) as rev, SUM(quantity) as units FROM sales")
        db_rev = float(db_sales_agg["rev"])
        db_units = int(db_sales_agg["units"])

        # 3. API Truth
        res = self.client.get("/api/dashboard")
        api_data = res.json()
        api_rev = float(api_data["total_revenue"])
        api_units = int(api_data["total_units_sold"])

        # Assert 100% exact match across all layers
        self.assertEqual(src_store_cnt, db_store_cnt)
        self.assertEqual(src_prod_cnt, db_prod_cnt)
        self.assertEqual(src_sales_cnt, db_sales_cnt)
        self.assertEqual(src_rev, db_rev)
        self.assertEqual(src_units, db_units)
        self.assertEqual(db_rev, api_rev)
        self.assertEqual(db_units, api_units)


if __name__ == "__main__":
    unittest.main()
