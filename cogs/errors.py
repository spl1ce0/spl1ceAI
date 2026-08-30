import logging
import discord
from discord.ext import commands
from discord import app_commands
from cogs.utils.constants import Emojis, ErrorMessages
from cogs.utils.exceptions import (
    AIQuotaReachedError,
    AIRateLimitError,
    AIServiceUnavailableError,
    AISafetyBlockedError,
    AIConfigurationError
)

logger = logging.getLogger(__name__)


def format_cooldown_error(retry_after: float) -> str:
    retry_ts = int(discord.utils.utcnow().timestamp() + retry_after)
    return (
        f"### ⏱️ Command on Cooldown\n"
        f"You are using this command too fast.\n"
        f"Available again <t:{retry_ts}:R> (in `{retry_after:.1f}s`)."
    )


def format_missing_permissions_error(perms_list: list, is_bot: bool = False) -> str:
    perms_str = " • ".join(f"`{p}`" for p in perms_list)
    if is_bot:
        return (
            f"### 🔒 Bot Missing Permissions\n"
            f"The bot requires additional permissions in this channel:\n"
            f"{perms_str}"
        )
    return (
        f"### 🔒 Missing Permissions\n"
        f"You do not have the required permissions to run this command:\n"
        f"{perms_str}"
    )


def format_quota_error(error: AIQuotaReachedError) -> str:
    reset_ts = getattr(error, 'reset_ts', None)
    is_image = getattr(error, 'is_image', False)
    if is_image and reset_ts:
        return (
            f"### ⚠️ Image Generation Limit Reached\n"
            f"Free tier includes 1 image generation every 2 weeks.\n"
            f"Next image available <t:{reset_ts}:R>.\n\n"
            f"-# 💡 Upgrade to **Premium (2.99€/mo)** for 10 images/week or connect your own API key in `/settings`."
        )
    elif reset_ts:
        return (
            f"### ⚠️ AI Token Quota Reached\n"
            f"This server has used its weekly token allowance (**100,000 / 100,000 tokens**).\n"
            f"Weekly allowance resets <t:{reset_ts}:R> *(Monday 00:00 UTC)*.\n\n"
            f"-# 💡 Server admins can upgrade to **Premium (500k tokens/week)** with `/upgrade` or link their own free API key in `/settings`."
        )
    return f"### ⚠️ AI Quota Reached\n{str(error)}"


def format_missing_arg_error(param_name: str, prefix: str, cmd_name: str, signature: str) -> str:
    return (
        f"### ⚠️ Missing Required Argument\n"
        f"Missing parameter: `<{param_name}>`\n\n"
        f"**Usage**\n`{prefix}{cmd_name} {signature}`"
    )


def format_bad_arg_error(prefix: str, cmd_name: str, signature: str) -> str:
    return (
        f"### ⚠️ Invalid Argument Passed\n"
        f"Please check the command syntax and try again.\n\n"
        f"**Usage**\n`{prefix}{cmd_name} {signature}`"
    )


def format_unexpected_error() -> str:
    return (
        f"### ❌ Something Went Wrong\n"
        f"An unexpected error occurred while executing this command.\n"
        f"The incident has been automatically logged for diagnostics."
    )


class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.original_tree_on_error = bot.tree.on_error
        bot.tree.on_error = self.on_app_command_error

    def cog_unload(self):
        self.bot.tree.on_error = self.original_tree_on_error

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Unwrap CommandInvokeError to get the real cause
        if isinstance(error, app_commands.CommandInvokeError):
            error = error.original

        # Silently ignore dev/owner check failures to prevent giving away command existence
        if isinstance(error, (commands.NotOwner, app_commands.CheckFailure)):
            return

        if isinstance(error, app_commands.CommandOnCooldown):
            response_content = format_cooldown_error(error.retry_after)
        elif isinstance(error, app_commands.MissingPermissions):
            response_content = format_missing_permissions_error(error.missing_permissions, is_bot=False)
        elif isinstance(error, app_commands.BotMissingPermissions):
            response_content = format_missing_permissions_error(error.missing_permissions, is_bot=True)
        elif isinstance(error, AIQuotaReachedError):
            response_content = format_quota_error(error)
        elif isinstance(error, (AIRateLimitError, AIServiceUnavailableError)):
            response_content = f"### ⚠️ Service Busy\n{ErrorMessages.BUSY_OR_LIMIT}"
        elif isinstance(error, AISafetyBlockedError):
            response_content = f"### ⚠️ Content Blocked\n{ErrorMessages.SAFETY_BLOCKED}"
        elif isinstance(error, AIConfigurationError):
            response_content = f"### ❌ AI Configuration Error\nAI service is misconfigured. Please check API keys in `/settings`."
        else:
            # Uncaught slash command error
            logger.error(f"Slash command error: {error}", exc_info=error)
            response_content = format_unexpected_error()

        # Telemetry: Log Error & Failed Execution (ignore developer/analytics cogs)
        command_name = interaction.command.name if interaction.command else "Unknown"
        cog_binding = getattr(interaction.command, "binding", None)
        cog_name = getattr(cog_binding, "qualified_name", "") if cog_binding else ""
        
        if cog_name not in ["Dev", "Analytics", "ErrorHandler"]:
            guild_id = interaction.guild_id
            channel_id = interaction.channel_id
            user_id = interaction.user.id
            
            import datetime
            execution_time_ms = 0
            if interaction.created_at:
                execution_time_ms = int((datetime.datetime.now(datetime.timezone.utc) - interaction.created_at).total_seconds() * 1000)

            import traceback
            tb_string = "".join(traceback.format_exception(type(error), error, error.__traceback__))

            try:
                await self.bot.db_manager.log_error(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    user_id=user_id,
                    command_name=command_name,
                    error_type=error.__class__.__name__,
                    error_message=str(error),
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

        # Send response safely checking if interaction was already acknowledged
        try:
            if interaction.response.is_done():
                await interaction.followup.send(response_content, ephemeral=True)
            else:
                await interaction.response.send_message(response_content, ephemeral=True)
        except Exception as e:
            logger.error(f"Failed to send slash error response: {e}")

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

        if isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(format_cooldown_error(error.retry_after))
        elif isinstance(error, commands.MissingPermissions):
            await ctx.reply(format_missing_permissions_error(error.missing_permissions, is_bot=False))
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.reply(format_missing_permissions_error(error.missing_permissions, is_bot=True))
        elif isinstance(error, commands.MissingRequiredArgument):
            prefix = ctx.prefix or "!"
            cmd_name = ctx.command.qualified_name if ctx.command else "command"
            sig = ctx.command.signature if ctx.command else ""
            await ctx.reply(format_missing_arg_error(error.param.name, prefix, cmd_name, sig))
        elif isinstance(error, commands.BadArgument):
            prefix = ctx.prefix or "!"
            cmd_name = ctx.command.qualified_name if ctx.command else "command"
            sig = ctx.command.signature if ctx.command else ""
            await ctx.reply(format_bad_arg_error(prefix, cmd_name, sig))
        elif isinstance(error, AIQuotaReachedError):
            await ctx.reply(format_quota_error(error))
        elif isinstance(error, (AIRateLimitError, AIServiceUnavailableError)):
            await ctx.reply(f"### ⚠️ Service Busy\n{ErrorMessages.BUSY_OR_LIMIT}")
        elif isinstance(error, AISafetyBlockedError):
            await ctx.reply(f"### ⚠️ Content Blocked\n{ErrorMessages.SAFETY_BLOCKED}")
        elif isinstance(error, AIConfigurationError):
            await ctx.reply(f"### ❌ AI Configuration Error\nAI service is misconfigured. Please check API keys.")
        else:
            logger.error(f"Prefix command error: {error}", exc_info=error)
            await ctx.reply(format_unexpected_error())

        # Telemetry: Log Error & Failed Execution (ignore developer/analytics cogs)
        if not (ctx.cog and ctx.cog.qualified_name in ["Dev", "Analytics", "ErrorHandler"]):
            guild_id = ctx.guild.id if ctx.guild else None
            channel_id = ctx.channel.id if ctx.channel else None
            user_id = ctx.author.id
            command_name = ctx.command.qualified_name if ctx.command else "Unknown"
            is_slash = ctx.interaction is not None

            import time
            start_time = getattr(ctx, "telemetry_start_time", None)
            execution_time_ms = int((time.perf_counter() - start_time) * 1000) if start_time else 0

            import traceback
            tb_string = "".join(traceback.format_exception(type(error), error, error.__traceback__))

            try:
                await self.bot.db_manager.log_error(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    user_id=user_id,
                    command_name=command_name,
                    error_type=error.__class__.__name__,
                    error_message=str(error),
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

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
