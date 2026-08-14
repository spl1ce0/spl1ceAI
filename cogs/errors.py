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

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Save the original tree error handler, then override it
        self.original_tree_on_error = bot.tree.on_error
        bot.tree.on_error = self.on_app_command_error

    def cog_unload(self):
        # Restore original tree error handler when cog is unloaded
        self.bot.tree.on_error = self.original_tree_on_error

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Unwrap CommandInvokeError to get the real cause
        if isinstance(error, app_commands.CommandInvokeError):
            error = error.original

        response_content = None
        
        if isinstance(error, app_commands.CommandOnCooldown):
            response_content = f"{Emojis.WARNING} This command is on cooldown. Try again in `{error.retry_after:.1f}` seconds."
        elif isinstance(error, app_commands.MissingPermissions):
            perms = ", ".join(f"`{p}`" for p in error.missing_permissions)
            response_content = f"{Emojis.WARNING} You lack the required permissions to run this command: {perms}"
        elif isinstance(error, app_commands.BotMissingPermissions):
            perms = ", ".join(f"`{p}`" for p in error.missing_permissions)
            response_content = f"{Emojis.WARNING} The bot lacks the required permissions to run this command: {perms}"
        elif isinstance(error, AIQuotaReachedError):
            response_content = ErrorMessages.QUOTA_REACHED
        elif isinstance(error, (AIRateLimitError, AIServiceUnavailableError)):
            response_content = ErrorMessages.BUSY_OR_LIMIT
        elif isinstance(error, AISafetyBlockedError):
            response_content = ErrorMessages.SAFETY_BLOCKED
        elif isinstance(error, AIConfigurationError):
            response_content = f"{Emojis.ERROR} AI service is misconfigured. Please check API keys."
        else:
            # Uncaught slash command error
            logger.error(f"Slash command error: {error}", exc_info=error)
            response_content = f"{Emojis.ERROR} An unexpected error occurred while running the command."

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
        # If the command has its own local error handler, skip global handling
        if hasattr(ctx.command, 'on_error'):
            return

        # Unwrap CommandInvokeError to get the real cause
        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        # Also skip if it's already handled by app command handler (hybrid command slash path)
        if isinstance(error, app_commands.AppCommandError):
            return

        if isinstance(error, commands.CommandNotFound):
            return  # Silently ignore command not found to avoid chat clutter

        if isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(f"{Emojis.WARNING} This command is on cooldown. Try again in `{error.retry_after:.1f}` seconds.")
        elif isinstance(error, commands.MissingPermissions):
            perms = ", ".join(f"`{p}`" for p in error.missing_permissions)
            await ctx.reply(f"{Emojis.WARNING} You lack the required permissions to run this command: {perms}")
        elif isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(f"`{p}`" for p in error.missing_permissions)
            await ctx.reply(f"{Emojis.WARNING} The bot lacks the required permissions to run this command: {perms}")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f"{Emojis.WARNING} Missing required argument: `{error.param.name}`. Correct usage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`")
        elif isinstance(error, commands.BadArgument):
            await ctx.reply(f"{Emojis.WARNING} Invalid argument passed. Correct usage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`")
        elif isinstance(error, AIQuotaReachedError):
            await ctx.reply(ErrorMessages.QUOTA_REACHED)
        elif isinstance(error, (AIRateLimitError, AIServiceUnavailableError)):
            await ctx.reply(ErrorMessages.BUSY_OR_LIMIT)
        elif isinstance(error, AISafetyBlockedError):
            await ctx.reply(ErrorMessages.SAFETY_BLOCKED)
        elif isinstance(error, AIConfigurationError):
            await ctx.reply(f"{Emojis.ERROR} AI service is misconfigured. Please check API keys.")
        else:
            # Uncaught prefix command error
            logger.error(f"Prefix command error: {error}", exc_info=error)
            await ctx.reply(f"{Emojis.ERROR} An unexpected error occurred while running the command.")

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
