TRACK_ID=PS03

# Retail - Sales and Inventory Copilot (RetailIQ)

RetailIQ is an evidence-first AI Copilot and Retail Intelligence application for store managers running multi-store small-to-medium retail operations.

It combines a **Deterministic Python Analytics Engine** with **Google Gemini LLM** to deliver natural-language insights, stock-out predictions, reorder recommendations, and trend analysis—strictly backed by verifiable data evidence and transparent business assumptions.

---

## Architecture Overview

```
Browser (http://localhost:8000)
    │
    ▼
FastAPI Server (0.0.0.0:8000)
    │
    ├── Direct API Endpoints (/api/dashboard, /api/inventory, /api/sales, etc.)
    │
    ▼
Query Engine & Natural Language Intent Classifier
    │
    ▼
Deterministic Retail Intelligence Engine (Python + Pandas + SQLite)
    │   ├── Stock-Out Prediction Engine
    │   ├── Slow-Moving Inventory & Overstock Detector
    │   ├── Period-over-Period Sales Trend Engine
    │   └── Reorder Recommendation Engine
    │
    ▼
Structured Evidence & Assumption Package
    │
    ▼
Google Gemini API (google-genai / gemini-3.5-flash-lite)
    │   └── Explanation Layer ONLY (Strict Data-Grounded System Prompt)
    │
    ▼
Structured JSON Response → Modern SaaS Frontend
```

### Core Architecture Principles
1. **Deterministic Source of Truth**: Python performs all calculations, aggregation, stock-out risks, and reorder formulas. Gemini never invents numbers.
2. **Evidence-First**: Every answer displays exact supporting numbers, calculation periods, target thresholds, and explicit assumptions.
3. **Data-Grounded & Strict Fallback**: When input data is insufficient (e.g., asking why sales increased without promotional data), the system explicitly refuses to guess. If the Gemini API is unreachable or key is unconfigured, the app falls back seamlessly to a deterministic text response.
4. **Single-Command Startup**: Both backend and static frontend are served directly by FastAPI on port 8000. No separate build tools or node servers required.

---

## Dataset Description

The application includes realistic synthetic retail operational data generated for 5 stores over a 90-day period:

- **Stores**: Downtown Flagship, Metro Hub, Westside Plaza, North Park Outlet, Airport Express.
- **Products**: 40 distinct products across 8 categories (*Electronics, Accessories, Audio, Computers, Mobile, Home Appliances, Office, Gaming*).
- **Inventory**: Stock levels, reorder points, cost prices, selling prices across all store-product combinations.
- **Sales History**: Daily transactional sales with built-in realistic business scenarios:
  - Critical stock-out risk (e.g. Wireless Ergonomic Mouse)
  - Warning stock-out risk (e.g. Noise-Canceling Headphones)
  - Overstocked items (e.g. USB-C Cable 2m)
  - Slow-moving inventory (e.g. Smart Watch Band)
  - Sales spikes (e.g. Pro Laptop 15-inch with +40% increase)
  - Sales drops (e.g. Gaming Controller)
  - Insufficient data scenario (e.g. missing promotional/marketing logs)

---

## Key Business Assumptions & Thresholds

| Metric | Calculation / Business Rule | Threshold |
|--------|-----------------------------|-----------|
| **Average Daily Sales (ADS)** | `Total Units Sold (Last 30 Days) / 30` | N/A |
| **Days Remaining** | `Current Stock / ADS` | Safe handling for 0 sales |
| **Stock-Out Status** | `Days Remaining <= 2` → **CRITICAL**<br>`Days Remaining <= 7` → **WARNING**<br>Otherwise → **HEALTHY** | Configurable in `inventory_rules.py` |
| **Target Inventory Coverage** | Standard stock target to cover future demand | **7 Days** (Configurable) |
| **Recommended Reorder** | `max(0, (ADS * Target Coverage) - Current Stock)` | Rounded up to integer |
| **Overstock Threshold** | `Days Remaining > 30` AND `Current Stock >= 50` | Flagged as Overstocked |
| **Slow-Moving Threshold** | `Sales (Last 30 Days) < 5` AND `Current Stock >= 20` | Flagged as Slow-Moving |
| **Sales Spike / Drop** | `((Current 30d Sales - Previous 30d Sales) / Previous 30d Sales) * 100` | ** Spike >= +30%**<br>** Drop <= -30%** |

---

## Features

- 📊 **Executive Dashboard**: Real-time sales, unit volume, inventory valuation, attention alert banners, top performing products, and store distribution charts.
- 📦 **Inventory Management**: Searchable and filterable table by Store, Category, and Inventory Status with instant reorder quantity insights.
- 📈 **Sales Analytics**: 90-day daily revenue trend, store-by-store performance, top growth & decline analysis.
- 🤖 **AI Copilot**: Interactive natural language assistant powered by Gemini API, complete with structured output: Answer, Key Metrics, Recommended Action, Detailed Evidence, Business Assumptions, and Data Sufficiency badges.
- ⚡ **Offline-First & Fast**: Zero external CDN script dependencies. Pure Vanilla HTML/CSS/JS with embedded responsive SVG graphics. Startup time < 3 seconds.

---

## How to Run

### Requirements
- Python 3.9+ (Tested on Python 3.11)
- Environment Variable: `GEMINI_API_KEY` (Optional; system will fall back to deterministic response if absent)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Set Environment Variable (Optional for Gemini integration)
On Windows (PowerShell):
```powershell
$env:GEMINI_API_KEY="your_gemini_api_key_here"
```
On Linux / macOS:
```bash
export GEMINI_API_KEY="your_gemini_api_key_here"
```

### Step 3: Start Application
```bash
python app.py
```

### Step 4: Open in Browser
Open your browser and navigate to:
```
http://localhost:8000
```

---

## Interactive Demo Flow

1. **Dashboard Overview**: Review real-time KPIs and top alerts on the home tab.
2. **Copilot Query 1 ("What needs my attention today?")**: View instant severity-ranked critical stock, slow-moving items, and sales anomalies.
3. **Copilot Query 2 ("What should I reorder?")**: Inspect products requiring stock replenishment along with daily demand, current stock, and calculated reorder units.
4. **Copilot Query 3 ("How did laptops perform this month?")**: See exact period sales figures and growth percentages.
5. **Copilot Query 4 ("Why did laptop sales increase?")**: Observe the evidence-grounding feature in action. The copilot acknowledges the 40% sales rise but explicitly states that missing marketing/promotional data prevents determining the root cause.

---

## Known Limitations & Design Choices
- **Deterministic Supremacy**: Calculations are executed entirely in Python SQLite queries to guarantee 100% numerical accuracy.
- **Data Boundaries**: The copilot will refuse to speculate on external factors (marketing campaigns, competitor prices, weather) not present in the dataset.
- **Offline Reliability**: Uses standalone static assets without third-party JS libraries, ensuring high performance under strict network constraints.
