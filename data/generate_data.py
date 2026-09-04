import os
import csv
import random
from datetime import datetime, timedelta

def generate_retail_dataset():
    data_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(data_dir, exist_ok=True)

    random.seed(42)  # Reproducible seed for 10-year dataset

    # 1. Stores with realistic opening dates across 10 years (2016 to 2022)
    stores = [
        {"store_id": "STR001", "store_name": "Downtown Flagship", "location": "City Center", "size_sqft": 12000, "open_date": "2016-01-01"},
        {"store_id": "STR002", "store_name": "Metro Hub Store", "location": "Transit Center", "size_sqft": 8500, "open_date": "2017-03-01"},
        {"store_id": "STR003", "store_name": "Westside Plaza", "location": "Suburban Mall", "size_sqft": 10000, "open_date": "2018-06-01"},
        {"store_id": "STR004", "store_name": "North Park Outlet", "location": "North Suburbs", "size_sqft": 6000, "open_date": "2020-01-15"},
        {"store_id": "STR005", "store_name": "Airport Express", "location": "Terminal 2", "size_sqft": 3500, "open_date": "2022-04-01"},
    ]

    stores_csv = os.path.join(data_dir, "stores.csv")
    with open(stores_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["store_id", "store_name", "location", "size_sqft", "open_date"])
        writer.writeheader()
        writer.writerows(stores)

    # 2. Products with introduction dates (catalog growth from 2016 to 2022)
    products = [
        # 2016 Launch SKUs (Computers, Core Accessories)
        {"product_id": "PRD001", "product_name": "Pro Laptop 15-inch", "category": "Computers", "cost_price": 850.00, "unit_price": 1200.00, "reorder_point": 10, "intro_date": "2016-01-01"},
        {"product_id": "PRD002", "product_name": "Ultra Slim Notebook 13", "category": "Computers", "cost_price": 650.00, "unit_price": 950.00, "reorder_point": 8, "intro_date": "2016-01-01"},
        {"product_id": "PRD003", "product_name": "Desktop Workstation i7", "category": "Computers", "cost_price": 1100.00, "unit_price": 1600.00, "reorder_point": 5, "intro_date": "2016-01-01"},
        {"product_id": "PRD004", "product_name": "Gaming Desktop RTX", "category": "Gaming", "cost_price": 1400.00, "unit_price": 2000.00, "reorder_point": 4, "intro_date": "2016-01-01"},
        {"product_id": "PRD005", "product_name": "Curved Monitor 27-inch", "category": "Electronics", "cost_price": 180.00, "unit_price": 280.00, "reorder_point": 12, "intro_date": "2016-01-01"},
        {"product_id": "PRD006", "product_name": "Wireless Ergonomic Mouse", "category": "Accessories", "cost_price": 18.00, "unit_price": 35.00, "reorder_point": 25, "intro_date": "2016-01-01"},
        {"product_id": "PRD007", "product_name": "Mechanical RGB Keyboard", "category": "Accessories", "cost_price": 45.00, "unit_price": 85.00, "reorder_point": 15, "intro_date": "2016-01-01"},
        {"product_id": "PRD008", "product_name": "USB-C Multi-Port Hub", "category": "Accessories", "cost_price": 22.00, "unit_price": 45.00, "reorder_point": 20, "intro_date": "2016-01-01"},
        {"product_id": "PRD009", "product_name": "USB-C Cable 2m", "category": "Accessories", "cost_price": 4.00, "unit_price": 15.00, "reorder_point": 30, "intro_date": "2016-01-01"},
        {"product_id": "PRD010", "product_name": "HD Webcam 1080p", "category": "Electronics", "cost_price": 30.00, "unit_price": 60.00, "reorder_point": 12, "intro_date": "2016-01-01"},

        # 2018 Launch SKUs (Audio, Mobile)
        {"product_id": "PRD011", "product_name": "Noise-Canceling Headphones", "category": "Audio", "cost_price": 120.00, "unit_price": 220.00, "reorder_point": 15, "intro_date": "2018-03-01"},
        {"product_id": "PRD012", "product_name": "Bluetooth Speaker Portable", "category": "Audio", "cost_price": 35.00, "unit_price": 75.00, "reorder_point": 20, "intro_date": "2018-03-01"},
        {"product_id": "PRD013", "product_name": "True Wireless Earbuds", "category": "Audio", "cost_price": 50.00, "unit_price": 110.00, "reorder_point": 25, "intro_date": "2018-03-01"},
        {"product_id": "PRD014", "product_name": "Studio Condenser Mic", "category": "Audio", "cost_price": 70.00, "unit_price": 130.00, "reorder_point": 8, "intro_date": "2018-03-01"},
        {"product_id": "PRD015", "product_name": "Soundbar with Subwoofer", "category": "Audio", "cost_price": 110.00, "unit_price": 210.00, "reorder_point": 10, "intro_date": "2018-03-01"},
        {"product_id": "PRD016", "product_name": "Flagship Smartphone 128GB", "category": "Mobile", "cost_price": 600.00, "unit_price": 899.00, "reorder_point": 10, "intro_date": "2018-09-01"},
        {"product_id": "PRD017", "product_name": "Budget Smartphone 64GB", "category": "Mobile", "cost_price": 180.00, "unit_price": 299.00, "reorder_point": 15, "intro_date": "2018-09-01"},
        {"product_id": "PRD018", "product_name": "Tablet 10-inch 64GB", "category": "Mobile", "cost_price": 220.00, "unit_price": 349.00, "reorder_point": 12, "intro_date": "2018-09-01"},
        {"product_id": "PRD019", "product_name": "Smart Fitness Watch", "category": "Mobile", "cost_price": 85.00, "unit_price": 149.00, "reorder_point": 15, "intro_date": "2018-09-01"},
        {"product_id": "PRD020", "product_name": "Smart Watch Replacement Band", "category": "Mobile", "cost_price": 5.00, "unit_price": 25.00, "reorder_point": 20, "intro_date": "2018-09-01"},

        # 2020 Launch SKUs (Home Appliances, Office Storage)
        {"product_id": "PRD021", "product_name": "Robotic Vacuum Cleaner", "category": "Home Appliances", "cost_price": 180.00, "unit_price": 320.00, "reorder_point": 8, "intro_date": "2020-02-01"},
        {"product_id": "PRD022", "product_name": "Air Purifier HEPA", "category": "Home Appliances", "cost_price": 90.00, "unit_price": 160.00, "reorder_point": 10, "intro_date": "2020-02-01"},
        {"product_id": "PRD023", "product_name": "Compact Espresso Machine", "category": "Home Appliances", "cost_price": 110.00, "unit_price": 199.00, "reorder_point": 6, "intro_date": "2020-02-01"},
        {"product_id": "PRD024", "product_name": "Smart LED Desk Lamp", "category": "Home Appliances", "cost_price": 20.00, "unit_price": 45.00, "reorder_point": 15, "intro_date": "2020-02-01"},
        {"product_id": "PRD025", "product_name": "Electric Kettle 1.7L", "category": "Home Appliances", "cost_price": 15.00, "unit_price": 35.00, "reorder_point": 12, "intro_date": "2020-02-01"},
        {"product_id": "PRD026", "product_name": "Portable SSD 1TB", "category": "Office", "cost_price": 60.00, "unit_price": 105.00, "reorder_point": 15, "intro_date": "2020-06-01"},
        {"product_id": "PRD027", "product_name": "External Hard Drive 4TB", "category": "Office", "cost_price": 70.00, "unit_price": 115.00, "reorder_point": 10, "intro_date": "2020-06-01"},
        {"product_id": "PRD028", "product_name": "Ergonomic Office Chair", "category": "Office", "cost_price": 140.00, "unit_price": 260.00, "reorder_point": 5, "intro_date": "2020-06-01"},
        {"product_id": "PRD029", "product_name": "Motorized Standing Desk", "category": "Office", "cost_price": 250.00, "unit_price": 450.00, "reorder_point": 4, "intro_date": "2020-06-01"},
        {"product_id": "PRD030", "product_name": "Wireless Document Scanner", "category": "Office", "cost_price": 130.00, "unit_price": 220.00, "reorder_point": 5, "intro_date": "2020-06-01"},

        # 2022 Launch SKUs (Gaming VR, Accessories)
        {"product_id": "PRD031", "product_name": "Next-Gen Gaming Console", "category": "Gaming", "cost_price": 400.00, "unit_price": 499.00, "reorder_point": 8, "intro_date": "2022-01-15"},
        {"product_id": "PRD032", "product_name": "Retro Gaming Controller", "category": "Gaming", "cost_price": 25.00, "unit_price": 55.00, "reorder_point": 15, "intro_date": "2022-01-15"},
        {"product_id": "PRD033", "product_name": "Gaming Headset 7.1 Surround", "category": "Gaming", "cost_price": 45.00, "unit_price": 89.00, "reorder_point": 12, "intro_date": "2022-01-15"},
        {"product_id": "PRD034", "product_name": "VR Headset 128GB", "category": "Gaming", "cost_price": 290.00, "unit_price": 399.00, "reorder_point": 6, "intro_date": "2022-01-15"},
        {"product_id": "PRD035", "product_name": "Racing Wheel Controller", "category": "Gaming", "cost_price": 150.00, "unit_price": 270.00, "reorder_point": 4, "intro_date": "2022-01-15"},
        {"product_id": "PRD036", "product_name": "Wireless Charging Pad", "category": "Accessories", "cost_price": 10.00, "unit_price": 25.00, "reorder_point": 20, "intro_date": "2022-05-01"},
        {"product_id": "PRD037", "product_name": "Laptop Backpack Water Resistant", "category": "Accessories", "cost_price": 25.00, "unit_price": 59.00, "reorder_point": 15, "intro_date": "2022-05-01"},
        {"product_id": "PRD038", "product_name": "Surge Protector 8-Outlet", "category": "Electronics", "cost_price": 12.00, "unit_price": 29.00, "reorder_point": 25, "intro_date": "2022-05-01"},
        {"product_id": "PRD039", "product_name": "Stylus Pen Universal", "category": "Accessories", "cost_price": 15.00, "unit_price": 39.00, "reorder_point": 10, "intro_date": "2022-05-01"},
        {"product_id": "PRD040", "product_name": "Legacy Media Adapter", "category": "Electronics", "cost_price": 8.00, "unit_price": 19.00, "reorder_point": 10, "intro_date": "2016-01-01"},
    ]

    products_csv = os.path.join(data_dir, "products.csv")
    with open(products_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["product_id", "product_name", "category", "cost_price", "unit_price", "reorder_point", "intro_date"])
        writer.writeheader()
        writer.writerows(products)

    # 3. 10-Year Sales Dataset Generation (2016-01-01 to 2026-09-03)
    start_date = datetime(2016, 1, 1)
    end_date = datetime(2026, 9, 3)
    total_days = (end_date - start_date).days + 1

    sales_records = []
    movement_records = []
    running_stock = {}  # (store_id, product_id) -> int

    for day_offset in range(total_days):
        current_dt = start_date + timedelta(days=day_offset)
        date_str = current_dt.strftime("%Y-%m-%d")
        year = current_dt.year
        month = current_dt.month
        is_weekend = current_dt.weekday() in (5, 6)

        # Multi-year growth multiplier (e.g. 2016 is 0.4x, scaling to 1.0x in 2026)
        year_growth_multiplier = 0.4 + (year - 2016) * 0.06

        # Seasonality multiplier: Nov-Dec holiday boost (1.5x), Aug-Sep back to school (1.25x)
        season_mult = 1.0
        if month in (11, 12):
            season_mult = 1.5
        elif month in (8, 9):
            season_mult = 1.25

        weekend_mult = 1.25 if is_weekend else 1.0

        for s in stores:
            s_id = s["store_id"]
            if date_str < s["open_date"]:
                continue  # Store not open yet

            for p in products:
                p_id = p["product_id"]
                if date_str < p["intro_date"]:
                    continue  # Product not introduced yet

                key = (s_id, p_id)

                # Initialize stock ledger balance if this is the first day store/product is active
                if key not in running_stock:
                    init_stock = random.randint(30, 80)
                    running_stock[key] = init_stock
                    movement_records.append({
                        "movement_id": f"MOV_INIT_{date_str.replace('-','')}_{s_id}_{p_id}",
                        "date": date_str,
                        "store_id": s_id,
                        "product_id": p_id,
                        "movement_type": "OPENING",
                        "quantity": init_stock,
                        "reason": "Opening Catalog Inventory"
                    })

                # Base sales probability
                base_prob = 0.25 * year_growth_multiplier * season_mult * weekend_mult

                # Specific SKUs override rules for grounded scenarios:
                if p_id == "PRD006":  # Ergonomic Mouse (High volume)
                    base_prob *= 2.0
                elif p_id == "PRD011": # Headphones
                    base_prob *= 1.5
                elif p_id == "PRD020": # Watch Band (Slow moving)
                    base_prob *= 0.1
                elif p_id == "PRD009": # USB Cable (High stock overstock)
                    base_prob *= 0.8

                if random.random() < min(0.95, base_prob):
                    max_q = 3 if p["unit_price"] > 300 else 6
                    qty = random.randint(1, max_q)

                    # Deduct from running stock (prevent negative)
                    qty = min(qty, max(1, running_stock[key]))
                    running_stock[key] -= qty

                    unit_price = p["unit_price"]
                    revenue = round(qty * unit_price, 2)

                    sales_records.append({
                        "sale_id": f"SAL_{date_str.replace('-','')}_{s_id}_{p_id}",
                        "date": date_str,
                        "store_id": s_id,
                        "product_id": p_id,
                        "quantity": qty,
                        "unit_price": unit_price,
                        "total_revenue": revenue
                    })

                    movement_records.append({
                        "movement_id": f"MOV_SALE_{date_str.replace('-','')}_{s_id}_{p_id}",
                        "date": date_str,
                        "store_id": s_id,
                        "product_id": p_id,
                        "movement_type": "SALE",
                        "quantity": -qty,
                        "reason": "Customer Sale Transaction"
                    })

                # Automatic Periodic Supplier Replenishment Purchase Order
                if running_stock[key] <= p["reorder_point"]:
                    po_qty = random.randint(25, 60)
                    # For demo scenario PRD006 at STR001 on final date, keep stock low (6 units) for Critical Alert
                    if date_str >= "2026-08-25" and p_id == "PRD006" and s_id == "STR001":
                        pass  # Allow stock to remain low at 6
                    elif date_str >= "2026-08-25" and p_id == "PRD011" and s_id == "STR001":
                        pass  # Allow stock to remain warning at 15
                    else:
                        running_stock[key] += po_qty
                        movement_records.append({
                            "movement_id": f"MOV_PURCH_{date_str.replace('-','')}_{s_id}_{p_id}",
                            "date": date_str,
                            "store_id": s_id,
                            "product_id": p_id,
                            "movement_type": "PURCHASE",
                            "quantity": po_qty,
                            "reason": "Supplier Replenishment"
                        })

    # Save Sales CSV
    sales_csv = os.path.join(data_dir, "sales.csv")
    with open(sales_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["sale_id", "date", "store_id", "product_id", "quantity", "unit_price", "total_revenue"])
        writer.writeheader()
        writer.writerows(sales_records)

    # Save Inventory Movements CSV
    movements_csv = os.path.join(data_dir, "inventory_movements.csv")
    with open(movements_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["movement_id", "date", "store_id", "product_id", "movement_type", "quantity", "reason"])
        writer.writeheader()
        writer.writerows(movement_records)

    # 4. Save Final Real-Time Current Inventory Table
    inventory_records = []
    for s in stores:
        s_id = s["store_id"]
        for p in products:
            p_id = p["product_id"]
            key = (s_id, p_id)
            stock = running_stock.get(key, 0)
            
            # Specific stock levels for demo scenarios on final date:
            if p_id == "PRD006" and s_id == "STR001":
                stock = 6
            elif p_id == "PRD011" and s_id == "STR001":
                stock = 15
            elif p_id == "PRD009" and s_id == "STR001":
                stock = 180
            elif p_id == "PRD020" and s_id == "STR001":
                stock = 45

            inventory_records.append({
                "store_id": s_id,
                "product_id": p_id,
                "current_stock": stock,
                "last_restock_date": "2026-08-25"
            })

    inventory_csv = os.path.join(data_dir, "inventory.csv")
    with open(inventory_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["store_id", "product_id", "current_stock", "last_restock_date"])
        writer.writeheader()
        writer.writerows(inventory_records)

    print(f"10-Year Retail Dataset generated successfully in '{data_dir}':")
    print(f"- Range: 2016-01-01 to 2026-09-03 ({total_days} days)")
    print(f"- Stores: {len(stores)}")
    print(f"- Products: {len(products)}")
    print(f"- Sales Records: {len(sales_records)}")
    print(f"- Movements Audit Records: {len(movement_records)}")
    print(f"- Inventory Master Records: {len(inventory_records)}")

if __name__ == "__main__":
    generate_retail_dataset()
