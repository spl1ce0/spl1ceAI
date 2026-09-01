# Billing & Polar.sh Subsystem (`cogs/billing/`)

This package manages server premium subscriptions, Polar.sh checkout sessions (Merchant of Record), asynchronous webhook listeners, customer billing portals, and database tier synchronization.

---

## 📁 Files & Structure

* **`cog.py` (`Billing`)**: The Discord Cog front-end. Defines `/premium` (aliases `/subscribe`, `/plan`, `/upgrade`). Builds an interactive 3-page comparative paginator (`Free` ➔ `👑 Premium` ➔ `🔑 BYOK`) using Discord Components V2 with dynamic `[ ◀ ] [ Action Button ] [ ▶ ]` navigation, 1-click **👑 Upgrade (2.99€/mo)** checkout link, **⚙️ Manage Subscription** portal link, and **⚙️ Setup / Manage Keys** modal integration.
* **`service.py` (`PolarBillingService`)**: Core Polar.sh business logic. Handles API checkout creation with `{guild_id, user_id}` metadata mapping, self-service customer portal routing, and cryptographic StandardWebhooks HMAC-SHA256 signature verification (`Webhook-Signature`).
* **`webhook.py` (`PolarWebhookServer`)**: Asynchronous `aiohttp.web` HTTP server that listens on `/webhook/polar` (default port `8080`) to process subscription events in real-time.

---

## 💳 Polar.sh Lifecycle Events

| Webhook Event (`type`) | Action Taken by `PolarWebhookServer` | Resulting Tier State |
| :--- | :--- | :--- |
| `subscription.created` / `subscription.active` / `order.created` | Extracts `guild_id`, `customer_id`, `subscription_id`, saves to `guild_subscriptions` table | `is_premium = 1` (Active) |
| `subscription.updated` | Updates subscription status (`active`, `trialing`) & renewal dates | `is_premium = 1` if active, else `0` |
| `subscription.canceled` / `subscription.revoked` | Marks subscription as cancelled in database | `is_premium = 0` (Reverts to Free Snapshot) |

---

## ⚙️ Environment Variables

Configure the following keys in `.env`:

```env
POLAR_ACCESS_TOKEN=polar_at_...
POLAR_PRODUCT_ID=...
POLAR_WEBHOOK_SECRET=whsec_...
```

