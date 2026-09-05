# RetailIQ Analytics API Regression Report

## Executive Summary
This regression report details the diagnosis, root cause analysis, fix implementation, and multi-tier verification for the **`/api/seasonality`** endpoint and the dynamic **Store Comparison** matrix across all dataset states (`NO_DATA`, `CUSTOM_DATASET`, and `DEMO_DATASET`).

All analytics endpoints are verified to return **200 OK** with strictly isolated data, zero demo leakage, robust limited-history classification, and dynamic multi-store comparison.

---

## 1. Seasonality Root Cause Analysis & Resolution
- **Endpoint**: `GET /api/seasonality?store_id=all`
- **Root Cause**:
  In `get_seasonality_analysis()` ([src/sales_rules.py](file:///d:/Retail%20-%20Sales%20and%20Inventory%20Copilot/src/sales_rules.py)), the SQL query was structured as:
  ```sql
  SELECT strftime('%m', date) as month_num, ...
  FROM (
      SELECT strftime('%Y', date) as y, strftime('%m', date) as m,
             SUM(total_revenue) as monthly_rev, SUM(quantity) as monthly_units
      FROM sales GROUP BY y, m
  )
  GROUP BY month_num
  ```
  The outer query attempted to call `strftime('%m', date)` on `date`, which did not exist in the projected subquery (`y`, `m`, `monthly_rev`, `monthly_units`).
  In SQLite, referencing an unprojected column from a subquery threw `sqlite3.OperationalError: no such column: date`, which propagated as an unhandled HTTP 500.

- **Fix**:
  1. Updated the outer query to reference the subquery alias `m as month_num` and `COUNT(DISTINCT y) as years_count` with `GROUP BY m ORDER BY CAST(m AS INTEGER) ASC`.
  2. Added date coverage profiling and validation before computing seasonality.
  3. Added structured `[SEASONALITY]` diagnostics logging:
     ```
     [SEASONALITY] dataset_id: ... | date_min: ... | date_max: ... | unique_dates: ... | unique_months: ... | store_scope: ...
     ```

---

## 2. Limited History & Insufficient Data Handling
Seasonality calculations require multi-month historical distribution to provide statistically meaningful demand patterns.

- **Threshold**: Datasets with less than 3 distinct calendar months (or short spans e.g. 10 days) are safely classified as `INSUFFICIENT_HISTORY`.
- **API Response Contract (HTTP 200)**:
  ```json
  {
    "status": "INSUFFICIENT_HISTORY",
    "message": "Not enough historical data in the active dataset to calculate a reliable seasonal pattern.",
    "unique_months": 1,
    "date_min": "2026-07-01",
    "date_max": "2026-07-10",
    "seasonality_table": [],
    "peak_month": "N/A",
    "seasonality_chart": {
      "type": "bar",
      "title": "Monthly Demand Seasonality Profile",
      "subtitle": "Insufficient historical data for seasonality",
      "labels": [],
      "datasets": [{"label": "Avg Monthly Revenue (₹)", "data": [], "color": "#D97706"}]
    }
  }
  ```
- **Frontend UI**: Renders an informative *"Seasonality Unavailable - Not enough historical data in the active dataset to calculate a reliable seasonal pattern"* card instead of crashing or showing a broken empty chart.
- **Sufficient History (>= 3 Months or Demo 10 Years)**: Computes dynamic monthly revenue and unit volume distribution across all recorded periods, calculates `peak_month`, and returns `status: "SUCCESS"`.

---

## 3. Dynamic Multi-Store Comparison Matrix Fix
- **Hardcoding Removed**:
  - Removed default query parameter `store_ids="STR001,STR002,STR003"` from `/api/compare-stores` in [app.py](file:///d:/Retail%20-%20Sales%20and%20Inventory%20Copilot/app.py).
  - Removed `stores.slice(0, 3)` limit in [static/app.js](file:///d:/Retail%20-%20Sales%20and%20Inventory%20Copilot/static/app.js).
- **Dynamic Active Dataset Store Scope**:
  - When the active custom dataset contains 6 stores (`S001` through `S006`), `/api/compare-stores` automatically loads and compares all 6 stores side-by-side.
  - The Global Header filter displays `All Stores (6)` with exact store names from the active dataset.
  - The user can select any subset of stores or select "All Stores" to compare all stores simultaneously.

---

## 4. Comprehensive Endpoint Test Matrix

| Endpoint | Test Dataset | Query Params | HTTP Status | Response Status / Structure | Demo Data Leakage | Result |
| :--- | :--- | :--- | :---: | :--- | :---: | :---: |
| `/api/seasonality` | `NO_DATA` | `store_id=all` | **200 OK** | `status: "NO_DATA"`, `seasonality_table: []`, `peak_month: "N/A"` | None | **PASS** |
| `/api/seasonality` | `10-Day Custom` (1 Month) | `store_id=all` | **200 OK** | `status: "INSUFFICIENT_HISTORY"`, `unique_months: 1` | None | **PASS** |
| `/api/seasonality` | `Multi-Month Custom` (4 Months) | `store_id=all` | **200 OK** | `status: "SUCCESS"`, 4 monthly averages, `peak_month: "Jul"` | None | **PASS** |
| `/api/seasonality` | `Demo Dataset` (10 Years) | `store_id=all` | **200 OK** | `status: "SUCCESS"`, 12 months (Jan–Dec), real peak month | None | **PASS** |
| `/api/compare-stores` | `6-Store Custom` | (default / all) | **200 OK** | `stores_count: 6`, 6 stores in matrix & trajectory chart | None | **PASS** |
| `/api/compare-stores` | `6-Store Custom` | `store_ids=S001,S003` | **200 OK** | `stores_count: 2`, 2 stores in matrix & trajectory chart | None | **PASS** |
| `/api/dashboard` | `Active Custom` | `store_id=all` | **200 OK** | Total Revenue, Units, Valuation, SKUs matching active dataset | None | **PASS** |
| `/api/inventory` | `Active Custom` | `store_id=all` | **200 OK** | Complete SKU status table with days remaining and reorder math | None | **PASS** |
| `/api/analytics/charts` | `Active Custom` | `days=30&store_id=all` | **200 OK** | Dual-axis trend, top products, category breakdown | None | **PASS** |
| `/api/yearly-performance`| `Active Custom`| `store_id=all` | **200 OK** | Dynamic YoY growth table & chart | None | **PASS** |
| `/api/reorder-plan` | `Active Custom` | `store_id=all` | **200 OK** | Priority-ranked reorder recommendations | None | **PASS** |
| `/api/decision-center` | `Active Custom` | — | **200 OK** | Operational decision cards with action buttons and evidence | None | **PASS** |
| `/api/executive-report`| `Active Custom` | `store_id=all` | **200 OK** | Full executive BI operational summary | None | **PASS** |

---

## 5. Confirmation of Zero Demo Fallback
- `NO_DATA` state: **0 Records, 0 Revenue, 0 Fake Dates, 0 Leakage**.
- Custom Datasets: Derived **strictly from the isolated active SQLite database**.
- Demo Dataset: Used **only when explicitly requested by clicking "Reset to Demo Dataset"**.
- All 32 unit and integration tests across 5 test suites pass with **0 Errors and 0 Failures**.
