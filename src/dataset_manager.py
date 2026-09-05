import os
import json
import uuid
import shutil
import sqlite3
import datetime
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATASETS_DIR = os.path.join(DATA_DIR, "datasets")
METADATA_FILE = os.path.join(DATASETS_DIR, "datasets_metadata.json")

# Invalidation callback list
_INVALIDATION_CALLBACKS = []

def register_invalidation_callback(cb):
    """Registers a callback function to be called when the active dataset changes."""
    if cb not in _INVALIDATION_CALLBACKS:
        _INVALIDATION_CALLBACKS.append(cb)

def _trigger_invalidation():
    """Triggers all registered cache / memory invalidation callbacks."""
    for cb in _INVALIDATION_CALLBACKS:
        try:
            cb()
        except Exception as e:
            print(f"Error in dataset invalidation callback: {e}")

class ActiveDatasetManager:
    """
    Single Source of Truth for the Active RetailIQ Dataset.
    Manages isolated SQLite database files per dataset with atomic switching and rollback.
    Default state on clean start: None (NO_DATA).
    """
    _instance = None
    _active_dataset_id = None
    _metadata = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._init_storage()
        return cls._instance

    def _ensure_empty_db(self) -> str:
        """Ensures a schema-initialized 0-row SQLite template exists for NO_DATA state."""
        empty_path = os.path.join(DATASETS_DIR, "empty.sqlite")
        if not os.path.exists(empty_path):
            conn = sqlite3.connect(empty_path)
            c = conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS stores (store_id TEXT PRIMARY KEY, store_name TEXT, location TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS products (product_id TEXT PRIMARY KEY, product_name TEXT, category TEXT, unit_price REAL, cost_price REAL)")
            c.execute("CREATE TABLE IF NOT EXISTS inventory (store_id TEXT, product_id TEXT, current_stock INTEGER, reorder_point INTEGER, safety_stock INTEGER, last_restock_date TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS sales (sale_id TEXT PRIMARY KEY, store_id TEXT, product_id TEXT, date TEXT, quantity INTEGER, unit_price REAL, total_revenue REAL)")
            c.execute("CREATE TABLE IF NOT EXISTS inventory_movements (movement_id TEXT PRIMARY KEY, date TEXT, store_id TEXT, product_id TEXT, movement_type TEXT, quantity INTEGER)")
            conn.commit()
            conn.close()
        return empty_path

    def _init_storage(self):
        """Initializes datasets storage directory and metadata file."""
        os.makedirs(DATASETS_DIR, exist_ok=True)
        self._ensure_empty_db()

        if os.path.exists(METADATA_FILE):
            try:
                with open(METADATA_FILE, "r", encoding="utf-8") as f:
                    self._metadata = json.load(f)
                    self._active_dataset_id = self._metadata.get("active_dataset_id", None)
            except Exception as e:
                print(f"Error reading datasets metadata: {e}")
                self._metadata = {"active_dataset_id": None, "datasets": {}}
        else:
            self._metadata = {"active_dataset_id": None, "datasets": {}}

        # Sync metadata and disk: remove broken references only
        self._purge_orphans_on_startup()
        self._save_metadata()

    def _purge_orphans_on_startup(self):
        """
        Syncs metadata and disk on startup for Single Active Dataset model:
        - Keeps demo dataset metadata and file.
        - If an active custom dataset is set and its file exists, keeps it.
        - Removes any non-active custom datasets from metadata and disk so active storage contains only 1 active dataset.
        - If active dataset file is missing, resets to NO_DATA.
        """
        raw_datasets = self._metadata.get("datasets", {})
        cleaned_datasets = {}
        for ds_id, ds in raw_datasets.items():
            if ds_id == "demo":
                cleaned_datasets[ds_id] = ds
                continue
            sqlite_file = os.path.join(DATASETS_DIR, f"{ds_id}.sqlite")
            if os.path.exists(sqlite_file):
                cleaned_datasets[ds_id] = ds
            else:
                print(f"[RetailIQ] Purging orphaned metadata entry '{ds_id}' (file missing).")
                if ds_id == self._active_dataset_id:
                    print(f"[RetailIQ] Active dataset '{ds_id}' file missing — resetting to NO_DATA.")
                    self._active_dataset_id = None

        # Clean up stray unreferenced sqlite files
        registered_files = {f"{ds_id}.sqlite" for ds_id in cleaned_datasets.keys()}
        registered_files.add("demo.sqlite")
        registered_files.add("empty.sqlite")

        if os.path.exists(DATASETS_DIR):
            for fname in os.listdir(DATASETS_DIR):
                if fname.endswith(".sqlite") and fname not in registered_files and not fname.startswith("staging_"):
                    try:
                        os.remove(os.path.join(DATASETS_DIR, fname))
                    except Exception:
                        pass

        self._metadata["datasets"] = cleaned_datasets

    def _save_metadata(self):
        """Persists metadata to disk."""
        try:
            self._metadata["active_dataset_id"] = self._active_dataset_id
            with open(METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self._metadata, f, indent=2)
        except Exception as e:
            print(f"Error saving datasets metadata: {e}")

    @classmethod
    def get_active_dataset_id(cls) -> Optional[str]:
        inst = cls.get_instance()
        return inst._active_dataset_id

    @classmethod
    def get_active_db_path(cls) -> str:
        """Returns the absolute file path to the active SQLite database."""
        inst = cls.get_instance()
        ds_id = inst._active_dataset_id
        if not ds_id or ds_id in ["none", "null"]:
            return inst._ensure_empty_db()

        if ds_id == "demo":
            demo_path = os.path.join(DATASETS_DIR, "demo.sqlite")
            if os.path.exists(demo_path):
                return demo_path
            # Fallback to root retail.sqlite if demo.sqlite not created yet
            root_db = os.path.join(os.path.dirname(DATA_DIR), "retail.sqlite")
            if os.path.exists(root_db):
                return root_db
            return inst._ensure_empty_db()
        
        target_path = os.path.join(DATASETS_DIR, f"{ds_id}.sqlite")
        if os.path.exists(target_path):
            return target_path
        
        # If target file missing, fallback to None (NO_DATA)
        print(f"Active dataset {ds_id} not found on disk, resetting to NO_DATA.")
        inst._active_dataset_id = None
        inst._save_metadata()
        _trigger_invalidation()
        return inst._ensure_empty_db()

    @classmethod
    def get_active_dataset(cls) -> Dict[str, Any]:
        """Returns full metadata for the currently active dataset."""
        inst = cls.get_instance()
        ds_id = inst._active_dataset_id
        if not ds_id or ds_id in ["none", "null"]:
            return {
                "dataset_id": None,
                "dataset_name": "No Dataset Active",
                "status": "NO_DATA",
                "is_demo": False,
                "is_active": False,
                "store_count": 0,
                "product_count": 0,
                "sales_count": 0,
                "inventory_count": 0,
                "total_stock_units": 0,
                "min_date": None,
                "max_date": None,
                "total_revenue": 0.0,
                "total_units_sold": 0,
                "created_at": None
            }

        ds_info = inst._metadata.get("datasets", {}).get(ds_id)
        if not ds_info:
            ds_info = inst._compute_dataset_metrics(ds_id, cls.get_active_db_path(), is_demo=(ds_id == "demo"))
            if ds_info:
                inst._metadata.setdefault("datasets", {})[ds_id] = ds_info
                inst._save_metadata()

        if ds_info:
            res = dict(ds_info)
            res["status"] = "DEMO_ACTIVE" if ds_id == "demo" else "CUSTOM_ACTIVE"
            res["is_active"] = True
            return res

        return {
            "dataset_id": None,
            "dataset_name": "No Dataset Active",
            "status": "NO_DATA",
            "is_demo": False,
            "is_active": False,
            "store_count": 0,
            "product_count": 0,
            "sales_count": 0,
            "inventory_count": 0,
            "total_stock_units": 0,
            "min_date": None,
            "max_date": None,
            "total_revenue": 0.0,
            "total_units_sold": 0,
            "created_at": None
        }

    @classmethod
    def get_active_dataset_latest_date(cls) -> Optional[str]:
        """Returns the latest snapshot / transaction date in the active dataset."""
        inst = cls.get_instance()
        if not inst._active_dataset_id:
            return None
        meta = cls.get_active_dataset()
        if meta and meta.get("max_date"):
            return str(meta["max_date"])
        try:
            db_path = cls.get_active_db_path()
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("SELECT MAX(date) FROM sales")
            row = c.fetchone()
            if row and row[0]:
                conn.close()
                return str(row[0])
            c.execute("SELECT MAX(last_restock_date) FROM inventory")
            row = c.fetchone()
            conn.close()
            if row and row[0]:
                return str(row[0])
        except Exception:
            pass
        return None

    @classmethod
    def list_datasets(cls) -> List[Dict[str, Any]]:
        """Returns list of all registered datasets."""
        inst = cls.get_instance()
        active_id = inst._active_dataset_id
        result = []
        for ds_id, ds in inst._metadata.get("datasets", {}).items():
            item = dict(ds)
            item["is_active"] = (ds_id == active_id and active_id is not None)
            result.append(item)
        
        # Ensure demo is always present as an available option
        demo_dest = os.path.join(DATASETS_DIR, "demo.sqlite")
        root_db = os.path.join(os.path.dirname(DATA_DIR), "retail.sqlite")
        effective_demo = demo_dest if os.path.exists(demo_dest) else (root_db if os.path.exists(root_db) else None)
        
        if not any(d["dataset_id"] == "demo" for d in result) and effective_demo:
            demo_meta = inst._compute_dataset_metrics("demo", effective_demo, is_demo=True)
            if demo_meta:
                inst._metadata.setdefault("datasets", {})["demo"] = demo_meta
                inst._save_metadata()
                demo_meta["is_active"] = (active_id == "demo")
                result.insert(0, demo_meta)
        
        return sorted(result, key=lambda x: (not x.get("is_active", False), x.get("created_at", "")), reverse=False)

    @classmethod
    def activate_dataset(cls, dataset_id: Optional[str]) -> Dict[str, Any]:
        """Switches the active dataset, clears caches, and returns the new active dataset metadata."""
        inst = cls.get_instance()
        if not dataset_id or str(dataset_id).lower() in ["none", "null", ""]:
            inst._active_dataset_id = None
            inst._save_metadata()
            _trigger_invalidation()
            print("[RetailIQ] Active dataset set to: NO_DATA")
            return cls.get_active_dataset()

        if dataset_id != "demo":
            target_file = os.path.join(DATASETS_DIR, f"{dataset_id}.sqlite")
            if not os.path.exists(target_file):
                raise ValueError(f"Dataset '{dataset_id}' does not exist on disk.")
        
        inst._active_dataset_id = dataset_id
        inst._save_metadata()
        _trigger_invalidation()
        print(f"[RetailIQ] Switched active dataset to: {dataset_id}")
        return cls.get_active_dataset()

    @classmethod
    def clear_active_dataset(cls) -> Dict[str, Any]:
        """Clears the active dataset, resetting to NO_DATA."""
        return cls.activate_dataset(None)

    @classmethod
    def reset_to_demo(cls) -> Dict[str, Any]:
        """Explicitly activates the Demo Retail Dataset."""
        return cls.activate_dataset("demo")

    @classmethod
    def delete_dataset(cls, dataset_id: str) -> None:
        """
        Permanently deletes a dataset: removes its SQLite file and metadata entry.

        Rules:
        - 'demo' cannot be deleted.
        - If the deleted dataset is currently active, the state transitions to NO_DATA.
          It does NOT automatically fall back to demo or any other dataset.
        - Raises ValueError for invalid or protected dataset IDs.
        """
        if not dataset_id or dataset_id == "demo":
            raise ValueError("The demo dataset cannot be deleted.")

        inst = cls.get_instance()
        datasets = inst._metadata.get("datasets", {})

        if dataset_id not in datasets:
            # Still check if a stray file exists and clean it up
            stray_file = os.path.join(DATASETS_DIR, f"{dataset_id}.sqlite")
            if os.path.exists(stray_file):
                try:
                    os.remove(stray_file)
                except Exception as e:
                    print(f"[RetailIQ] Warning: could not remove stray file {stray_file}: {e}")
            raise ValueError(f"Dataset '{dataset_id}' not found in registry.")

        # If this is the currently active dataset, reset to NO_DATA first
        was_active = (inst._active_dataset_id == dataset_id)
        if was_active:
            inst._active_dataset_id = None
            print(f"[RetailIQ] Active dataset '{dataset_id}' is being deleted — transitioning to NO_DATA.")

        # Remove the SQLite file
        sqlite_file = os.path.join(DATASETS_DIR, f"{dataset_id}.sqlite")
        if os.path.exists(sqlite_file):
            try:
                os.remove(sqlite_file)
                print(f"[RetailIQ] Deleted dataset file: {sqlite_file}")
            except Exception as e:
                raise RuntimeError(f"Failed to delete dataset file '{sqlite_file}': {e}")

        # Remove metadata entry
        del inst._metadata["datasets"][dataset_id]
        inst._save_metadata()

        # Invalidate caches and frontend state
        _trigger_invalidation()
        print(f"[RetailIQ] Dataset '{dataset_id}' deleted successfully.")

    @classmethod
    def register_demo_dataset(cls, db_path: str):
        """Initializes or registers the default demo dataset without auto-activating it."""
        inst = cls.get_instance()
        demo_dest = os.path.join(DATASETS_DIR, "demo.sqlite")
        if not os.path.exists(demo_dest) and os.path.exists(db_path):
            try:
                shutil.copyfile(db_path, demo_dest)
            except Exception as e:
                print(f"Error copying demo database: {e}")
        
        effective_path = demo_dest if os.path.exists(demo_dest) else db_path
        metrics = inst._compute_dataset_metrics("demo", effective_path, is_demo=True)
        if metrics:
            inst._metadata.setdefault("datasets", {})["demo"] = metrics
            inst._save_metadata()

    def _compute_dataset_metrics(self, dataset_id: str, db_path: str, is_demo: bool = False, dataset_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Queries the SQLite file directly to calculate dataset statistics."""
        if not os.path.exists(db_path):
            return None
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            c.execute("SELECT COUNT(*) as cnt FROM stores")
            store_cnt = c.fetchone()["cnt"]

            c.execute("SELECT COUNT(*) as cnt FROM products")
            prod_cnt = c.fetchone()["cnt"]

            c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_revenue), 0) as rev, COALESCE(SUM(quantity), 0) as units, MIN(date) as min_d, MAX(date) as max_d FROM sales")
            sales_row = c.fetchone()
            sales_cnt = sales_row["cnt"]
            total_rev = round(float(sales_row["rev"]), 2)
            total_units = int(sales_row["units"])
            min_date = sales_row["min_d"] or "2026-01-01"
            max_date = sales_row["max_d"] or "2026-01-01"

            c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(current_stock), 0) as stock_units FROM inventory")
            inv_row = c.fetchone()
            inv_cnt = inv_row["cnt"]
            total_stock_units = int(inv_row["stock_units"])

            conn.close()

            name = dataset_name or ("Demo Retail Dataset" if is_demo else f"Custom Dataset ({dataset_id[:8]})")
            return {
                "dataset_id": dataset_id,
                "dataset_name": name,
                "is_demo": is_demo,
                "store_count": store_cnt,
                "product_count": prod_cnt,
                "sales_count": sales_cnt,
                "inventory_count": inv_cnt,
                "total_stock_units": total_stock_units,
                "min_date": min_date,
                "max_date": max_date,
                "total_revenue": total_rev,
                "total_units_sold": total_units,
                "created_at": datetime.datetime.now().isoformat()
            }
        except Exception as e:
            print(f"Error computing dataset metrics for {db_path}: {e}")
            return None

def get_active_dataset_id() -> str:
    return ActiveDatasetManager.get_active_dataset_id()

def get_active_dataset_db_path() -> str:
    return ActiveDatasetManager.get_active_db_path()

def get_active_dataset_metadata() -> Dict[str, Any]:
    return ActiveDatasetManager.get_active_dataset()

def get_active_dataset_latest_date() -> str:
    return ActiveDatasetManager.get_active_dataset_latest_date()

def delete_dataset(dataset_id: str) -> None:
    """Module-level convenience wrapper for ActiveDatasetManager.delete_dataset()."""
    ActiveDatasetManager.delete_dataset(dataset_id)



# ==============================================================================
# DATA NORMALIZATION & ATOMIC IMPORT ENGINE
# ==============================================================================

# Flexible column synonym maps for retail data
SYNONYM_MAPS = {
    "store_id": ["store_id", "storeid", "store", "store_code", "store_number", "store_no", "store id", "store code", "store_num"],
    "store_name": ["store_name", "storename", "store_title", "store", "name", "store name", "store title", "location_name"],
    "location": ["location", "city", "region", "address", "area", "zone", "state", "territory"],
    "square_feet": ["square_feet", "sqft", "sq_ft", "square_ft", "area_sqft", "size"],
    "opening_date": ["opening_date", "opened_date", "open_date", "start_date", "established_date"],

    "product_id": ["product_id", "productid", "product", "sku", "item_id", "itemid", "item_code", "product_code", "product id", "sku_code"],
    "product_name": ["product_name", "productname", "product_title", "product", "name", "item_name", "item", "title", "product name", "description"],
    "category": ["category", "dept", "department", "product_category", "product_group", "group", "family", "class"],
    "unit_price": ["unit_price", "unitprice", "price", "selling_price", "retail_price", "sale_price", "price_per_unit", "mrp", "rate"],
    "cost_price": ["cost_price", "costprice", "cost", "cogs", "wholesale_price", "purchase_price", "unit_cost"],
    "reorder_point": ["reorder_point", "reorderpoint", "min_stock", "safety_stock", "threshold", "reorder_level"],

    "current_stock": ["current_stock", "currentstock", "stock", "stock_on_hand", "quantity_on_hand", "qty_on_hand", "inventory", "stock_level", "units_in_stock", "stock_units", "quantity"],
    "last_restock_date": ["last_restock_date", "restock_date", "last_restocked", "restocked_on", "restock_date_last"],

    "sale_id": ["sale_id", "saleid", "transaction_id", "order_id", "receipt_id", "invoice_id", "txn_id", "id"],
    "date": ["date", "sale_date", "transaction_date", "order_date", "txn_date", "timestamp", "datetime", "invoice_date", "sales_date"],
    "quantity": ["quantity", "qty", "units", "units_sold", "volume", "quantity_sold", "sold_units", "count", "items_sold"],
    "total_revenue": ["total_revenue", "totalrevenue", "revenue", "sales", "total_amount", "amount", "total_sales", "total_price", "sales_amount", "line_total", "total"]
}

def _resolve_column(df_cols: List[str], target_field: str) -> Optional[str]:
    """Finds matching column in dataframe using synonym maps."""
    synonyms = SYNONYM_MAPS.get(target_field, [target_field])
    lower_map = {c.strip().lower().replace(" ", "_").replace("-", "_"): c for c in df_cols}
    for syn in synonyms:
        syn_clean = syn.lower().replace(" ", "_").replace("-", "_")
        if syn_clean in lower_map:
            return lower_map[syn_clean]
    return None

def validate_and_profile_retail_data(
    sales_df: Optional[pd.DataFrame] = None,
    inventory_df: Optional[pd.DataFrame] = None,
    products_df: Optional[pd.DataFrame] = None,
    stores_df: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """
    Profiles uploaded raw retail dataframes, detects column mappings, and performs non-destructive validation.
    Returns:
    - is_valid: bool
    - summary: Record counts, date bounds, total revenue, store/product counts
    - column_mappings: Detected internal mapping for each provided table
    - warnings: Non-fatal data quality notes (missing fields with auto-fallbacks)
    - errors: Fatal issues that prevent ingestion
    """
    errors: List[str] = []
    warnings: List[str] = []
    column_mappings: Dict[str, Dict[str, Optional[str]]] = {
        "sales": {},
        "inventory": {},
        "products": {},
        "stores": {}
    }

    if sales_df is None or sales_df.empty:
        errors.append("Sales dataset is missing or empty. At least one sales transaction table is required.")
        return {
            "is_valid": False,
            "errors": errors,
            "warnings": warnings,
            "summary": {},
            "column_mappings": column_mappings
        }

    # 1. Profile Sales Table
    s_cols = list(sales_df.columns)
    for field in ["date", "product_id", "product_name", "store_id", "store_name", "quantity", "unit_price", "total_revenue", "category"]:
        mapped = _resolve_column(s_cols, field)
        if mapped:
            column_mappings["sales"][field] = mapped

    # Check required sales fields
    if not column_mappings["sales"].get("date"):
        errors.append("Sales data is missing a valid transaction date column ('date', 'sale_date', 'transaction_date').")
    else:
        # Date parsing check
        date_col = column_mappings["sales"]["date"]
        parsed_dates = pd.to_datetime(sales_df[date_col], errors='coerce')
        nat_count = parsed_dates.isna().sum()
        if nat_count == len(sales_df):
            errors.append(f"All values in sales date column '{date_col}' could not be parsed. Expected YYYY-MM-DD or standard date format.")
        elif nat_count > 0:
            warnings.append(f"{nat_count:,} sales records have unparseable dates and will be assigned latest valid date.")

    if not column_mappings["sales"].get("product_id") and not column_mappings["sales"].get("product_name"):
        errors.append("Sales data must contain a product reference ('product_id', 'sku', or 'product_name').")

    if not column_mappings["sales"].get("quantity"):
        warnings.append("No explicit quantity column found in sales data; defaulting to 1 unit per transaction.")

    # 2. Profile Inventory Table (if provided)
    if inventory_df is not None and not inventory_df.empty:
        inv_cols = list(inventory_df.columns)
        for field in ["product_id", "store_id", "current_stock", "reorder_point", "last_restock_date"]:
            mapped = _resolve_column(inv_cols, field)
            if mapped:
                column_mappings["inventory"][field] = mapped
        if not column_mappings["inventory"].get("current_stock"):
            warnings.append("Inventory table missing 'current_stock' / 'quantity_on_hand' column; stock will be synthesized.")
    else:
        warnings.append("No separate inventory table uploaded; initial stock levels will be derived from sales and product catalog.")

    # 3. Profile Products Table (if provided)
    if products_df is not None and not products_df.empty:
        p_cols = list(products_df.columns)
        for field in ["product_id", "product_name", "category", "unit_price", "cost_price", "reorder_point"]:
            mapped = _resolve_column(p_cols, field)
            if mapped:
                column_mappings["products"][field] = mapped
    else:
        warnings.append("No separate products catalog uploaded; product IDs and categories will be extracted directly from sales records.")

    # 4. Profile Stores Table (if provided)
    if stores_df is not None and not stores_df.empty:
        st_cols = list(stores_df.columns)
        for field in ["store_id", "store_name", "location", "square_feet"]:
            mapped = _resolve_column(st_cols, field)
            if mapped:
                column_mappings["stores"][field] = mapped
    else:
        warnings.append("No separate stores table uploaded; store locations will be auto-discovered from sales records.")

    # Perform Dry-Run Normalization to compute verified summary metrics
    summary = {}
    if not errors:
        try:
            stores_norm, prods_norm, inv_norm, sales_norm, movs_norm = normalize_retail_data(
                sales_df=sales_df,
                inventory_df=inventory_df,
                products_df=products_df,
                stores_df=stores_df
            )
            summary = {
                "sales_count": int(len(sales_norm)),
                "products_count": int(len(prods_norm)),
                "stores_count": int(len(stores_norm)),
                "inventory_count": int(len(inv_norm)),
                "movements_count": int(len(movs_norm)),
                "min_date": str(sales_norm["date"].min()),
                "max_date": str(sales_norm["date"].max()),
                "total_revenue": round(float(sales_norm["total_revenue"].sum()), 2),
                "total_units": int(sales_norm["quantity"].sum()),
                "sample_stores": stores_norm["store_name"].head(5).tolist(),
                "sample_products": prods_norm["product_name"].head(5).tolist(),
                "sample_categories": prods_norm["category"].unique().tolist()[:6]
            }
        except Exception as e:
            errors.append(f"Validation dry-run error: {str(e)}")

    is_valid = len(errors) == 0

    return {
        "is_valid": is_valid,
        "summary": summary,
        "column_mappings": column_mappings,
        "warnings": warnings,
        "errors": errors
    }

def normalize_retail_data(
    sales_df: pd.DataFrame,
    inventory_df: Optional[pd.DataFrame] = None,
    products_df: Optional[pd.DataFrame] = None,
    stores_df: Optional[pd.DataFrame] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Normalizes arbitrary retail inputs into standard RetailIQ relational tables:
    (stores, products, inventory, sales, inventory_movements).
    Auto-derives missing entities, cleans types, formats dates, and synthesizes movements.
    """
    if sales_df is None or sales_df.empty:
        raise ValueError("Sales data is required and cannot be empty.")

    # 1. Normalize Sales DataFrame
    sales_norm = pd.DataFrame()
    
    # Date column
    col_date = _resolve_column(sales_df.columns, "date")
    if not col_date:
        raise ValueError("Sales data must contain a 'date' or 'transaction_date' column.")
    
    # Convert dates to YYYY-MM-DD
    sales_norm["date"] = pd.to_datetime(sales_df[col_date], errors='coerce').dt.strftime('%Y-%m-%d')
    if sales_norm["date"].isna().all():
        raise ValueError("Could not parse dates in sales data. Supported format: YYYY-MM-DD.")
    # Fill any NaT with max date
    max_d = sales_norm["date"].dropna().max() or datetime.date.today().strftime('%Y-%m-%d')
    sales_norm["date"] = sales_norm["date"].fillna(max_d)

    # Store ID & Product ID
    col_store_id = _resolve_column(sales_df.columns, "store_id")
    col_store_name = _resolve_column(sales_df.columns, "store_name")
    if col_store_id:
        sales_norm["store_id"] = sales_df[col_store_id].astype(str).str.strip()
    elif col_store_name:
        sales_norm["store_id"] = sales_df[col_store_name].astype(str).str.strip()
    else:
        sales_norm["store_id"] = "STR001"

    col_prod_id = _resolve_column(sales_df.columns, "product_id")
    col_prod_name = _resolve_column(sales_df.columns, "product_name")
    if col_prod_id:
        sales_norm["product_id"] = sales_df[col_prod_id].astype(str).str.strip()
    elif col_prod_name:
        sales_norm["product_id"] = sales_df[col_prod_name].astype(str).str.strip()
    else:
        sales_norm["product_id"] = "PRD001"

    # Quantity
    col_qty = _resolve_column(sales_df.columns, "quantity")
    if col_qty:
        sales_norm["quantity"] = pd.to_numeric(sales_df[col_qty], errors='coerce').fillna(1).astype(int)
    else:
        sales_norm["quantity"] = 1
    # Ensure positive quantity
    sales_norm["quantity"] = sales_norm["quantity"].apply(lambda q: max(1, abs(int(q))))

    # Unit Price & Total Revenue
    col_price = _resolve_column(sales_df.columns, "unit_price")
    col_rev = _resolve_column(sales_df.columns, "total_revenue")

    if col_rev and col_price:
        sales_norm["total_revenue"] = pd.to_numeric(sales_df[col_rev], errors='coerce').fillna(0.0).round(2)
        sales_norm["unit_price"] = pd.to_numeric(sales_df[col_price], errors='coerce').fillna(0.0).round(2)
    elif col_rev and not col_price:
        sales_norm["total_revenue"] = pd.to_numeric(sales_df[col_rev], errors='coerce').fillna(0.0).round(2)
        sales_norm["unit_price"] = (sales_norm["total_revenue"] / sales_norm["quantity"].replace(0, 1)).round(2)
    elif col_price and not col_rev:
        sales_norm["unit_price"] = pd.to_numeric(sales_df[col_price], errors='coerce').fillna(10.0).round(2)
        sales_norm["total_revenue"] = (sales_norm["quantity"] * sales_norm["unit_price"]).round(2)
    else:
        sales_norm["unit_price"] = 100.0
        sales_norm["total_revenue"] = (sales_norm["quantity"] * 100.0).round(2)

    # Sale ID
    col_sale_id = _resolve_column(sales_df.columns, "sale_id")
    if col_sale_id:
        sales_norm["sale_id"] = sales_df[col_sale_id].astype(str).str.strip()
    else:
        sales_norm["sale_id"] = [f"SAL_{i+1:06d}" for i in range(len(sales_norm))]

    sales_norm = sales_norm[["sale_id", "date", "store_id", "product_id", "quantity", "unit_price", "total_revenue"]]

    # 2. Normalize Products DataFrame
    unique_prod_ids = sales_norm["product_id"].unique()
    products_norm = pd.DataFrame()

    if products_df is not None and not products_df.empty:
        col_p_id = _resolve_column(products_df.columns, "product_id")
        col_p_name = _resolve_column(products_df.columns, "product_name")
        col_p_cat = _resolve_column(products_df.columns, "category")
        col_p_price = _resolve_column(products_df.columns, "unit_price")
        col_p_cost = _resolve_column(products_df.columns, "cost_price")
        col_p_reorder = _resolve_column(products_df.columns, "reorder_point")

        products_norm["product_id"] = products_df[col_p_id].astype(str).str.strip() if col_p_id else [f"PRD{i+1:03d}" for i in range(len(products_df))]
        products_norm["product_name"] = products_df[col_p_name].astype(str).str.strip() if col_p_name else products_norm["product_id"]
        products_norm["category"] = products_df[col_p_cat].astype(str).str.strip() if col_p_cat else "General Merchandise"
        
        if col_p_price:
            products_norm["unit_price"] = pd.to_numeric(products_df[col_p_price], errors='coerce').fillna(100.0).round(2)
        else:
            # Map from sales unit_price average
            avg_p = sales_norm.groupby("product_id")["unit_price"].mean().to_dict()
            products_norm["unit_price"] = products_norm["product_id"].map(avg_p).fillna(100.0).round(2)

        if col_p_cost:
            products_norm["cost_price"] = pd.to_numeric(products_df[col_p_cost], errors='coerce').fillna(products_norm["unit_price"] * 0.6).round(2)
        else:
            products_norm["cost_price"] = (products_norm["unit_price"] * 0.6).round(2)

        if col_p_reorder:
            products_norm["reorder_point"] = pd.to_numeric(products_df[col_p_reorder], errors='coerce').fillna(20).astype(int)
        else:
            products_norm["reorder_point"] = 20

    # Ensure all sales products exist in products table
    existing_pids = set(products_norm["product_id"].tolist()) if not products_norm.empty else set()
    missing_pids = [pid for pid in unique_prod_ids if pid not in existing_pids]
    if missing_pids:
        missing_rows = []
        for pid in missing_pids:
            # Check if name was in sales_df
            p_name = pid
            if col_prod_name and col_prod_id and col_prod_id in sales_df.columns and col_prod_name in sales_df.columns:
                match = sales_df[sales_df[col_prod_id].astype(str).str.strip() == pid]
                if not match.empty:
                    p_name = str(match[col_prod_name].iloc[0]).strip()
            
            p_sales = sales_norm[sales_norm["product_id"] == pid]
            avg_price = float(p_sales["unit_price"].mean()) if not p_sales.empty else 100.0
            
            # Auto categorize based on product name
            cat = "General Merchandise"
            p_l = p_name.lower()
            if any(k in p_l for k in ["laptop", "computer", "pc", "desktop", "macbook", "notebook"]):
                cat = "Computers"
            elif any(k in p_l for k in ["phone", "smartphone", "mobile", "iphone", "android", "samsung"]):
                cat = "Mobile"
            elif any(k in p_l for k in ["headphone", "audio", "speaker", "earbuds", "soundbar"]):
                cat = "Audio"
            elif any(k in p_l for k in ["watch", "wearable", "band", "fitbit"]):
                cat = "Wearables"
            elif any(k in p_l for k in ["gaming", "console", "game", "controller", "switch"]):
                cat = "Gaming"

            missing_rows.append({
                "product_id": pid,
                "product_name": p_name,
                "category": cat,
                "unit_price": round(avg_price, 2),
                "cost_price": round(avg_price * 0.6, 2),
                "reorder_point": 20
            })
        products_norm = pd.concat([products_norm, pd.DataFrame(missing_rows)], ignore_index=True)

    products_norm = products_norm[["product_id", "product_name", "category", "unit_price", "cost_price", "reorder_point"]].drop_duplicates(subset=["product_id"])

    # 3. Normalize Stores DataFrame
    unique_store_ids = sales_norm["store_id"].unique()
    stores_norm = pd.DataFrame()

    if stores_df is not None and not stores_df.empty:
        col_s_id = _resolve_column(stores_df.columns, "store_id")
        col_s_name = _resolve_column(stores_df.columns, "store_name")
        col_s_loc = _resolve_column(stores_df.columns, "location")
        col_s_sqft = _resolve_column(stores_df.columns, "square_feet")
        col_s_date = _resolve_column(stores_df.columns, "opening_date")

        stores_norm["store_id"] = stores_df[col_s_id].astype(str).str.strip() if col_s_id else [f"STR{i+1:03d}" for i in range(len(stores_df))]
        stores_norm["store_name"] = stores_df[col_s_name].astype(str).str.strip() if col_s_name else stores_norm["store_id"]
        stores_norm["location"] = stores_df[col_s_loc].astype(str).str.strip() if col_s_loc else "Retail Outlet"
        stores_norm["square_feet"] = pd.to_numeric(stores_df[col_s_sqft], errors='coerce').fillna(8000).astype(int) if col_s_sqft else 8000
        stores_norm["opening_date"] = pd.to_datetime(stores_df[col_s_date], errors='coerce').dt.strftime('%Y-%m-%d').fillna("2020-01-01") if col_s_date else "2020-01-01"

    # Ensure all sales stores exist in stores table
    existing_sids = set(stores_norm["store_id"].tolist()) if not stores_norm.empty else set()
    missing_sids = [sid for sid in unique_store_ids if sid not in existing_sids]
    if missing_sids:
        missing_rows = []
        for sid in missing_sids:
            s_name = sid
            if col_store_name and col_store_id and col_store_id in sales_df.columns and col_store_name in sales_df.columns:
                match = sales_df[sales_df[col_store_id].astype(str).str.strip() == sid]
                if not match.empty:
                    s_name = str(match[col_store_name].iloc[0]).strip()
            missing_rows.append({
                "store_id": sid,
                "store_name": s_name,
                "location": "Retail Outlet",
                "square_feet": 8000,
                "opening_date": "2020-01-01"
            })
        stores_norm = pd.concat([stores_norm, pd.DataFrame(missing_rows)], ignore_index=True)

    stores_norm = stores_norm[["store_id", "store_name", "location", "square_feet", "opening_date"]].drop_duplicates(subset=["store_id"])

    # 4. Normalize Inventory DataFrame
    inventory_norm = pd.DataFrame()
    if inventory_df is not None and not inventory_df.empty:
        col_i_store = _resolve_column(inventory_df.columns, "store_id")
        col_i_prod = _resolve_column(inventory_df.columns, "product_id")
        col_i_stock = _resolve_column(inventory_df.columns, "current_stock")
        col_i_date = _resolve_column(inventory_df.columns, "last_restock_date")

        inventory_norm["store_id"] = inventory_df[col_i_store].astype(str).str.strip() if col_i_store else "STR001"
        inventory_norm["product_id"] = inventory_df[col_i_prod].astype(str).str.strip() if col_i_prod else "PRD001"
        inventory_norm["current_stock"] = pd.to_numeric(inventory_df[col_i_stock], errors='coerce').fillna(0).astype(int) if col_i_stock else 50
        inventory_norm["last_restock_date"] = pd.to_datetime(inventory_df[col_i_date], errors='coerce').dt.strftime('%Y-%m-%d').fillna(max_d) if col_i_date else max_d

    # Ensure all (store_id, product_id) permutations from stores and products have inventory records
    all_sids = stores_norm["store_id"].tolist()
    all_pids = products_norm["product_id"].tolist()
    
    existing_pairs = set(zip(inventory_norm["store_id"], inventory_norm["product_id"])) if not inventory_norm.empty else set()
    missing_inv_rows = []
    
    for sid in all_sids:
        for pid in all_pids:
            if (sid, pid) not in existing_pairs:
                # Estimate a reasonable current stock based on recent sales velocity
                prod_sales = sales_norm[(sales_norm["store_id"] == sid) & (sales_norm["product_id"] == pid)]
                units_sold = prod_sales["quantity"].sum() if not prod_sales.empty else 0
                estimated_stock = max(10, int(units_sold * 0.2)) if units_sold > 0 else 25
                missing_inv_rows.append({
                    "store_id": sid,
                    "product_id": pid,
                    "current_stock": estimated_stock,
                    "last_restock_date": max_d
                })

    if missing_inv_rows:
        inventory_norm = pd.concat([inventory_norm, pd.DataFrame(missing_inv_rows)], ignore_index=True)

    inventory_norm = inventory_norm[["store_id", "product_id", "current_stock", "last_restock_date"]].drop_duplicates(subset=["store_id", "product_id"])

    # 5. Synthesize Inventory Movements DataFrame
    # Builds chronological daily running balance per store & product
    movements_list = []
    mov_counter = 1

    # Map current stock
    stock_lookup = {(r["store_id"], r["product_id"]): int(r["current_stock"]) for _, r in inventory_norm.iterrows()}

    # Group sales chronologically
    sorted_sales = sales_norm.sort_values(by=["date", "sale_id"])
    
    # Calculate starting stock at beginning of period:
    # starting_stock = current_stock + total_sales_in_period
    sales_totals = sorted_sales.groupby(["store_id", "product_id"])["quantity"].sum().to_dict()
    
    current_balances = {}
    for (sid, pid), end_stock in stock_lookup.items():
        sold_qty = sales_totals.get((sid, pid), 0)
        # Starting stock was end_stock + sold_qty
        start_stock = max(0, end_stock + sold_qty)
        current_balances[(sid, pid)] = start_stock
        
        # Initial movement record on min_date
        min_sale_d = sorted_sales["date"].min() or "2026-01-01"
        movements_list.append({
            "movement_id": f"MOV_{mov_counter:08d}",
            "date": min_sale_d,
            "store_id": sid,
            "product_id": pid,
            "movement_type": "INITIAL_STOCK",
            "quantity": start_stock,
            "running_balance": start_stock
        })
        mov_counter += 1

    # Add outbound sale movements
    for _, s_row in sorted_sales.iterrows():
        sid = s_row["store_id"]
        pid = s_row["product_id"]
        d = s_row["date"]
        q = int(s_row["quantity"])
        
        prev_bal = current_balances.get((sid, pid), 50)
        new_bal = max(0, prev_bal - q)
        current_balances[(sid, pid)] = new_bal

        movements_list.append({
            "movement_id": f"MOV_{mov_counter:08d}",
            "date": d,
            "store_id": sid,
            "product_id": pid,
            "movement_type": "SALE",
            "quantity": -q,
            "running_balance": new_bal
        })
        mov_counter += 1

    movements_norm = pd.DataFrame(movements_list)

    return stores_norm, products_norm, inventory_norm, sales_norm, movements_norm


def create_and_activate_dataset(
    dataset_name: str,
    sales_df: pd.DataFrame,
    inventory_df: Optional[pd.DataFrame] = None,
    products_df: Optional[pd.DataFrame] = None,
    stores_df: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """
    SINGLE ACTIVE DATASET REPLACEMENT PIPELINE:
    1. Validates inputs and normalizes data.
    2. Builds isolated staging SQLite database: data/datasets/staging_<uuid>.sqlite.
    3. Indexes tables and runs integrity verification (row counts, referential integrity, date ranges, metrics sanity).
    4. ONLY AFTER 100% SUCCESS:
       a. Removes old active dataset (and any older custom datasets) from disk and metadata.
       b. Atomically promotes staging DB to datasets/<id>.sqlite.
       c. Sets active_dataset_id to new dataset.
       d. Invalidates all caches and clears Copilot conversation memory.
    If validation/verification fails: clean rollback, staging DB deleted, previous active dataset stays 100% intact.
    """
    inst = ActiveDatasetManager.get_instance()
    dataset_id = "ds_" + uuid.uuid4().hex[:8]
    staging_file = os.path.join(DATASETS_DIR, f"staging_{dataset_id}.sqlite")
    final_file = os.path.join(DATASETS_DIR, f"{dataset_id}.sqlite")

    try:
        # Step 1: Normalize Data
        stores_df_n, prods_df_n, inv_df_n, sales_df_n, movs_df_n = normalize_retail_data(
            sales_df=sales_df,
            inventory_df=inventory_df,
            products_df=products_df,
            stores_df=stores_df
        )

        # Step 2: Build SQLite Staging Database
        if os.path.exists(staging_file):
            os.remove(staging_file)

        conn = sqlite3.connect(staging_file)
        stores_df_n.to_sql("stores", conn, if_exists="replace", index=False)
        prods_df_n.to_sql("products", conn, if_exists="replace", index=False)
        inv_df_n.to_sql("inventory", conn, if_exists="replace", index=False)
        sales_df_n.to_sql("sales", conn, if_exists="replace", index=False)
        movs_df_n.to_sql("inventory_movements", conn, if_exists="replace", index=False)

        # Step 3: Create Indexes
        c = conn.cursor()
        c.execute("CREATE INDEX idx_sales_date ON sales(date)")
        c.execute("CREATE INDEX idx_sales_product ON sales(product_id)")
        c.execute("CREATE INDEX idx_sales_store ON sales(store_id)")
        c.execute("CREATE INDEX idx_inventory_product ON inventory(product_id)")
        c.execute("CREATE INDEX idx_inventory_store ON inventory(store_id)")
        c.execute("CREATE INDEX idx_movements_date ON inventory_movements(date)")
        c.execute("CREATE INDEX idx_movements_store ON inventory_movements(store_id)")
        c.execute("CREATE INDEX idx_movements_prod ON inventory_movements(product_id)")

        # Step 4: Comprehensive Verification Sanity Checks
        c.execute("SELECT COUNT(*) as cnt FROM sales")
        s_cnt = c.fetchone()[0]
        c.execute("SELECT COUNT(*) as cnt FROM products")
        p_cnt = c.fetchone()[0]
        c.execute("SELECT COUNT(*) as cnt FROM stores")
        st_cnt = c.fetchone()[0]
        c.execute("SELECT COUNT(*) as cnt FROM inventory")
        i_cnt = c.fetchone()[0]

        if s_cnt == 0 or p_cnt == 0 or st_cnt == 0 or i_cnt == 0:
            conn.close()
            raise ValueError(f"Integrity check failed: sales={s_cnt}, products={p_cnt}, stores={st_cnt}, inventory={i_cnt}")

        # Referential integrity check
        c.execute("SELECT COUNT(*) FROM sales WHERE product_id NOT IN (SELECT product_id FROM products)")
        orphan_sales_p = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM sales WHERE store_id NOT IN (SELECT store_id FROM stores)")
        orphan_sales_s = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM inventory WHERE product_id NOT IN (SELECT product_id FROM products)")
        orphan_inv_p = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM inventory WHERE store_id NOT IN (SELECT store_id FROM stores)")
        orphan_inv_s = c.fetchone()[0]

        if orphan_sales_p > 0 or orphan_sales_s > 0 or orphan_inv_p > 0 or orphan_inv_s > 0:
            conn.close()
            raise ValueError(
                f"Referential integrity failure: orphan_sales_p={orphan_sales_p}, orphan_sales_s={orphan_sales_s}, "
                f"orphan_inv_p={orphan_inv_p}, orphan_inv_s={orphan_inv_s}"
            )

        # Date validation check
        c.execute("SELECT MIN(date), MAX(date) FROM sales")
        min_d, max_d = c.fetchone()
        if not min_d or not max_d:
            conn.close()
            raise ValueError("Invalid date range detected in sales records.")

        # Metric sanity checks
        c.execute("SELECT COALESCE(SUM(total_revenue), 0), COALESCE(SUM(quantity), 0) FROM sales")
        tot_rev, tot_qty = c.fetchone()
        c.execute("SELECT COALESCE(SUM(current_stock), 0) FROM inventory")
        tot_stock = c.fetchone()[0]

        conn.commit()
        conn.close()

        metrics = {
            "dataset_id": dataset_id,
            "dataset_name": dataset_name or f"Custom Dataset ({dataset_id[:8]})",
            "is_demo": False,
            "store_count": int(st_cnt),
            "product_count": int(p_cnt),
            "sales_count": int(s_cnt),
            "inventory_count": int(i_cnt),
            "total_stock_units": int(tot_stock),
            "min_date": str(min_d),
            "max_date": str(max_d),
            "total_revenue": round(float(tot_rev), 2),
            "total_units_sold": int(tot_qty),
            "created_at": datetime.datetime.now().isoformat()
        }

        # Step 5: Update Manager Metadata & Set Active
        inst._metadata.setdefault("datasets", {})[dataset_id] = metrics
        inst._active_dataset_id = dataset_id

        # Step 6: Atomic Promotion
        if os.path.exists(final_file):
            os.remove(final_file)
        os.rename(staging_file, final_file)

        # Step 7: REMOVE OLD ACTIVE DATASET (and all older custom datasets)
        # ONLY executed after 100% successful validation, verification, and promotion.
        old_datasets = list(inst._metadata.get("datasets", {}).keys())
        for old_id in old_datasets:
            if old_id != "demo" and old_id != dataset_id:
                old_file = os.path.join(DATASETS_DIR, f"{old_id}.sqlite")
                if os.path.exists(old_file):
                    try:
                        os.remove(old_file)
                        print(f"[RetailIQ] Removed old dataset file: {old_file}")
                    except Exception as e:
                        print(f"[RetailIQ] Warning: failed to remove old dataset file {old_file}: {e}")
                if old_id in inst._metadata.get("datasets", {}):
                    del inst._metadata["datasets"][old_id]

        # Also purge any stray non-demo .sqlite files in DATASETS_DIR
        for fname in os.listdir(DATASETS_DIR):
            if fname.endswith(".sqlite") and fname not in ["demo.sqlite", "empty.sqlite", f"{dataset_id}.sqlite"]:
                stray_path = os.path.join(DATASETS_DIR, fname)
                try:
                    os.remove(stray_path)
                    print(f"[RetailIQ] Purged stray old database: {stray_path}")
                except Exception as e:
                    print(f"[RetailIQ] Warning: could not remove {stray_path}: {e}")

        inst._save_metadata()

        # Step 8: Clear All Caches and Reset Copilot Context
        _trigger_invalidation()

        print(f"[RetailIQ] Dataset '{dataset_name}' ({dataset_id}) promoted to SINGLE ACTIVE DATASET successfully.")
        return metrics

    except Exception as e:
        # ROLLBACK: remove staging file
        if os.path.exists(staging_file):
            try:
                os.remove(staging_file)
            except Exception:
                pass
        print(f"[RetailIQ] Dataset upload failed during validation: {e}. Staging rollback completed. Previous active dataset remains active.")
        raise
