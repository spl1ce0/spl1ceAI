import logging
import json
import datetime
from aiohttp import web
from cogs.billing.service import PolarBillingService

logger = logging.getLogger(__name__)

class PolarWebhookServer:
    """Asynchronous HTTP Webhook server for receiving Polar.sh subscription lifecycle events."""

    def __init__(self, bot, billing_service: PolarBillingService, port: int = 8080):
        self.bot = bot
        self.billing_service = billing_service
        self.port = port
        self.app = web.Application()
        self.app.router.add_post("/webhook/polar", self.handle_webhook)
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
            logger.info(f"Polar Webhook server listening on http://0.0.0.0:{self.port}/webhook/polar")
        except Exception as e:
            logger.error(f"Failed to start Polar Webhook server on port {self.port}: {e}")

    async def stop(self):
        """Stops the webhook server cleanly."""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("Polar Webhook server stopped.")

    async def handle_health(self, request: web.Request) -> web.Response:
        """Simple health check endpoint."""
        return web.json_response({"status": "ok", "service": "spl1ceAI Polar Billing Webhook"})

    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Handles incoming Polar.sh webhook events."""
        payload = await request.read()
        headers = dict(request.headers)

        # Verify HMAC signature
        if not self.billing_service.verify_webhook_signature(payload, headers):
            logger.warning("Polar webhook signature verification failed.")
            return web.Response(status=400, text="Invalid signature")

        try:
            event_json = json.loads(payload.decode("utf-8"))
        except Exception as e:
            logger.warning(f"Invalid JSON payload in webhook: {e}")
            return web.Response(status=400, text="Invalid JSON")

        event_type = event_json.get("type") or event_json.get("event")
        data = event_json.get("data", {})
        metadata = data.get("metadata") or data.get("custom_field_data") or {}

        logger.info(f"Received Polar webhook event: {event_type}")

        try:
            # 1. Subscription Created / Active / Order Paid
            if event_type in ["subscription.created", "subscription.active", "order.created"]:
                guild_id_str = metadata.get("guild_id")
                user_id_str = metadata.get("user_id")
                subscription_id = str(data.get("id"))
                customer_id = str(data.get("customer_id") or data.get("user_id") or "")
                status = str(data.get("status", "active"))
                current_period_end = data.get("current_period_end") or data.get("ends_at")

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

                    logger.info(f"✅ Polar Premium subscription activated for Guild {guild_id} (Sub ID: {subscription_id})")

            # 2. Subscription Updated
            elif event_type in ["subscription.updated"]:
                subscription_id = str(data.get("id"))
                status = str(data.get("status", "active"))
                current_period_end = data.get("current_period_end") or data.get("ends_at")
                cancelled = int(bool(data.get("cancel_at_period_end", False) or status == "canceled"))

                guild_id = await self.bot.db_manager.update_subscription_status(
                    subscription_id=subscription_id,
                    status=status,
                    current_period_end=current_period_end,
                    cancel_at_period_end=cancelled
                )

                if guild_id:
                    is_active = 1 if status in ["active", "trialing"] else 0
                    await self.bot.db_manager.update_guild_setting(guild_id, "is_premium", is_active)
                    self.bot.settings_cache.setdefault(guild_id, {})["is_premium"] = is_active
                    logger.info(f"Polar Subscription {subscription_id} for Guild {guild_id} updated: status='{status}' (is_premium={is_active})")

            # 3. Subscription Canceled / Revoked
            elif event_type in ["subscription.canceled", "subscription.revoked"]:
                subscription_id = str(data.get("id"))
                status = str(data.get("status", "canceled"))

                guild_id = await self.bot.db_manager.update_subscription_status(
                    subscription_id=subscription_id,
                    status=status
                )

                if guild_id:
                    await self.bot.db_manager.update_guild_setting(guild_id, "is_premium", 0)
                    self.bot.settings_cache.setdefault(guild_id, {})["is_premium"] = 0
                    logger.info(f"❌ Polar Premium subscription ended for Guild {guild_id} (Status: {status})")

        except Exception as e:
            logger.error(f"Error processing Polar event '{event_type}': {e}", exc_info=True)
            return web.Response(status=500, text="Internal Server Error")

        return web.json_response({"status": "success", "event": event_type})

