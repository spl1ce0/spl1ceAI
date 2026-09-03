import uuid
import logging
import datetime
import traceback
from typing import Optional, List

import discord
from discord.ext import commands
from discord import app_commands, ui

from cogs.utils.constants import Emojis
from cogs.utils.exceptions import (
    AIQuotaReachedError,
    AIRateLimitError,
    AIServiceUnavailableError,
    AISafetyBlockedError,
    AIConfigurationError,
    AIError,
    EconomyError,
    InsufficientBalanceError,
    DailyAlreadyClaimedError,
    ToolError,
    InvalidURLError,
    MediaTooLongError,
    MediaDownloadError
)

logger = logging.getLogger(__name__)


# =========================================================================
# --- COMPONENTS V2 ERROR CARD VIEW ---
# =========================================================================

class ErrorCardView(ui.LayoutView):
    """Discord Components V2 layout view for modern, card-based error reporting."""

    def __init__(
        self,
        title: str,
        description: str,
        details: Optional[str] = None,
        buttons: Optional[List[ui.Button]] = None,
        timeout: Optional[float] = 180.0
    ):
        super().__init__(timeout=timeout)
        container = ui.Container()

        # 1. Header and Primary Description
        content = f"### {title}\n{description}"
        if details:
            content += f"\n\n{details}"
        container.add_item(ui.TextDisplay(content))

        # 2. Interactive Buttons (if any)
        if buttons:
            container.add_item(ui.Separator())
            row = ui.ActionRow()
            for btn in buttons[:5]:
                row.add_item(btn)
            container.add_item(row)

        self.add_item(container)


# =========================================================================
# --- ERROR CARD FACTORY BUILDERS ---
# =========================================================================

def build_cooldown_card(retry_after: float) -> ErrorCardView:
    retry_ts = int(discord.utils.utcnow().timestamp() + retry_after)
    return ErrorCardView(
        title="⏱️ Command on Cooldown",
        description="You are using this command too fast.",
        details=f"-# Available again <t:{retry_ts}:R> (in `{retry_after:.1f}s`)."
    )


def build_permissions_card(perms_list: list, is_bot: bool = False) -> ErrorCardView:
    perms_str = " • ".join(f"`{p}`" for p in perms_list)
    if is_bot:
        return ErrorCardView(
            title="🔒 Bot Missing Permissions",
            description="The bot requires additional permissions in this channel to complete this command.",
            details=f"-# Required: {perms_str}"
        )
    return ErrorCardView(
        title="🔒 Missing Permissions",
        description="You do not have the required permissions to run this command.",
        details=f"-# Required: {perms_str}"
    )


def build_quota_card(error: AIQuotaReachedError, checkout_url: Optional[str] = None) -> ErrorCardView:
    reset_ts = getattr(error, 'reset_ts', None)
    is_image = getattr(error, 'is_image', False)

    portal_link = checkout_url or "https://polar.sh/spl1ceai/portal"
    upgrade_btn = ui.Button(label="👑 Upgrade Plan", url=portal_link, style=discord.ButtonStyle.link)

    if is_image:
        tip = "Upgrade to **Premium (2.99€/mo)** for 20 images/month or connect your own API key in `/settings`."
        if reset_ts:
            details_text = f"-# Next image generation unlocks <t:{reset_ts}:R>.\n-# {tip}"
        else:
            details_text = f"-# {tip}"

        return ErrorCardView(
            title="⚠️ Image Generation Limit Reached",
            description="The free tier includes 1 image generation every 2 weeks.",
            details=details_text,
            buttons=[upgrade_btn]
        )

    # Token Quota
    tip = "Server admins can upgrade to **Premium (500k tokens/wk)** with `/upgrade` or link a free API key in `/settings`."
    if reset_ts:
        details_text = f"-# Weekly quota resets <t:{reset_ts}:R> *(Monday 00:00 UTC)*.\n-# {tip}"
    else:
        details_text = f"-# {tip}"

    return ErrorCardView(
        title="⚠️ AI Token Quota Reached",
        description="This server has used its weekly token allowance (**100,000 / 100,000 tokens**).",
        details=details_text,
        buttons=[upgrade_btn]
    )


def build_missing_arg_card(param_name: str, prefix: str, cmd_name: str, signature: str) -> ErrorCardView:
    return ErrorCardView(
        title="⚠️ Missing Required Argument",
        description=f"Missing required parameter: `<{param_name}>`",
        details=f"**Usage**\n`{prefix}{cmd_name} {signature}`\n-# Supply the required parameter and run the command again."
    )


def build_bad_arg_card(prefix: str, cmd_name: str, signature: str) -> ErrorCardView:
    return ErrorCardView(
        title="⚠️ Invalid Argument Passed",
        description="One or more arguments provided are invalid.",
        details=f"**Usage**\n`{prefix}{cmd_name} {signature}`\n-# Check the syntax above to ensure your inputs match the expected format."
    )


def build_ai_busy_card() -> ErrorCardView:
    return ErrorCardView(
        title="⚠️ AI Service Busy",
        description="The upstream AI provider is currently experiencing high load or rate limits.",
        details="-# Please wait a few moments and try your request again."
    )


def build_ai_safety_card() -> ErrorCardView:
    return ErrorCardView(
        title="🛡️ Content Blocked",
        description="This prompt or response was blocked by upstream safety and content moderation filters.",
        details="-# Please rephrase your query and try again."
    )


def build_ai_config_card() -> ErrorCardView:
    return ErrorCardView(
        title="❌ AI Configuration Error",
        description="The AI service is misconfigured or the linked API key is invalid.",
        details="-# Server admins can review and update API keys in `/settings`."
    )


def build_unexpected_card(incident_id: str) -> ErrorCardView:
    return ErrorCardView(
        title="❌ Something Went Wrong",
        description="An unexpected error occurred while executing this command.",
        details=f"-# Incident ID: `{incident_id}` • Automatically logged for diagnostics."
    )


def build_insufficient_balance_card(current: float, required: float) -> ErrorCardView:
    return ErrorCardView(
        title="🪙 Insufficient Balance",
        description=f"You need **{required:,.2f} 🪙** for this action, but your balance is **{current:,.2f} 🪙**.",
        details="-# Claim your daily coins with `/daily` or win hands in `/blackjack`."
    )


def build_daily_cooldown_card(next_claim_ts: int) -> ErrorCardView:
    return ErrorCardView(
        title="⏱️ Daily Already Claimed",
        description="You have already claimed your daily coin reward today.",
        details=f"-# Next reward unlocks <t:{next_claim_ts}:R> (at <t:{next_claim_ts}:t>)."
    )


def build_tool_error_card(error: Exception) -> ErrorCardView:
    return ErrorCardView(
        title="⚠️ Tool Operation Failed",
        description=str(error),
        details="-# Please check the command arguments or URL and try again."
    )


def build_user_not_found_card(arg: str) -> ErrorCardView:
    return ErrorCardView(
        title="⚠️ User Not Found",
        description=f"Could not find any user or member matching `{arg}`.",
        details="-# Mention the user directly (@user) or provide their numerical Discord ID."
    )


# =========================================================================
# --- ERROR HANDLER COG ---
# =========================================================================

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.original_tree_on_error = bot.tree.on_error
        bot.tree.on_error = self.on_app_command_error

    def cog_unload(self):
        self.bot.tree.on_error = self.original_tree_on_error

    async def _get_checkout_url(self, guild_id: Optional[int], user_id: Optional[int]) -> str:
        """Helper to fetch a pre-filled Polar checkout session if available."""
        billing_cog = self.bot.get_cog("Billing")
        if billing_cog and hasattr(billing_cog, "billing_service") and billing_cog.billing_service.is_configured:
            try:
                if guild_id and user_id:
                    url = await billing_cog.billing_service.create_checkout_session(
                        guild_id=guild_id,
                        user_id=user_id
                    )
                    if url:
                        return url
            except Exception as e:
                logger.debug(f"Failed to generate checkout link for error card: {e}")
        return "https://polar.sh/spl1ceai/portal"

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Unwrap CommandInvokeError to access the original root cause
        if isinstance(error, app_commands.CommandInvokeError):
            error = error.original

        # Silently ignore dev/owner check failures to avoid giving away hidden command existence
        if isinstance(error, (commands.NotOwner, app_commands.CheckFailure)):
            return

        incident_id = f"ERR-{uuid.uuid4().hex[:6].upper()}"

        if isinstance(error, app_commands.CommandOnCooldown):
            view = build_cooldown_card(error.retry_after)
        elif isinstance(error, app_commands.MissingPermissions):
            view = build_permissions_card(error.missing_permissions, is_bot=False)
        elif isinstance(error, app_commands.BotMissingPermissions):
            view = build_permissions_card(error.missing_permissions, is_bot=True)
        elif isinstance(error, AIQuotaReachedError):
            checkout_url = await self._get_checkout_url(interaction.guild_id, interaction.user.id)
            view = build_quota_card(error, checkout_url=checkout_url)
        elif isinstance(error, (AIRateLimitError, AIServiceUnavailableError)):
            view = build_ai_busy_card()
        elif isinstance(error, AISafetyBlockedError):
            view = build_ai_safety_card()
        elif isinstance(error, InsufficientBalanceError):
            view = build_insufficient_balance_card(error.current_balance, error.required_amount)
        elif isinstance(error, DailyAlreadyClaimedError):
            view = build_daily_cooldown_card(error.next_claim_ts)
        elif isinstance(error, (commands.MemberNotFound, commands.UserNotFound)):
            view = build_user_not_found_card(getattr(error, "argument", "user"))
        elif isinstance(error, ToolError):
            view = build_tool_error_card(error)
        else:
            # Uncaught slash command error
            logger.error(f"Slash command error [{incident_id}]: {error}", exc_info=error)
            view = build_unexpected_card(incident_id)

        # Telemetry: Log Error & Failed Execution (ignore developer/analytics cogs)
        command_name = interaction.command.name if interaction.command else "Unknown"
        cog_binding = getattr(interaction.command, "binding", None)
        cog_name = getattr(cog_binding, "qualified_name", "") if cog_binding else ""
        
        if cog_name not in ["Dev", "Analytics", "ErrorHandler"]:
            guild_id = interaction.guild_id
            channel_id = interaction.channel_id
            user_id = interaction.user.id
            
            execution_time_ms = 0
            if interaction.created_at:
                execution_time_ms = int((datetime.datetime.now(datetime.timezone.utc) - interaction.created_at).total_seconds() * 1000)

            tb_string = "".join(traceback.format_exception(type(error), error, error.__traceback__))

            try:
                await self.bot.db_manager.log_error(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    user_id=user_id,
                    command_name=command_name,
                    error_type=error.__class__.__name__,
                    error_message=f"[{incident_id}] {str(error)}",
                    traceback=tb_string
                )
                await self.bot.db_manager.log_command_execution(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    user_id=user_id,
                    command_name=command_name,
                    is_slash=True,
                    execution_time_ms=execution_time_ms,
                    success=False
                )
            except Exception as e:
                logger.error(f"Failed to log slash error telemetry: {e}")

        # Send Components V2 response safely checking if interaction was already acknowledged
        try:
            if interaction.response.is_done():
                await interaction.followup.send(view=view, ephemeral=True)
            else:
                await interaction.response.send_message(view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to send slash error view: {e}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if hasattr(ctx.command, 'on_error'):
            return

        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        if isinstance(error, app_commands.AppCommandError):
            return

        # Silently ignore command not found and dev/owner check failures to prevent giving away command existence
        if isinstance(error, (commands.CommandNotFound, commands.NotOwner, app_commands.CheckFailure)):
            return

        incident_id = f"ERR-{uuid.uuid4().hex[:6].upper()}"
        prefix = ctx.prefix or "!"
        cmd_name = ctx.command.qualified_name if ctx.command else "command"
        sig = ctx.command.signature if ctx.command else ""

        if isinstance(error, commands.CommandOnCooldown):
            view = build_cooldown_card(error.retry_after)
        elif isinstance(error, commands.MissingPermissions):
            view = build_permissions_card(error.missing_permissions, is_bot=False)
        elif isinstance(error, commands.BotMissingPermissions):
            view = build_permissions_card(error.missing_permissions, is_bot=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            view = build_missing_arg_card(error.param.name, prefix, cmd_name, sig)
        elif isinstance(error, commands.BadArgument):
            view = build_bad_arg_card(prefix, cmd_name, sig)
        elif isinstance(error, AIQuotaReachedError):
            guild_id = ctx.guild.id if ctx.guild else None
            checkout_url = await self._get_checkout_url(guild_id, ctx.author.id)
            view = build_quota_card(error, checkout_url=checkout_url)
        elif isinstance(error, (AIRateLimitError, AIServiceUnavailableError)):
            view = build_ai_busy_card()
        elif isinstance(error, AISafetyBlockedError):
            view = build_ai_safety_card()
        elif isinstance(error, AIConfigurationError):
            view = build_ai_config_card()
        elif isinstance(error, InsufficientBalanceError):
            view = build_insufficient_balance_card(error.current_balance, error.required_amount)
        elif isinstance(error, DailyAlreadyClaimedError):
            view = build_daily_cooldown_card(error.next_claim_ts)
        elif isinstance(error, (commands.MemberNotFound, commands.UserNotFound)):
            view = build_user_not_found_card(getattr(error, "argument", "user"))
        elif isinstance(error, ToolError):
            view = build_tool_error_card(error)
        else:
            logger.error(f"Prefix command error [{incident_id}]: {error}", exc_info=error)
            view = build_unexpected_card(incident_id)

        # Telemetry: Log Error & Failed Execution (ignore developer/analytics cogs)
        if not (ctx.cog and ctx.cog.qualified_name in ["Dev", "Analytics", "ErrorHandler"]):
            guild_id = ctx.guild.id if ctx.guild else None
            channel_id = ctx.channel.id if ctx.channel else None
            user_id = ctx.author.id
            is_slash = ctx.interaction is not None

            import time
            start_time = getattr(ctx, "telemetry_start_time", None)
            execution_time_ms = int((time.perf_counter() - start_time) * 1000) if start_time else 0

            tb_string = "".join(traceback.format_exception(type(error), error, error.__traceback__))

            try:
                await self.bot.db_manager.log_error(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    user_id=user_id,
                    command_name=command_name,
                    error_type=error.__class__.__name__,
                    error_message=f"[{incident_id}] {str(error)}",
                    traceback=tb_string
                )
                await self.bot.db_manager.log_command_execution(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    user_id=user_id,
                    command_name=command_name,
                    is_slash=is_slash,
                    execution_time_ms=execution_time_ms,
                    success=False
                )
            except Exception as e:
                logger.error(f"Failed to log prefix error telemetry: {e}")

        try:
            await ctx.reply(view=view)
        except Exception as e:
            logger.error(f"Failed to send prefix error view: {e}")


async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
