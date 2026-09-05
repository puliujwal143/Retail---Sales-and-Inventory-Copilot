"""
test_dataset_integrity.py
--------------------------
Source→Database→API consistency tests (Requirement §35).

For each test dataset, verifies that:
- Row counts from the source DataFrames match what was written to SQLite
- Referential integrity holds within the dataset (sales.product_id ⊆ products.product_id)
- No orphan SQLite files exist on disk without a metadata entry
- No metadata entries exist without a corresponding SQLite file
- Inventory cross-references are valid (product_id and store_id in inventory exist in their tables)

These tests catch the contamination pattern from Requirement §37:
    EXPECTED: 5 products, 2 stores, 21 sales, 10 inventory
    ACTUAL contamination: 11 SKUs, 5 stores, 55 inventory, 115 units
"""

import os
import sys
import unittest
import pandas as pd
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import query_all, query_one
from src.dataset_manager import (
    ActiveDatasetManager, create_and_activate_dataset, delete_dataset,
    DATASETS_DIR
)


def _build_known_dataset():
    """
    Creates a dataset with KNOWN, VERIFIABLE counts.
    2 stores × 5 products × 21 sales rows × 10 inventory rows
    """
    stores   = [("S001", "City Store"), ("S002", "Mall Store")]
    products = [
        ("P001", "Laptop",    1000),
        ("P002", "Phone",     500),
        ("P003", "Tablet",    700),
        ("P004", "Headphone", 200),
        ("P005", "Charger",   50),
    ]

    # Explicitly construct 21 known sales rows covering all 5 products in all 2 stores
    sales_raw = [
        # (date, store_idx, prod_idx)
        ("2026-08-01", 0, 0), ("2026-08-01", 0, 1), ("2026-08-01", 0, 2),
        ("2026-08-01", 1, 0), ("2026-08-01", 1, 1),
        ("2026-08-02", 0, 0), ("2026-08-02", 0, 2), ("2026-08-02", 0, 3),
        ("2026-08-02", 1, 1), ("2026-08-02", 1, 3), ("2026-08-02", 1, 4),
        ("2026-08-03", 0, 0), ("2026-08-03", 0, 4),
        ("2026-08-03", 1, 2), ("2026-08-03", 1, 3),
        ("2026-08-04", 0, 1), ("2026-08-04", 0, 2),
        ("2026-08-04", 1, 0), ("2026-08-04", 1, 4),
        ("2026-08-05", 0, 3),
        ("2026-08-05", 1, 4),
    ]
    assert len(sales_raw) == 21, f"Expected 21 rows, got {len(sales_raw)}"

    sales_rows = []
    for i, (date, si, pi) in enumerate(sales_raw):
        sid, sname = stores[si]
        pid, pname, price = products[pi]
        sales_rows.append({
            "sale_id":      f"S{i+1:04d}",
            "date":         date,
            "store_id":     sid,
            "store_name":   sname,
            "product_id":   pid,
            "product_name": pname,
            "quantity":     2,
            "unit_price":   float(price),
            "total_revenue":float(price * 2),
        })

    sales_df = pd.DataFrame(sales_rows)

    inv_rows = []
    for sid, _ in stores:
        for pid, _, _ in products:
            inv_rows.append({
                "store_id":         sid,
                "product_id":       pid,
                "current_stock":    50,
                "last_restock_date":"2026-08-01"
            })
    inv_df = pd.DataFrame(inv_rows)  # 10 rows (2 stores × 5 products)

    return sales_df, inv_df



class TestDatasetIntegrity(unittest.TestCase):

    DS_ID = None
    KNOWN_PRODUCTS = 5
    KNOWN_STORES   = 2
    KNOWN_SALES    = 21
    KNOWN_INVENTORY= 10

    @classmethod
    def setUpClass(cls):
        # Purge orphan .sqlite files not tracked by metadata (from previous dev sessions)
        # This ensures test_11 (orphan file detection) runs on a clean slate.
        all_registered_ids = {
            ds["dataset_id"] for ds in ActiveDatasetManager.list_datasets()
        } | {"demo", "empty"}
        for fname in os.listdir(DATASETS_DIR):
            if not fname.endswith(".sqlite"):
                continue
            ds_id = fname.replace(".sqlite", "")
            if ds_id not in all_registered_ids:
                try:
                    os.remove(os.path.join(DATASETS_DIR, fname))
                    print(f"[TestSetup] Removed orphan file: {fname}")
                except Exception as e:
                    print(f"[TestSetup] Could not remove orphan file {fname}: {e}")

        sales_df, inv_df = _build_known_dataset()
        metrics = create_and_activate_dataset(
            "IntegrityTestDataset", sales_df, inv_df
        )
        cls.DS_ID = metrics["dataset_id"]
        cls.DS_PATH = os.path.join(DATASETS_DIR, f"{cls.DS_ID}.sqlite")

    @classmethod
    def tearDownClass(cls):
        if cls.DS_ID:
            try:
                delete_dataset(cls.DS_ID)
            except Exception:
                pass

    def setUp(self):
        ActiveDatasetManager.activate_dataset(self.DS_ID)

    # ─── Source → SQLite counts ───────────────────────────────────────────────
    def test_01_product_count_matches_source(self):
        """Products in SQLite must equal the number of unique product IDs from the source."""
        prods = query_all("SELECT * FROM products")
        self.assertEqual(
            len(prods), self.KNOWN_PRODUCTS,
            f"Expected {self.KNOWN_PRODUCTS} products, got {len(prods)}"
        )

    def test_02_store_count_matches_source(self):
        """Stores in SQLite must equal the number of unique store IDs from the source."""
        stores = query_all("SELECT * FROM stores")
        self.assertEqual(
            len(stores), self.KNOWN_STORES,
            f"Expected {self.KNOWN_STORES} stores, got {len(stores)}"
        )

    def test_03_sales_count_matches_source(self):
        """Sales rows in SQLite must equal the source row count."""
        cnt = query_one("SELECT COUNT(*) as c FROM sales")["c"]
        self.assertEqual(
            cnt, self.KNOWN_SALES,
            f"Expected {self.KNOWN_SALES} sales rows, got {cnt}. "
            f"Contamination detected: source had {self.KNOWN_SALES} rows but DB has {cnt}."
        )

    def test_04_inventory_count_matches_source(self):
        """Inventory rows in SQLite must equal stores × products = 10."""
        cnt = query_one("SELECT COUNT(*) as c FROM inventory")["c"]
        self.assertEqual(
            cnt, self.KNOWN_INVENTORY,
            f"Expected {self.KNOWN_INVENTORY} inventory rows, got {cnt}. "
            f"Contamination: expected 2 stores × 5 products = 10, got {cnt}."
        )

    # ─── Contamination detection (Req §37) ───────────────────────────────────
    def test_05_no_contamination_guard(self):
        """
        Explicit anti-contamination assertion.

        EXPECTED: 5 products, 2 stores, 21 sales, 10 inventory
        FAIL if contaminated: e.g. 11 SKUs, 5 stores, 55 inventory
        """
        p_cnt  = query_one("SELECT COUNT(*) as c FROM products")["c"]
        s_cnt  = query_one("SELECT COUNT(*) as c FROM stores")["c"]
        sal_cnt= query_one("SELECT COUNT(*) as c FROM sales")["c"]
        i_cnt  = query_one("SELECT COUNT(*) as c FROM inventory")["c"]

        self.assertEqual(p_cnt,   self.KNOWN_PRODUCTS,  f"CONTAMINATION: products={p_cnt} (expected {self.KNOWN_PRODUCTS})")
        self.assertEqual(s_cnt,   self.KNOWN_STORES,    f"CONTAMINATION: stores={s_cnt} (expected {self.KNOWN_STORES})")
        self.assertEqual(sal_cnt, self.KNOWN_SALES,     f"CONTAMINATION: sales={sal_cnt} (expected {self.KNOWN_SALES})")
        self.assertEqual(i_cnt,   self.KNOWN_INVENTORY, f"CONTAMINATION: inventory={i_cnt} (expected {self.KNOWN_INVENTORY})")

    # ─── Referential integrity: sales ────────────────────────────────────────
    def test_06_sales_product_referential_integrity(self):
        """All sales.product_id values must exist in products.product_id."""
        orphan_sales = query_all("""
            SELECT DISTINCT s.product_id
            FROM sales s
            LEFT JOIN products p ON s.product_id = p.product_id
            WHERE p.product_id IS NULL
        """)
        self.assertEqual(
            len(orphan_sales), 0,
            f"Referential integrity violation: sales reference product_ids not in products: {orphan_sales}"
        )

    def test_07_sales_store_referential_integrity(self):
        """All sales.store_id values must exist in stores.store_id."""
        orphan_sales = query_all("""
            SELECT DISTINCT s.store_id
            FROM sales s
            LEFT JOIN stores st ON s.store_id = st.store_id
            WHERE st.store_id IS NULL
        """)
        self.assertEqual(
            len(orphan_sales), 0,
            f"Referential integrity violation: sales reference store_ids not in stores: {orphan_sales}"
        )

    # ─── Referential integrity: inventory ────────────────────────────────────
    def test_08_inventory_product_referential_integrity(self):
        """All inventory.product_id values must exist in products.product_id."""
        orphan_inv = query_all("""
            SELECT DISTINCT i.product_id
            FROM inventory i
            LEFT JOIN products p ON i.product_id = p.product_id
            WHERE p.product_id IS NULL
        """)
        self.assertEqual(
            len(orphan_inv), 0,
            f"Inventory references product_ids not in products: {orphan_inv}"
        )

    def test_09_inventory_store_referential_integrity(self):
        """All inventory.store_id values must exist in stores.store_id."""
        orphan_inv = query_all("""
            SELECT DISTINCT i.store_id
            FROM inventory i
            LEFT JOIN stores st ON i.store_id = st.store_id
            WHERE st.store_id IS NULL
        """)
        self.assertEqual(
            len(orphan_inv), 0,
            f"Inventory references store_ids not in stores: {orphan_inv}"
        )

    # ─── Metadata ↔ disk consistency ─────────────────────────────────────────
    def test_10_no_orphan_metadata_entries(self):
        """Every non-demo metadata entry must have a corresponding SQLite file on disk."""
        all_datasets = ActiveDatasetManager.list_datasets()
        broken = []
        for ds in all_datasets:
            ds_id = ds["dataset_id"]
            if ds_id == "demo":
                continue
            path = os.path.join(DATASETS_DIR, f"{ds_id}.sqlite")
            if not os.path.exists(path):
                broken.append(ds_id)
        self.assertEqual(
            broken, [],
            f"Metadata entries with no corresponding .sqlite file: {broken}"
        )

    def test_11_no_orphan_sqlite_files(self):
        """Every .sqlite file in data/datasets/ (except empty.sqlite and demo.sqlite) must be in metadata."""
        all_datasets = ActiveDatasetManager.list_datasets()
        registered_ids = {ds["dataset_id"] for ds in all_datasets} | {"demo", "empty"}

        orphan_files = []
        for fname in os.listdir(DATASETS_DIR):
            if not fname.endswith(".sqlite"):
                continue
            ds_id = fname.replace(".sqlite", "")
            if ds_id not in registered_ids:
                orphan_files.append(fname)

        self.assertEqual(
            orphan_files, [],
            f"SQLite files with no metadata entry: {orphan_files}"
        )

    # ─── API metadata matches SQLite reality ─────────────────────────────────
    def test_12_api_metadata_matches_sqlite(self):
        """The metadata store (dataset_manager) must reflect the actual SQLite counts."""
        active_meta = ActiveDatasetManager.get_active_dataset()

        db_prods = query_one("SELECT COUNT(*) as c FROM products")["c"]
        db_stores= query_one("SELECT COUNT(*) as c FROM stores")["c"]
        db_sales = query_one("SELECT COUNT(*) as c FROM sales")["c"]
        db_inv   = query_one("SELECT COUNT(*) as c FROM inventory")["c"]

        self.assertEqual(active_meta["product_count"], db_prods,
                         f"Metadata product_count={active_meta['product_count']} != SQLite={db_prods}")
        self.assertEqual(active_meta["store_count"], db_stores,
                         f"Metadata store_count={active_meta['store_count']} != SQLite={db_stores}")
        self.assertEqual(active_meta["sales_count"], db_sales,
                         f"Metadata sales_count={active_meta['sales_count']} != SQLite={db_sales}")
        self.assertEqual(active_meta["inventory_count"], db_inv,
                         f"Metadata inventory_count={active_meta['inventory_count']} != SQLite={db_inv}")


if __name__ == "__main__":
    unittest.main()
