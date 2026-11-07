# db_access.py
import sqlite3

DB_NAME = "shopee_sandbox.db"

def get_connection():
    """Helper to connect to the SQLite database."""
    return sqlite3.connect(DB_NAME)

def view_products():
    """Queries and prints all stored products/inventory."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT item_id, item_name, item_sku, price, stock, last_updated FROM products")
    rows = cursor.fetchall()
    conn.close()
    
    print("\n" + "="*50)
    print("          STORED PRODUCTS / INVENTORY          ")
    print("="*50)
    
    if not rows:
        print("No products found in database yet. Run production_agent.py first.")
        return
        
    for row in rows:
        item_id, name, sku, price, stock, updated = row
        print(f"ID: {item_id} | SKU: {sku:<12} | Price: ${price:<6} | Stock: {stock:<4}")
        print(f"Name: {name}")
        print(f"Last Synced: {updated}")
        print("-" * 50)

def view_orders():
    """Queries and prints all stored orders and their sold items."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT order_sn, order_status, buyer_username, total_amount, create_time, last_updated FROM orders")
    orders = cursor.fetchall()
    
    print("\n" + "="*50)
    print("                STORED ORDERS                  ")
    print("="*50)
    
    if not orders:
        print("No orders found in database yet.")
        conn.close()
        return
        
    for order in orders:
        order_sn, status, buyer, total, create_time, updated = order
        print(f"📦 Order SN: {order_sn} | Status: {status}")
        print(f"   Buyer: {buyer} | Total: ${total} | Created: {create_time}")
        
        # Fetch corresponding line items for this order
        cursor.execute("SELECT item_name, item_sku, quantity, price FROM order_items WHERE order_sn = ?", (order_sn,))
        items = cursor.fetchall()
        
        print("   Sold Items:")
        if items:
            for item in items:
                i_name, i_sku, qty, i_price = item
                print(f"     • {qty}x {i_name} (SKU: {i_sku}) @ ${i_price}")
        else:
            print("     • (No item details recorded)")
            
        print("-" * 50)
        
    conn.close()

if __name__ == "__main__":
    print(f"Reading from database: {DB_NAME}")
    view_products()
    view_orders()