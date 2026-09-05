import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.dataset_manager import ActiveDatasetManager
from src.query_engine import process_query_intent
from src.gemini import generate_copilot_response

import pandas as pd
from src.dataset_manager import create_and_activate_dataset

class TestCopilotIntents(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create self-contained fixture with City Store (72,400 rev, 105 units) and Mall Store (600 rev, 5 units)
        sales_df = pd.DataFrame([
            {
                "sale_id": "S001", "date": "2026-08-01",
                "store_id": "S001", "store_name": "City Store",
                "product_id": "P001", "product_name": "Fast Selling Phone",
                "quantity": 100, "unit_price": 700.0, "total_revenue": 70000.0,
            },
            {
                "sale_id": "S002", "date": "2026-08-02",
                "store_id": "S001", "store_name": "City Store",
                "product_id": "P002", "product_name": "Slow Selling TV",
                "quantity": 5, "unit_price": 480.0, "total_revenue": 2400.0,
            },
            {
                "sale_id": "S003", "date": "2026-08-03",
                "store_id": "S002", "store_name": "Mall Store",
                "product_id": "P001", "product_name": "Fast Selling Phone",
                "quantity": 5, "unit_price": 120.0, "total_revenue": 600.0,
            },
        ])
        inv_df = pd.DataFrame([
            {"store_id": "S001", "product_id": "P001", "current_stock": 50, "last_restock_date": "2026-08-01"},
            {"store_id": "S001", "product_id": "P002", "current_stock": 100, "last_restock_date": "2026-08-01"},
            {"store_id": "S002", "product_id": "P001", "current_stock": 20, "last_restock_date": "2026-08-01"},
            {"store_id": "S002", "product_id": "P002", "current_stock": 30, "last_restock_date": "2026-08-01"},
        ])
        create_and_activate_dataset("Sales", sales_df, inv_df)

    @classmethod
    def tearDownClass(cls):
        ActiveDatasetManager.clear_active_dataset()

    def run_query_and_print_trace(self, question: str, expected_intent: str):
        processed = process_query_intent(question)
        response = generate_copilot_response(processed)

        def safe_str(val):
            return str(val).encode('ascii', 'backslashreplace').decode('ascii')

        print("\n" + "="*70)
        print(f"USER QUERY            : {question}")
        print(f"-> INTENT             : {response.get('intent')} (Expected: {expected_intent})")
        print(f"-> DATA SOURCE        : {safe_str(response.get('data_scope'))}")
        print(f"-> KEY METRICS        : {safe_str(response.get('key_metrics'))}")
        print(f"-> RECOMMENDATIONS    : {safe_str(response.get('recommendations'))}")
        print(f"-> CHART              : {'None' if response.get('chart') is None else safe_str(response['chart'].get('title'))}")
        print(f"-> FINAL RESPONSE     : {safe_str(response.get('answer'))}")
        print("="*70)

        self.assertEqual(response.get("intent"), expected_intent)
        return response

    def test_01_what_items_do_i_have(self):
        res = self.run_query_and_print_trace("What items do I have?", "PRODUCT_LIST")
        self.assertIsNone(res.get("chart"))
        self.assertEqual(res.get("recommendations"), [])
        self.assertIn("products in your active dataset", res.get("answer"))

    def test_02_what_products_do_i_have(self):
        res = self.run_query_and_print_trace("What products do I have?", "PRODUCT_LIST")
        self.assertIsNone(res.get("chart"))
        self.assertEqual(res.get("recommendations"), [])

    def test_03_list_my_products(self):
        res = self.run_query_and_print_trace("List my products.", "PRODUCT_LIST")
        self.assertIsNone(res.get("chart"))
        self.assertEqual(res.get("recommendations"), [])

    def test_04_show_all_my_products(self):
        res = self.run_query_and_print_trace("Show all my products.", "PRODUCT_LIST")
        self.assertIsNone(res.get("chart"))
        self.assertEqual(res.get("recommendations"), [])

    def test_05_what_products_are_available(self):
        res = self.run_query_and_print_trace("What products are available?", "PRODUCT_LIST")
        self.assertIsNone(res.get("chart"))
        self.assertEqual(res.get("recommendations"), [])

    def test_06_show_my_products_with_stock(self):
        res = self.run_query_and_print_trace("Show my products with stock.", "PRODUCT_LIST")
        self.assertIsNone(res.get("chart"))
        self.assertIn("in stock", res.get("answer"))

    def test_07_which_product_sold_the_most(self):
        res = self.run_query_and_print_trace("Which product sold the most?", "TOP_PRODUCT_BY_UNITS")
        self.assertIn("sold the most units", res.get("answer"))

    def test_08_which_product_generated_the_most_revenue(self):
        res = self.run_query_and_print_trace("Which product generated the most revenue?", "TOP_PRODUCT_BY_REVENUE")
        self.assertIn("generated the most revenue", res.get("answer"))

    def test_09_how_many_products_do_i_have(self):
        res = self.run_query_and_print_trace("How many products do I have?", "PRODUCT_COUNT")
        self.assertIsNone(res.get("chart"))
        self.assertIn("products (SKUs) in your active dataset", res.get("answer"))

    def test_10_how_much_stock_do_i_have(self):
        res = self.run_query_and_print_trace("How much stock do I have?", "INVENTORY_SUMMARY")
        self.assertIsNone(res.get("chart"))
        self.assertIn("stock units on hand", res.get("answer"))

    def test_11_which_products_should_i_reorder(self):
        res = self.run_query_and_print_trace("Which products should I reorder?", "REORDER")
        self.assertIn("replenishment", res.get("answer"))

    def test_12_which_products_are_overstocked(self):
        res = self.run_query_and_print_trace("Which products are overstocked?", "OVERSTOCK")
        self.assertIn("overstock", res.get("answer").lower())

    def test_13_what_needs_my_attention_today(self):
        res = self.run_query_and_print_trace("What needs my attention today?", "ATTENTION_TODAY")
        self.assertTrue(len(res.get("key_metrics", [])) > 0 or "Evaluated" in res.get("answer"))

    def test_14_how_did_sales_perform(self):
        res = self.run_query_and_print_trace("How did sales perform?", "SALES_SUMMARY")
        self.assertIn("Total Revenue", res.get("answer"))

    def test_15_give_me_list_if_items_i_have(self):
        res = self.run_query_and_print_trace("give me list if items i have?", "PRODUCT_LIST")
        self.assertIsNone(res.get("chart"))
        self.assertEqual(res.get("recommendations"), [])

    def test_16_follow_up_sequence(self):
        # 1. "What items do I have?" -> PRODUCT_LIST
        q1 = self.run_query_and_print_trace("What items do I have?", "PRODUCT_LIST")
        self.assertEqual(q1["intent"], "PRODUCT_LIST")
        self.assertIsNone(q1.get("chart"))
        self.assertEqual(q1.get("recommendations"), [])

        # 2. "Which one sells the most?" -> TOP_PRODUCT_BY_UNITS
        q2 = self.run_query_and_print_trace("Which one sells the most?", "TOP_PRODUCT_BY_UNITS")
        self.assertEqual(q2["intent"], "TOP_PRODUCT_BY_UNITS")

        # 3. "How much stock do I have?" -> INVENTORY_SUMMARY
        q3 = self.run_query_and_print_trace("How much stock do I have?", "INVENTORY_SUMMARY")
        self.assertEqual(q3["intent"], "INVENTORY_SUMMARY")
        self.assertIsNone(q3.get("chart"))

        # 4. "Which ones should I reorder?" -> REORDER
        q4 = self.run_query_and_print_trace("Which ones should I reorder?", "REORDER")
        self.assertEqual(q4["intent"], "REORDER")

        # 5. "Which are overstocked?" -> OVERSTOCK
        q5 = self.run_query_and_print_trace("Which are overstocked?", "OVERSTOCK")
        self.assertEqual(q5["intent"], "OVERSTOCK")

    # =========================================================================
    # DEDICATED STORE INTENT SUITE (10 USER BENCHMARK QUERIES)
    # =========================================================================

    def test_17_what_stores_do_i_have(self):
        res = self.run_query_and_print_trace("What stores do I have?", "STORE_LIST")
        self.assertIsNone(res.get("chart"))
        self.assertIn("City Store", res.get("answer"))

    def test_18_how_many_stores_do_i_have(self):
        res = self.run_query_and_print_trace("How many stores do I have?", "STORE_COUNT")
        self.assertIsNone(res.get("chart"))
        self.assertIn("stores in your active dataset", res.get("answer"))

    def test_19_which_stores_are_performing_best(self):
        res = self.run_query_and_print_trace("Which stores are performing best?", "STORE_PERFORMANCE")
        self.assertIn("City Store", res.get("answer"))
        self.assertIn("72,400", res.get("answer"))
        self.assertIn("Mall Store", res.get("answer"))
        self.assertIn("600", res.get("answer"))
        self.assertIn("71,800", res.get("answer"))
        self.assertIsNotNone(res.get("chart"))
        self.assertIn("Store Performance by Revenue", res.get("chart", {}).get("title"))

    def test_20_which_store_is_doing_best(self):
        res = self.run_query_and_print_trace("Which store is doing best?", "STORE_PERFORMANCE")
        self.assertIn("City Store", res.get("answer"))
        self.assertIn("72,400", res.get("answer"))

    def test_21_which_store_made_the_most_revenue(self):
        res = self.run_query_and_print_trace("Which store made the most revenue?", "STORE_PERFORMANCE_BY_REVENUE")
        self.assertIn("City Store", res.get("answer"))
        self.assertIn("72,400", res.get("answer"))

    def test_22_which_store_sold_the_most_units(self):
        res = self.run_query_and_print_trace("Which store sold the most units?", "STORE_PERFORMANCE_BY_UNITS")
        self.assertIn("City Store", res.get("answer"))
        self.assertIn("105 units", res.get("answer"))

    def test_23_which_store_is_performing_worst(self):
        res = self.run_query_and_print_trace("Which store is performing worst?", "STORE_PERFORMANCE")
        self.assertIn("Mall Store", res.get("answer"))
        self.assertIn("600", res.get("answer"))

    def test_24_compare_city_store_and_mall_store(self):
        res = self.run_query_and_print_trace("Compare City Store and Mall Store.", "STORE_COMPARISON")
        self.assertIn("City Store", res.get("answer"))
        self.assertIn("Mall Store", res.get("answer"))
        self.assertIn("71,800", res.get("answer"))

    def test_25_how_is_city_store_performing(self):
        res = self.run_query_and_print_trace("How is City Store performing?", "STORE_PERFORMANCE")
        self.assertIn("City Store", res.get("answer"))
        self.assertIn("72,400", res.get("answer"))

    def test_26_list_all_my_stores(self):
        res = self.run_query_and_print_trace("List all my stores.", "STORE_LIST")
        self.assertIsNone(res.get("chart"))
        self.assertIn("City Store", res.get("answer"))

if __name__ == "__main__":
    unittest.main()
