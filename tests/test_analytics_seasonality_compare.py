import os
import sys
import unittest
import pandas as pd
from fastapi.testclient import TestClient

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from src.dataset_manager import ActiveDatasetManager, create_and_activate_dataset

class TestSeasonalityAndStoreComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        ActiveDatasetManager.clear_active_dataset()

    def tearDown(self):
        ActiveDatasetManager.clear_active_dataset()

    def test_01_no_data_state(self):
        """Test 1: NO_DATA state for seasonality & store comparison."""
        res_season = self.client.get("/api/seasonality?store_id=all")
        self.assertEqual(res_season.status_code, 200)
        data_s = res_season.json()
        self.assertEqual(data_s["status"], "NO_DATA")
        self.assertEqual(data_s["seasonality_table"], [])
        self.assertEqual(data_s["peak_month"], "N/A")
        self.assertEqual(data_s["seasonality_chart"]["labels"], [])

        res_comp = self.client.get("/api/compare-stores")
        self.assertEqual(res_comp.status_code, 200)
        data_c = res_comp.json()
        self.assertEqual(data_c["stores_count"], 0)
        self.assertEqual(data_c["comparison_table"], [])
        self.assertEqual(data_c["comparison_chart"]["labels"], [])

    def test_02_small_dataset_insufficient_history(self):
        """Test 2: Small dataset (10 days in 1 month) -> INSUFFICIENT_HISTORY with HTTP 200."""
        stores_df = pd.DataFrame([
            {"store_id": "S001", "store_name": "Store 1", "location": "Loc 1"},
            {"store_id": "S002", "store_name": "Store 2", "location": "Loc 2"}
        ])
        prods_df = pd.DataFrame([
            {"product_id": "P01", "product_name": "Item 1", "category": "General", "unit_price": 100.0, "cost_price": 50.0}
        ])
        inv_df = pd.DataFrame([
            {"store_id": "S001", "product_id": "P01", "current_stock": 50, "reorder_point": 10, "safety_stock": 5, "last_restock_date": "2026-07-01"},
            {"store_id": "S002", "product_id": "P01", "current_stock": 40, "reorder_point": 10, "safety_stock": 5, "last_restock_date": "2026-07-01"}
        ])
        sales_df = pd.DataFrame([
            {"sale_id": f"S{i:03d}", "store_id": "S001" if i % 2 == 0 else "S002", "product_id": "P01", "date": f"2026-07-0{i}", "quantity": 2, "unit_price": 100.0, "total_revenue": 200.0}
            for i in range(1, 10)
        ])

        create_and_activate_dataset("Short Sales Dataset", sales_df, inv_df, prods_df, stores_df)

        res = self.client.get("/api/seasonality?store_id=all")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(data["unique_months"], 1)
        self.assertEqual(data["peak_month"], "N/A")
        self.assertIn("not enough historical data", data["message"].lower())
        self.assertEqual(data["seasonality_table"], [])
        self.assertEqual(data["seasonality_chart"]["labels"], [])

    def test_03_multi_store_comparison_all_stores(self):
        """Test 3: Custom dataset with 6 stores -> /api/compare-stores returns all 6 stores without truncation."""
        stores_df = pd.DataFrame([
            {"store_id": f"S00{i}", "store_name": f"Store {i}", "location": f"Zone {i}"}
            for i in range(1, 7)
        ])
        prods_df = pd.DataFrame([
            {"product_id": "P01", "product_name": "Item 1", "category": "General", "unit_price": 100.0, "cost_price": 50.0}
        ])
        inv_df = pd.DataFrame([
            {"store_id": f"S00{i}", "product_id": "P01", "current_stock": 50, "reorder_point": 10, "safety_stock": 5, "last_restock_date": "2026-07-01"}
            for i in range(1, 7)
        ])
        sales_df = pd.DataFrame([
            {"sale_id": f"S{i:03d}", "store_id": f"S00{(i % 6) + 1}", "product_id": "P01", "date": "2026-07-05", "quantity": 2, "unit_price": 100.0, "total_revenue": 200.0}
            for i in range(1, 25)
        ])

        create_and_activate_dataset("Six Store Dataset", sales_df, inv_df, prods_df, stores_df)

        # 1. Without store_ids (default)
        res_comp = self.client.get("/api/compare-stores")
        self.assertEqual(res_comp.status_code, 200)
        comp_data = res_comp.json()
        self.assertEqual(comp_data["stores_count"], 6)
        self.assertEqual(len(comp_data["comparison_table"]), 6)
        self.assertEqual(len(comp_data["comparison_chart"]["datasets"]), 6)

        # 2. With store_ids=all
        res_comp_all = self.client.get("/api/compare-stores?store_ids=all")
        self.assertEqual(res_comp_all.status_code, 200)
        self.assertEqual(res_comp_all.json()["stores_count"], 6)

        # 3. With specific subset e.g. S001, S003
        res_subset = self.client.get("/api/compare-stores?store_ids=S001,S003")
        self.assertEqual(res_subset.status_code, 200)
        self.assertEqual(res_subset.json()["stores_count"], 2)

    def test_04_multi_month_dataset_seasonality_success(self):
        """Test 4: Multi-month dataset (5 distinct months across 2 years) -> SUCCESS seasonality profile."""
        stores_df = pd.DataFrame([{"store_id": "S001", "store_name": "Main Store", "location": "HQ"}])
        prods_df = pd.DataFrame([{"product_id": "P01", "product_name": "Item 1", "category": "General", "unit_price": 100.0, "cost_price": 50.0}])
        inv_df = pd.DataFrame([{"store_id": "S001", "product_id": "P01", "current_stock": 50, "reorder_point": 10, "safety_stock": 5, "last_restock_date": "2026-07-01"}])
        
        sales_records = [
            {"sale_id": "S1", "store_id": "S001", "product_id": "P01", "date": "2025-01-15", "quantity": 10, "unit_price": 100.0, "total_revenue": 1000.0},
            {"sale_id": "S2", "store_id": "S001", "product_id": "P01", "date": "2025-03-20", "quantity": 20, "unit_price": 100.0, "total_revenue": 2000.0},
            {"sale_id": "S3", "store_id": "S001", "product_id": "P01", "date": "2025-07-10", "quantity": 50, "unit_price": 100.0, "total_revenue": 5000.0},
            {"sale_id": "S4", "store_id": "S001", "product_id": "P01", "date": "2025-11-05", "quantity": 30, "unit_price": 100.0, "total_revenue": 3000.0},
            {"sale_id": "S5", "store_id": "S001", "product_id": "P01", "date": "2026-01-15", "quantity": 15, "unit_price": 100.0, "total_revenue": 1500.0},
            {"sale_id": "S6", "store_id": "S001", "product_id": "P01", "date": "2026-07-10", "quantity": 60, "unit_price": 100.0, "total_revenue": 6000.0}
        ]
        sales_df = pd.DataFrame(sales_records)

        create_and_activate_dataset("Seasonality Test Dataset", sales_df, inv_df, prods_df, stores_df)

        res = self.client.get("/api/seasonality?store_id=all")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["unique_months"], 6)
        self.assertEqual(len(data["seasonality_table"]), 4)
        self.assertEqual(data["peak_month"], "Jul")
        self.assertIn("Jul", data["seasonality_chart"]["labels"])
        self.assertIn("Jan", data["seasonality_chart"]["labels"])
        # Verify Jan average is (1000 + 1500)/2 = 1250.0
        jan_row = next(r for r in data["seasonality_table"] if r["month_name"] == "Jan")
        self.assertEqual(jan_row["avg_revenue"], 1250.0)

    def test_05_demo_dataset_full_seasonality(self):
        """Test 5: Demo dataset (10 years) -> 12 months seasonality profile."""
        ActiveDatasetManager.reset_to_demo()
        res = self.client.get("/api/seasonality?store_id=all")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(len(data["seasonality_chart"]["labels"]), 12)
        self.assertIsNotNone(data["peak_month"])
        self.assertNotEqual(data["peak_month"], "N/A")

if __name__ == "__main__":
    unittest.main()
