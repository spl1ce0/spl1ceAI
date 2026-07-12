from discord.ext import commands as cmds
from discord.ext.commands import Context, GuildConverter

import discord
from cogs.utils.constants import Emojis
from discord import ui
import typing
from typing import Optional
import logging
import subprocess
import os
import asyncio
import time
import json


logger = logging.getLogger(__name__)


class Dev(cmds.Cog):

    def __init__(self, bot):
        self.bot = bot


    @cmds.hybrid_command(name="are_you_alive", aliases=["alive", "are_u_alive", "areualive"])
    async def alive(self, ctx):
        """Tells if the bot is alive."""

        await ctx.reply(f"Yes I'm alive, broski. {Emojis.YELLOW_LOOK}")


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



    @cmds.command(name='update')
    @cmds.is_owner()
    async def update(self, ctx):
        """Runs the update.sh script to update the bot."""
        await ctx.message.add_reaction(Emojis.RELOAD)
        
        data = {
            'channel_id': ctx.channel.id,
            'message_id': ctx.message.id,
            'start_time': time.time()
        }
        await self.bot.db.execute(
            "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
            ('restart_info', json.dumps(data))
        )
        await self.bot.db.commit()
            
        subprocess.run(['./update.sh'])


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
        await self.bot.db.execute(
            "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
            ('restart_info', json.dumps(data))
        )
        await self.bot.db.commit()
            
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
        await ctx.reply(content=view.get_page_content(), view=view)


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
                emoji="🧠"
            ),
        ]
        super().__init__(placeholder="Select log file...", min_values=1, max_values=1, options=options)
        for option in self.options:
            if option.value == current_file:
                option.default = True

    async def callback(self, interaction: discord.Interaction):
        view: LogPaginationView = self.view
        view.log_filename = self.values[0]
        view.load_logs()
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
        
        self.load_logs()
        self.current_page = self.total_pages - 1
        
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
        
        self.update_buttons()

    def update_select_menu(self):
        if self.select_menu:
            self.remove_item(self.select_menu)
        self.select_menu = LogFileSelect(self.log_filename)
        self.select_menu.row = 0
        self.add_item(self.select_menu)

    def load_logs(self):
        if not os.path.exists(self.log_filename):
            self.lines = [f"Log file '{self.log_filename}' not found."]
        else:
            try:
                with open(self.log_filename, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
                    self.lines = all_lines[-self.lines_history:]
            except Exception as e:
                self.lines = [f"Error reading log file: {e}"]
        
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
        self.load_logs()
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