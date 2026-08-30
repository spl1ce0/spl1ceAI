# Billing & Lemon Squeezy Subsystem (`cogs/billing/`)

This package manages server premium subscriptions, Lemon Squeezy Checkout sessions (Merchant of Record), asynchronous webhook listeners, customer billing portals, and database tier synchronization.

---

## 📁 Files & Structure

* **`cog.py` (`Billing`)**: The Discord Cog front-end. Defines `/premium` (aliases `/subscribe`, `/plan`, `/upgrade`). Builds an interactive 3-page comparative paginator (`Free` ➔ `👑 Premium` ➔ `🔑 BYOK`) using Discord Components V2 with dynamic `[ ◀ ] [ Action Button ] [ ▶ ]` navigation, 1-click **👑 Upgrade (2.99€/mo)** checkout link, **⚙️ Manage Subscription** portal link, and **⚙️ Setup / Manage Keys** modal integration.
* **`service.py` (`LemonSqueezyService`)**: Core Lemon Squeezy business logic. Handles API checkout creation with `{guild_id, user_id}` custom data mapping, self-service customer portal routing, and cryptographic HMAC-SHA256 signature verification (`X-Signature`).
* **`webhook.py` (`LemonSqueezyWebhookServer`)**: Asynchronous `aiohttp.web` HTTP server that listens on `/webhook/lemonsqueezy` (default port `8080`) to process subscription events in real-time.

---

## 💳 Lemon Squeezy Lifecycle Events

| Webhook Event (`meta.event_name`) | Action Taken by `LemonSqueezyWebhookServer` | Resulting Tier State |
| :--- | :--- | :--- |
| `subscription_created` | Extracts `guild_id`, `customer_id`, `subscription_id`, saves to `guild_subscriptions` table | `is_premium = 1` (Active) |
| `subscription_updated` / `subscription_resumed` | Updates subscription status (`active`, `on_trial`, `past_due`) & renewal dates | `is_premium = 1` if active, else `0` |
| `subscription_cancelled` / `subscription_expired` | Marks subscription as cancelled in database | `is_premium = 0` (Reverts to Free Snapshot) |

---

## ⚙️ Environment Variables

Configure the following keys in `.env`:

```env
LEMONSQUEEZY_API_KEY=...
LEMONSQUEEZY_STORE_ID=...
LEMONSQUEEZY_STORE_SLUG=spl1ceai
LEMONSQUEEZY_VARIANT_ID=...
LEMONSQUEEZY_WEBHOOK_SECRET=...
```
