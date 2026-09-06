TRACK_ID: PS03

---

## Project Overview

**RetailIQ** is an enterprise-grade retail operations assistant and multi-store analytics platform designed for store managers, inventory planners, and retail executives.

RetailIQ bridges the gap between raw transactional data and strategic decision-making. Unlike generic AI assistants that hallucinate calculations or speculate on missing data, RetailIQ implements an **Evidence-First Architecture**:

1. **Deterministic Analytics Engine**: 100% of numerical calculations, historical inventory reconciliations, stockout risk scores, seasonal demand indices, and reorder quantities are computed deterministically in Python using SQLite and Pandas.
2. **Strict Single Active Dataset Replacement Model**: Every uploaded retail dataset runs in complete cryptographic isolation in a dedicated SQLite database. Activating a new dataset atomically purges previous active data, flushes analytical caches, and wipes conversational memory to guarantee zero cross-contamination.
3. **Evidence-Grounded AI Copilot**: Powered by Google Gemini (`gemini-2.0-flash` / `gemini-1.5-flash` / `gemini-2.5-flash`), the AI acts strictly as an **explanation layer** over structured evidence. If the required data does not exist in the active dataset, RetailIQ explicitly flags the missing data rather than fabricating an answer.

---

## Key Principle

$$\mathbf{Trustworthy\ Retail\ AI} = \mathbf{Deterministic\ BI\ Engine\ (100\%)} + \mathbf{Structured\ Evidence\ Grounding} + \mathbf{LLM\ Explanation\ Layer}$$

> **Core Rule**: The LLM is never the source of numerical truth. Python computes; Gemini explains.

---

## Problem Statement

### The Problem
Multi-store retail operations face critical day-to-day challenges:
- **Frequent Stockouts & Lost Revenue**: Store managers lack real-time visibility into days of supply, leading to stockouts on top-selling SKUs.
- **Capital Locked in Overstock**: Slow-moving inventory ties up working capital without automated alerts to pause replenishment.
- **Fragmented Multi-Store Data**: Comparing store performance, identifying regional demand patterns, and calculating purchase order quantities across locations requires complex manual spreadsheets.
- **Unreliable "Black Box" AI**: Generic conversational chatbots often invent sales figures, hallucinate inventory levels, and fabricate causes for sales anomalies without data evidence.

### Why It Matters
A single stockout on a high-velocity product directly loses revenue and damages customer loyalty. Conversely, over-purchasing slow-moving items restricts cash flow. Retailers need automated, mathematically verified intelligence that explains *why* an anomaly occurred and *what exact action* to take.

### How RetailIQ Solves It
RetailIQ delivers an end-to-end decision intelligence platform that combines automated data ingestion, multi-store stock reconciliation, intelligent reorder planning, historical date snapshots, operational decision prioritization, and an evidence-grounded AI copilot that cites its data sources and assumptions.

---

## Key Features

### 1. Single Active Dataset Replacement Model
- **Atomic Dataset Switching**: Uploading and activating a new dataset stages it in a temporary database, verifies referential integrity, and atomically promotes it as the single active source of truth.
- **Zero Cross-Contamination**: Activating dataset $B$ deletes dataset $A$'s active SQLite file, invalidates all backend caches, and clears the AI conversational context.
- **NO_DATA Safe State**: When no dataset is active, all dashboard endpoints return clean empty contracts (HTTP 200) and the Copilot safely informs the user to upload data.

### 2. Dual Upload Modes with Strict Validation
- **Mutually Exclusive Input Options**:
  - **Option A: Single File** (`.csv`, `.xlsx`, `.xls`) with automatic sheet detection (`sales`, `inventory`, `products`, `stores`) or single-table transaction mapping.
  - **Option B: 4 Separate CSVs** (`Sales (Required) *`, `Inventory (Required) *`, `Products (Required) *`, `Stores (Required) *`).
- **Strict Validation**: Mandatory Dataset Name requirement, file extension checks, and dual frontend/backend validation preventing mixed or incomplete uploads.
- **Intelligent Auto-Mapping & Synthesis**: Automatically normalizes diverse column naming conventions (e.g., `Date`, `SKU`, `Product`, `Qty`, `Price`, `Revenue`, `Stock`) and synthesizes missing catalog/movement tables from sales transactions.

### 3. Real-Time Executive KPI Dashboard
- Top-level operational metrics: Total Revenue, Total Units Sold, Gross Margin %, Total Inventory Valuation, Active SKUs, and Store Count.
- Instant attention badges highlighting critical out-of-stock items, low-stock warnings, and top revenue drivers.
- Global store filtering (`All Stores` or specific store location) and historical date snapshot controls.

### 4. Inventory Health & Stockout Risk Engine
- Calculates **Average Daily Sales (ADS)** over a rolling 30-day demand window.
- Computes **Days Remaining** of stock per product-store pair.
- Automatically classifies inventory status into 6 discrete states:
  - `OUT_OF_STOCK`: Stock $\le 0$
  - `CRITICAL`: Days Remaining $\le 2$ days
  - `WARNING`: Days Remaining $\le 7$ days
  - `SLOW_MOVING`: 30-day sales $< 5$ units and stock $\ge 20$ units
  - `OVERSTOCK`: Days Remaining $> 30$ days and stock $\ge 50$ units
  - `HEALTHY`: Stable stock coverage between 7 and 30 days

### 5. Historical Date Snapshot Engine
- Reconstructs exact retail KPIs, stock levels, and inventory valuation for any historical calendar date using an audited movement ledger ($\text{Stock}_D = \text{Opening} + \sum \text{Purchases} - \sum \text{Sales}$).
- Supports historical operational auditing across multi-year retail timelines.

### 6. Intelligent Reorder Planner & Purchase Order Export
- Implements 7-day target coverage replenishment math: $\text{Reorder Qty} = \max(0, \lceil(\text{ADS} \times 7) - \text{Current Stock}\rceil)$.
- Filter reorder recommendations by urgency (`Critical`, `High`, `Normal`) or category.
- One-click **CSV Export** generating purchase order queues ready for procurement systems.

### 7. Multi-Timeframe Sales Analytics & Seasonality
- Interactive SVG chart visualizations across `7D`, `30D`, `90D`, `6M`, `1Y`, `3Y`, `5Y`, and `10Y` timeframes.
- Multi-year annual trends with year-over-year (YoY) revenue and volume growth rates.
- 12-month demand seasonality profiling identifying annual peak and low demand periods.

### 8. Store Comparison Matrix
- Side-by-side multi-store KPI benchmarking comparing revenue, volume, average order size, and stock risk across selected store networks.

### 9. Operational Decision Center
- Actionable decision cards prioritized by severity (`CRITICAL`, `HIGH`, `MEDIUM`).
- Each card details the operational issue, business impact, immediate action required, and concrete data evidence trace.

### 10. Printable Executive BI Operations Report
- Clean printable/PDF summary report layout (`window.print()`) formatted for executive briefing, containing anomaly detection, procurement actions, and revenue rankings.

### 11. Evidence-Grounded AI Copilot
- Natural language query interface supporting queries on inventory status, product performance, store rankings, reorder actions, and period comparisons.
- Structured output schema detailing answer, key metrics, evidence sources, assumptions, and data sufficiency.
- Built-in **Offline Deterministic Fallback Engine** ensuring 100% feature availability even without an internet connection or Gemini API key.

---

## System Architecture

```
+-----------------------------------------------------------------------------------+
|                            CLIENT TIER (Modern Web UI)                            |
|  - Single-Page Responsive Dashboard        - Multi-View Tab Navigation            |
|  - Pure SVG Chart Visualization Engine     - Real-Time Dataset Switcher & Uploader|
|  - Date Snapshot Controller                - Printable Executive Report Engine    |
+------------------------------------------+----------------------------------------+
                                           | HTTP / REST API (JSON & FormData)
                                           v
+-----------------------------------------------------------------------------------+
|                        APPLICATION SERVER TIER (FastAPI)                          |
|  - FastAPI ASGI Server (Port 8000)         - Request Validation & Schema Models   |
|  - Static Asset Delivery                   - Error & Exception Handling Middleware|
+-------------------+---------------------------------------+-----------------------+
                    |                                       |
                    v                                       v
+---------------------------------------+   +---------------------------------------+
|    DATASET MANAGER & LIFECYCLE TIER   |   |   DETERMINISTIC ANALYTICS & RULES     |
|  - Single Active Dataset Controller   |   |  - Inventory Health & Stockout Rules  |
|  - Staging SQLite Pipeline            |   |  - Rolling 30-Day Demand Engine (ADS) |
|  - Schema Validation & Profiling      |   |  - 7-Day Target Reorder Calculator    |
|  - Atomic Promotion & File Purging    |   |  - Historical Stock Reconstruction    |
|  - Global Cache Invalidation Callback |   |  - Seasonality & YoY Trend Analytics  |
+-------------------+-------------------+   +-------------------+-------------------+
                    |                                           |
                    v                                           v
+---------------------------------------+   +---------------------------------------+
|       DATA & PERSISTENCE TIER         |   |    QUERY PARSER & EVIDENCE ENGINE     |
|  - Active SQLite DB (ds_<uuid>.sqlite)|   |  - Natural Language Intent Classifier |
|  - Demo Dataset (demo.sqlite)         |   |  - Entity Resolution (Product/Store)  |
|  - Metadata Registry (JSON)           |   |  - Grounding State & Data Sufficiency |
|  - Empty Schema Template (NO_DATA)    |   |  - Structured Evidence Taxonomy       |
+---------------------------------------+   +-------------------+-------------------+
                                                                |
                                                                v
+-----------------------------------------------------------------------------------+
|                         AI COPILOT & EXPLANATION TIER                             |
|  - Google Gemini API Integration (`gemini-2.0-flash`, `gemini-1.5-flash`)         |
|  - Strict Grounded System Prompt & JSON Mode Formatting                           |
|  - Zero-Hallucination Guardrails & Unresolved Entity Fallback                     |
|  - Offline Deterministic Explanation Fallback Engine                              |
+-----------------------------------------------------------------------------------+
```

---

## Application Workflow

```
[User Ingests Data]
       │
       ▼
[Dual Upload Validation] ──(Fails Validation)──> [Display Formatted Error to User]
       │ (Passes Validation)
       ▼
[Stage in Temporary SQLite (staging_<uuid>.sqlite)]
       │
       ▼
[Verify Schema & Referential Integrity]
       │
       ▼
[Atomic Promotion to Active Dataset]
       │
       ├── 1. Purge Previous Active SQLite Database File
       ├── 2. Update Active Dataset Metadata Registry
       ├── 3. Invalidate All In-Memory Caches
       └── 4. Reset AI Copilot Conversational Context
       │
       ▼
[Deterministic Query Execution]
       │
       ├── Dashboard Summary & KPIs
       ├── Inventory Status & ADS Calculation
       ├── Reorder Planner & Purchase Orders
       ├── Sales Trends & Monthly Seasonality
       └── Decision Center Prioritization
       │
       ▼
[Natural Language Copilot Request (/api/chat)]
       │
       ├── 1. Intent Classification & Entity Resolution
       ├── 2. Validate Entities Against Active Dataset
       │      └─ If Unresolved SKU/Store: Return Grounded "Data Not Found" (NO_DATA)
       ├── 3. Assemble Structured Evidence & Metric Assumptions
       ├── 4. Generate Grounded Explanation via Gemini (or Offline Fallback)
       └── 5. Return Validated Structured JSON Payload
       │
       ▼
[Render Clean B2B Frontend Visualizations]
```

---

## Input & Dataset Format

RetailIQ supports two mutually exclusive upload modes:

### Mode A: Single File (`.csv`, `.xlsx`, `.xls`)
- Upload a single CSV file or a multi-sheet Excel workbook.
- When uploading an Excel workbook, RetailIQ automatically detects named sheets: `sales` / `transactions`, `inventory` / `stock`, `products` / `items`, `stores` / `locations`.
- If only sales records are provided, RetailIQ automatically synthesizes product catalogues, store entities, and inventory movements.

### Mode B: 4 Separate CSV Files
All four CSV files are mandatory when selecting 4 CSV Mode:
1. **Sales Transactions CSV (`sales_file`)** — Required
2. **Inventory Levels CSV (`inventory_file`)** — Required
3. **Products Catalog CSV (`products_file`)** — Required
4. **Store Locations CSV (`stores_file`)** — Required

### Table Schemas & Column Mappings

| Table | Required Columns | Flexible Accepted Aliases | Purpose |
|---|---|---|---|
| **`sales`** | `sale_id`, `store_id`, `product_id`, `date`, `quantity`, `unit_price`, `total_revenue` | `Date`, `Transaction Date`, `Store`, `Store ID`, `SKU`, `Product ID`, `Qty`, `Quantity`, `Price`, `Unit Price`, `Revenue`, `Total` | Transactional sales history |
| **`inventory`** | `store_id`, `product_id`, `current_stock`, `reorder_point`, `safety_stock`, `last_restock_date` | `Store`, `SKU`, `Product`, `Stock`, `Current Stock`, `Quantity on Hand`, `Reorder Level`, `Restock Date` | Current on-hand stock and safety buffers |
| **`products`** | `product_id`, `product_name`, `category`, `unit_price`, `cost_price` | `SKU`, `Product ID`, `Product Name`, `Item`, `Category`, `Department`, `Price`, `Cost` | Master product catalog |
| **`stores`** | `store_id`, `store_name`, `location` | `Store ID`, `Store Name`, `Store`, `Location`, `City`, `Region` | Retail store locations |

### Example CSV Data

#### `sales.csv`
```csv
sale_id,store_id,product_id,date,quantity,unit_price,total_revenue
S00001,STR001,PRD001,2026-08-01,3,1200.0,3600.0
S00002,STR001,PRD002,2026-08-01,1,25000.0,25000.0
S00003,STR002,PRD001,2026-08-02,5,1200.0,6000.0
```

#### `inventory.csv`
```csv
store_id,product_id,current_stock,reorder_point,safety_stock,last_restock_date
STR001,PRD001,14,20,10,2026-07-28
STR001,PRD002,2,5,2,2026-07-25
STR002,PRD001,45,20,10,2026-07-30
```

#### `products.csv`
```csv
product_id,product_name,category,unit_price,cost_price
PRD001,Wireless Headphones,Audio,1200.0,750.0
PRD002,Office Laptop Pro,Computers,25000.0,18000.0
```

#### `stores.csv`
```csv
store_id,store_name,location
STR001,Downtown Flagship,Downtown Central
STR002,Metro Hub Store,Metro Commercial Area
```

---

## Core Processing & Business Intelligence Logic

### 1. Rolling Average Daily Sales (ADS)
$$\text{ADS} = \frac{\sum_{t \in [D-30, D]} \text{Units Sold}_t}{30}$$
If no sales occurred in the 30-day window, $\text{ADS} = 0$.

### 2. Historical Stock Level Reconstruction
For any historical date $D$, stock is reconciled mathematically from the movement ledger:
$$\text{Stock}_D = \text{Opening Stock} + \sum_{t \le D} \text{Purchases}_t - \sum_{t \le D} \text{Sales}_t \pm \sum_{t \le D} \text{Adjustments}_t$$

### 3. Days of Supply Remaining
$$\text{Days Remaining} = \begin{cases} \frac{\text{Current Stock}}{\text{ADS}} & \text{if } \text{ADS} > 0 \\ 999.0 & \text{if } \text{ADS} = 0 \text{ and Stock} > 0 \\ 0.0 & \text{if Stock} \le 0 \end{cases}$$

### 4. 7-Day Target Inventory Reorder Math
$$\text{Target Stock} = \text{ADS} \times 7$$
$$\text{Recommended Reorder Qty} = \max(0, \lceil \text{Target Stock} - \text{Current Stock} \rceil)$$

### 5. Year-over-Year (YoY) Growth Rate
$$\text{YoY Growth \%} = \left( \frac{\text{Revenue}_{\text{Year } N} - \text{Revenue}_{\text{Year } N-1}}{\text{Revenue}_{\text{Year } N-1}} \right) \times 100$$

### 6. Monthly Seasonality Index
$$\text{Monthly Share \%} = \left( \frac{\text{Historical Revenue}_{\text{Month } m}}{\sum_{k=1}^{12} \text{Historical Revenue}_{\text{Month } k}} \right) \times 100$$

---

## AI Copilot & Grounding Integration

### Model Integration
- **SDK**: `google-genai` Python SDK
- **Models**: `gemini-2.0-flash` (Primary), `gemini-1.5-flash`, `gemini-2.5-flash`
- **Output Format**: Structured JSON Mode (`response_mime_type="application/json"`)

### AI Responsibilities
The Gemini LLM is used exclusively to:
1. Translate structured deterministic analytical facts into professional executive prose.
2. Structure observations, hypotheses, and unknowns into clear managerial explanations.
3. Formulate context-aware operational recommendations derived from deterministic rules.

### Anti-Hallucination & Grounding Guardrails
1. **Runtime Entity Verification**: Before calling the LLM, the Query Planner validates whether requested products, categories, or stores exist in the active dataset. If a user asks *"How did laptop sales perform?"* and no laptop SKU exists, RetailIQ halts LLM execution and immediately responds:
   > *"'Laptop' data was not found in the current dataset. Available products are: [List of actual SKUs]."*
2. **Data Sufficiency Enforcement**: If a user asks a root-cause question without supporting data (e.g. *"Why did sales drop last Tuesday?"*), the system marks data sufficiency as `insufficient`, preventing the AI from fabricating external causes like marketing campaigns or weather.
3. **Offline Deterministic Fallback**: When running without an internet connection or `GEMINI_API_KEY`, RetailIQ's template-based deterministic engine generates structured, formatted executive responses without error.

---

## Dashboards & Visualizations

| View / Tab | Key Visualizations & Features | Business Value |
|---|---|---|
| **Dashboard** | KPI stat cards, Gross Margin tracker, Inventory Valuation, Attention item alerts, Top 5 Products, Store Performance matrix | Instant high-level snapshot of overall business health |
| **Inventory Health** | Searchable/filterable inventory grid, stock levels, ADS, days remaining, status badges (`CRITICAL`, `WARNING`, `HEALTHY`, `OVERSTOCK`), SKU detail modal | Immediate stockout prevention and excess stock detection |
| **Sales Analytics Workspace** | Multi-timeframe line charts (`7D` to `10Y`), category distribution donuts, sales spikes, sales drops, seasonality charts | In-depth trend analysis and demand forecasting |
| **AI Copilot** | Natural language chat interface, metric tags, evidence citations, assumption disclosures, data sufficiency badges | Interactive conversational operations advisor |
| **Reorder Planner** | Replenishment priority table, 7-day target stock math, recommended reorder units, one-click CSV export | Rapid purchase order generation for suppliers |
| **Decision Center** | Ranked action cards (`CRITICAL`, `HIGH`, `MEDIUM`) with issue details, financial impact, recommended action, and data evidence | Clear daily operational prioritization for store managers |
| **Store Comparison** | Side-by-side multi-store comparison matrix, revenue contribution %, stock distribution, and volume rankings | Cross-location performance benchmarking |
| **Executive BI Report** | Print/PDF-ready layout (`window.print()`), executive KPI summary, anomaly log, urgent procurement recommendations | Formal reporting for executive and leadership meetings |
| **Data Management Hub** | Single Active Dataset status card, dual-mode upload form, schema validation profiler, demo reset button | Complete data ingestion, profiling, and lifecycle control |

---

## Technology Stack

```
+---------------------------------------------------------------------------------+
|                                TECHNOLOGY STACK                                 |
+-------------------+-------------------------------------------------------------+
| Frontend          | HTML5, Vanilla CSS3 (Custom Design System), JavaScript (ES6)|
|                   | Pure SVG Chart Rendering (Zero external JS dependencies)    |
+-------------------+-------------------------------------------------------------+
| Backend           | Python 3.9+ (Tested on 3.11 & 3.14), FastAPI, Uvicorn,      |
|                   | Pydantic v2                                                 |
+-------------------+-------------------------------------------------------------+
| Database          | SQLite3 (Isolated per-dataset database architecture)        |
+-------------------+-------------------------------------------------------------+
| Data Processing   | Pandas 2.0+, NumPy, openpyxl, python-multipart              |
+-------------------+-------------------------------------------------------------+
| AI & LLM          | Google Gemini API (`google-genai`), Structured JSON Mode,   |
|                   | Deterministic Rule-Based Fallback Engine                    |
+-------------------+-------------------------------------------------------------+
| Testing & QA      | Python `unittest`, FastAPI `TestClient`, HTTPX              |
+-------------------+-------------------------------------------------------------+
| Export & Print    | Dynamic CSV Generation, Print Stylesheet (`@media print`)   |
+-------------------+-------------------------------------------------------------+
```

---

## Project Structure

```
Retail - Sales and Inventory Copilot/
├── app.py                              # FastAPI server, REST API endpoints, and startup lifecycle
├── requirements.txt                    # Project Python dependencies
├── README.md                           # Comprehensive project documentation
├── data/
│   ├── datasets/                       # Isolated SQLite databases and metadata registry
│   │   ├── datasets_metadata.json      # Single Active Dataset registry
│   │   ├── empty.sqlite                # Zero-row schema template for NO_DATA state
│   │   └── demo.sqlite                 # 10-Year historical retail demo database
│   ├── generate_data.py                # Synthetic 10-year retail dataset generator (seed: 42)
│   ├── sales.csv                       # 10-Year synthetic transactional sales records
│   ├── inventory.csv                   # Synthetic inventory stock levels
│   ├── inventory_movements.csv         # 10-Year audited inventory movement ledger
│   ├── products.csv                    # Product catalog records (40 SKUs)
│   └── stores.csv                      # Store location records (5 stores)
├── src/
│   ├── __init__.py                     # Package initialization
│   ├── analytics.py                    # Top-level KPI aggregations and dashboard summaries
│   ├── analytics_engine.py             # Multi-dimensional analytics computation engine
│   ├── chart_engine.py                 # Pure SVG chart definition generator
│   ├── database.py                     # SQLite connection helper and query runner
│   ├── dataset_manager.py              # Single Active Dataset Manager, staging, and lifecycle
│   ├── evidence.py                     # Structured evidence data models
│   ├── evidence_engine.py              # Evidence classification and taxonomy builder
│   ├── forecasting.py                  # Demand forecasting algorithms
│   ├── gemini.py                       # Google Gemini client and offline fallback engine
│   ├── inventory_rules.py              # ADS calculation, days remaining, and inventory status
│   ├── query_context.py                # Canonical query specification models
│   ├── query_engine.py                 # Intent routing and query orchestration
│   ├── query_planner.py                # Natural language intent parsing and entity extraction
│   ├── recommendation.py               # Operational attention item detection
│   ├── response_engine.py              # Structured response packaging and formatting
│   ├── sales_rules.py                  # Multi-year sales trends, spikes, drops, and seasonality
│   └── validation.py                   # Data ingestion schema and referential integrity validator
├── static/
│   ├── app.js                          # Frontend client logic, state sync, and view rendering
│   ├── index.html                      # Single-page web application UI and layout
│   └── style.css                       # Modern enterprise B2B stylesheet and design tokens
└── tests/
    ├── test_active_dataset_propagation.py # Entity isolation and active dataset verification
    ├── test_ai_grounding.py               # AI grounding and unresolved entity guardrail tests
    ├── test_analytics_seasonality_compare.py # Seasonality and multi-store comparison tests
    ├── test_copilot_dataset_isolation.py  # Context wipe and Copilot isolation tests
    ├── test_copilot_intents.py            # Natural language intent routing test suite
    ├── test_dataset_integrity.py          # SQLite referential integrity and orphan file tests
    ├── test_dataset_isolation.py          # Multi-dataset data separation tests
    ├── test_dataset_lifecycle.py          # Upload, atomic promotion, and deletion tests
    ├── test_no_data_state.py              # Clean empty state (NO_DATA) contract tests
    ├── test_single_active_dataset.py      # End-to-end Single Active Dataset replacement tests
    └── test_upload_validation.py          # Strict upload validation and mutual exclusivity tests
```

---

## Installation

### Prerequisites
- **Python 3.9+** (Tested and certified on Python 3.11 and Python 3.14)
- **Git**

### Step 1: Clone Repository
```bash
git clone https://github.com/puliujwal143/Retail---Sales-and-Inventory-Copilot.git
cd "Retail - Sales and Inventory Copilot"
```

### Step 2: Create Virtual Environment
On Windows (PowerShell / Command Prompt):
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

On Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Configuration & Environment Variables

RetailIQ functions out-of-the-box in **Offline Deterministic Mode** without requiring any external API keys. To enable Google Gemini conversational explanations:

### Environment Variable
| Variable Name | Required? | Description |
|---|---|---|
| `GEMINI_API_KEY` | Optional | Google Gemini API key for natural language explanations. If omitted, the system seamlessly falls back to the deterministic explanation engine. |

### Setting the Environment Variable

On Windows (PowerShell):
```powershell
$env:GEMINI_API_KEY="your_actual_api_key_here"
```

On Windows (Command Prompt):
```cmd
set GEMINI_API_KEY=your_actual_api_key_here
```

On Linux / macOS:
```bash
export GEMINI_API_KEY="your_actual_api_key_here"
```

> **Security Note**: Never commit API keys or `.env` files to public version control repositories.

---

## Running the Application

### Start the Server
```bash
python app.py
```
*Or run using Uvicorn directly:*
```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Access the Web Dashboard
Open your browser and navigate to:
```
http://localhost:8000
```

### Recommended User Walkthrough
1. **Explore the Demo Dataset**: Click through the **Dashboard**, **Inventory Health**, **Sales Analytics**, and **Reorder Planner** tabs to inspect real-time metrics and charts.
2. **Interact with the AI Copilot**:
   - Ask *"What needs my attention today?"* to see prioritized stockout risks.
   - Ask *"Which products should I reorder?"* to view exact 7-day target replenishment calculations.
   - Ask *"How did sales perform in 2025?"* to inspect annual growth statistics.
3. **Test Historical Date Snapshots**: Select any date from the top header dropdown (e.g., `2024-06-15`) to see the entire dashboard reconstruct historical inventory and sales as of that date.
4. **Upload Custom Retail Data**: Navigate to **Data Management Workbench**, enter a Dataset Name, choose your upload mode (Single File or 4 Separate CSVs), profile the schema, and click **Import & Activate Dataset** to switch the workspace.

---

## Testing & Quality Assurance

RetailIQ includes an automated test suite comprising **109 unit and integration tests** covering API contracts, dataset isolation, AI grounding, mathematical accuracy, and upload validation.

### Run All Unit & Integration Tests
```bash
python -m unittest discover tests -v
```

### Verified Test Suite Breakdown

```
+----------------------------------------+------------+--------------------------------------------------------+
| Test File                              | Test Count | Primary Focus Area                                     |
+----------------------------------------+------------+--------------------------------------------------------+
| test_upload_validation.py              | 9 tests    | Strict upload mode validation & mutual exclusivity     |
| test_single_active_dataset.py          | 20 tests   | Single Active Dataset replacement lifecycle            |
| test_dataset_lifecycle.py              | 7 tests    | Atomic staging, promotion, deletion, and rollback      |
| test_dataset_isolation.py              | 8 tests    | Zero cross-dataset data leakage assertions             |
| test_dataset_integrity.py              | 12 tests   | SQLite referential integrity & orphan file detection   |
| test_no_data_state.py                  | 3 tests    | Clean empty state contracts across all endpoints       |
| test_copilot_dataset_isolation.py      | 8 tests    | Context wipe and conversational scope isolation        |
| test_copilot_intents.py                | 26 tests   | Natural language intent routing and entity matching    |
| test_ai_grounding.py                   | 6 tests    | Anti-hallucination & unresolved entity guardrails      |
| test_analytics_seasonality_compare.py  | 5 tests    | Seasonality indices & multi-store comparison math      |
| test_active_dataset_propagation.py     | 5 tests    | Overlapping ID isolation and live propagation          |
+----------------------------------------+------------+--------------------------------------------------------+
| TOTAL VERIFIED PASSING TESTS           | 109 tests  | 100% Passing (Ran in ~14.6s)                           |
+----------------------------------------+------------+--------------------------------------------------------+
```

---

## Data Integrity, AI Grounding & Safety

```
+-----------------------------------------------------------------------------------+
|                        DATA INTEGRITY & GROUNDING GUARANTEES                      |
+-----------------------------------------------------------------------------------+
| 1. Cryptographic Dataset Isolation                                                |
|    Each dataset is stored in an independent SQLite file (ds_<uuid>.sqlite).       |
|    There are no shared tables or cross-database foreign keys.                     |
+-----------------------------------------------------------------------------------+
| 2. Atomic Replacement & Garbage Collection                                        |
|    Activating a new dataset deletes previous custom database files on disk,       |
|    preventing storage bloat and accidental data mixing.                           |
+-----------------------------------------------------------------------------------+
| 3. In-Memory Cache Invalidation & Conversational Memory Wipe                      |
|    Dataset transitions trigger registered callbacks that flush analytical caches  |
|    and wipe conversational history, ensuring AI reasoning starts from zero.       |
+-----------------------------------------------------------------------------------+
| 4. Entity-Level Verification & Anti-Hallucination Guardrails                      |
|    Queries referencing non-existent SKUs/stores immediately return structured     |
|    NO_DATA grounding responses, preventing the LLM from substituting totals.     |
+-----------------------------------------------------------------------------------+
| 5. Explicit Assumption Disclosure                                                 |
|    Every recommendation details its underlying assumptions: rolling 30-day ADS    |
|    window, 7-day target coverage, and 30-day overstock threshold.                 |
+-----------------------------------------------------------------------------------+
```

---

## Design & Product Principles

- **Deterministic Supremacy**: Calculations must always be performed by deterministic Python algorithms, never estimated by generative AI.
- **Evidence Over Assumption**: Every recommendation must cite observable facts from transactional ledgers.
- **Fail-Safe Offline Operation**: Core business analytics and decision workflows must function seamlessly without external cloud API dependencies.
- **Single Source of Truth**: The active dataset must govern every screen, calculation, report, and conversational insight across the platform.

---

## Final Project Status

| Area | Status | Verification Summary |
|---|---|---|
| **Core Analytics Engine** | Verified | Rolling ADS, days remaining, inventory valuation, margin, and YoY growth |
| **Data Ingestion & Profiler**| Verified | Dual upload modes, strict validation, column auto-mapping, and smart synthesis |
| **Dataset Isolation** | Verified | Single Active Dataset Replacement Model with atomic SQLite promotion |
| **AI Copilot** | Verified | Grounded Gemini integration + Offline Deterministic Fallback Engine |
| **Visualizations & UI** | Verified | Pure SVG multi-timeframe charts, printable BI report, and Decision Center |
| **Test Suite** | Verified | **109 / 109 automated tests passing** |
| **Deployment** | Verified | Single-command startup (`python app.py`) on port 8000 |

---

## Disclaimer & Operational Limitations

- **Prototype & Operational System**: RetailIQ is an operational decision support system designed to assist retail managers. Procurement and financial decisions should be verified against enterprise ERP systems.
- **External Variable Boundaries**: RetailIQ analyzes internal point-of-sale (POS) and inventory movement data. It explicitly refuses to speculate on unrecorded external factors (such as unlogged marketing spend, competitor pricing, or macroeconomic shifts).
- **Supported File Types**: Ingestion supports `.csv`, `.xlsx`, and `.xls` files formatted according to standard tabular retail conventions.