# production_agent.py
import time
import sqlite3
import schedule
from datetime import datetime
from refresh_token_always_call import call_api

DB_NAME = "shopee_sandbox.db"

def init_db():
    """Initializes SQLite database and tables if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Products / Inventory Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            item_id INTEGER PRIMARY KEY,
            item_name TEXT,
            item_sku TEXT,
            price REAL,
            stock INTEGER,
            last_updated TEXT
        )
    """)
    
    # Orders Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_sn TEXT PRIMARY KEY,
            order_status TEXT,
            buyer_username TEXT,
            total_amount REAL,
            create_time TEXT,
            last_updated TEXT
        )
    """)
    
    # Order Items Table (Granular sold items)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_sn TEXT,
            item_name TEXT,
            item_sku TEXT,
            quantity INTEGER,
            price REAL,
            FOREIGN KEY (order_sn) REFERENCES orders (order_sn)
        )
    """)
    
    conn.commit()
    conn.close()

def save_inventory_to_db(products):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    for p in products:
        cursor.execute("""
            INSERT INTO products (item_id, item_name, item_sku, price, stock, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(item_id) DO UPDATE SET
                item_name=excluded.item_name,
                item_sku=excluded.item_sku,
                price=excluded.price,
                stock=excluded.stock,
                last_updated=excluded.last_updated
        """, (
            p.get("item_id"),
            p.get("item_name"),
            p.get("item_sku"),
            p.get("price_info", [{}])[0].get("current_price", 0.0),
            p.get("stock_info_v2", {}).get("summary_info", {}).get("total_available_stock", 0),
            now_str
        ))
        
    conn.commit()
    conn.close()
    print("💾 Inventory snapshot successfully saved to SQLite database.")

def save_orders_to_db(orders):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    for order in orders:
        order_sn = order.get("order_sn")
        create_time_ts = order.get("create_time", 0)
        create_time_str = datetime.fromtimestamp(create_time_ts).strftime('%Y-%m-%d %H:%M:%S') if create_time_ts else ""
        
        # Insert or update order header
        cursor.execute("""
            INSERT INTO orders (order_sn, order_status, buyer_username, total_amount, create_time, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(order_sn) DO UPDATE SET
                order_status=excluded.order_status,
                last_updated=excluded.last_updated
        """, (
            order_sn,
            order.get("order_status"),
            order.get("buyer_username"),
            order.get("total_amount", 0.0),
            create_time_str,
            now_str
        ))
        
        # Clear old order_items for this order_sn to prevent duplication on re-syncs
        cursor.execute("DELETE FROM order_items WHERE order_sn = ?", (order_sn,))
        
        # Insert sold items
        for item in order.get("item_list", []):
            cursor.execute("""
                INSERT INTO order_items (order_sn, item_name, item_sku, quantity, price)
                VALUES (?, ?, ?, ?, ?)
            """, (
                order_sn,
                item.get("item_name"),
                item.get("item_sku"),
                item.get("model_quantity_purchased", 0),
                item.get("model_discounted_price", 0.0)
            ))
            
    conn.commit()
    conn.close()
    if orders:
        print(f"💾 Saved {len(orders)} order(s) to SQLite database.")

def sync_inventory():
    print("\n--- [Task 1/2] Syncing Catalog Inventory ---")
    try:
        list_params = {
            "offset": 0,
            "page_size": 50,
            "item_status": "NORMAL"
        }
        catalog_res = call_api("/api/v2/product/get_item_list", method="GET", payload=list_params)
        
        if "response" in catalog_res and "item" in catalog_res["response"]:
            items = catalog_res["response"]["item"]
            item_ids = [str(item["item_id"]) for item in items]
            print(f"--> Found {len(item_ids)} items in store catalog.")
            
            if item_ids:
                detail_params = {
                    "item_id_list": ",".join(item_ids)
                }
                details_res = call_api("/api/v2/product/get_item_base_info", method="GET", payload=detail_params)
                
                if "response" in details_res and "item_list" in details_res["response"]:
                    product_list = details_res["response"]["item_list"]
                    
                    # Save to SQLite DB
                    save_inventory_to_db(product_list)
                    
                    print("\nLive Inventory Snapshot:")
                    for product in product_list:
                        p_id = product.get("item_id")
                        p_name = product.get("item_name")
                        p_sku = product.get("item_sku")
                        price = product["price_info"][0]["current_price"] if product.get("price_info") else "N/A"
                        stock = product.get("stock_info_v2", {}).get("summary_info", {}).get("total_available_stock", 0)
                        print(f"  • ID: {p_id} | SKU: {p_sku:<12} | Price: ${price:<6} | Stock: {stock:<4} | {p_name}")
                else:
                    print(f"Failed to fetch item details: {details_res}")
        else:
            print(f"Failed to fetch item list: {catalog_res}")
            
    except Exception as e:
        print(f"❌ Error during inventory sync: {e}")

def sync_recent_orders():
    print("\n--- [Task 2/2] Checking Recent Orders & Sold Items ---")
    try:
        now = int(time.time())
        one_day_ago = now - (24 * 60 * 60)
        
        list_params = {
            "time_range_field": "create_time",
            "time_from": one_day_ago,
            "time_to": now,
            "page_size": 20
        }
        
        list_res = call_api("/api/v2/order/get_order_list", method="GET", payload=list_params)
        
        if "response" not in list_res or "order_list" not in list_res["response"]:
            print(f"No new orders or error: {list_res}")
            return
            
        orders = list_res["response"]["order_list"]
        if not orders:
            print("--> No new orders in the last 24 hours.")
            return
            
        order_sns = [order["order_sn"] for order in orders]
        print(f"--> Found {len(order_sns)} recent orders. Fetching granular details...")
        
        detail_params = {
            "order_sn_list": ",".join(order_sns),
            "response_optional_fields": "item_list,buyer_username,recipient_address,payment_method,estimated_shipping_fee,total_amount"
        }
        
        details_res = call_api("/api/v2/order/get_order_detail", method="GET", payload=detail_params)
        
        if "response" in details_res and "order_list" in details_res["response"]:
            order_list = details_res["response"]["order_list"]
            
            # Save orders to SQLite DB
            save_orders_to_db(order_list)
            
            for order in order_list:
                order_sn = order.get("order_sn")
                status = order.get("order_status")
                buyer = order.get("buyer_username")
                total = order.get("total_amount")
                
                create_time = datetime.fromtimestamp(order.get("create_time", 0)).strftime('%Y-%m-%d %H:%M')
                
                print(f"\n📦 Order: {order_sn} | Status: {status} | Total: ${total}")
                print(f"   Buyer: {buyer} | Created: {create_time}")
                print("   Sold Items:")
                for item in order.get("item_list", []):
                    name = item.get("item_name")
                    sku = item.get("item_sku")
                    qty = item.get("model_quantity_purchased")
                    price = item.get("model_discounted_price")
                    print(f"     -> {qty}x {name} (SKU: {sku}) @ ${price}")
        else:
            print(f"Failed to fetch order details: {details_res}")
            
    except Exception as e:
        print(f"❌ Error during order sync: {e}")

def run_hourly_agent():
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n==========================================")
    print(f"[{now_str}] 🚀 Unified Agent Execution Started")
    print(f"==========================================")
    
    sync_inventory()
    sync_recent_orders()
    
    print(f"\n==========================================")
    print(f"[{now_str}] ✅ Execution Complete. Sleeping...")
    print(f"==========================================")

if __name__ == "__main__":
    print("Initializing Shopee Unified Background Agent with SQLite...")
    
    # Initialize DB tables on startup
    init_db()
    
    # Run immediate first execution
    run_hourly_agent()
    
    # Schedule agent to run every 1 hour
    schedule.every(1).hours.do(run_hourly_agent)
    
    print("\n[Agent Active] Polling catalog and orders every hour. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(1)