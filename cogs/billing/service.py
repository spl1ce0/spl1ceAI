import os
import hmac
import hashlib
import base64
import json
import logging
from typing import Optional, Dict, Any
import aiohttp

logger = logging.getLogger(__name__)

class PolarBillingService:
    """Manages Polar.sh checkouts, customer subscriptions, and webhook signature verification."""

    BASE_API_URL = "https://api.polar.sh/v1"

    def __init__(self):
        self.access_token = os.getenv("POLAR_ACCESS_TOKEN") or os.getenv("POLAR_API_KEY")
        self.product_id = os.getenv("POLAR_PRODUCT_ID")
        self.webhook_secret = os.getenv("POLAR_WEBHOOK_SECRET")
        self.org_slug = os.getenv("POLAR_ORGANIZATION_SLUG", "spl1ceai")

    @property
    def is_configured(self) -> bool:
        """Returns True if Polar Product ID or Access Token is configured."""
        return bool(self.product_id or self.access_token)

    async def create_checkout_session(
        self,
        guild_id: int,
        user_id: int,
        guild_name: str = "",
        user_name: str = ""
    ) -> str:
        """Generates a Polar.sh Checkout URL with guild_id and user_id in metadata."""
        custom_metadata = {
            "guild_id": str(guild_id),
            "user_id": str(user_id),
            "guild_name": guild_name[:100],
            "user_name": user_name[:100]
        }

        # 1. Direct API Checkout Session Creation
        if self.access_token and self.product_id:
            try:
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.access_token}"
                }
                payload = {
                    "products": [self.product_id],
                    "metadata": custom_metadata,
                    "success_url": "https://discord.com/channels/@me"
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{self.BASE_API_URL}/checkouts/", json=payload, headers=headers) as resp:
                        if resp.status in (200, 201):
                            data = await resp.json()
                            checkout_url = data.get("url")
                            if checkout_url:
                                logger.info(f"Created Polar checkout session: {checkout_url}")
                                return checkout_url
                        else:
                            err = await resp.text()
                            logger.warning(f"Polar API returned {resp.status}: {err}")

            except Exception as e:
                logger.error(f"Failed to create Polar API checkout session: {e}")

        # 2. Hosted Link Fallback (Direct Product link with query params)
        if self.product_id:
            import urllib.parse
            params = {
                "metadata[guild_id]": str(guild_id),
                "metadata[user_id]": str(user_id),
            }
            query_str = urllib.parse.urlencode(params)
            return f"https://polar.sh/checkout?product_id={self.product_id}&{query_str}"

        raise ValueError("Polar is not configured. Please set POLAR_PRODUCT_ID in .env.")

    def get_customer_portal_url(self, customer_id: Optional[str] = None) -> str:
        """Returns the self-service Polar customer subscription management URL."""
        return f"https://polar.sh/{self.org_slug}/portal"

    async def sync_active_subscriptions(self, bot) -> int:
        """Queries Polar API for active subscriptions and syncs them to the database and cache."""
        if not self.access_token:
            return 0
        try:
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {self.access_token}"
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_API_URL}/subscriptions/", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("items", [])
                        count = 0
                        for sub in items:
                            status = sub.get("status")
                            metadata = sub.get("metadata") or sub.get("custom_field_data") or {}
                            guild_id_str = metadata.get("guild_id")
                            if not guild_id_str:
                                continue
                            guild_id = int(guild_id_str)
                            user_id_str = metadata.get("user_id")
                            user_id = int(user_id_str) if user_id_str else None
                            sub_id = str(sub.get("id"))
                            cust_id = str(sub.get("customer_id") or "")
                            end_date = sub.get("current_period_end")

                            is_active = 1 if status in ["active", "trialing"] else 0

                            await bot.db_manager.save_subscription(
                                guild_id=guild_id,
                                customer_id=cust_id,
                                subscription_id=sub_id,
                                status=status,
                                user_id=user_id,
                                current_period_end=end_date
                            )
                            await bot.db_manager.update_guild_setting(guild_id, "is_premium", is_active)
                            bot.settings_cache.setdefault(guild_id, {})["is_premium"] = is_active
                            count += 1
                            logger.info(f"Synced Polar subscription for Guild {guild_id}: is_premium={is_active}")
                        return count
                    else:
                        err = await resp.text()
                        logger.warning(f"Polar sync subscriptions returned {resp.status}: {err}")
        except Exception as e:
            logger.error(f"Error syncing Polar subscriptions: {e}")
        return 0

    def verify_webhook_signature(self, payload: bytes, headers: dict) -> bool:
        """
        Verifies Polar.sh StandardWebhooks HMAC-SHA256 signature.
        Polar uses Standard Webhooks spec:
        - Header: Webhook-Id, Webhook-Timestamp, Webhook-Signature
        """
        if not self.webhook_secret:
            logger.warning("POLAR_WEBHOOK_SECRET is not configured. Skipping signature check.")
            return True

        # Standard Webhooks headers (case-insensitive lookup)
        h_lower = {k.lower(): v for k, v in headers.items()}
        msg_id = h_lower.get("webhook-id")
        msg_timestamp = h_lower.get("webhook-timestamp")
        msg_signature = h_lower.get("webhook-signature")

        # Fallback to direct X-Signature or standard HMAC header if passed
        if not msg_signature:
            msg_signature = h_lower.get("x-signature") or h_lower.get("polar-signature")

        if not msg_signature:
            logger.warning("Missing webhook signature header from Polar request.")
            return False

        secret = self.webhook_secret.strip()

        # Handle StandardWebhooks format with msg_id & timestamp
        if msg_id and msg_timestamp:
            try:
                if secret.startswith("whsec_"):
                    key = base64.b64decode(secret[6:])
                else:
                    key = secret.encode("utf-8")

                to_sign = f"{msg_id}.{msg_timestamp}.".encode("utf-8") + payload
                expected_sig = base64.b64encode(hmac.new(key, to_sign, hashlib.sha256).digest()).decode("utf-8")

                # Header format: v1,<sig1> v1,<sig2>
                signatures = [s.strip().replace("v1,", "") for s in msg_signature.split(" ")]
                for sig in signatures:
                    if hmac.compare_digest(expected_sig, sig):
                        return True
            except Exception as e:
                logger.error(f"Error during StandardWebhooks signature check: {e}")

        # Fallback to direct raw payload HMAC check
        try:
            raw_key = secret.encode("utf-8")
            raw_digest_hex = hmac.new(raw_key, payload, hashlib.sha256).hexdigest()
            raw_digest_b64 = base64.b64encode(hmac.new(raw_key, payload, hashlib.sha256).digest()).decode("utf-8")

            clean_sig = msg_signature.replace("v1,", "").strip()
            if hmac.compare_digest(raw_digest_hex, clean_sig) or hmac.compare_digest(raw_digest_b64, clean_sig):
                return True
        except Exception as e:
            logger.error(f"Error during fallback HMAC signature check: {e}")

        return False
