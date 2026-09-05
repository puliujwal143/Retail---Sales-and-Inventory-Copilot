import unittest
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import init_db, query_all
from src.dataset_manager import ActiveDatasetManager
from src.query_engine import process_query_intent
from src.gemini import generate_copilot_response

def safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'ignore').decode('ascii'))

import pandas as pd
from src.dataset_manager import create_and_activate_dataset

class TestAIGroundingPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create explicit fixture dataset with Fast Selling Phone and City Store
        sales_df = pd.DataFrame([
            {
                "sale_id": "S001",
                "date": "2026-08-05",
                "store_id": "S1",
                "store_name": "City Store",
                "product_id": "P1",
                "product_name": "Fast Selling Phone",
                "quantity": 12,
                "unit_price": 5000.0,
                "total_revenue": 60000.0,
            },
            {
                "sale_id": "S002",
                "date": "2026-08-10",
                "store_id": "S1",
                "store_name": "City Store",
                "product_id": "P2",
                "product_name": "Slow Selling TV",
                "quantity": 1,
                "unit_price": 13000.0,
                "total_revenue": 13000.0,
            }
        ])
        inv_df = pd.DataFrame([
            {"store_id": "S1", "product_id": "P1", "current_stock": 50, "last_restock_date": "2026-08-01"},
            {"store_id": "S1", "product_id": "P2", "current_stock": 10, "last_restock_date": "2026-08-01"},
        ])
        cls.metrics = create_and_activate_dataset("AIGroundingFixture", sales_df, inv_df)
        cls.active_ds = ActiveDatasetManager.get_active_dataset()
        safe_print(f"\n[SETUP] Active Dataset: {cls.active_ds.get('dataset_name')} (ID: {cls.active_ds.get('dataset_id')})")
        products = query_all("SELECT product_id, product_name FROM products")
        stores = query_all("SELECT store_id, store_name FROM stores")
        safe_print(f"[SETUP] Available Products: {[p['product_name'] for p in products]}")
        safe_print(f"[SETUP] Available Stores: {[s['store_name'] for s in stores]}")

    @classmethod
    def tearDownClass(cls):
        ActiveDatasetManager.clear_active_dataset()

    def test_1_nonexistent_product(self):
        """Test 1: 'How did laptop sales perform?' -> NO_DATA if Laptop doesn't exist."""
        q = "How did laptop sales perform?"
        processed = process_query_intent(q)
        res = generate_copilot_response(processed)

        safe_print(f"\n--- TEST 1: {q} ---")
        safe_print(f"Grounding State: {res.get('grounding_state')}")
        safe_print(f"Answer: {res.get('answer')}")
        safe_print(f"Key Metrics: {res.get('key_metrics')}")
        safe_print(f"Chart: {res.get('chart')}")

        self.assertEqual(res.get("grounding_state"), "NO_DATA")
        self.assertEqual(res.get("key_metrics"), [])
        self.assertIsNone(res.get("chart"))
        self.assertIn("laptop", res.get("answer", "").lower())
        self.assertIn("not found", res.get("answer", "").lower())
        # Ensure overall total (73,000 or 115 units) is NEVER mentioned as laptop sales
        self.assertNotIn("73,000", res.get("answer", ""))

    def test_2_existing_product_isolated(self):
        """Test 2: 'How did Fast Selling Phone perform?' -> Metrics ONLY for Fast Selling Phone."""
        q = "How did Fast Selling Phone perform?"
        processed = process_query_intent(q)
        res = generate_copilot_response(processed)

        safe_print(f"\n--- TEST 2: {q} ---")
        safe_print(f"Grounding State: {res.get('grounding_state')}")
        safe_print(f"Answer: {res.get('answer')}")
        safe_print(f"Key Metrics: {res.get('key_metrics')}")

        self.assertEqual(res.get("grounding_state"), "DATA_FOUND")
        self.assertTrue(len(res.get("key_metrics", [])) > 0)
        self.assertIn("Fast Selling Phone", res.get("answer", ""))
        # Check that Fast Selling Phone revenue is calculated (₹60,000 in custom dataset)
        rev_metric = next((m for m in res.get("key_metrics", []) if "revenue" in m.get("label", "").lower()), None)
        self.assertIsNotNone(rev_metric)
        self.assertIn("60,000", rev_metric.get("value", ""))

    def test_3_overall_sales_query(self):
        """Test 3: 'How did sales perform?' -> Overall dataset metrics."""
        q = "How did sales perform?"
        processed = process_query_intent(q)
        res = generate_copilot_response(processed)

        safe_print(f"\n--- TEST 3: {q} ---")
        safe_print(f"Grounding State: {res.get('grounding_state')}")
        safe_print(f"Answer: {res.get('answer')}")
        safe_print(f"Key Metrics: {res.get('key_metrics')}")

        self.assertEqual(res.get("grounding_state"), "DATA_FOUND")
        self.assertTrue(len(res.get("key_metrics", [])) > 0)
        self.assertIsNotNone(res.get("chart"))

    def test_4_nonexistent_product_with_existing_store(self):
        """Test 4: 'How did laptop sales perform in City Store?' -> NO_DATA if Laptop doesn't exist, even if City Store exists."""
        q = "How did laptop sales perform in City Store?"
        processed = process_query_intent(q)
        res = generate_copilot_response(processed)

        safe_print(f"\n--- TEST 4: {q} ---")
        safe_print(f"Grounding State: {res.get('grounding_state')}")
        safe_print(f"Answer: {res.get('answer')}")
        safe_print(f"Key Metrics: {res.get('key_metrics')}")

        self.assertEqual(res.get("grounding_state"), "NO_DATA")
        self.assertEqual(res.get("key_metrics"), [])
        self.assertIsNone(res.get("chart"))
        self.assertIn("laptop", res.get("answer", "").lower())
        self.assertIn("not found", res.get("answer", "").lower())

    def test_5_specific_date_range(self):
        """Test 5: 'Show sales for August 2026.' -> Only records actually within that date range."""
        q = "Show sales for August 2026."
        processed = process_query_intent(q)
        res = generate_copilot_response(processed)

        safe_print(f"\n--- TEST 5: {q} ---")
        safe_print(f"Grounding State: {res.get('grounding_state')}")
        safe_print(f"Answer: {res.get('answer')}")
        safe_print(f"Data Scope: {res.get('data_scope')}")
        safe_print(f"Key Metrics: {res.get('key_metrics')}")

        self.assertEqual(res.get("grounding_state"), "DATA_FOUND")
        self.assertIn("2026-08", res.get("data_scope", ""))
        self.assertTrue(len(res.get("key_metrics", [])) > 0)

    def test_6_nonexistent_store(self):
        """Test 6: Ask about a nonexistent store. -> NO_DATA and no use of overall store totals."""
        q = "How did sales perform in London Store?"
        processed = process_query_intent(q)
        res = generate_copilot_response(processed)

        safe_print(f"\n--- TEST 6: {q} ---")
        safe_print(f"Grounding State: {res.get('grounding_state')}")
        safe_print(f"Answer: {res.get('answer')}")
        safe_print(f"Key Metrics: {res.get('key_metrics')}")

        self.assertEqual(res.get("grounding_state"), "NO_DATA")
        self.assertEqual(res.get("key_metrics"), [])
        self.assertIsNone(res.get("chart"))
        self.assertIn("london", res.get("answer", "").lower())
        self.assertIn("not found", res.get("answer", "").lower())

if __name__ == "__main__":
    unittest.main()
