# RetailIQ: NO DATA State Implementation Report

**Author:** Antigravity AI Engineering Team  
**Date:** 2026-09-05  
**Version:** 3.0.0 (Strict Zero-Data Default Architecture)  
**Status:** COMPLETE & VERIFIED

---

## 1. Executive Summary & Core Architecture

RetailIQ has been transitioned to a strict **"NO DATA UNTIL USER UPLOADS DATA"** default state. When the application launches for the first time or when active datasets are cleared, RetailIQ operates as an **empty retail workspace**:

- **Initial State:** `active_dataset_id = None` (`NO_DATA` state).
- **All business metrics:** Default to `₹0.00`, `0 units`, `0 SKUs`, `0 stores`, and `0 alerts`.
- **Demo Dataset:** Remains fully preserved on disk (`data/datasets/demo.sqlite`), but **never** loads or activates automatically on startup. It is accessible strictly on-demand via the *"Use Demo Dataset"* button.
- **Data Grounding & Safety:** All analytics engines, query engines, and AI Copilot endpoints return deterministic zero/empty state payloads without executing queries against demo tables or triggering AI hallucinations.

---

## 2. Dataset State Model

The centralized dataset lifecycle in `src/dataset_manager.py` manages three mutually exclusive states:

| State | `active_dataset_id` | Status Badge | Description |
| :--- | :--- | :--- | :--- |
| **`NO_DATA`** | `null` / `None` | `NO DATA` (Gray/Neutral) | **Default on startup**. Workspace is empty. All APIs return zero/empty state. |
| **`CUSTOM_ACTIVE`** | `"ds_<uuid>"` | `CUSTOM ACTIVE` (Emerald) | User uploaded a custom dataset (CSV/Excel) and activated it. |
| **`DEMO_ACTIVE`** | `"demo"` | `DEMO ACTIVE` (Purple/Indigo) | User explicitly clicked *"Use Demo Dataset"* for testing/exploration. |

### State Transitions

```
                    ┌─────────────────────────┐
                    │     APPLICATION START   │
                    └────────────┬────────────┘
                                 ▼
                     ┌───────────────────────┐
                     │        NO_DATA        │ ◄────────────────┐
                     │ (active_dataset_id:   │                  │
                     │         None)         │                  │
                     └───────────┬───────────┘                  │
                                 │                              │
             ┌───────────────────┴───────────────────┐          │
             ▼                                       ▼          │
   [User Uploads Data]                     [User Selects Demo]  │
             ▼                                       ▼          │
   ┌───────────────────┐                   ┌───────────────────┐│
   │   CUSTOM_ACTIVE   │                   │    DEMO_ACTIVE    ││
   │ (active_dataset_id│                   │(active_dataset_id:││
   │  = "ds_<hash>")   │                   │      "demo")      ││
   └─────────┬─────────┘                   └─────────┬─────────┘│
             │                                       │          │
             └───────────────────┬───────────────────┘          │
                                 ▼                              │
                     [User Clicks "Clear Dataset"]              │
                                 └──────────────────────────────┘
```

---

## 3. Backend Implementation & API Behavior

### A. Centralized Active Dataset Source of Truth (`src/dataset_manager.py`)
- `_active_dataset_id` defaults to `None`.
- `get_active_db_path()`: When `active_dataset_id` is `None`, points to `data/datasets/empty.sqlite` (a valid SQLite database schema with zero rows across `sales`, `inventory`, `products`, `stores`).
- `get_active_dataset()`: When `active_dataset_id` is `None`, returns standardized metadata:
  ```json
  {
    "dataset_id": null,
    "dataset_name": "No Dataset Active",
    "status": "NO_DATA",
    "is_demo": false,
    "store_count": 0,
    "product_count": 0,
    "sales_count": 0,
    "inventory_count": 0,
    "total_stock_units": 0,
    "total_revenue": 0.0,
    "total_units_sold": 0,
    "min_date": null,
    "max_date": null
  }
  ```
- `clear_active_dataset()`: Sets `active_dataset_id = None`, updates `datasets_metadata.json`, and flushes thread caches.

### B. Analytical Endpoints Under `NO_DATA`

| Endpoint | HTTP Method | `NO_DATA` Response Behavior |
| :--- | :--- | :--- |
| `/api/datasets/active` | `GET` | Returns `status: "NO_DATA"`, all entity counts = `0`. |
| `/api/dashboard` | `GET` | Returns `no_data: True`, `total_revenue: 0.0`, `total_units_sold: 0`, `critical_low_stock_count: 0`, `overstock_count: 0`, `growth_pct: 0.0`, empty arrays for tables & sparklines. |
| `/api/inventory` | `GET` | Returns `[]` (empty list). |
| `/api/reorder-plan` | `GET` | Returns `[]` (empty list). |
| `/api/stores` | `GET` | Returns `[]` (empty list). |
| `/api/products` | `GET` | Returns `[]` (empty list). |
| `/api/compare-stores` | `GET` | Returns `stores_count: 0`, `comparison_table: []`, `summary_cards: []`. |
| `/api/decision-center` | `GET` | Returns `[]` (empty list). |
| `/api/alerts` | `GET` | Returns `[]` (empty list). |
| `/api/executive-report` | `GET` | Returns zeroed KPIs (`revenue: 0.0`), `critical_stock_items: []`, `recommended_reorders: []`. |
| `/api/chat` | `POST` | Intercepts immediately; returns *"I don't have an active retail dataset yet. Please upload your sales, inventory, product, and store data in Data Management so I can analyze it."* Zero metrics, zero hallucination, no LLM calls. |
| `/api/datasets/clear` | `POST` | Clears active dataset to `None` and returns `NO_DATA` status. |
| `/api/datasets/reset` | `POST` | Activates `demo.sqlite` on-demand with 5 stores, 40 SKUs, 114,515 sales. |

---

## 4. Frontend UI & Empty-State UX (`static/index.html` & `static/app.js`)

### A. Global Header & Initial Elements
- **Header Pill:** Displays `No Dataset Active • Not Connected` with a neutral `[NO DATA]` badge.
- **Store Filter:** Populates with only `All Stores (0)` when no stores exist.
- **Upload Data CTA:** Prominently visible in the top header and Data Management hub.

### B. Empty State Views per Workspace View
1. **Dashboard:**
   - KPIs: `₹0.00` Revenue, `0` Units Sold, `0` Low Stock, `0` Overstock, `0%` Sales Growth.
   - Sales Chart: Empty-state card with *"No sales data available. Upload a retail dataset to see revenue and sales trends."*
   - Inventory Health: Donut chart displays zero counts with *"No inventory data available. Upload inventory data to calculate stock health."*
   - Needs Attention: Empty-state card *"No attention items. Upload retail data to identify stock risks and sales anomalies."*
   - Top Products: Empty-state table card *"No product data available."*
   - Store Performance: Empty-state table card *"No store data available."*
2. **Inventory Page:**
   - Top KPI cards: `Total SKUs: 0`, `Critical: 0`, `Warning: 0`, `Overstock: 0`, `Slow Moving: 0`.
   - Inventory Table: Empty state message *"No inventory data available."*
3. **Reorder Planner:**
   - Empty state banner: *"No reorder recommendations. Upload inventory and sales data to generate replenishment recommendations."*
4. **Store Comparison:**
   - Empty state banner: *"No store data available. Upload your retail dataset to compare store performance."*
5. **Decision Center:**
   - Empty state banner: *"No operational decisions available. Upload retail data to generate evidence-based recommendations."*
6. **Executive BI Report:**
   - Summary message: *"Executive report will be generated after retail data is uploaded."*
   - Zeroed financial metrics.

---

## 5. Verification & Test Results

The implementation was validated using automated end-to-end integration tests:

### Test Suite: `tests/test_no_data_state.py`
- `test_initial_no_data_state`:
  - Verified `/api/datasets/active` returns `status: "NO_DATA"`.
  - Verified `/api/dashboard` returns `no_data: True`, `total_revenue == 0.0`.
  - Verified `/api/inventory`, `/api/reorder-plan`, `/api/compare-stores`, `/api/decision-center`, `/api/alerts` return empty arrays `[]`.
  - Verified `/api/executive-report` returns zeroed KPIs.
  - Verified `/api/chat` returns grounded upload prompt without LLM hallucination.
- `test_dataset_lifecycle_transitions`:
  - `NO_DATA` $\rightarrow$ Reset to Demo (`/api/datasets/reset`) $\rightarrow$ Revenue $> ₹1,000,000$, 5 Stores, 40 SKUs.
  - Switch $\rightarrow$ Clear Active Dataset (`/api/datasets/clear`) $\rightarrow$ `NO_DATA` $\rightarrow$ Revenue $= ₹0.00$, 0 records.
- **Result:** **PASSED (2/2 tests, 100% success)**.

### Test Suite: `tests/test_dataset_isolation.py`
- Tested custom dataset upload (`Dataset 2: 2 Stores, 5 SKUs, 21 Sales, 10 Inventory`).
- Verified zero leakage of demo products or demo stores.
- Bidirectional switching between custom dataset, demo dataset, and `NO_DATA`.
- **Result:** **PASSED (8/8 tests, 100% success)**.

---

## 6. Confirmation Checklist

- [x] Initial application start loads in `NO_DATA` state.
- [x] Header displays *"No Dataset Active • Not Connected"*.
- [x] Dashboard metrics display `₹0.00`, `0 units`, `0 alerts`, `0 overstock`, `0% growth`.
- [x] No fake demo charts, products, or stores appear on fresh launch.
- [x] Inventory, Reorder, Stores, Decision Center, Executive Report show clean empty-state cards.
- [x] AI Copilot queries in `NO_DATA` state cleanly ask the user to upload data first.
- [x] Demo dataset is preserved on disk in `data/datasets/demo.sqlite` and only activated on explicit user action.
- [x] User dataset upload dynamically activates uploaded dataset across all views.
- [x] User can click *"Clear Active Dataset"* to return to the clean empty state at any time.
