import os
import sqlite3
import pandas as pd
from typing import Optional

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "retail.sqlite")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def get_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(force: bool = False):
    """
    Initializes SQLite tables from CSV files if not initialized or forced.
    Zero external server dependency. Works immediately.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Check if tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sales'")
    table_exists = cursor.fetchone() is not None

    if table_exists and not force:
        conn.close()
        return

    print("Initializing SQLite database from CSV data...")

    stores_csv = os.path.join(DATA_DIR, "stores.csv")
    products_csv = os.path.join(DATA_DIR, "products.csv")
    inventory_csv = os.path.join(DATA_DIR, "inventory.csv")
    sales_csv = os.path.join(DATA_DIR, "sales.csv")

    if not os.path.exists(stores_csv):
        # Auto generate if CSV missing
        from data.generate_data import generate_retail_dataset
        generate_retail_dataset()

    df_stores = pd.read_csv(stores_csv)
    df_products = pd.read_csv(products_csv)
    df_inventory = pd.read_csv(inventory_csv)
    df_sales = pd.read_csv(sales_csv)

    # Write to SQLite
    df_stores.to_sql("stores", conn, if_exists="replace", index=False)
    df_products.to_sql("products", conn, if_exists="replace", index=False)
    df_inventory.to_sql("inventory", conn, if_exists="replace", index=False)
    df_sales.to_sql("sales", conn, if_exists="replace", index=False)

    # Create indexes for fast querying
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_store ON sales(store_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_product ON inventory(product_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_store ON inventory(store_id)")

    conn.commit()
    conn.close()
    print("SQLite database initialized successfully.")

def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Executes SQL query and returns result as a pandas DataFrame."""
    conn = get_connection()
    try:
        df = pd.read_sql_query(sql, conn, params=params)
        return df
    finally:
        conn.close()

def query_one(sql: str, params: tuple = ()) -> Optional[dict]:
    """Executes SQL query and returns single row dictionary or None."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()

def query_all(sql: str, params: tuple = ()) -> list[dict]:
    """Executes SQL query and returns list of row dictionaries."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
