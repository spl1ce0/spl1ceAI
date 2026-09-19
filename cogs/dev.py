from discord.ext import commands as cmds
from discord.ext.commands import Context, GuildConverter

import discord
from cogs.utils.constants import Emojis
from cogs.utils.cards import send_confirmation, send_info, send_warning
from discord import ui
import typing
from typing import Optional
import logging
import subprocess
import os
import asyncio
import time
import datetime
import json
import psutil
import io


logger = logging.getLogger(__name__)


class Dev(cmds.Cog):

    def __init__(self, bot):
        self.bot = bot


    @cmds.group(name='extensions', aliases=['ext'])
    @cmds.is_owner()
    async def extensions(self, ctx: Context):
        pass


    @extensions.command(name='reload')
    @cmds.is_owner()
    async def extensions_reload(self, ctx: Context, *, extension: str):
        if extension == 'all':
            await self.reload_all(ctx)
            return

        try:
            await self.bot.reload_extension("cogs."+extension)
        except cmds.ExtensionError as e:
            await ctx.message.add_reaction(Emojis.ERROR)
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction(Emojis.SUCCESS)


    @extensions.command(name='load')
    @cmds.is_owner()
    async def extensions_load(self, ctx: Context, *, extension: str):
        if extension == 'all':
            await self.load_all(ctx)
            return
        
        try:
            await self.bot.load_extension("cogs."+extension)
        except cmds.ExtensionError as e:
            await ctx.message.add_reaction(Emojis.ERROR)
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction(Emojis.SUCCESS)
        

    @extensions.command(name='unload')
    @cmds.is_owner()
    async def extensions_unload(self, ctx: Context, *, extension: str):
        if extension == 'all':
            await self.unload_all(ctx)
            return

        try:
            await self.bot.unload_extension("cogs."+extension)
        except cmds.ExtensionError as e:
            await ctx.message.add_reaction(Emojis.ERROR)
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction(Emojis.SUCCESS)
        

    async def reload_all(self, ctx: Context):
        """Reloads every extension."""
        extensions = list(self.bot.extensions.keys())

        reloaded = []
        failed = []

        for extension in extensions:
            try:
                await self.bot.reload_extension(extension)
                reloaded.append(extension)
            except Exception as e:
                failed.append(f"{extension} (Error: {e})")

        if failed:
            message_lines = [f"{Emojis.SUCCESS} Reloaded: {', '.join(reloaded) if reloaded else 'None'}"]
            message_lines.append(f"{Emojis.ERROR} Failed:")
            for failure in failed:
                message_lines.append(f"  - {failure}")
            await ctx.message.add_reaction(Emojis.ERROR)
            await ctx.reply("\n".join(message_lines))
            
        else:
            await ctx.message.add_reaction(Emojis.SUCCESS)
    

    async def load_all(self, ctx: Context):
        """Loads every extension in `bot.initial_extensions` that isn't already loaded."""
        extensions = [
            extention
            for extention in self.bot.initial_extensions
            if extention not in self.bot.extensions
        ]

        loaded = []
        failed = []

        for extension in extensions:
            try:
                await self.bot.load_extension(extension)
                loaded.append(extension)
            except Exception as e:
                failed.append(f"{extension} (Error: {e})")

        if failed:
            message_lines = [f"{Emojis.SUCCESS} Loaded: {', '.join(loaded) if loaded else 'None'}"]
            message_lines.append(f"{Emojis.ERROR} Failed:")
            for failure in failed:
                message_lines.append(f"  - {failure}")
            await ctx.message.add_reaction(Emojis.ERROR)
            await ctx.reply("\n".join(message_lines))
        else:
            await ctx.message.add_reaction(Emojis.SUCCESS)
    

    async def unload_all(self, ctx: Context):
        """Unloads every extension."""
        extensions = list(self.bot.extensions.keys())

        unloaded = []
        failed = []

        for extension in extensions:
            try:
                await self.bot.unload_extension(extension)
                unloaded.append(extension)
            except Exception as e:
                failed.append(f"{extension} (Error: {e})")

        if failed:
            message_lines = [f"{Emojis.SUCCESS} Unloaded: {', '.join(unloaded) if unloaded else 'None'}"]
            message_lines.append(f"{Emojis.ERROR} Failed:")
            for failure in failed:
                message_lines.append(f"  - {failure}")
            await ctx.message.add_reaction(Emojis.ERROR)
            await ctx.reply("\n".join(message_lines))
        else:
            await ctx.message.add_reaction(Emojis.SUCCESS)



    @cmds.group(name='update', invoke_without_command=True)
    @cmds.is_owner()
    async def update(self, ctx: Context):
        """Update system components (bot or website)."""
        await send_info(
            ctx,
            "System Update",
            "Please specify a target component to update:",
            details="• `!update bot` — Pull latest repository changes and restart bot service.\n• `!update web` — Pull website repository and rebuild production bundle."
        )


    @update.command(name='bot', aliases=['core', 'app'])
    @cmds.is_owner()
    async def update_bot(self, ctx: Context):
        """Runs the update.sh script to pull latest changes and restart the bot."""
        await ctx.message.add_reaction(Emojis.RELOAD)
        status_msg = await ctx.reply("🔄 **Updating bot...** Pulling latest code and dependencies.", mention_author=False)

        data = {
            'channel_id': ctx.channel.id,
            'message_id': ctx.message.id,
            'status_message_id': status_msg.id,
            'action': 'update',
            'start_time': time.time()
        }
        await self.bot.db_manager.save_system_state('restart_info', json.dumps(data))

        try:
            await asyncio.create_subprocess_exec('./update.sh')
        except Exception as e:
            logger.error(f"Failed to start update process: {e}")
            try:
                await ctx.message.remove_reaction(Emojis.RELOAD, self.bot.user)
            except Exception:
                pass
            await ctx.message.add_reaction(Emojis.ERROR)
            await status_msg.edit(content=f"❌ **Failed to execute update script:** `{e}`")


    @update.command(name='web', aliases=['website', 'site'])
    @cmds.is_owner()
    async def update_web(self, ctx: Context):
        """Runs the update_website.sh script to pull and rebuild the website."""
        await ctx.message.add_reaction(Emojis.RELOAD)
        status_msg = await ctx.reply("🔄 **Updating website...** Pulling latest code and rebuilding bundle.", mention_author=False)

        try:
            proc = await asyncio.create_subprocess_exec(
                './update_website.sh',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            try:
                await ctx.message.remove_reaction(Emojis.RELOAD, self.bot.user)
            except Exception:
                pass

            if proc.returncode == 0:
                await ctx.message.add_reaction(Emojis.SUCCESS)
                await status_msg.edit(content="✅ **Website updated successfully!** Live at https://spl1ceai.com")
            else:
                await ctx.message.add_reaction(Emojis.ERROR)
                err_msg = (stderr or stdout).decode()[-1000:]
                await status_msg.edit(content=f"❌ **Website update failed:**\n```\n{err_msg}\n```")
        except Exception as e:
            logger.error(f"Failed to start website update process: {e}")
            try:
                await ctx.message.remove_reaction(Emojis.RELOAD, self.bot.user)
            except Exception:
                pass
            await ctx.message.add_reaction(Emojis.ERROR)
            await status_msg.edit(content=f"❌ **Failed to execute update script:** `{e}`")


    @cmds.command(name='restart')
    @cmds.is_owner()
    async def restart(self, ctx):
        """Restarts the bot by closing the connection and letting the service manager restart it."""
        await ctx.message.add_reaction(Emojis.RELOAD)
        
        data = {
            'channel_id': ctx.channel.id,
            'message_id': ctx.message.id,
            'start_time': time.time()
        }
        await self.bot.db_manager.save_system_state('restart_info', json.dumps(data))
            
        await asyncio.sleep(1)
        await self.bot.close()



    @cmds.group(name='commands')
    @cmds.is_owner()
    async def commands(self, ctx):
        pass
        
    
    @commands.command(name='remove')
    @cmds.is_owner()
    async def remove(self, ctx: Context, command: str, scope: Optional[str], guild: Optional[discord.Guild] = None):
        """Removes a command from the tree. If no guild is provided, removes it globally."""
        if scope == 'local':
            target = target or str(ctx.guild.id)
            guild = await GuildConverter().convert(ctx, target)
        elif scope == 'global':
            guild = None
        else:
            await ctx.message.add_reaction(Emojis.ERROR)
            return
        
        try:
            self.bot.tree.remove_command(command, guild=guild)
            await ctx.message.add_reaction(Emojis.SUCCESS)
        except Exception as e:
            logger.error(f"Remove command failed: {e}")
            await ctx.message.add_reaction(Emojis.ERROR)
        
    
    @commands.command(name='clear')
    @cmds.is_owner()
    async def clear(self, ctx: Context, scope: Optional[str], target: Optional[str] = None):
        """Clears commands from the tree. If no guild is provided, clears globally."""

        if scope == 'local':
            target = target or str(ctx.guild.id)
            guild = await GuildConverter().convert(ctx, target)
        elif scope == 'global':
            guild = None
        else:
            await ctx.message.add_reaction(Emojis.ERROR)
            return

        try:
            self.bot.tree.clear_commands(guild=guild)
            await ctx.message.add_reaction(Emojis.SUCCESS)
        except Exception as e:
            logger.error(f"Clear commands failed: {e}")
            await ctx.message.add_reaction(Emojis.ERROR)


    @commands.command(name='sync')
    @cmds.is_owner()
    async def sync(self, ctx: Context, scope: Optional[str] = None, target: Optional[str] = None):
        """Syncs commands to the tree."""
        if scope == 'local':
            target = target or str(ctx.guild.id)
            guild = await GuildConverter().convert(ctx, target)
        elif scope == 'global':
            guild = None
        else:
            await ctx.message.add_reaction(Emojis.ERROR)
            return
        
        try: 
            await self.bot.tree.sync(guild=guild)
            await ctx.message.add_reaction(Emojis.SUCCESS)
        except Exception as e:
            logger.error(f"Sync command failed: {e}")
            await ctx.message.add_reaction(Emojis.ERROR)
            
    @cmds.command(name='logs')
    @cmds.is_owner()
    async def logs(self, ctx: Context, arg1: typing.Union[int, str] = 20, arg2: typing.Union[int, str] = None):
        """Displays the latest logs in an interactive paginated container.
        
        Usage:
            !logs [lines] [ai|discord]
            !logs [ai|discord] [lines]
        """
        lines = 20
        log_filename = "discord.log"

        def parse_arg(arg):
            nonlocal lines, log_filename
            if isinstance(arg, int):
                lines = arg
            elif isinstance(arg, str):
                if arg.isdigit():
                    lines = int(arg)
                else:
                    val = arg.lower()
                    if val in ["ai", "chatbot", "ai.log"]:
                        log_filename = "ai.log"
                    elif val in ["discord", "bot", "discord.log"]:
                        log_filename = "discord.log"

        parse_arg(arg1)
        if arg2 is not None:
            parse_arg(arg2)

        view = LogPaginationView(self.bot, log_filename=log_filename, page_size=lines)
        await view.load_logs()
        view.current_page = view.total_pages - 1
        view.update_buttons()
        await ctx.reply(content=view.get_page_content(), view=view)


    @cmds.command(name='set_premium', aliases=['setpremium', 'grant_premium'])
    @cmds.is_owner()
    async def set_premium(self, ctx: Context, guild: typing.Optional[discord.Guild] = None, status: bool = True):
        """Grants or revokes Premium status for a server (Owner only).
        
        Usage:
            =set_premium [guild_id] [true/false]
        """
        target_guild = guild or ctx.guild
        if not target_guild:
            await send_warning(ctx, "Server Required", "Please specify a valid guild ID or run this command inside a server.")
            return

        val = 1 if status else 0
        await self.bot.db_manager.update_guild_setting(target_guild.id, "is_premium", val)
        self.bot.settings_cache.setdefault(target_guild.id, {})["is_premium"] = val
        state_str = "👑 **Premium Plan** (1M tokens/wk, 30 msgs context, vision, 7 images/wk [30/mo])" if status else "🆓 **Free Snapshot Plan**"
        await send_confirmation(
            ctx,
            "Server Tier Updated",
            f"Updated **{target_guild.name}** (`{target_guild.id}`) to {state_str}.",
            thumbnail_url=target_guild.icon.url if target_guild.icon else None
        )

    @cmds.hybrid_command(name="inspect", aliases=["audituser", "userlookup", "whois", "userdossier"])
    @cmds.is_owner()
    @discord.app_commands.describe(user="The user ID or mention to audit")
    async def inspect_user(self, ctx: Context, user: str):
        """[Owner Only] Deep intelligence audit on any user across telemetry, commands, and AI queries."""
        await ctx.defer(ephemeral=True)
        # Parse user ID from string or mention
        clean_uid = user.strip("<@!>")
        try:
            target_uid = int(clean_uid)
        except ValueError:
            await send_warning(ctx, "Invalid User", "Invalid user ID or mention provided.", ephemeral=True)
            return

        from cogs.analytics.views import AnalyticsLayoutView
        view = AnalyticsLayoutView(self.bot)
        await view.render_user_dossier(target_uid)
        await ctx.reply(view=view, ephemeral=True)

    @cmds.hybrid_command(name="blacklist", aliases=["blockuser", "banuser"])
    @cmds.is_owner()
    @discord.app_commands.describe(user="The user to blacklist", reason="Reason for the ban")
    async def blacklist_command(self, ctx: Context, user: str, *, reason: str = "Violated bot usage policies"):
        """[Owner Only] Globally blocks a user from using any bot commands or AI interactions."""
        await ctx.defer(ephemeral=True)
        clean_uid = user.strip("<@!>")
        try:
            target_uid = int(clean_uid)
        except ValueError:
            await send_warning(ctx, "Invalid User", "Invalid user ID or mention.", ephemeral=True)
            return

        await self.bot.db_manager.blacklist_user(target_uid, reason=reason, admin_id=ctx.author.id)
        self.bot.blacklist_cache.add(target_uid)
        target_user = self.bot.get_user(target_uid)
        thumb = target_user.display_avatar.url if target_user else None
        await send_warning(
            ctx,
            "User Blacklisted",
            f"User `{target_uid}` is now globally blacklisted.",
            footer=f"Reason: {reason}",
            thumbnail_url=thumb,
            ephemeral=True
        )

    @cmds.hybrid_command(name="unblacklist", aliases=["unblockuser", "unbanuser"])
    @cmds.is_owner()
    @discord.app_commands.describe(user="The user to unblacklist")
    async def unblacklist_command(self, ctx: Context, user: str):
        """[Owner Only] Removes a user from the global blacklist."""
        await ctx.defer(ephemeral=True)
        clean_uid = user.strip("<@!>")
        try:
            target_uid = int(clean_uid)
        except ValueError:
            await send_warning(ctx, "Invalid User", "Invalid user ID or mention.", ephemeral=True)
            return

        await self.bot.db_manager.unblacklist_user(target_uid)
        self.bot.blacklist_cache.discard(target_uid)
        target_user = self.bot.get_user(target_uid)
        thumb = target_user.display_avatar.url if target_user else None
        await send_confirmation(
            ctx,
            "User Unblacklisted",
            f"User `{target_uid}` has been removed from the global blacklist.",
            thumbnail_url=thumb,
            ephemeral=True
        )

    @cmds.hybrid_command(name="inspectguild", aliases=["auditguild", "guildlookup", "guilddossier", "whoisguild"])
    @cmds.is_owner()
    @discord.app_commands.describe(guild="The server ID to audit (or 'this' for current server)")
    async def inspect_guild(self, ctx: Context, guild: str = "this"):
        """[Owner Only] Deep intelligence audit on any server across settings, telemetry, commands, and AI queries."""
        await ctx.defer(ephemeral=True)
        if guild == "this" and ctx.guild:
            target_gid = ctx.guild.id
        else:
            clean_gid = guild.strip("<@!&#> ")
            try:
                target_gid = int(clean_gid)
            except ValueError:
                await ctx.reply("❌ Invalid server ID provided.", ephemeral=True)
                return

        from cogs.analytics.views import AnalyticsLayoutView
        view = AnalyticsLayoutView(self.bot)
        await view.render_server_dossier(target_gid)
        await ctx.reply(view=view, ephemeral=True)

    @cmds.hybrid_command(name="givemoney", aliases=["grantmoney", "addmoney", "givecoins"])
    @cmds.is_owner()
    @discord.app_commands.describe(user="The user to send money to", amount="Amount of euros to grant")
    async def give_money(self, ctx: Context, user: discord.User, amount: float):
        """[Owner Only] Grants money to any user's economy wallet."""
        await ctx.defer(ephemeral=True)
        if amount <= 0:
            await send_warning(ctx, "Invalid Amount", "Amount must be greater than 0.", ephemeral=True)
            return

        new_bal = await self.bot.db_manager.adjust_user_balance(user.id, amount)
        await send_confirmation(
            ctx,
            "Balance Granted",
            f"Granted **+{amount:,.2f}€** to {user.mention}.",
            footer=f"New Balance: {new_bal:,.2f}€",
            thumbnail_url=user.display_avatar.url,
            ephemeral=True
        )

    @cmds.hybrid_command(name="testwelcome")
    @cmds.is_owner()
    async def test_welcome(self, ctx: Context):
        """[Owner Only] Previews the guild join welcome card."""
        from cogs.utils.cards import build_guild_welcome_card
        view = build_guild_welcome_card(self.bot)
        await ctx.reply(view=view, ephemeral=True)


class LogFileSelect(discord.ui.Select):
    def __init__(self, current_file):
        options = [
            discord.SelectOption(
                label="discord.log", 
                value="discord.log", 
                description="Main bot system logs",
                emoji=Emojis.ROBOT
            ),
            discord.SelectOption(
                label="ai.log", 
                value="ai.log", 
                description="AI chatbot fallback & conversation logs",
                emoji=Emojis.BRAIN
            ),
        ]
        super().__init__(placeholder="Select log file...", min_values=1, max_values=1, options=options)
        for option in self.options:
            if option.value == current_file:
                option.default = True

    async def callback(self, interaction: discord.Interaction):
        view: LogPaginationView = self.view
        view.log_filename = self.values[0]
        await view.load_logs()
        view.current_page = view.total_pages - 1
        view.update_select_menu()
        view.update_buttons()
        await interaction.response.edit_message(content=view.get_page_content(), view=view)


class LogPaginationView(discord.ui.View):
    def __init__(self, bot, log_filename="discord.log", lines_history=1000, page_size=20, timeout=120):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.log_filename = log_filename
        self.lines_history = lines_history
        self.page_size = page_size
        self.lines = []
        self.current_page = 0
        self.total_pages = 0
        
        # Select menu component
        self.select_menu = None
        self.update_select_menu()
        
        # Pagination buttons
        self.older_btn = discord.ui.Button(label="◀ Older", style=discord.ButtonStyle.gray, row=1)
        self.older_btn.callback = self.older_callback
        
        self.refresh_btn = discord.ui.Button(emoji=Emojis.RELOAD, label="Refresh", style=discord.ButtonStyle.blurple, row=1)
        self.refresh_btn.callback = self.refresh_callback
        
        self.newer_btn = discord.ui.Button(label="Newer ▶", style=discord.ButtonStyle.gray, row=1)
        self.newer_btn.callback = self.newer_callback
        
        self.add_item(self.older_btn)
        self.add_item(self.refresh_btn)
        self.add_item(self.newer_btn)

    def update_select_menu(self):
        if self.select_menu:
            self.remove_item(self.select_menu)
        self.select_menu = LogFileSelect(self.log_filename)
        self.select_menu.row = 0
        self.add_item(self.select_menu)

    async def load_logs(self):
        def _read_file_sync(filename, history_limit):
            if not os.path.exists(filename):
                return [f"Log file '{filename}' not found."]
            try:
                with open(filename, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
                    return all_lines[-history_limit:]
            except Exception as e:
                return [f"Error reading log file: {e}"]

        self.lines = await asyncio.to_thread(_read_file_sync, self.log_filename, self.lines_history)
        
        self.total_pages = (len(self.lines) + self.page_size - 1) // self.page_size
        if self.total_pages == 0:
            self.total_pages = 1

    def get_page_content(self):
        start = self.current_page * self.page_size
        end = start + self.page_size
        page_lines = self.lines[start:end]
        
        content = "".join(page_lines)
        if len(content) > 1900:
            content = content[-1900:] + "\n[Truncated due to character limit]"
            
        return f"📄 **{self.log_filename} (Page {self.current_page + 1}/{self.total_pages})**\n```log\n{content}\n```"

    def update_buttons(self):
        self.older_btn.disabled = self.current_page <= 0
        self.newer_btn.disabled = self.current_page >= self.total_pages - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(f"{Emojis.ERROR} This menu is developer-only.", ephemeral=True)
            return False
        return True

    async def older_callback(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(content=self.get_page_content(), view=self)

    async def refresh_callback(self, interaction: discord.Interaction):
        await self.load_logs()
        if self.current_page >= self.total_pages:
            self.current_page = self.total_pages - 1
        if self.current_page < 0:
            self.current_page = 0
        self.update_buttons()
        await interaction.response.edit_message(content=self.get_page_content(), view=self)

    async def newer_callback(self, interaction: discord.Interaction):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(content=self.get_page_content(), view=self)


async def setup(bot):
    await bot.add_cog(Dev(bot))
