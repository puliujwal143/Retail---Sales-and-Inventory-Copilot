"""
test_dataset_isolation.py
--------------------------
Verifies that every analytics layer (inventory, dashboard, copilot, store comparison)
reads ONLY from the currently active dataset, with zero contamination from any other
dataset including the demo.

All test data is self-created in setUpClass() — no reliance on pre-existing disk state.
"""

import os
import sys
import unittest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import query_all, query_one
from src.dataset_manager import (
    ActiveDatasetManager, create_and_activate_dataset,
    get_active_dataset_latest_date
)
from src.inventory_rules import get_inventory_status_df
from src.sales_rules import get_yearly_performance, get_daily_sales_trend, compare_stores_analytics
from src.analytics import get_dashboard_summary
from src.query_engine import process_query_intent


def _make_sales_df(stores, products, dates_units_revenue):
    """
    Builds a minimal sales DataFrame.
    stores:  [(store_id, store_name), ...]
    products: [(product_id, product_name, price), ...]
    dates_units_revenue: list of (date, store_id, product_id, qty, revenue)
    """
    rows = []
    for i, (date, sid, pid, qty, rev) in enumerate(dates_units_revenue):
        rows.append({
            "sale_id": f"T{i+1:04d}",
            "date": date,
            "store_id": sid,
            "store_name": next(s[1] for s in stores if s[0] == sid),
            "product_id": pid,
            "product_name": next(p[1] for p in products if p[0] == pid),
            "quantity": qty,
            "unit_price": next(p[2] for p in products if p[0] == pid),
            "total_revenue": rev,
        })
    return pd.DataFrame(rows)


def _make_inventory_df(stores, products, stock_map):
    """
    stock_map: {(store_id, product_id): current_stock}
    """
    rows = []
    for (sid, pid), stock in stock_map.items():
        rows.append({
            "store_id": sid,
            "product_id": pid,
            "current_stock": stock,
            "last_restock_date": "2026-08-01"
        })
    return pd.DataFrame(rows)


# ─── Fixture definition ───────────────────────────────────────────────────────
# Dataset has exactly: 2 stores, 5 products, 21 sales rows, 10 inventory rows
STORES = [("S001", "City Store"), ("S002", "Mall Store")]
PRODUCTS = [
    ("P001", "Fast Selling Phone", 5000),
    ("P002", "Slow Selling TV", 20000),
    ("P003", "Popular Headphones", 2000),
    ("P004", "Old Keyboard", 500),
    ("P005", "Water Bottle", 200),
]

# 21 sales rows across 5 dates
SALES_ROWS = [
    # date         sid     pid     qty  rev
    ("2026-08-01", "S001", "P001", 10, 50000),
    ("2026-08-01", "S001", "P003", 5,  10000),
    ("2026-08-01", "S002", "P005", 2,  400),
    ("2026-08-01", "S002", "P002", 1,  20000),
    ("2026-08-01", "S001", "P004", 3,  1500),
    ("2026-08-02", "S001", "P001", 8,  40000),
    ("2026-08-02", "S002", "P003", 3,  6000),
    ("2026-08-02", "S001", "P002", 1,  20000),
    ("2026-08-02", "S002", "P004", 2,  1000),
    ("2026-08-02", "S002", "P005", 5,  1000),
    ("2026-08-02", "S001", "P005", 4,  800),
    ("2026-08-03", "S001", "P001", 6,  30000),
    ("2026-08-03", "S002", "P003", 2,  4000),
    ("2026-08-03", "S001", "P004", 1,  500),
    ("2026-08-04", "S001", "P003", 4,  8000),
    ("2026-08-04", "S002", "P001", 2,  10000),
    ("2026-08-04", "S001", "P002", 1,  20000),
    ("2026-08-05", "S001", "P003", 5,  10000),
    ("2026-08-05", "S002", "P004", 1,  500),
    ("2026-08-05", "S001", "P005", 3,  600),
    ("2026-08-05", "S002", "P001", 2,  10000),
]

# 10 inventory rows (2 stores × 5 products)
INVENTORY_MAP = {
    ("S001", "P001"): 5,
    ("S001", "P002"): 50,
    ("S001", "P003"): 100,
    ("S001", "P004"): 80,
    ("S001", "P005"): 120,
    ("S002", "P001"): 8,
    ("S002", "P002"): 60,
    ("S002", "P003"): 40,
    ("S002", "P004"): 45,
    ("S002", "P005"): 30,
}

EXPECTED_TOTAL_REVENUE = sum(r[4] for r in SALES_ROWS)   # 243300.0
EXPECTED_TOTAL_UNITS   = sum(r[3] for r in SALES_ROWS)   # 70
EXPECTED_TOTAL_STOCK   = sum(INVENTORY_MAP.values())       # 538

DEMO_NAMES = [
    "Pro Laptop 15-inch", "Ultra Slim Notebook 13", "Wireless Ergonomic Mouse",
    "Wireless Document Scanner", "Downtown Flagship", "Metro Hub Store",
    "Westside Plaza", "North Park Outlet", "Airport Express"
]


class TestDatasetIsolation(unittest.TestCase):

    FIXTURE_DS_ID = None   # set in setUpClass

    @classmethod
    def setUpClass(cls):
        """Create a controlled fixture dataset and activate it."""
        try:
            sales_df = _make_sales_df(STORES, PRODUCTS, SALES_ROWS)
            inv_df   = _make_inventory_df(STORES, PRODUCTS, INVENTORY_MAP)
            metrics  = create_and_activate_dataset(
                dataset_name="IsolationTestDataset",
                sales_df=sales_df,
                inventory_df=inv_df,
            )
            cls.FIXTURE_DS_ID = metrics["dataset_id"]
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise

    @classmethod
    def tearDownClass(cls):
        """Delete the fixture dataset after tests complete."""
        if cls.FIXTURE_DS_ID:
            try:
                ActiveDatasetManager.delete_dataset(cls.FIXTURE_DS_ID)
            except Exception:
                pass

    def setUp(self):
        """Ensure the fixture dataset is active before each test."""
        ActiveDatasetManager.activate_dataset(self.FIXTURE_DS_ID)

    # ─── Test 01: Metadata matches fixture ───────────────────────────────────
    def test_01_active_dataset_metadata(self):
        active = ActiveDatasetManager.get_active_dataset()
        self.assertEqual(active["dataset_id"], self.FIXTURE_DS_ID)
        self.assertEqual(active["store_count"], 2)
        self.assertEqual(active["product_count"], 5)
        self.assertEqual(active["sales_count"], 21)
        self.assertEqual(active["inventory_count"], 10)
        self.assertEqual(active["total_stock_units"], EXPECTED_TOTAL_STOCK)
        self.assertEqual(active["min_date"], "2026-08-01")
        self.assertEqual(active["max_date"], "2026-08-05")
        self.assertEqual(get_active_dataset_latest_date(), "2026-08-05")

    # ─── Test 02: DB tables contain only fixture data ────────────────────────
    def test_02_database_stores_and_products(self):
        stores = query_all("SELECT * FROM stores")
        self.assertEqual(len(stores), 2)
        store_names = [s["store_name"] for s in stores]
        self.assertIn("City Store", store_names)
        self.assertIn("Mall Store", store_names)

        products = query_all("SELECT * FROM products")
        self.assertEqual(len(products), 5)
        prod_names = [p["product_name"] for p in products]
        for expected_name in ["Fast Selling Phone", "Slow Selling TV",
                               "Popular Headphones", "Old Keyboard", "Water Bottle"]:
            self.assertIn(expected_name, prod_names)

        # No demo entities must appear
        for demo_name in DEMO_NAMES:
            self.assertNotIn(demo_name, store_names)
            self.assertNotIn(demo_name, prod_names)

    # ─── Test 03: Inventory status uses only fixture data ────────────────────
    def test_03_inventory_status_isolation(self):
        inv_df = get_inventory_status_df()
        self.assertEqual(len(inv_df), 10, f"Expected 10 inventory rows, got {len(inv_df)}")

        inv_prod_names  = inv_df["product_name"].tolist()
        inv_store_names = inv_df["store_name"].tolist()

        for demo_name in DEMO_NAMES:
            self.assertNotIn(demo_name, inv_prod_names)
            self.assertNotIn(demo_name, inv_store_names)

        total_stock = int(inv_df["current_stock"].sum())
        self.assertEqual(total_stock, EXPECTED_TOTAL_STOCK,
                         f"Expected total stock {EXPECTED_TOTAL_STOCK}, got {total_stock}")

    # ─── Test 04: Dashboard reads only fixture dataset ───────────────────────
    def test_04_dashboard_summary_isolation(self):
        dash = get_dashboard_summary()
        self.assertEqual(dash["total_transactions"], 21)
        self.assertEqual(dash["total_inventory_records"], 10)
        self.assertEqual(dash["total_inventory_units"], EXPECTED_TOTAL_STOCK)
        self.assertEqual(len(dash["store_performance"]), 2)

        for p in dash["top_products"]:
            self.assertNotIn(p["product_name"], DEMO_NAMES)

    # ─── Test 05: Sales rules use fixture dates / scope ──────────────────────
    def test_05_sales_rules_isolation(self):
        yearly = get_yearly_performance()
        years = [row["year"] for row in yearly.get("yearly_table", [])]
        self.assertEqual(years, ["2026"])

        daily_trend = get_daily_sales_trend(30)
        trend_dates = [d["date"] for d in daily_trend]
        self.assertEqual(len(trend_dates), 5)
        self.assertEqual(trend_dates[0], "2026-08-01")
        self.assertEqual(trend_dates[-1], "2026-08-05")

    # ─── Test 06: Store comparison uses fixture stores ───────────────────────
    def test_06_store_comparison_isolation(self):
        comp = compare_stores_analytics(store_ids=["S001", "S002"], time_days=30)
        self.assertEqual(comp["stores_count"], 2)
        comp_store_names = [s["store_name"] for s in comp.get("comparison_table", [])]
        self.assertIn("City Store", comp_store_names)
        self.assertIn("Mall Store", comp_store_names)
        for demo_name in DEMO_NAMES:
            self.assertNotIn(demo_name, comp_store_names)

    # ─── Test 07: Copilot uses fixture context ───────────────────────────────
    def test_07_copilot_queries_scope(self):
        q_stores = process_query_intent("How many stores do I have?")
        self.assertIn(q_stores.get("intent", ""), [
            "STORE_COUNT", "DATASET_METADATA", "STORE_LIST"
        ])
        ctx = q_stores.get("context_summary", "")
        self.assertIn("2", ctx)  # 2 stores mentioned

        q_prods = process_query_intent("How many products do I have?")
        self.assertIn(q_prods.get("intent", ""), [
            "PRODUCT_COUNT", "DATASET_METADATA", "PRODUCT_LIST"
        ])
        ctx2 = q_prods.get("context_summary", "")
        self.assertIn("5", ctx2)  # 5 products

    # ─── Test 08: Bidirectional switching Demo ↔ Fixture ─────────────────────
    def test_08_bidirectional_switching(self):
        # 1. Switch to Demo
        ActiveDatasetManager.activate_dataset("demo")
        demo_meta = ActiveDatasetManager.get_active_dataset()
        self.assertEqual(demo_meta["dataset_id"], "demo")
        # Demo has more than 2 stores and more than 5 products
        self.assertGreater(demo_meta["store_count"], 2)
        self.assertGreater(demo_meta["product_count"], 5)

        demo_stores = query_all("SELECT * FROM stores")
        self.assertGreater(len(demo_stores), 2)

        # 2. Switch back to fixture
        ActiveDatasetManager.activate_dataset(self.FIXTURE_DS_ID)
        ds2_meta = ActiveDatasetManager.get_active_dataset()
        self.assertEqual(ds2_meta["dataset_id"], self.FIXTURE_DS_ID)
        self.assertEqual(ds2_meta["store_count"], 2)
        self.assertEqual(ds2_meta["product_count"], 5)
        self.assertEqual(ds2_meta["inventory_count"], 10)

        ds2_stores = query_all("SELECT * FROM stores")
        self.assertEqual(len(ds2_stores), 2)
        ds2_inv = get_inventory_status_df()
        self.assertEqual(len(ds2_inv), 10)


if __name__ == "__main__":
    unittest.main()
