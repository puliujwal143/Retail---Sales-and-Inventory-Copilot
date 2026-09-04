import os
import csv
import random
from datetime import datetime, timedelta

def generate_retail_dataset():
    data_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(data_dir, exist_ok=True)

    # 1. Stores (5 stores)
    stores = [
        {"store_id": "STR001", "store_name": "Downtown Flagship", "location": "City Center", "size_sqft": 12000},
        {"store_id": "STR002", "store_name": "Metro Hub Store", "location": "Transit Center", "size_sqft": 8500},
        {"store_id": "STR003", "store_name": "Westside Plaza", "location": "Suburban Mall", "size_sqft": 10000},
        {"store_id": "STR004", "store_name": "North Park Outlet", "location": "North Suburbs", "size_sqft": 6000},
        {"store_id": "STR005", "store_name": "Airport Express", "location": "Terminal 2", "size_sqft": 3500},
    ]

    stores_csv = os.path.join(data_dir, "stores.csv")
    with open(stores_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["store_id", "store_name", "location", "size_sqft"])
        writer.writeheader()
        writer.writerows(stores)

    # 2. Products (40 products across 8 categories)
    products = [
        # Electronics & Computers
        {"product_id": "PRD001", "product_name": "Pro Laptop 15-inch", "category": "Computers", "cost_price": 850.00, "unit_price": 1200.00, "reorder_point": 10},
        {"product_id": "PRD002", "product_name": "Ultra Slim Notebook 13", "category": "Computers", "cost_price": 650.00, "unit_price": 950.00, "reorder_point": 8},
        {"product_id": "PRD003", "product_name": "Desktop Workstation i7", "category": "Computers", "cost_price": 1100.00, "unit_price": 1600.00, "reorder_point": 5},
        {"product_id": "PRD004", "product_name": "Gaming Desktop RTX", "category": "Gaming", "cost_price": 1400.00, "unit_price": 2000.00, "reorder_point": 4},
        {"product_id": "PRD005", "product_name": "Curved Monitor 27-inch", "category": "Electronics", "cost_price": 180.00, "unit_price": 280.00, "reorder_point": 12},
        
        # Accessories & Peripherals
        {"product_id": "PRD006", "product_name": "Wireless Ergonomic Mouse", "category": "Accessories", "cost_price": 18.00, "unit_price": 35.00, "reorder_point": 25},
        {"product_id": "PRD007", "product_name": "Mechanical RGB Keyboard", "category": "Accessories", "cost_price": 45.00, "unit_price": 85.00, "reorder_point": 15},
        {"product_id": "PRD008", "product_name": "USB-C Multi-Port Hub", "category": "Accessories", "cost_price": 22.00, "unit_price": 45.00, "reorder_point": 20},
        {"product_id": "PRD009", "product_name": "USB-C Cable 2m", "category": "Accessories", "cost_price": 4.00, "unit_price": 15.00, "reorder_point": 30},
        {"product_id": "PRD010", "product_name": "HD Webcam 1080p", "category": "Electronics", "cost_price": 30.00, "unit_price": 60.00, "reorder_point": 12},

        # Audio
        {"product_id": "PRD011", "product_name": "Noise-Canceling Headphones", "category": "Audio", "cost_price": 120.00, "unit_price": 220.00, "reorder_point": 15},
        {"product_id": "PRD012", "product_name": "Bluetooth Speaker Portable", "category": "Audio", "cost_price": 35.00, "unit_price": 75.00, "reorder_point": 20},
        {"product_id": "PRD013", "product_name": "True Wireless Earbuds", "category": "Audio", "cost_price": 50.00, "unit_price": 110.00, "reorder_point": 25},
        {"product_id": "PRD014", "product_name": "Studio Condenser Mic", "category": "Audio", "cost_price": 70.00, "unit_price": 130.00, "reorder_point": 8},
        {"product_id": "PRD015", "product_name": "Soundbar with Subwoofer", "category": "Audio", "cost_price": 110.00, "unit_price": 210.00, "reorder_point": 10},

        # Mobile & Wearables
        {"product_id": "PRD016", "product_name": "Flagship Smartphone 128GB", "category": "Mobile", "cost_price": 600.00, "unit_price": 899.00, "reorder_point": 10},
        {"product_id": "PRD017", "product_name": "Budget Smartphone 64GB", "category": "Mobile", "cost_price": 180.00, "unit_price": 299.00, "reorder_point": 15},
        {"product_id": "PRD018", "product_name": "Tablet 10-inch 64GB", "category": "Mobile", "cost_price": 220.00, "unit_price": 349.00, "reorder_point": 12},
        {"product_id": "PRD019", "product_name": "Smart Fitness Watch", "category": "Mobile", "cost_price": 85.00, "unit_price": 149.00, "reorder_point": 15},
        {"product_id": "PRD020", "product_name": "Smart Watch Replacement Band", "category": "Mobile", "cost_price": 5.00, "unit_price": 25.00, "reorder_point": 20},

        # Home Appliances
        {"product_id": "PRD021", "product_name": "Robotic Vacuum Cleaner", "category": "Home Appliances", "cost_price": 180.00, "unit_price": 320.00, "reorder_point": 8},
        {"product_id": "PRD022", "product_name": "Air Purifier HEPA", "category": "Home Appliances", "cost_price": 90.00, "unit_price": 160.00, "reorder_point": 10},
        {"product_id": "PRD023", "product_name": "Compact Espresso Machine", "category": "Home Appliances", "cost_price": 110.00, "unit_price": 199.00, "reorder_point": 6},
        {"product_id": "PRD024", "product_name": "Smart LED Desk Lamp", "category": "Home Appliances", "cost_price": 20.00, "unit_price": 45.00, "reorder_point": 15},
        {"product_id": "PRD025", "product_name": "Electric Kettle 1.7L", "category": "Home Appliances", "cost_price": 15.00, "unit_price": 35.00, "reorder_point": 12},

        # Office & Storage
        {"product_id": "PRD026", "product_name": "Portable SSD 1TB", "category": "Office", "cost_price": 60.00, "unit_price": 105.00, "reorder_point": 15},
        {"product_id": "PRD027", "product_name": "External Hard Drive 4TB", "category": "Office", "cost_price": 70.00, "unit_price": 115.00, "reorder_point": 10},
        {"product_id": "PRD028", "product_name": "Ergonomic Office Chair", "category": "Office", "cost_price": 140.00, "unit_price": 260.00, "reorder_point": 5},
        {"product_id": "PRD029", "product_name": "Motorized Standing Desk", "category": "Office", "cost_price": 250.00, "unit_price": 450.00, "reorder_point": 4},
        {"product_id": "PRD030", "product_name": "Wireless Document Scanner", "category": "Office", "cost_price": 130.00, "unit_price": 220.00, "reorder_point": 5},

        # Gaming & VR
        {"product_id": "PRD031", "product_name": "Next-Gen Gaming Console", "category": "Gaming", "cost_price": 400.00, "unit_price": 499.00, "reorder_point": 8},
        {"product_id": "PRD032", "product_name": "Retro Gaming Controller", "category": "Gaming", "cost_price": 25.00, "unit_price": 55.00, "reorder_point": 15},
        {"product_id": "PRD033", "product_name": "Gaming Headset 7.1 Surround", "category": "Gaming", "cost_price": 45.00, "unit_price": 89.00, "reorder_point": 12},
        {"product_id": "PRD034", "product_name": "VR Headset 128GB", "category": "Gaming", "cost_price": 290.00, "unit_price": 399.00, "reorder_point": 6},
        {"product_id": "PRD035", "product_name": "Racing Wheel Controller", "category": "Gaming", "cost_price": 150.00, "unit_price": 270.00, "reorder_point": 4},

        # Additional items for depth
        {"product_id": "PRD036", "product_name": "Wireless Charging Pad", "category": "Accessories", "cost_price": 10.00, "unit_price": 25.00, "reorder_point": 20},
        {"product_id": "PRD037", "product_name": "Laptop Backpack Water Resistant", "category": "Accessories", "cost_price": 25.00, "unit_price": 59.00, "reorder_point": 15},
        {"product_id": "PRD038", "product_name": "Surge Protector 8-Outlet", "category": "Electronics", "cost_price": 12.00, "unit_price": 29.00, "reorder_point": 25},
        {"product_id": "PRD039", "product_name": "Stylus Pen Universal", "category": "Accessories", "cost_price": 15.00, "unit_price": 39.00, "reorder_point": 10},
        {"product_id": "PRD040", "product_name": "Legacy Media Adapter", "category": "Electronics", "cost_price": 8.00, "unit_price": 19.00, "reorder_point": 10},
    ]

    products_csv = os.path.join(data_dir, "products.csv")
    with open(products_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["product_id", "product_name", "category", "cost_price", "unit_price", "reorder_point"])
        writer.writeheader()
        writer.writerows(products)

    # 3. Sales History (90 days of daily sales per product/store)
    # Target date range: last 90 days ending yesterday
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    sales_records = []
    
    # We will seed specific scenarios across 90 days:
    # 1. PRD006 (Wireless Ergonomic Mouse): Very high demand recently (~4/day across stores) -> current stock 6 -> Critical Stock-Out (1.5 days)
    # 2. PRD011 (Noise-Canceling Headphones): Demand ~3/day -> current stock 15 -> Warning (5 days)
    # 3. PRD001 (Pro Laptop 15-inch): Spike in last 30 days (+40% compared to previous 30 days)
    # 4. PRD032 (Retro Gaming Controller): Drop in last 30 days (-70% compared to previous 30 days)
    # 5. PRD020 (Smart Watch Band): High inventory (45 units), low sales (2 units in 30 days) -> Slow moving
    # 6. PRD009 (USB-C Cable 2m): Huge inventory (180 units), moderate sales -> Overstock
    # 7. PRD040 (Legacy Media Adapter): Zero sales in last 60 days -> Insufficient sales movement

    random.seed(42)  # Reproducible seed

    # Generate daily sales for 90 days (day 0 to day 89)
    # Period 1: days 0-29 (60 to 90 days ago)
    # Period 2: days 30-59 (30 to 60 days ago)
    # Period 3: days 60-89 (last 30 days)

    for day_offset in range(90):
        current_dt = start_date + timedelta(days=day_offset)
        date_str = current_dt.strftime("%Y-%m-%d")
        
        period = 1 if day_offset < 30 else (2 if day_offset < 60 else 3)

        for s in stores:
            s_id = s["store_id"]
            for p in products:
                p_id = p["product_id"]

                # Default daily units
                base_prob = 0.35
                min_u, max_u = 1, 3

                # Product specific rules for realistic demo scenarios:
                if p_id == "PRD006":  # Wireless Ergonomic Mouse (High demand)
                    base_prob = 0.8
                    min_u, max_u = 2, 5
                elif p_id == "PRD011":  # Noise-Canceling Headphones
                    base_prob = 0.65
                    min_u, max_u = 1, 4
                elif p_id == "PRD001":  # Pro Laptop (Spike in period 3)
                    if period == 2:
                        base_prob = 0.4
                        min_u, max_u = 1, 2
                    elif period == 3:
                        base_prob = 0.75
                        min_u, max_u = 2, 4
                    else:
                        base_prob = 0.4
                        min_u, max_u = 1, 2
                elif p_id == "PRD032":  # Retro Gaming Controller (Drop in period 3)
                    if period == 2:
                        base_prob = 0.7
                        min_u, max_u = 2, 4
                    elif period == 3:
                        base_prob = 0.15
                        min_u, max_u = 1, 1
                    else:
                        base_prob = 0.6
                        min_u, max_u = 2, 3
                elif p_id == "PRD020":  # Smart Watch Band (Slow moving)
                    base_prob = 0.03
                    min_u, max_u = 1, 1
                elif p_id == "PRD009":  # USB-C Cable (Overstock)
                    base_prob = 0.3
                    min_u, max_u = 1, 2
                elif p_id == "PRD040":  # Legacy Media Adapter (Zero sales recently)
                    base_prob = 0.0 if period >= 2 else 0.05
                    min_u, max_u = 1, 1

                # Generate transaction
                if random.random() < base_prob:
                    qty = random.randint(min_u, max_u)
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

    sales_csv = os.path.join(data_dir, "sales.csv")
    with open(sales_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["sale_id", "date", "store_id", "product_id", "quantity", "unit_price", "total_revenue"])
        writer.writeheader()
        writer.writerows(sales_records)

    # 4. Inventory Data (Stock level per product and store)
    inventory_records = []
    for s in stores:
        s_id = s["store_id"]
        for p in products:
            p_id = p["product_id"]

            # Specific stock levels for demo scenarios:
            if p_id == "PRD006" and s_id == "STR001":
                # Critical stock: 6 units (ADS ~4 => 1.5 days)
                stock = 6
            elif p_id == "PRD006":
                stock = 12
            elif p_id == "PRD011" and s_id == "STR001":
                # Warning stock: 15 units (ADS ~3 => 5 days)
                stock = 15
            elif p_id == "PRD009" and s_id == "STR001":
                # Overstock: 180 units
                stock = 180
            elif p_id == "PRD020" and s_id == "STR001":
                # Slow moving: 45 units
                stock = 45
            else:
                # Normal stock based on reorder point
                stock = random.randint(p["reorder_point"] + 5, p["reorder_point"] + 40)

            inventory_records.append({
                "store_id": s_id,
                "product_id": p_id,
                "current_stock": stock,
                "last_restock_date": (end_date - timedelta(days=random.randint(5, 30))).strftime("%Y-%m-%d")
            })

    inventory_csv = os.path.join(data_dir, "inventory.csv")
    with open(inventory_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["store_id", "product_id", "current_stock", "last_restock_date"])
        writer.writeheader()
        writer.writerows(inventory_records)

    # 5. Inventory Movements (Historical audit trail for exact date snapshots)
    movement_records = []
    start_date_str = start_date.strftime("%Y-%m-%d")
    
    # Map sales by (date, store_id, product_id)
    sales_by_key = {}
    for s_rec in sales_records:
        key = (s_rec["date"], s_rec["store_id"], s_rec["product_id"])
        sales_by_key[key] = sales_by_key.get(key, 0) + s_rec["quantity"]

    # Reconstruct exact backward/forward ledger per (store_id, product_id)
    for inv_rec in inventory_records:
        s_id = inv_rec["store_id"]
        p_id = inv_rec["product_id"]
        curr_stock = inv_rec["current_stock"]

        # Sum all sales for this store & product over 90 days
        tot_sales = sum(qty for (d, s, p), qty in sales_by_key.items() if s == s_id and p == p_id)
        
        # Determine opening stock 90 days ago and restock events
        opening_stock = max(10, curr_stock + tot_sales - (tot_sales // 2))
        
        # Add OPENING movement
        movement_records.append({
            "movement_id": f"MOV_INIT_{s_id}_{p_id}",
            "date": start_date_str,
            "store_id": s_id,
            "product_id": p_id,
            "movement_type": "OPENING",
            "quantity": opening_stock,
            "reason": "Opening Inventory Balance"
        })

        running_stock = opening_stock
        restock_sum = 0

        # Simulate day by day
        for day_offset in range(90):
            d_str = (start_date + timedelta(days=day_offset)).strftime("%Y-%m-%d")
            key = (d_str, s_id, p_id)
            daily_qty = sales_by_key.get(key, 0)

            if daily_qty > 0:
                running_stock -= daily_qty
                movement_records.append({
                    "movement_id": f"MOV_SALE_{d_str.replace('-','')}_{s_id}_{p_id}",
                    "date": d_str,
                    "store_id": s_id,
                    "product_id": p_id,
                    "movement_type": "SALE",
                    "quantity": -daily_qty,
                    "reason": "Customer Sale Transaction"
                })

            # Check if stock needed restock during the timeline or to align with curr_stock
            if day_offset in (25, 55, 80) and running_stock < 30:
                add_qty = 20
                running_stock += add_qty
                restock_sum += add_qty
                movement_records.append({
                    "movement_id": f"MOV_PURCH_{d_str.replace('-','')}_{s_id}_{p_id}",
                    "date": d_str,
                    "store_id": s_id,
                    "product_id": p_id,
                    "movement_type": "PURCHASE",
                    "quantity": add_qty,
                    "reason": "Supplier Replenishment Shipment"
                })

        # Final adjustment movement if needed to match current_stock exactly on today's date
        final_date_str = (end_date - timedelta(days=1)).strftime("%Y-%m-%d")
        diff = curr_stock - running_stock
        if diff != 0:
            movement_records.append({
                "movement_id": f"MOV_ADJ_{final_date_str.replace('-','')}_{s_id}_{p_id}",
                "date": final_date_str,
                "store_id": s_id,
                "product_id": p_id,
                "movement_type": "PURCHASE" if diff > 0 else "ADJUSTMENT",
                "quantity": diff,
                "reason": "Audit Balance Alignment"
            })

    movements_csv = os.path.join(data_dir, "inventory_movements.csv")
    with open(movements_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["movement_id", "date", "store_id", "product_id", "movement_type", "quantity", "reason"])
        writer.writeheader()
        writer.writerows(movement_records)

    print(f"Dataset generated successfully in '{data_dir}':")
    print(f"- Stores: {len(stores)}")
    print(f"- Products: {len(products)}")
    print(f"- Sales Records: {len(sales_records)}")
    print(f"- Inventory Records: {len(inventory_records)}")
    print(f"- Inventory Movement Records: {len(movement_records)}")

if __name__ == "__main__":
    generate_retail_dataset()

