import logging
import discord
from discord.ext import commands
from discord import app_commands
from cogs.utils.constants import Emojis

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
        else:
            # Uncaught slash command error
            logger.error(f"Slash command error: {error}", exc_info=error)
            response_content = f"{Emojis.ERROR} An unexpected error occurred while running the command."

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
        else:
            # Uncaught prefix command error
            logger.error(f"Prefix command error: {error}", exc_info=error)
            await ctx.reply(f"{Emojis.ERROR} An unexpected error occurred while running the command.")

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
