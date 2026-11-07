# backfill_history.py
import time
from datetime import datetime, timedelta
from refresh_token_always_call import call_api
from sandbox_agent import init_db, save_orders_to_db

def backfill_past_six_months():
    print("Initializing DB...")
    init_db()
    
    now = datetime.now()
    six_months_ago = now - timedelta(days=180)
    
    print(f"Starting historical order backfill from {six_months_ago.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}...")
    
    current_end = now
    
    # Loop backward in 15-day blocks
    while current_end > six_months_ago:
        current_start = max(current_end - timedelta(days=15), six_months_ago)
        
        time_from_ts = int(current_start.timestamp())
        time_to_ts = int(current_end.timestamp())
        
        print(f"\nFetching chunk: {current_start.strftime('%Y-%m-%d')} to {current_end.strftime('%Y-%m-%d')}...")
        
        try:
            list_params = {
                "time_range_field": "create_time",
                "time_from": time_from_ts,
                "time_to": time_to_ts,
                "page_size": 100
            }
            
            list_res = call_api("/api/v2/order/get_order_list", method="GET", payload=list_params)
            
            if "response" in list_res and "order_list" in list_res["response"]:
                orders = list_res["response"]["order_list"]
                if orders:
                    order_sns = [order["order_sn"] for order in orders]
                    print(f"  -> Found {len(order_sns)} orders. Fetching details...")
                    
                    detail_params = {
                        "order_sn_list": ",".join(order_sns),
                        "response_optional_fields": "item_list,buyer_username,recipient_address,payment_method,estimated_shipping_fee,total_amount"
                    }
                    
                    details_res = call_api("/api/v2/order/get_order_detail", method="GET", payload=detail_params)
                    
                    if "response" in details_res and "order_list" in details_res["response"]:
                        order_list = details_res["response"]["order_list"]
                        save_orders_to_db(order_list)
                        print(f"  -> Successfully saved {len(order_list)} orders to SQLite.")
                else:
                    print("  -> No orders found in this time window.")
            else:
                print(f"  -> API response warning: {list_res}")
                
        except Exception as e:
            print(f"  ❌ Error fetching chunk: {e}")
            
        # Shift window backward
        current_end = current_start
        # Brief sleep to avoid hammering the sandbox API rate limit
        time.sleep(0.5)

    print("\n✅ Historical backfill complete! Your SQLite database is fully seeded.")

if __name__ == "__main__":
    backfill_past_six_months()