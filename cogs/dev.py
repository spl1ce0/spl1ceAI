from discord.ext import commands as cmds
from discord.ext.commands import Context, GuildConverter

import discord
import typing
from typing import Optional
import logging
import subprocess
import os


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
        await ctx.reply("Update initiated.")
        subprocess.run(['./update.sh'])



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


async def setup(bot):
    await bot.add_cog(Dev(bot))