import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import query_all, query_one
from src.dataset_manager import ActiveDatasetManager, get_active_dataset_latest_date
from src.inventory_rules import get_inventory_status_df, get_low_stock_items
from src.sales_rules import get_yearly_performance, get_seasonality_analysis, get_daily_sales_trend, compare_stores_analytics
from src.analytics import get_dashboard_summary
from src.recommendation import get_attention_items
from src.query_engine import process_query_intent

DEMO_PRODUCTS = [
    "Pro Laptop 15-inch",
    "Ultra Slim Notebook 13",
    "Wireless Ergonomic Mouse",
    "Wireless Document Scanner",
    "Downtown Flagship",
    "Metro Hub Store",
    "Westside Plaza",
    "North Park Outlet",
    "Airport Express"
]

# Dynamically find the active or uploaded custom dataset named Sales
sales_datasets = [d for d in ActiveDatasetManager.list_datasets() if d.get("dataset_name") == "Sales"]
if sales_datasets:
    CUSTOM_DS_ID = sales_datasets[0]["dataset_id"]
else:
    custom_datasets = [d for d in ActiveDatasetManager.list_datasets() if not d.get("is_demo")]
    CUSTOM_DS_ID = custom_datasets[0]["dataset_id"] if custom_datasets else "demo"

class TestDatasetIsolation(unittest.TestCase):

    def setUp(self):
        # Ensure Custom Dataset is active
        if CUSTOM_DS_ID != "demo_retail_dataset":
            ActiveDatasetManager.activate_dataset(CUSTOM_DS_ID)

    def test_01_active_dataset_metadata(self):
        active = ActiveDatasetManager.get_active_dataset()
        self.assertEqual(active["dataset_id"], CUSTOM_DS_ID)
        self.assertEqual(active["dataset_name"], "Sales")
        self.assertEqual(active["store_count"], 2)
        self.assertEqual(active["product_count"], 5)
        self.assertEqual(active["sales_count"], 21)
        self.assertEqual(active["inventory_count"], 10)
        self.assertEqual(active["total_stock_units"], 538)
        self.assertEqual(active["min_date"], "2026-08-01")
        self.assertEqual(active["max_date"], "2026-08-05")
        self.assertEqual(active["total_revenue"], 73000.0)
        self.assertEqual(active["total_units_sold"], 115)
        self.assertEqual(get_active_dataset_latest_date(), "2026-08-05")

    def test_02_database_stores_and_products(self):
        stores = query_all("SELECT * FROM stores")
        self.assertEqual(len(stores), 2)
        store_names = [s["store_name"] for s in stores]
        self.assertIn("City Store", store_names)
        self.assertIn("Mall Store", store_names)

        products = query_all("SELECT * FROM products")
        self.assertEqual(len(products), 5)
        prod_names = [p["product_name"] for p in products]
        expected_prods = ["Fast Selling Phone", "Slow Selling TV", "Popular Headphones", "Old Keyboard", "Water Bottle"]
        for p in expected_prods:
            self.assertIn(p, prod_names)

        # Zero demo products or demo stores in DB
        for demo_name in DEMO_PRODUCTS:
            self.assertNotIn(demo_name, store_names)
            self.assertNotIn(demo_name, prod_names)

    def test_03_inventory_status_isolation(self):
        inv_df = get_inventory_status_df()
        self.assertEqual(len(inv_df), 10)
        
        inv_prod_names = inv_df["product_name"].tolist()
        inv_store_names = inv_df["store_name"].tolist()

        for demo_name in DEMO_PRODUCTS:
            self.assertNotIn(demo_name, inv_prod_names)
            self.assertNotIn(demo_name, inv_store_names)

        # Total stock units must match 538
        total_stock = inv_df["current_stock"].sum()
        self.assertEqual(total_stock, 538)

        # Fast Selling Phone at City Store has 5 units, status CRITICAL, recommended reorder 79
        phone_s001 = inv_df[(inv_df["store_id"] == "S001") & (inv_df["product_id"] == "P001")].iloc[0]
        self.assertEqual(phone_s001["current_stock"], 5)
        self.assertEqual(phone_s001["status"], "CRITICAL")
        self.assertEqual(phone_s001["recommended_reorder"], 79)

    def test_04_dashboard_summary_isolation(self):
        dash = get_dashboard_summary()
        self.assertEqual(dash["total_revenue"], 73000.0)
        self.assertEqual(dash["total_units_sold"], 115)
        self.assertEqual(dash["total_transactions"], 21)
        self.assertEqual(dash["total_inventory_records"], 10)
        self.assertEqual(dash["total_inventory_units"], 538)
        self.assertEqual(dash["critical_low_stock_count"], 2)
        self.assertEqual(dash["overstock_count"], 3)
        self.assertEqual(len(dash["store_performance"]), 2)

        for p in dash["top_products"]:
            self.assertNotIn(p["product_name"], DEMO_PRODUCTS)

    def test_05_sales_rules_and_charts_isolation(self):
        yearly = get_yearly_performance()
        self.assertEqual(yearly["yearly_chart"]["title"], "Annual Revenue (2026)")
        self.assertEqual(len(yearly["yearly_table"]), 1)
        self.assertEqual(yearly["yearly_table"][0]["year"], "2026")

        daily_trend = get_daily_sales_trend(30)
        self.assertEqual(len(daily_trend), 5)
        trend_dates = [d["date"] for d in daily_trend]
        self.assertEqual(trend_dates, ["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-04", "2026-08-05"])

    def test_06_store_comparison_isolation(self):
        comp = compare_stores_analytics(store_ids=["S001", "S002"], time_days=30)
        self.assertEqual(comp["stores_count"], 2)
        comp_store_names = [s["store_name"] for s in comp["comparison_table"]]
        self.assertIn("City Store", comp_store_names)
        self.assertIn("Mall Store", comp_store_names)
        for demo_name in DEMO_PRODUCTS:
            self.assertNotIn(demo_name, comp_store_names)

    def test_07_copilot_queries_and_scope(self):
        # Metadata query: how many stores
        q_stores = process_query_intent("How many stores do I have?")
        self.assertIn(q_stores["intent"], ["STORE_COUNT", "DATASET_METADATA", "STORE_LIST"])
        self.assertIn("2 stores", q_stores["context_summary"])
        self.assertIn("City Store", q_stores["context_summary"])
        self.assertIn("Mall Store", q_stores["context_summary"])

        # Metadata query: how many products
        q_prods = process_query_intent("How many products do I have?")
        self.assertIn(q_prods["intent"], ["PRODUCT_COUNT", "DATASET_METADATA", "PRODUCT_LIST"])
        self.assertIn("5 products", q_prods["context_summary"])

        # Scope isolation: Mall Store sales
        q_mall = process_query_intent("What is the sales at Mall Store?")
        self.assertIn("Scope: Mall Store", q_mall["data_scope"])
        self.assertIn("600.00", q_mall["context_summary"])
        self.assertIn("10 units", q_mall["context_summary"])

        # Date isolation: August 2
        q_aug2 = process_query_intent("sales on August 2")
        self.assertIn("2026-08-02", q_aug2["data_scope"])
        self.assertIn("13,600.00", q_aug2["context_summary"])

    def test_08_bidirectional_switching(self):
        # 1. Switch to Demo
        ActiveDatasetManager.activate_dataset("demo")
        demo_meta = ActiveDatasetManager.get_active_dataset()
        self.assertEqual(demo_meta["dataset_id"], "demo")
        self.assertEqual(demo_meta["store_count"], 5)
        self.assertEqual(demo_meta["product_count"], 40)
        
        demo_stores = query_all("SELECT * FROM stores")
        self.assertEqual(len(demo_stores), 5)
        demo_inv = get_inventory_status_df()
        self.assertEqual(len(demo_inv), 200)

        # 2. Switch back to Dataset 2
        ActiveDatasetManager.activate_dataset(CUSTOM_DS_ID)
        ds2_meta = ActiveDatasetManager.get_active_dataset()
        self.assertEqual(ds2_meta["dataset_id"], CUSTOM_DS_ID)
        self.assertEqual(ds2_meta["store_count"], 2)
        self.assertEqual(ds2_meta["product_count"], 5)
        self.assertEqual(ds2_meta["inventory_count"], 10)

        ds2_stores = query_all("SELECT * FROM stores")
        self.assertEqual(len(ds2_stores), 2)
        ds2_inv = get_inventory_status_df()
        self.assertEqual(len(ds2_inv), 10)

if __name__ == "__main__":
    unittest.main()
