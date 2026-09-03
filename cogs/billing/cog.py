import discord
from discord.ext import commands
from discord import ui
import typing
import logging
from cogs.utils.constants import Emojis, DefaultSettings
from cogs.billing.service import PolarBillingService
from cogs.billing.webhook import PolarWebhookServer

logger = logging.getLogger(__name__)


class BYOKModal(ui.Modal, title="Link Custom API Keys"):
    gemini_key = ui.TextInput(
        label="Google Gemini Key",
        placeholder="Google AI Studio key (or leave blank)",
        required=False,
        max_length=200
    )
    xai_key = ui.TextInput(
        label="xAI Grok Key",
        placeholder="xAI API key (or leave blank)",
        required=False,
        max_length=200
    )
    openai_key = ui.TextInput(
        label="OpenAI Key",
        placeholder="OpenAI API key (or leave blank)",
        required=False,
        max_length=200
    )
    anthropic_key = ui.TextInput(
        label="Anthropic Claude Key",
        placeholder="Anthropic API key (or leave blank)",
        required=False,
        max_length=200
    )
    deepseek_key = ui.TextInput(
        label="DeepSeek Key",
        placeholder="DeepSeek API key (or leave blank)",
        required=False,
        max_length=200
    )

    def __init__(self, guild_settings: dict, guild_id: int, parent_view):
        super().__init__()
        self.guild_id = guild_id
        self.parent_view = parent_view
        self.guild_settings = guild_settings
        if guild_settings.get("byok_gemini_key"):
            self.gemini_key.default = guild_settings["byok_gemini_key"]
        if guild_settings.get("byok_xai_key"):
            self.xai_key.default = guild_settings["byok_xai_key"]
        if guild_settings.get("byok_openai_key"):
            self.openai_key.default = guild_settings["byok_openai_key"]
        if guild_settings.get("byok_anthropic_key"):
            self.anthropic_key.default = guild_settings["byok_anthropic_key"]
        if guild_settings.get("byok_deepseek_key"):
            self.deepseek_key.default = guild_settings["byok_deepseek_key"]

    async def on_submit(self, interaction: discord.Interaction):
        g_key = self.gemini_key.value.strip() if self.gemini_key.value else None
        x_key = self.xai_key.value.strip() if self.xai_key.value else None
        o_key = self.openai_key.value.strip() if self.openai_key.value else None
        a_key = self.anthropic_key.value.strip() if self.anthropic_key.value else None
        d_key = self.deepseek_key.value.strip() if self.deepseek_key.value else None

        key_updates = [
            ("byok_gemini_key", g_key),
            ("byok_xai_key", x_key),
            ("byok_openai_key", o_key),
            ("byok_anthropic_key", a_key),
            ("byok_deepseek_key", d_key)
        ]

        bot = self.parent_view.bot
        for col, val in key_updates:
            old_val = self.guild_settings.get(col)
            await bot.db_manager.update_guild_setting(self.guild_id, col, val)
            await bot.db_manager.log_settings_change(self.guild_id, interaction.user.id, col, str(old_val), str(val))
            bot.settings_cache.setdefault(self.guild_id, {})[col] = val
            self.guild_settings[col] = val

        if hasattr(self.parent_view, "render_ai") and getattr(self.parent_view, "active_tab", "") == "ai":
            self.parent_view.render_ai()
            await interaction.response.edit_message(view=self.parent_view)
        elif hasattr(self.parent_view, "switch_plan_page"):
            await self.parent_view.switch_plan_page(interaction, 2)
        elif hasattr(self.parent_view, "switch_page"):
            self.parent_view.switch_page(2)
            await interaction.response.edit_message(view=self.parent_view)


class PremiumContainer(ui.Container):
    """Layout container presenting a 3-page comparative plan paginator."""

    def __init__(self, bot, guild: discord.Guild, user: typing.Union[discord.User, discord.Member], is_premium: bool, has_byok: bool, parent_view, checkout_url: typing.Optional[str] = None, portal_url: typing.Optional[str] = None, page_idx: int = 1):
        super().__init__()
        self.bot = bot
        self.guild = guild
        self.user = user
        self.is_premium = is_premium
        self.has_byok = has_byok
        self.parent_view = parent_view
        self.checkout_url = checkout_url
        self.portal_url = portal_url
        self.page_idx = max(0, min(2, page_idx))
        self._build_container()

    def _build_container(self):
        # 1. Title Header & Server Subtext
        self.add_item(ui.TextDisplay(f"# Server Plan\n-# {self.guild.name}"))
        self.add_item(ui.Separator())

        # Determine active status per plan
        is_free_current = (not self.is_premium and not self.has_byok)
        is_premium_current = self.is_premium
        is_byok_current = (self.has_byok and not self.is_premium)

        # 2. Page Content Rendering
        if self.page_idx == 0:
            # --- PAGE 1: FREE PLAN ---
            curr_tag = " (Current)" if is_free_current else ""
            content = (
                f"## Free Plan{curr_tag}\n"
                f"**0.00€ / month**\n\n"
                f"✅ 100k tokens/week\n"
                f"✅ 5–10 message context window\n"
                f"✅ 2 image gens/month\n"
                f"✅ Websearch\n"
                f"❌ Vision\n"
                f"❌ Custom system instructions"
            )
        elif self.page_idx == 1:
            # --- PAGE 2: PREMIUM PLAN ---
            curr_tag = " (Current)" if is_premium_current else ""
            content = (
                f"## Premium Plan{curr_tag}\n"
                f"**2.99€ / month**\n\n"
                f"✅ 500k tokens/week\n"
                f"✅ 30 message context window\n"
                f"✅ 20 image gens/month\n"
                f"✅ Websearch\n"
                f"✅ Vision\n"
                f"✅ Custom system instructions"
            )
        else:
            # --- PAGE 3: BYOK ---
            curr_tag = " (Current)" if is_byok_current else ""
            content = (
                f"## Bring Your Own Key{curr_tag}\n"
                f"**0.00€ / month**\n\n"
                f"✅ ∞ tokens/week\n"
                f"✅ 30 message context window\n"
                f"✅ ∞ image gens/week\n"
                f"✅ Websearch\n"
                f"✅ Vision\n"
                f"✅ Custom system instructions\n"
                f"✅ Customizable settings"
            )

        self.add_item(ui.TextDisplay(content))
        self.add_item(ui.Separator())

        # 3. Dynamic 3-Button Navigation Row: [ ◀ ] [ Action Button ] [ ▶ ]
        nav_row = ui.ActionRow()

        # Prev Button
        prev_btn = ui.Button(
            label="◀",
            style=discord.ButtonStyle.gray,
            disabled=(self.page_idx == 0)
        )
        async def _on_prev(interaction: discord.Interaction):
            self.parent_view.switch_page(self.page_idx - 1)
            await interaction.response.edit_message(view=self.parent_view)
        prev_btn.callback = _on_prev
        nav_row.add_item(prev_btn)

        # Center Action Button
        if self.page_idx == 0:
            status_label = "Current Plan" if is_free_current else "Default Plan"
            action_btn = ui.Button(
                label=status_label,
                style=discord.ButtonStyle.gray,
                disabled=True
            )
            nav_row.add_item(action_btn)
        elif self.page_idx == 1:
            if not self.is_premium:
                final_checkout = self.checkout_url or "https://polar.sh"
                upgrade_btn = ui.Button(
                    label="👑 Upgrade",
                    url=final_checkout,
                    style=discord.ButtonStyle.link
                )
                nav_row.add_item(upgrade_btn)
            elif self.portal_url:
                portal_btn = ui.Button(
                    label="Manage Billing",
                    url=self.portal_url,
                    style=discord.ButtonStyle.link
                )
                nav_row.add_item(portal_btn)
            else:
                active_btn = ui.Button(
                    label="👑 Premium Active",
                    style=discord.ButtonStyle.gray,
                    disabled=True
                )
                nav_row.add_item(active_btn)
        else:
            byok_label = "⚙️ Manage Keys" if self.has_byok else "⚙️ Setup Keys"
            byok_btn = ui.Button(
                label=byok_label,
                style=discord.ButtonStyle.gray
            )
            async def _on_byok_click(interaction: discord.Interaction):
                settings = self.bot.settings_cache.get(self.guild.id, {})
                await interaction.response.send_modal(BYOKModal(settings, self.guild.id, self.parent_view))
            byok_btn.callback = _on_byok_click
            nav_row.add_item(byok_btn)

        # Next Button
        next_btn = ui.Button(
            label="▶",
            style=discord.ButtonStyle.gray,
            disabled=(self.page_idx == 2)
        )
        async def _on_next(interaction: discord.Interaction):
            self.parent_view.switch_page(self.page_idx + 1)
            await interaction.response.edit_message(view=self.parent_view)
        next_btn.callback = _on_next
        nav_row.add_item(next_btn)

        self.add_item(nav_row)


class PremiumView(ui.LayoutView):
    """View handling the 3-page comparative plan carousel."""

    def __init__(self, bot, guild: discord.Guild, user: typing.Union[discord.User, discord.Member], billing_service: PolarBillingService, checkout_url: typing.Optional[str] = None, portal_url: typing.Optional[str] = None, initial_page: int = 1):
        super().__init__(timeout=180.0)
        self.bot = bot
        self.guild = guild
        self.user = user
        self.billing_service = billing_service
        self.checkout_url = checkout_url
        self.portal_url = portal_url
        self.page_idx = initial_page
        self.switch_page(self.page_idx)

    def switch_page(self, page_idx: int):
        self.page_idx = max(0, min(2, page_idx))
        self.clear_items()
        is_premium = self.bot.settings_cache.get(self.guild.id, {}).get("is_premium", 0) == 1
        guild_settings = self.bot.settings_cache.get(self.guild.id, {})
        has_byok = any(
            guild_settings.get(k)
            for k in ["byok_gemini_key", "byok_xai_key", "byok_openai_key", "byok_anthropic_key", "byok_deepseek_key", "byok_glm_key"]
        )

        container = PremiumContainer(
            self.bot,
            self.guild,
            self.user,
            is_premium,
            has_byok,
            self,
            self.checkout_url,
            self.portal_url,
            page_idx=self.page_idx
        )
        self.add_item(container)


class Billing(commands.Cog):
    """Manages Polar.sh subscriptions, checkout links, customer portals, and premium upgrades."""

    def __init__(self, bot):
        self.bot = bot
        self.billing_service = PolarBillingService()
        port = int(getattr(DefaultSettings, "WEBHOOK_PORT", 8080))
        self.webhook_server = PolarWebhookServer(bot, self.billing_service, port=port)

    async def cog_load(self):
        """Starts the webhook server and syncs active subscriptions when the cog loads."""
        await self.webhook_server.start()
        try:
            await self.billing_service.sync_active_subscriptions(self.bot)
        except Exception as e:
            logger.warning(f"Initial Polar subscription sync failed: {e}")

    async def cog_unload(self):
        """Stops the webhook server cleanly on cog unload."""
        await self.webhook_server.stop()

    @commands.hybrid_command(name="premium", aliases=["subscribe", "plan", "upgrade"])
    @commands.guild_only()
    async def premium(self, ctx: commands.Context):
        """Displays server premium status and provides a direct Polar.sh checkout link."""
        await ctx.defer(ephemeral=True)

        checkout_url = None
        portal_url = None

        if self.billing_service.is_configured:
            try:
                # Sync subscriptions directly from Polar API as a fail-safe
                await self.billing_service.sync_active_subscriptions(self.bot)

                checkout_url = await self.billing_service.create_checkout_session(
                    guild_id=ctx.guild.id,
                    user_id=ctx.author.id,
                    guild_name=ctx.guild.name,
                    user_name=str(ctx.author)
                )

                sub = await self.bot.db_manager.get_subscription(ctx.guild.id)
                if sub and sub.get("customer_id"):
                    portal_url = self.billing_service.get_customer_portal_url(sub["customer_id"])
            except Exception as e:
                logger.error(f"Error preparing Polar.sh links for /premium: {e}")

        view = PremiumView(
            self.bot,
            ctx.guild,
            ctx.author,
            self.billing_service,
            checkout_url=checkout_url,
            portal_url=portal_url,
            initial_page=1
        )

        await ctx.reply(view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Billing(bot))
