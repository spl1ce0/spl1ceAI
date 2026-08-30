import os
import hmac
import hashlib
import json
import logging
from typing import Optional, Dict, Any
import aiohttp

logger = logging.getLogger(__name__)

class LemonSqueezyService:
    """Manages Lemon Squeezy checkouts, customer portals, and webhook signature verification."""

    BASE_API_URL = "https://api.lemonsqueezy.com/v1"

    def __init__(self):
        self.api_key = os.getenv("LEMONSQUEEZY_API_KEY")
        self.store_id = os.getenv("LEMONSQUEEZY_STORE_ID", "462404")
        self.variant_id = os.getenv("LEMONSQUEEZY_VARIANT_ID", "2069890")
        self.webhook_secret = os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET")
        self.store_slug = os.getenv("LEMONSQUEEZY_STORE_SLUG", "spl1ceai")

    @property
    def is_configured(self) -> bool:
        """Returns True if Lemon Squeezy API credentials or Variant ID are configured."""
        return bool(self.variant_id or (self.api_key and self.store_id))

    async def create_checkout_session(
        self,
        guild_id: int,
        user_id: int,
        guild_name: str = "",
        user_name: str = ""
    ) -> str:
        """Generates a Lemon Squeezy Checkout URL with guild_id and user_id in custom data."""
        custom_data = {
            "guild_id": str(guild_id),
            "user_id": str(user_id),
            "guild_name": guild_name[:100],
            "user_name": user_name[:100]
        }

        # 1. Direct API Checkout Creation (if API Key and Store ID are provided)
        if self.api_key and self.variant_id:
            try:
                store_id_to_use = self.store_id
                if not store_id_to_use or store_id_to_use == "your_store_id":
                    store_id_to_use = "462404"

                headers = {
                    "Accept": "application/vnd.api+json",
                    "Content-Type": "application/vnd.api+json",
                    "Authorization": f"Bearer {self.api_key}"
                }
                payload = {
                    "data": {
                        "type": "checkouts",
                        "attributes": {
                            "checkout_data": {
                                "custom": custom_data
                            },
                            "product_options": {
                                "redirect_url": "https://discord.com/channels/@me"
                            }
                        },
                        "relationships": {
                            "store": {
                                "data": {
                                    "type": "stores",
                                    "id": str(store_id_to_use)
                                }
                            },
                            "variant": {
                                "data": {
                                    "type": "variants",
                                    "id": str(self.variant_id)
                                }
                            }
                        }
                    }
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{self.BASE_API_URL}/checkouts", json=payload, headers=headers) as resp:
                        if resp.status in (200, 201):
                            data = await resp.json()
                            checkout_url = data.get("data", {}).get("attributes", {}).get("url")
                            if checkout_url:
                                return checkout_url
                        else:
                            error_text = await resp.text()
                            logger.warning(f"Lemon Squeezy API returned {resp.status}: {error_text}. Falling back to hosted checkout.")
            except Exception as e:
                logger.error(f"Failed to create Lemon Squeezy API checkout session: {e}")

        # 2. Hosted Checkout Link Fallback (Works instantly with just Variant ID / Slug)
        if self.variant_id:
            import urllib.parse
            params = {
                "checkout[custom][guild_id]": str(guild_id),
                "checkout[custom][user_id]": str(user_id),
            }
            query_str = urllib.parse.urlencode(params)
            return f"https://{self.store_slug}.lemonsqueezy.com/buy/{self.variant_id}?{query_str}"

        raise ValueError("Lemon Squeezy is not configured. Please set LEMONSQUEEZY_VARIANT_ID in .env.")

    def get_customer_portal_url(self, customer_id: Optional[str] = None) -> str:
        """Returns the self-service Lemon Squeezy customer billing portal URL."""
        return f"https://{self.store_slug}.lemonsqueezy.com/billing"

    def verify_webhook_signature(self, payload: bytes, signature_header: str) -> bool:
        """Verifies Lemon Squeezy X-Signature HMAC-SHA256 digest."""
        if not self.webhook_secret:
            logger.warning("LEMONSQUEEZY_WEBHOOK_SECRET is not configured. Skipping signature check.")
            return True

        if not signature_header:
            return False

        digest = hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(digest, signature_header)
