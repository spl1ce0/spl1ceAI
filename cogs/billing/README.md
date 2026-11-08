# Billing & Polar.sh Subsystem (`cogs/billing/`)

This package manages server premium subscriptions, Polar.sh checkout sessions (Merchant of Record), asynchronous webhook listeners, customer billing portals, and database tier synchronization.

---

## 📁 Files & Structure

* **`cog.py` (`Billing`)**: Slash name `premium`. Prefix aliases `subscribe`, `plan`, `upgrade`. Three-page Components V2 pager (Free, Premium, BYOK) with previous/next buttons. The Premium page body hardcodes `2.99€ / month` (same text as `DefaultSettings.PREMIUM_PRICE_EUR`, but the cog does not read that constant). The upgrade button label is `👑 Upgrade` and links to the Polar checkout URL, or `https://polar.sh` if checkout creation returned nothing. The portal button label is `Manage Billing`. The BYOK page opens a key modal. On load the cog starts `PolarWebhookServer`.
* **`service.py` (`PolarBillingService`)**: Creates Polar checkouts with `guild_id` and `user_id` metadata, builds the customer portal URL, and checks Standard Webhooks HMAC-SHA256 (`webhook-id`, `webhook-timestamp`, `webhook-signature`, with `x-signature` / `polar-signature` as fallbacks). If `POLAR_WEBHOOK_SECRET` is unset, verification returns true and the body is accepted.
* **`webhook.py` (`PolarWebhookServer`)**: `aiohttp` server. POST `/webhook/polar`, `/webhook/billing`, and `/api/billing/webhook` share one handler. GET `/health` returns a JSON status. The same app mounts `cogs/dashboard_api.py`. Bind address `0.0.0.0` and port `DefaultSettings.WEBHOOK_PORT` (8080). The `PORT` variable in `.env.example` is not read.

---

## 💳 Polar.sh Lifecycle Events

| Webhook Event (`type`) | Action Taken by `PolarWebhookServer` | Resulting Tier State |
| :--- | :--- | :--- |
| `subscription.created` / `subscription.active` / `order.created` | If `metadata.guild_id` is present (or `custom_field_data`), calls `save_subscription` and sets `is_premium` to 1 in the database and `settings_cache`. `order.created` takes that path too. | `is_premium = 1` |
| `subscription.updated` | Calls `DatabaseManager.update_subscription_status` | That method is not defined. The handler catches the exception and returns HTTP 500. `is_premium` is not updated. |
| `subscription.canceled` / `subscription.revoked` | Same missing `update_subscription_status` call | Same HTTP 500. `is_premium` is not cleared by this path. |

`save_subscription` upserts `customer_id`, `subscription_id`, `status`, `user_id`, `variant_id`, and `current_period_end`. It does not write `cancel_at_period_end` or `price_id`. A missing `guild_id` on the create/active/order path leaves the guild unchanged. Other event names are logged and acknowledged with HTTP 200.

---

## ⚙️ Environment Variables

Configure the following keys in `.env`:

```env
POLAR_ACCESS_TOKEN=your_polar_access_token_here
POLAR_PRODUCT_ID=your_polar_product_id_here
POLAR_WEBHOOK_SECRET=your_polar_webhook_secret_here
POLAR_ORGANIZATION_SLUG=spl1ceai
```

`POLAR_API_KEY` is accepted as an alias of `POLAR_ACCESS_TOKEN`. `.env.example` still documents `LEMONSQUEEZY_*` keys. No billing module reads those names.

The checkout amount is whatever Polar has on `POLAR_PRODUCT_ID`. The Discord pager hardcodes `2.99€ / month`, which matches `DefaultSettings.PREMIUM_PRICE_EUR`. The same pager's image and context lines do not match `check_ai_quota_allowance`. See `cogs/ai/README.md` for the enforced limits versus the strings in `cogs/billing/cog.py` and `cogs/settings.py`.

