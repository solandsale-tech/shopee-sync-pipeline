# shopee-sync-pipeline
Headless Python background agent for automated Shopee store inventory and order synchronization into a local SQLite database.

# Internal Shopee Data Pipeline & Inventory Synchronization Daemon

## Overview
This repository contains a private, internal Python application developed exclusively for our store's internal operations. It acts as an automated background data pipeline that synchronizes catalog inventory levels and order history from the Shopee Open Platform into a local SQLite database (`shopee_sandbox.db`).

The application is a **headless background worker / daemon**. It has no user-facing graphical user interface (GUI) or web portal, and it relies strictly on API key authentication and OAuth 2.0 token exchanges rather than traditional user logins.

---

## Architecture & Features

### 1. Unified Background Sync (`production_agent.py`)
* **Catalog Inventory Sync:** Periodically queries live product stock levels, item SKUs, and pricing to maintain an up-to-date snapshot.
* **Order & Sales Tracking:** Polls order list endpoints to fetch granular order details, buyer demographics, line-item breakdowns, and fulfillment timestamps.
* **Persistent Local Storage:** Uses UPSERT logic (`ON CONFLICT ... DO UPDATE`) to store all product and order records inside `shopee_sandbox.db` without data duplication.

### 2. Historical Data Backfill (`backfill_db_past.py`)
* Automatically bypasses single-query time window limits by querying order lists in 15-day chunks to backfill historical order records into the local database.

### 3. Database Access & Analytics (`db_access.py`)
* Provides programmatic access to query local SQLite tables (`products`, `orders`, `order_items`) for internal financial reporting and sales analysis.

### 🔑 Secure API Client (`refresh_token_always_call.py`)
* **HMAC-SHA256 Signing:** Dynamically computes request signatures required by the Shopee Open Platform using your Partner ID and Partner Key.
* **Automatic Token Rotation:** Intercepts API responses, checks token validity, and automatically refreshes expired access tokens using stored refresh tokens without manual intervention.

---

## Authentication & Security
* **HMAC-SHA256 Signing:** All outgoing HTTP requests are signed dynamically using HMAC-SHA256 based on Partner credentials and API request paths.
* **Self-Healing Token Rotation:** Includes automatic token refresh logic (`call_api`) to seamlessly handle access token expiration without manual intervention.
* **Private Deployment:** Runs exclusively on private internal infrastructure. No third-party or client-facing web endpoints are exposed.

---

## System Requirements & Dependencies
* **Language:** Python 3.8+
* **Core Libraries:** `requests`, `sqlite3`, `schedule`

```bash
# Example execution command:
python production_agent.py
