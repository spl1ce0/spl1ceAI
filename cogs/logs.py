import logging
import datetime
import discord
from discord import ui
from discord.ext import commands
from cogs.utils.constants import DefaultSettings

logger = logging.getLogger(__name__)


class LogLayoutView(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)


class MessageDeleteContainer(ui.Container):
    def __init__(self, message: discord.Message):
        super().__init__()
        self.accent_color = discord.Color.red()
        
        title = ui.TextDisplay("### 🗑️ Message Deleted")
        self.add_item(title)
        self.add_item(ui.Separator())
        
        details = (
            f"**User:** {message.author.mention} (`{message.author.id}`)\n"
            f"**Channel:** {message.channel.mention}"
        )
        self.add_item(ui.TextDisplay(details))
        self.add_item(ui.Separator())
        
        if message.content:
            content_display = f"**Deleted Content:**\n> {message.clean_content}"
            self.add_item(ui.TextDisplay(content_display))
        else:
            self.add_item(ui.TextDisplay("**Deleted Content:** *(No text content)*"))
            
        if message.attachments:
            files = ", ".join(f"`{a.filename}`" for a in message.attachments)
            self.add_item(ui.TextDisplay(f"-# 📂 **Attachments:** {files}"))
            
        self.add_item(ui.Separator())
        
        footer = f"-# Message ID: {message.id} | Deleted <t:{int(datetime.datetime.now().timestamp())}:R>"
        self.add_item(ui.TextDisplay(footer))


class MessageDeleteUncachedContainer(ui.Container):
    def __init__(self, payload: discord.RawMessageDeleteEvent, channel: discord.TextChannel):
        super().__init__()
        self.accent_color = discord.Color.red()
        
        title = ui.TextDisplay("### 🗑️ Message Deleted (Uncached)")
        self.add_item(title)
        self.add_item(ui.Separator())
        
        details = (
            f"**Channel:** {channel.mention}\n"
            f"-# Content is unavailable because the message was sent before the bot started."
        )
        self.add_item(ui.TextDisplay(details))
        self.add_item(ui.Separator())
        
        footer = f"-# Message ID: {payload.message_id} | Deleted <t:{int(datetime.datetime.now().timestamp())}:R>"
        self.add_item(ui.TextDisplay(footer))


class MessageEditContainer(ui.Container):
    def __init__(self, before: discord.Message, after: discord.Message):
        super().__init__()
        self.accent_color = discord.Color.yellow()
        
        title = ui.TextDisplay("### ✏️ Message Edited")
        self.add_item(title)
        self.add_item(ui.Separator())
        
        details = (
            f"**User:** {before.author.mention} (`{before.author.id}`)\n"
            f"**Channel:** {before.channel.mention}"
        )
        details_display = ui.TextDisplay(details)
        jump_button = ui.Button(emoji="🔗", url=after.jump_url, style=discord.ButtonStyle.link)
        
        details_section = ui.Section(details_display, accessory=jump_button)
        self.add_item(details_section)
        self.add_item(ui.Separator())
        
        before_content = before.clean_content if before.content else "*(No text content)*"
        after_content = after.clean_content if after.content else "*(No text content)*"
        
        self.add_item(ui.TextDisplay(f"**Before:**\n> {before_content}"))
        self.add_item(ui.TextDisplay(f"**After:**\n> {after_content}"))
        
        self.add_item(ui.Separator())
        
        footer = f"-# Message ID: {before.id} | Edited <t:{int(datetime.datetime.now().timestamp())}:R>"
        self.add_item(ui.TextDisplay(footer))


class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if not payload.guild_id:
            return
            
        log_channel_id = self.bot.settings_cache.get(payload.guild_id, {}).get("log_channel")
        if not log_channel_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return

        channel = guild.get_channel(payload.channel_id)
        if not channel:
            return

        message = payload.cached_message
        if message:
            if message.author.bot:
                return
            view = LogLayoutView()
            container = MessageDeleteContainer(message)
            view.add_item(container)
            try:
                await log_channel.send(view=view)
            except Exception as e:
                logger.error(f"Failed to send delete log: {e}")
        else:
            view = LogLayoutView()
            container = MessageDeleteUncachedContainer(payload, channel)
            view.add_item(container)
            try:
                await log_channel.send(view=view)
            except Exception as e:
                logger.error(f"Failed to send uncached delete log: {e}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild:
            return

        if before.author.bot:
            return

        if before.content == after.content:
            return

        log_channel_id = self.bot.settings_cache.get(before.guild.id, {}).get("log_channel")
        if not log_channel_id:
            return

        log_channel = before.guild.get_channel(log_channel_id)
        if not log_channel:
            return

        view = LogLayoutView()
        container = MessageEditContainer(before, after)
        view.add_item(container)
        try:
            await log_channel.send(view=view)
        except Exception as e:
            logger.error(f"Failed to send edit log: {e}")


async def setup(bot):
    await bot.add_cog(Logs(bot))
