from discord.ext import commands as cmds
from discord.ext.commands import Context, GuildConverter

import discord
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

        await ctx.reply("Yes I'm alive, broski. <:CC_yellow_look:1440119405991166186>")


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
            await ctx.message.add_reaction('❌')
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('✅')


    @extensions.command(name='load')
    @cmds.is_owner()
    async def extensions_load(self, ctx: Context, *, extension: str):
        if extension == 'all':
            await self.load_all(ctx)
            return
        
        try:
            await self.bot.load_extension("cogs."+extension)
        except cmds.ExtensionError as e:
            await ctx.message.add_reaction('❌')
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('✅')
        

    @extensions.command(name='unload')
    @cmds.is_owner()
    async def extensions_unload(self, ctx: Context, *, extension: str):
        if extension == 'all':
            await self.unload_all(ctx)
            return

        try:
            await self.bot.unload_extension("cogs."+extension)
        except cmds.ExtensionError as e:
            await ctx.message.add_reaction('❌')
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('✅')
        

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
            message_lines = [f"✅ Reloaded: {', '.join(reloaded) if reloaded else 'None'}"]
            message_lines.append("❌ Failed:")
            for failure in failed:
                message_lines.append(f"  - {failure}")
            await ctx.message.add_reaction('❌')
            await ctx.reply("\n".join(message_lines))
            
        else:
            await ctx.message.add_reaction('✅')
    

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
            message_lines = [f"✅ Loaded: {', '.join(loaded) if loaded else 'None'}"]
            message_lines.append("❌ Failed:")
            for failure in failed:
                message_lines.append(f"  - {failure}")
            await ctx.message.add_reaction('❌')
            await ctx.reply("\n".join(message_lines))
        else:
            await ctx.message.add_reaction('✅')
    

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
            message_lines = [f"✅ Unloaded: {', '.join(unloaded) if unloaded else 'None'}"]
            message_lines.append("❌ Failed:")
            for failure in failed:
                message_lines.append(f"  - {failure}")
            await ctx.message.add_reaction('❌')
            await ctx.reply("\n".join(message_lines))
        else:
            await ctx.message.add_reaction('✅')



    @cmds.command(name='update')
    @cmds.is_owner()
    async def update(self, ctx):
        """Runs the update.sh script to update the bot."""
        await ctx.message.add_reaction('🔄')
        
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
        await ctx.message.add_reaction('🔄')
        
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
            await ctx.message.add_reaction('❌')
            return
        
        try:
            self.bot.tree.remove_command(command, guild=guild)
            await ctx.message.add_reaction('✅')
        except Exception as e:
            logger.error(f"Remove command failed: {e}")
            await ctx.message.add_reaction('❌')
        
    
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
            await ctx.message.add_reaction('❌')
            return

        try:
            self.bot.tree.clear_commands(guild=guild)
            await ctx.message.add_reaction('✅')
        except Exception as e:
            logger.error(f"Clear commands failed: {e}")
            await ctx.message.add_reaction('❌')


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
            await ctx.message.add_reaction('❌')
            return
        
        try: 
            await self.bot.tree.sync(guild=guild)
            await ctx.message.add_reaction('✅')
        except Exception as e:
            logger.error(f"Sync command failed: {e}")
            await ctx.message.add_reaction('❌')
            
    @cmds.command(name='logs')
    @cmds.is_owner()
    async def logs(self, ctx: Context, lines: int = 20):
        """Displays the latest logs in an interactive paginated container."""
        view = LogPaginationView(self.bot, page_size=lines)
        await ctx.reply(content=view.get_page_content(), view=view)


class LogPaginationView(discord.ui.View):
    def __init__(self, bot, lines_history=1000, page_size=20, timeout=120):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.lines_history = lines_history
        self.page_size = page_size
        self.lines = []
        self.current_page = 0
        self.total_pages = 0
        
        self.load_logs()
        self.current_page = self.total_pages - 1
        
        self.older_btn = discord.ui.Button(label="◀ Older", style=discord.ButtonStyle.gray)
        self.older_btn.callback = self.older_callback
        
        self.refresh_btn = discord.ui.Button(label="🔄 Refresh", style=discord.ButtonStyle.blurple)
        self.refresh_btn.callback = self.refresh_callback
        
        self.newer_btn = discord.ui.Button(label="Newer ▶", style=discord.ButtonStyle.gray)
        self.newer_btn.callback = self.newer_callback
        
        self.add_item(self.older_btn)
        self.add_item(self.refresh_btn)
        self.add_item(self.newer_btn)
        
        self.update_buttons()

    def load_logs(self):
        if not os.path.exists("discord.log"):
            self.lines = ["Log file 'discord.log' not found."]
        else:
            try:
                with open("discord.log", "r", encoding="utf-8", errors="replace") as f:
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
            
        return f"📄 **discord.log (Page {self.current_page + 1}/{self.total_pages})**\n```log\n{content}\n```"

    def update_buttons(self):
        self.older_btn.disabled = self.current_page <= 0
        self.newer_btn.disabled = self.current_page >= self.total_pages - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("❌ This menu is developer-only.", ephemeral=True)
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