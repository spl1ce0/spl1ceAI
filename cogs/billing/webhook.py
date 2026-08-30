import logging
import json
import datetime
from aiohttp import web
from cogs.billing.service import LemonSqueezyService

logger = logging.getLogger(__name__)

class LemonSqueezyWebhookServer:
    """Asynchronous HTTP Webhook server for receiving Lemon Squeezy subscription lifecycle events."""

    def __init__(self, bot, billing_service: LemonSqueezyService, port: int = 8080):
        self.bot = bot
        self.billing_service = billing_service
        self.port = port
        self.app = web.Application()
        self.app.router.add_post("/webhook/lemonsqueezy", self.handle_webhook)
        self.app.router.add_post("/webhook/billing", self.handle_webhook)
        self.app.router.add_post("/api/billing/webhook", self.handle_webhook)
        self.app.router.add_get("/health", self.handle_health)
        self.runner: web.AppRunner = None
        self.site: web.TCPSite = None

    async def start(self):
        """Starts the webhook listening server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, "0.0.0.0", self.port)
            await self.site.start()
            logger.info(f"Lemon Squeezy Webhook server listening on http://0.0.0.0:{self.port}/webhook/lemonsqueezy")
        except Exception as e:
            logger.error(f"Failed to start Lemon Squeezy Webhook server on port {self.port}: {e}")

    async def stop(self):
        """Stops the webhook server cleanly."""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("Lemon Squeezy Webhook server stopped.")

    async def handle_health(self, request: web.Request) -> web.Response:
        """Simple health check endpoint."""
        return web.json_response({"status": "ok", "service": "spl1ceAI Lemon Squeezy Billing Webhook"})

    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Handles incoming Lemon Squeezy webhook events."""
        payload = await request.read()
        sig_header = request.headers.get("X-Signature", "")

        # Verify HMAC signature
        if not self.billing_service.verify_webhook_signature(payload, sig_header):
            logger.warning("Lemon Squeezy webhook signature verification failed.")
            return web.Response(status=400, text="Invalid signature")

        try:
            event_json = json.loads(payload.decode("utf-8"))
        except Exception as e:
            logger.warning(f"Invalid JSON payload in webhook: {e}")
            return web.Response(status=400, text="Invalid JSON")

        meta = event_json.get("meta", {})
        event_name = meta.get("event_name")
        custom_data = meta.get("custom_data", {})
        data = event_json.get("data", {})
        attributes = data.get("attributes", {})

        logger.info(f"Received Lemon Squeezy webhook event: {event_name}")

        try:
            # 1. Subscription Created (Initial 2.99€ purchase completed)
            if event_name == "subscription_created":
                guild_id_str = custom_data.get("guild_id")
                user_id_str = custom_data.get("user_id")
                subscription_id = str(data.get("id"))
                customer_id = str(attributes.get("customer_id"))
                status = str(attributes.get("status", "active"))
                current_period_end = attributes.get("renews_at") or attributes.get("ends_at")

                if guild_id_str:
                    guild_id = int(guild_id_str)
                    user_id = int(user_id_str) if user_id_str else None

                    # Save subscription in DB
                    await self.bot.db_manager.save_subscription(
                        guild_id=guild_id,
                        customer_id=customer_id,
                        subscription_id=subscription_id,
                        status=status,
                        user_id=user_id,
                        current_period_end=current_period_end
                    )

                    # Activate Premium on Guild
                    await self.bot.db_manager.update_guild_setting(guild_id, "is_premium", 1)
                    self.bot.settings_cache.setdefault(guild_id, {})["is_premium"] = 1

                    logger.info(f"✅ Premium subscription activated for Guild {guild_id} (Sub ID: {subscription_id})")

            # 2. Subscription Updated / Resumed / Payment Success
            elif event_name in ["subscription_updated", "subscription_resumed", "subscription_unpaused", "subscription_payment_success"]:
                subscription_id = str(data.get("id"))
                status = str(attributes.get("status", "active"))
                current_period_end = attributes.get("renews_at") or attributes.get("ends_at")
                cancelled = int(bool(attributes.get("cancelled", False)))

                guild_id = await self.bot.db_manager.update_subscription_status(
                    subscription_id=subscription_id,
                    status=status,
                    current_period_end=current_period_end,
                    cancel_at_period_end=cancelled
                )

                if guild_id:
                    is_active = 1 if status in ["active", "on_trial", "past_due"] else 0
                    await self.bot.db_manager.update_guild_setting(guild_id, "is_premium", is_active)
                    self.bot.settings_cache.setdefault(guild_id, {})["is_premium"] = is_active
                    logger.info(f"Subscription {subscription_id} for Guild {guild_id} updated: status='{status}' (is_premium={is_active})")

            # 3. Subscription Cancelled / Expired
            elif event_name in ["subscription_cancelled", "subscription_expired", "subscription_paused"]:
                subscription_id = str(data.get("id"))
                status = str(attributes.get("status", "cancelled"))

                guild_id = await self.bot.db_manager.update_subscription_status(
                    subscription_id=subscription_id,
                    status=status
                )

                if guild_id:
                    await self.bot.db_manager.update_guild_setting(guild_id, "is_premium", 0)
                    self.bot.settings_cache.setdefault(guild_id, {})["is_premium"] = 0
                    logger.info(f"❌ Premium subscription ended for Guild {guild_id} (Status: {status})")

        except Exception as e:
            logger.error(f"Error processing Lemon Squeezy event '{event_name}': {e}", exc_info=True)
            return web.Response(status=500, text="Internal Server Error")

        return web.json_response({"status": "success", "event": event_name})
