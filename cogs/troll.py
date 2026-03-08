
import discord
from discord.ext import commands
from discord.ext.commands import MemberConverter
from discord import ui

import logging


logger = logging.getLogger(__name__)


class FakeBanContainer(ui.Container):
    
    BANNED_EMOJI = "<a:sAI_banned:1478422889668542545>"

    def __init__(self, user: discord.Member, reason: str):
        super().__init__()
        self.user = user
        self.reason = reason
        self._make_container()


    def _make_container(self):
        banDisplay = ui.TextDisplay(f"### {self.BANNED_EMOJI} {self.user.mention} has been banned.\n")
        self.add_item(banDisplay)

        reasonDisplay = ui.TextDisplay(f"- **Reason:** {self.reason}")
        self.add_item(reasonDisplay)
        
        self.accent_color = discord.Color.red()


class Troll(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    @commands.hybrid_command(name="ban", aliases=[])
    async def fakeban(self, ctx, member, *, reason):
        """Sends a fake ban message."""

        try:
            user = await MemberConverter().convert(ctx, member)
        except commands.MemberNotFound:  
            await ctx.reply("User not found.\n-# Mention the user or provide their ID.", ephemeral=True)  
            return
        
        ban_container = FakeBanContainer(user, reason)
        
        view = ui.LayoutView()
        view.add_item(ban_container)

        await ctx.reply(view=view)


async def setup(bot):
    await bot.add_cog(Troll(bot))
