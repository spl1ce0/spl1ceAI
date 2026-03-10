import discord
from discord.ext import commands
from discord.ext.commands import Context

from typing import Optional
import logging


logger = logging.getLogger(__name__)


class Dev(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    @commands.hybrid_command(name="are_you_alive", aliases=["alive", "are_u_alive", "areualive"])
    async def alive(self, ctx):
        """Tells if the bot is alive."""

        await ctx.reply("Yes I'm alive, broski. <:CC_yellow_look:1440119405991166186>")


    @commands.command(hidden=True)
    @commands.is_owner()
    async def load(self, ctx, *, extension: str):
        """Loads an Extension."""
        try:
            await self.bot.load_extension("cogs."+extension)
        except commands.ExtensionError as e:
            await ctx.message.add_reaction('❌')
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('✅')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def unload(self, ctx, *, extension: str):
        """Unloads an Extension."""
        try:
            await self.bot.unload_extension("cogs."+extension)
        except commands.ExtensionError as e:
            await ctx.message.add_reaction('❌')
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('✅')


    @commands.command(name="reload", aliases=['r'], hidden=True, invoke_without_command=True)
    @commands.is_owner()
    async def reload(self, ctx, *, extension: str):
        """Reloads an Extension."""
        
        try:
            await self.bot.reload_extension("cogs."+extension)
        except commands.ExtensionError as e:
            await ctx.message.add_reaction('❌')
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction('✅')



    @commands.group(name='sync_commands')
    @commands.is_owner()
    @commands.guild_only()
    async def sync(self, ctx: Context, guild_id: Optional[int], copy: bool = False) -> None:
        """Syncs the commands within the given guild"""

        if guild_id:
            guild = discord.Object(id=guild_id)
        else:
            guild = ctx.guild

        if copy:
            self.bot.tree.copy_global_to(guild=guild)

        commands = await self.bot.tree.sync(guild=guild)
        await ctx.reply(f'Successfully synced {len(commands)} commands')



    @sync.command(name='global')
    @commands.is_owner()
    async def sync_global(self, ctx: Context):
        """Syncs the commands globally"""


        commands = await self.bot.tree.sync(guild=None)
        await ctx.reply(f'Successfully synced {len(commands)} commands globally')

    
    @commands.command(name='clear_commands')
    @commands.guild_only()
    @commands.is_owner()
    async def clear_commands(self, ctx: Context, guild_id: int = None) -> None:
        

        if guild_id:
            guild = discord.Object(id=guild_id)
        else:
            guild = ctx.guild

        self.bot.tree.clear_commands(guild=guild)
        
        await ctx.reply(f'Successfully cleared all commands')



async def setup(bot):
    await bot.add_cog(Dev(bot))
