# KeystoneBid

Pennsylvania antique hunting license marketplace built with Django.

## Current Status (Alpha)

The platform now supports three marketplace paths:

- The Auction House: bid -> win -> pay -> ship -> receive
- The General Store: buy now -> pay -> ship -> receive
- The Trading Block: offer/counter -> accept -> dual ship -> confirm

Core Alpha systems are included:

- Orders + payment spine (`Order` + `PaymentTransaction`)
- Shipping + tracking integration (Shippo wrapper, webhook + polling fallback)
- Collections and wanted list
- Trade offers and dual-shipment lifecycle
- Enforcement (strikes, restrictions, excuse handshake)
- In-app notifications center
- Auction enhancements (reserve handling, Q&A)
- Favorites (listings + public collection items)

## Stack

- Django 5.x
- SQLite (development), PostgreSQL-ready for production
- Django templates + modular CSS + vanilla JS
- Stripe Checkout + webhook flow
- Shippo API integration for shipping/tracking

## Project Structure

```text
repo/
  manage.py
  config/
    settings/
      base.py
      development.py
      production.py
    urls.py
  apps/
    accounts/
    core/
    collections/
    listings/
    bids/
    orders/
    payments/
    shipping/
    trades/
    favorites/
    enforcement/
    notifications/
  templates/
  static/
  media/
```

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements/development.txt
```

3. Configure `.env` (copy from `.env.example` if needed).
4. Run migrations:

```bash
py manage.py migrate
```

5. Create a superuser:

```bash
py manage.py createsuperuser
```

6. Start the server:

```bash
py manage.py runserver
```

## Useful Management Commands

```bash
py manage.py close_auctions
py manage.py release_stale_buy_now --timeout-minutes 30
py manage.py poll_shipments --limit 200
py manage.py expire_trade_offers --limit 500
py manage.py poll_trade_shipments --limit 200
py manage.py auto_complete_orders --grace-days 3
py manage.py auto_complete_trades --grace-days 3
py manage.py enforce_policies
py manage.py enqueue_operational_notifications
py manage.py send_notifications --limit 200
```
