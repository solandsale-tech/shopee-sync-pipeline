# refresh_token_always_call.py
import requests
import time
import hmac
import hashlib
import os
from dotenv import load_dotenv, set_key

load_dotenv("creds.env", override=True)

# Sanitize inputs with .strip() to prevent hidden newline/space sign errors
PARTNER_ID = int(os.getenv("SHOPEE_PARTNER_ID").strip())
PARTNER_KEY = (os.getenv("SHOPEE_KEY") or os.getenv("SHOPEE_PARTNER_KEY")).strip()
SHOP_ID = int(os.getenv("SHOPEE_SHOP_ID").strip())
HOST = os.getenv("SHOPEE_HOST", "https://openplatform.sandbox.test-stable.shopee.sg").strip()

def refresh_access_token():
    path = "/api/v2/auth/access_token/get"
    timestamp = int(time.time())
    refresh_token = os.getenv("SHOPEE_REFRESH_TOKEN").strip()
    
    # Public auth endpoint signature: partner_id + path + timestamp
    base_string = f"{PARTNER_ID}{path}{timestamp}"
    sign = hmac.new(
        PARTNER_KEY.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    url = f"{HOST}{path}?partner_id={PARTNER_ID}&timestamp={timestamp}&sign={sign}"
    payload = {
        "partner_id": PARTNER_ID,
        "refresh_token": refresh_token,
        "shop_id": SHOP_ID
    }
    
    res = requests.post(url, json=payload).json()
    
    if "access_token" in res:
        new_access_token = res["access_token"].strip()
        new_refresh_token = res["refresh_token"].strip()
        
        # Save unquoted tokens cleanly to creds.env
        set_key("creds.env", "SHOPEE_ACCESS_TOKEN", new_access_token, quote_mode="never")
        set_key("creds.env", "SHOPEE_REFRESH_TOKEN", new_refresh_token, quote_mode="never")
        os.environ["SHOPEE_ACCESS_TOKEN"] = new_access_token
        os.environ["SHOPEE_REFRESH_TOKEN"] = new_refresh_token
        
        print("[Auth] Tokens refreshed and updated successfully.")
        return new_access_token
    else:
        raise Exception(f"[Auth] Token refresh failed: {res}")

def call_api(path, method="GET", payload=None):
    if payload is None:
        payload = {}
        
    current_token = os.getenv("SHOPEE_ACCESS_TOKEN").strip()
    timestamp = int(time.time())
    
    # Standard Shopee Open Platform V2 signature base string
    base_string = f"{PARTNER_ID}{path}{timestamp}{current_token}{SHOP_ID}"
    sign = hmac.new(
        PARTNER_KEY.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    # Common query parameters required for all V2 calls
    query_params = {
        "partner_id": PARTNER_ID,
        "timestamp": timestamp,
        "sign": sign,
        "access_token": current_token,
        "shop_id": SHOP_ID
    }
    
    if method.upper() == "GET":
        query_params.update(payload)
        url = f"{HOST}{path}"
        response = requests.get(url, params=query_params)
    else:
        url = f"{HOST}{path}"
        response = requests.post(url, params=query_params, json=payload)
        
    try:
        res_data = response.json()
    except Exception:
        raise Exception(f"Invalid JSON response: {response.text}")
        
    # Auto-refresh if signature or auth error occurs
    if res_data.get("error") in ["error_auth", "error_sign"] or "invalid" in str(res_data.get("message", "")).lower():
        print(f"[Auth] Encountered auth/sign error ({res_data.get('message')}). Refreshing token and retrying...")
        refresh_access_token()
        return call_api(path, method=method, payload=payload)
        
    return res_data