import os
import io
import sys
import unittest
import pandas as pd
from fastapi.testclient import TestClient

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from src.dataset_manager import ActiveDatasetManager, create_and_activate_dataset

class TestNoDataStateComprehensive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        ActiveDatasetManager.clear_active_dataset()

    def tearDown(self):
        ActiveDatasetManager.clear_active_dataset()

    def test_all_endpoints_return_200_and_clean_no_data_contract(self):
        """
        Tests every analytics endpoint under NO_DATA state.
        Ensures HTTP 200, valid schema contracts, zero numerical metrics, and empty arrays.
        """
        # 1. /api/datasets/active
        res = self.client.get("/api/datasets/active")
        self.assertEqual(res.status_code, 200)
        active_meta = res.json()
        self.assertIsNone(active_meta["dataset_id"])
        self.assertEqual(active_meta["status"], "NO_DATA")
        self.assertEqual(active_meta["store_count"], 0)
        self.assertEqual(active_meta["product_count"], 0)
        self.assertEqual(active_meta["sales_count"], 0)
        self.assertEqual(active_meta["inventory_count"], 0)
        self.assertEqual(active_meta["total_revenue"], 0.0)
        self.assertEqual(active_meta["total_units_sold"], 0)

        # 2. /api/dashboard
        res = self.client.get("/api/dashboard?store_id=all")
        self.assertEqual(res.status_code, 200)
        dash = res.json()
        self.assertTrue(dash["no_data"])
        self.assertEqual(dash["total_revenue"], 0.0)
        self.assertEqual(dash["total_units_sold"], 0)
        self.assertEqual(dash["critical_low_stock_count"], 0)
        self.assertEqual(dash["warning_low_stock_count"], 0)
        self.assertEqual(dash["overstock_count"], 0)
        self.assertEqual(dash["sales_growth_pct"], 0.0)
        self.assertEqual(dash["top_products"], [])
        self.assertEqual(dash["store_performance"], [])
        self.assertEqual(dash["category_performance"], [])
        self.assertEqual(dash["daily_trend"], [])
        self.assertEqual(dash["sparklines"]["revenue"], [])

        # 3. /api/inventory
        res = self.client.get("/api/inventory?store_id=all")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

        # 4. /api/sales
        res = self.client.get("/api/sales")
        self.assertEqual(res.status_code, 200)
        sales_summary = res.json()
        self.assertEqual(sales_summary["spikes"], [])
        self.assertEqual(sales_summary["drops"], [])
        self.assertEqual(sales_summary["category_performance"], [])
        self.assertEqual(sales_summary["store_performance"], [])

        # 5. /api/analytics/charts (days=30) - Must not throw 500
        res = self.client.get("/api/analytics/charts?days=30&store_id=all")
        self.assertEqual(res.status_code, 200)
        charts30 = res.json()
        self.assertEqual(charts30["combined_trend"]["labels"], [])
        self.assertEqual(charts30["combined_trend"]["datasets"][0]["data"], [])
        self.assertEqual(charts30["revenue_trend"]["labels"], [])
        self.assertEqual(charts30["units_trend"]["labels"], [])
        self.assertEqual(charts30["category_chart"]["labels"], [])
        self.assertEqual(charts30["top_products_chart"]["labels"], [])
        self.assertEqual(charts30["store_chart"]["labels"], [])
        self.assertEqual(charts30["spikes"], [])
        self.assertEqual(charts30["drops"], [])
        self.assertTrue(len(charts30["insights"]) > 0)

        # 6. /api/analytics/charts (days=180 - monthly mode) - Must not throw 500
        res = self.client.get("/api/analytics/charts?days=180&store_id=all")
        self.assertEqual(res.status_code, 200)
        charts180 = res.json()
        self.assertEqual(charts180["combined_trend"]["labels"], [])
        self.assertEqual(charts180["revenue_trend"]["labels"], [])

        # 7. /api/yearly-performance
        res = self.client.get("/api/yearly-performance?store_id=all")
        self.assertEqual(res.status_code, 200)
        yearly = res.json()
        self.assertEqual(yearly["yearly_table"], [])
        self.assertEqual(yearly["yearly_chart"]["labels"], [])
        self.assertEqual(yearly["growth_chart"]["labels"], [])
        self.assertEqual(yearly["best_year"], "N/A")

        # 8. /api/seasonality
        res = self.client.get("/api/seasonality?store_id=all")
        self.assertEqual(res.status_code, 200)
        season = res.json()
        self.assertEqual(season["seasonality_table"], [])
        self.assertEqual(season["seasonality_chart"]["labels"], [])
        self.assertEqual(season["peak_month"], "N/A")

        # 9. /api/reorder-plan
        res = self.client.get("/api/reorder-plan?store_id=all")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

        # 10. /api/decision-center
        res = self.client.get("/api/decision-center")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

        # 11. /api/compare-stores
        res = self.client.get("/api/compare-stores?store_ids=STR001,STR002&days=30")
        self.assertEqual(res.status_code, 200)
        comp = res.json()
        self.assertEqual(comp["stores_count"], 0)
        self.assertEqual(comp["comparison_table"], [])
        self.assertEqual(comp["comparison_chart"]["labels"], [])

        # 12. /api/executive-report
        res = self.client.get("/api/executive-report?store_id=all")
        self.assertEqual(res.status_code, 200)
        rep = res.json()
        self.assertEqual(rep["kpis"]["total_revenue"], 0.0)
        self.assertEqual(rep["kpis"]["total_units_sold"], 0)
        self.assertEqual(rep["critical_stock_items"], [])
        self.assertEqual(rep["recommended_reorders"], [])
        self.assertEqual(rep["top_products"], [])
        self.assertEqual(rep["store_performance"], [])

        # 13. /api/forecast
        res = self.client.get("/api/forecast?product_id=PRD001&store_id=all")
        self.assertEqual(res.status_code, 200)
        fc = res.json()
        self.assertEqual(fc["forecast_7d"], 0)
        self.assertEqual(fc["status"], "insufficient_data")

        # 14. /api/stores & /api/products
        res = self.client.get("/api/stores")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

        res = self.client.get("/api/products")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

        # 15. /api/alerts
        res = self.client.get("/api/alerts")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), [])

    def test_copilot_answers_safely_in_no_data_state(self):
        """
        Verifies that AI Copilot returns grounded no-data responses and NEVER queries
        or hallucinates from demo or previous datasets.
        """
        queries = [
            "What are my sales?",
            "Which products are overstocked?",
            "Which stores are performing best?",
            "Give me list of items I have?",
            "How did laptop sales perform?"
        ]

        for q in queries:
            res = self.client.post("/api/chat", json={"question": q})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            ans = data["answer"].lower()
            self.assertTrue(
                "don't have an active retail dataset" in ans or 
                "no dataset" in ans or 
                "upload" in ans or
                "no retail data" in ans,
                f"Query '{q}' returned ungrounded answer: {data['answer']}"
            )
            self.assertEqual(data["key_metrics"], [])
            self.assertIsNone(data["chart"])

    def test_full_dataset_switching_and_clearing_workflow(self):
        """
        Tests the complete multi-phase workflow:
        Start NO_DATA -> Upload Custom 1 -> Clear -> Upload Custom 2 -> Clear -> Reset Demo -> Clear.
        """
        # STEP A: Application starts in NO_DATA state
        res = self.client.get("/api/datasets/active").json()
        self.assertEqual(res["status"], "NO_DATA")
        self.assertEqual(self.client.get("/api/dashboard").json()["total_revenue"], 0.0)

        # STEP B: Clear active dataset explicitly
        res_clear = self.client.post("/api/datasets/clear")
        self.assertEqual(res_clear.status_code, 200)
        self.assertEqual(self.client.get("/api/datasets/active").json()["status"], "NO_DATA")

        # STEP C: Upload Custom Dataset 1 (2 stores, 5 products, 21 sales records)
        stores_df = pd.DataFrame([
            {"store_id": "STR_A", "store_name": "Alpha Store", "location": "North Mall"},
            {"store_id": "STR_B", "store_name": "Beta Store", "location": "South Mall"}
        ])
        prods_df = pd.DataFrame([
            {"product_id": "P01", "product_name": "Wireless Mouse", "category": "Accessories", "unit_price": 500.0, "cost_price": 300.0},
            {"product_id": "P02", "product_name": "Mechanical Keyboard", "category": "Accessories", "unit_price": 2000.0, "cost_price": 1200.0},
            {"product_id": "P03", "product_name": "USB-C Hub", "category": "Accessories", "unit_price": 800.0, "cost_price": 450.0},
            {"product_id": "P04", "product_name": "Monitor Arm", "category": "Office", "unit_price": 1500.0, "cost_price": 900.0},
            {"product_id": "P05", "product_name": "Desk Mat", "category": "Office", "unit_price": 400.0, "cost_price": 200.0}
        ])
        inv_df = pd.DataFrame([
            {"store_id": "STR_A", "product_id": "P01", "current_stock": 25, "reorder_point": 10, "safety_stock": 5, "last_restock_date": "2026-08-01"},
            {"store_id": "STR_A", "product_id": "P02", "current_stock": 4, "reorder_point": 8, "safety_stock": 3, "last_restock_date": "2026-08-01"},
            {"store_id": "STR_A", "product_id": "P03", "current_stock": 50, "reorder_point": 10, "safety_stock": 5, "last_restock_date": "2026-08-01"},
            {"store_id": "STR_A", "product_id": "P04", "current_stock": 2, "reorder_point": 5, "safety_stock": 2, "last_restock_date": "2026-08-01"},
            {"store_id": "STR_A", "product_id": "P05", "current_stock": 30, "reorder_point": 10, "safety_stock": 5, "last_restock_date": "2026-08-01"},
            {"store_id": "STR_B", "product_id": "P01", "current_stock": 15, "reorder_point": 10, "safety_stock": 5, "last_restock_date": "2026-08-01"},
            {"store_id": "STR_B", "product_id": "P02", "current_stock": 1, "reorder_point": 8, "safety_stock": 3, "last_restock_date": "2026-08-01"},
            {"store_id": "STR_B", "product_id": "P03", "current_stock": 40, "reorder_point": 10, "safety_stock": 5, "last_restock_date": "2026-08-01"},
            {"store_id": "STR_B", "product_id": "P04", "current_stock": 8, "reorder_point": 5, "safety_stock": 2, "last_restock_date": "2026-08-01"},
            {"store_id": "STR_B", "product_id": "P05", "current_stock": 10, "reorder_point": 10, "safety_stock": 5, "last_restock_date": "2026-08-01"}
        ])
        sales_df = pd.DataFrame([
            {"sale_id": f"S{i:03d}", "store_id": "STR_A" if i % 2 == 0 else "STR_B", "product_id": f"P0{(i % 5) + 1}", "date": f"2026-08-0{(i % 5) + 1}", "quantity": 2, "unit_price": 500.0, "total_revenue": 1000.0}
            for i in range(1, 22)
        ])

        metrics1 = create_and_activate_dataset("Custom Dataset 1", sales_df, inv_df, prods_df, stores_df)
        self.assertEqual(metrics1["store_count"], 2)
        self.assertEqual(metrics1["product_count"], 5)
        self.assertEqual(metrics1["sales_count"], 21)

        # Verify Custom 1 is active across APIs
        dash1 = self.client.get("/api/dashboard").json()
        self.assertFalse(dash1["no_data"])
        self.assertEqual(dash1["total_revenue"], 21000.0)
        self.assertEqual(dash1["total_units_sold"], 42)
        self.assertEqual(dash1["total_inventory_records"], 10)

        charts1 = self.client.get("/api/analytics/charts?days=30&store_id=all").json()
        self.assertTrue(len(charts1["combined_trend"]["labels"]) > 0)
        self.assertEqual(len(charts1["store_chart"]["labels"]), 2)

        # STEP D: Clear active dataset -> immediately back to NO_DATA
        res_clear2 = self.client.post("/api/datasets/clear")
        self.assertEqual(res_clear2.status_code, 200)

        dash_cleared = self.client.get("/api/dashboard").json()
        self.assertTrue(dash_cleared["no_data"])
        self.assertEqual(dash_cleared["total_revenue"], 0.0)
        self.assertEqual(dash_cleared["total_inventory_records"], 0)

        charts_cleared = self.client.get("/api/analytics/charts?days=30&store_id=all").json()
        self.assertEqual(charts_cleared["combined_trend"]["labels"], [])

        # STEP E: Upload Custom Dataset 2 (1 store, 2 products, 5 sales records)
        stores_df2 = pd.DataFrame([{"store_id": "STR_G", "store_name": "Gamma Boutique", "location": "Downtown"}])
        prods_df2 = pd.DataFrame([
            {"product_id": "PX1", "product_name": "Silk Scarf", "category": "Apparel", "unit_price": 1200.0, "cost_price": 600.0},
            {"product_id": "PX2", "product_name": "Leather Belt", "category": "Apparel", "unit_price": 1800.0, "cost_price": 900.0}
        ])
        inv_df2 = pd.DataFrame([
            {"store_id": "STR_G", "product_id": "PX1", "current_stock": 12, "reorder_point": 5, "safety_stock": 2, "last_restock_date": "2026-08-01"},
            {"store_id": "STR_G", "product_id": "PX2", "current_stock": 3, "reorder_point": 5, "safety_stock": 2, "last_restock_date": "2026-08-01"}
        ])
        sales_df2 = pd.DataFrame([
            {"sale_id": f"SG{i}", "store_id": "STR_G", "product_id": "PX1", "date": "2026-08-02", "quantity": 1, "unit_price": 1200.0, "total_revenue": 1200.0}
            for i in range(1, 6)
        ])

        metrics2 = create_and_activate_dataset("Custom Dataset 2", sales_df2, inv_df2, prods_df2, stores_df2)
        self.assertEqual(metrics2["store_count"], 1)
        self.assertEqual(metrics2["product_count"], 2)
        self.assertEqual(metrics2["sales_count"], 5)

        dash2 = self.client.get("/api/dashboard").json()
        self.assertFalse(dash2["no_data"])
        self.assertEqual(dash2["total_revenue"], 6000.0)
        self.assertEqual(dash2["total_units_sold"], 5)
        self.assertEqual(dash2["total_inventory_records"], 2)

        # STEP F: Clear again -> NO_DATA
        self.client.post("/api/datasets/clear")
        dash_final = self.client.get("/api/dashboard").json()
        self.assertTrue(dash_final["no_data"])
        self.assertEqual(dash_final["total_revenue"], 0.0)

        # STEP G: Reset to Demo Dataset
        res_demo = self.client.post("/api/datasets/reset")
        self.assertEqual(res_demo.status_code, 200)
        self.assertEqual(res_demo.json()["dataset"]["dataset_id"], "demo")

        dash_demo = self.client.get("/api/dashboard").json()
        self.assertFalse(dash_demo["no_data"])
        self.assertGreater(dash_demo["total_revenue"], 1000000.0)

        # STEP H: Final Clear back to NO_DATA
        self.client.post("/api/datasets/clear")
        self.assertEqual(self.client.get("/api/datasets/active").json()["status"], "NO_DATA")

if __name__ == "__main__":
    unittest.main()
