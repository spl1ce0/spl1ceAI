from discord.ext import commands
from discord.ext.commands import Context, GuildConverter

import logging
import subprocess
import os


logger = logging.getLogger(__name__)


class Dev(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    @commands.hybrid_command(name="are_you_alive", aliases=["alive", "are_u_alive", "areualive"])
    async def alive(self, ctx):
        """Tells if the bot is alive."""

        await ctx.reply("Yes I'm alive, broski. <:CC_yellow_look:1440119405991166186>")


    @commands.group(name='sync')
    @commands.is_owner()
    @commands.guild_only()
    async def sync(self, ctx: Context, guild: str) -> None:
        """Syncs the commands within the given guild"""
        if guild:
            guild = GuildConverter().convert(guild)
        else:
            await ctx.message.add_reaction('❌')
            await ctx.reply('Please provide a guild.')
            return

        commands = await self.bot.tree.sync(guild=guild)
        await ctx.message.add_reaction('✅')
        await ctx.reply(f'Successfully synced {len(commands)} commands')


    @sync.command(name='local')
    @commands.is_owner()
    @commands.guild_only()
    async def sync_local(self, ctx: Context):
        """Syncs the commands locally"""
        commands = await self.bot.tree.sync(guild=ctx.guild)
        await ctx.message.add_reaction('✅')
        await ctx.reply(f'Synced {len(commands)} commands locally.')


    @sync.command(name='global')
    @commands.is_owner()
    async def sync_global(self, ctx: Context):
        """Syncs the commands globally"""
        commands = await self.bot.tree.sync(guild=None)
        await ctx.message.add_reaction('✅')
        await ctx.reply(f'Synced {len(commands)} commands globally.')




    @commands.group(name='reload')
    @commands.is_owner()
    async def reload(self, ctx: Context, *, extension: str):
        """Reloads an extension."""
        try:
            await self.bot.reload_extension("cogs."+extension)
        except commands.ExtensionError as e:
            await ctx.message.add_reaction('❌')
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('✅')


    @commands.group(name='load')
    @commands.is_owner()
    async def load(self, ctx: Context, *, extension: str):
        """Loads an extension."""
        try:
            await self.bot.load_extension("cogs."+extension)
        except commands.ExtensionError as e:
            await ctx.message.add_reaction('❌')
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('✅')
        

    @commands.group(name='unload')
    @commands.is_owner()
    async def unload(self, ctx: Context, *, extension: str):
        """Unloads an extension."""
        try:
            await self.bot.unload_extension("cogs."+extension)
        except commands.ExtensionError as e:
            await ctx.message.add_reaction('❌')
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('✅')
        


    @reload.command(name='all')
    @commands.is_owner()
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
    

    @load.command(name='all')
    @commands.is_owner()
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
    

    @unload.command(name='all')
    @commands.is_owner()
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



    @commands.command(name='update')
    @commands.is_owner()
    async def update(self, ctx):
        """Runs the update.sh script to update the bot."""
        await ctx.reply("Update initiated.")
        subprocess.run(['./update.sh'])



    @commands.group(name='command_remove')
    @commands.is_owner()
    async def command_remove(self, ctx, command: str, *, guild: str = None):
        if guild:
            if guild == 'global':
                guild = None
            else:
                guild = GuildConverter(guild)
        else:
            guild = ctx.guild

        command = self.bot.tree.remove_command(name=command, guild=guild)
        if command:
            await ctx.message.add_reaction('✅')
        else:
            await ctx.message.add_reaction('❌')

    
    @command_remove.command(name='all')
    @commands.is_owner()
    async def command_remove_all(self, ctx, *, guild: str = None):
        if guild:
            if guild == 'global':
                guild = None
            else:
                guild = GuildConverter(guild)
        else:
            guild = ctx.guild

        try:
            self.bot.tree.clear_commands(guild=guild)
            await ctx.message.add_reaction('✅')
        except Exception as e:
            logging.error(e)
            await ctx.message.add_reaction('❌')



async def setup(bot):
    await bot.add_cog(Dev(bot))
