import os
import sys
import unittest
from fastapi.testclient import TestClient

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from src.dataset_manager import ActiveDatasetManager

class TestNoDataState(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_initial_no_data_state(self):
        # Force NO_DATA state
        ActiveDatasetManager.clear_active_dataset()
        
        # 1. /api/datasets/active
        res = self.client.get("/api/datasets/active")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsNone(data["dataset_id"])
        self.assertEqual(data["status"], "NO_DATA")
        self.assertEqual(data["store_count"], 0)
        self.assertEqual(data["product_count"], 0)
        self.assertEqual(data["sales_count"], 0)
        self.assertEqual(data["inventory_count"], 0)
        self.assertEqual(data["total_revenue"], 0.0)

        # 2. /api/dashboard
        res = self.client.get("/api/dashboard")
        self.assertEqual(res.status_code, 200)
        dash = res.json()
        self.assertTrue(dash["no_data"])
        self.assertEqual(dash["total_revenue"], 0.0)
        self.assertEqual(dash["total_units_sold"], 0)
        self.assertEqual(dash["critical_low_stock_count"], 0)
        self.assertEqual(dash["warning_low_stock_count"], 0)
        self.assertEqual(dash["overstock_count"], 0)
        self.assertEqual(dash["top_products"], [])
        self.assertEqual(dash["store_performance"], [])

        # 3. /api/inventory
        res = self.client.get("/api/inventory")
        self.assertEqual(res.status_code, 200)
        inv = res.json()
        self.assertEqual(inv, [])

        # 4. /api/reorder-plan
        res = self.client.get("/api/reorder-plan")
        self.assertEqual(res.status_code, 200)
        reorder = res.json()
        self.assertEqual(reorder, [])

        # 5. /api/decision-center
        res = self.client.get("/api/decision-center")
        self.assertEqual(res.status_code, 200)
        decisions = res.json()
        self.assertEqual(decisions, [])

        # 6. /api/alerts
        res = self.client.get("/api/alerts")
        self.assertEqual(res.status_code, 200)
        alerts = res.json()
        self.assertEqual(alerts, [])

        # 7. /api/executive-report
        res = self.client.get("/api/executive-report")
        self.assertEqual(res.status_code, 200)
        rep = res.json()
        self.assertEqual(rep["kpis"]["total_revenue"], 0.0)
        self.assertEqual(rep["critical_stock_items"], [])
        self.assertEqual(rep["recommended_reorders"], [])

        # 8. /api/chat during NO_DATA
        res = self.client.post("/api/chat", json={"question": "What are my best-selling products?"})
        self.assertEqual(res.status_code, 200)
        chat = res.json()
        self.assertTrue("don't have an active retail dataset" in chat["answer"] or "upload" in chat["answer"].lower())
        self.assertEqual(chat["key_metrics"], [])
        self.assertIsNone(chat["chart"])

    def test_dataset_lifecycle_transitions(self):
        # 1. Start at NO_DATA
        ActiveDatasetManager.clear_active_dataset()
        self.assertIsNone(ActiveDatasetManager.get_active_dataset_id())

        # 2. Reset to Demo
        res = self.client.post("/api/datasets/reset")
        self.assertEqual(res.status_code, 200)
        demo_meta = res.json()["dataset"]
        self.assertEqual(demo_meta["dataset_id"], "demo")
        self.assertEqual(demo_meta["store_count"], 5)
        self.assertEqual(demo_meta["product_count"], 40)
        self.assertEqual(demo_meta["sales_count"], 114515)

        # Check that dashboard now uses Demo
        dash = self.client.get("/api/dashboard").json()
        self.assertFalse(dash["no_data"])
        self.assertGreater(dash["total_revenue"], 1000000)

        # 3. Clear Active Dataset -> back to NO_DATA
        res = self.client.post("/api/datasets/clear")
        self.assertEqual(res.status_code, 200)
        clear_meta = res.json()["dataset"]
        self.assertIsNone(clear_meta["dataset_id"])
        self.assertEqual(clear_meta["status"], "NO_DATA")

        # Dashboard must be zeroed again
        dash2 = self.client.get("/api/dashboard").json()
        self.assertTrue(dash2["no_data"])
        self.assertEqual(dash2["total_revenue"], 0.0)

if __name__ == "__main__":
    unittest.main()
