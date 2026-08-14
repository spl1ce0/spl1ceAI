import os
import re
import tempfile
import shutil
import asyncio
import logging
import yt_dlp
import discord
from discord.ext import commands
from discord import ui
from cogs.utils.constants import Emojis, ErrorMessages

logger = logging.getLogger(__name__)


class ToolLayoutView(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)


class AvatarContainer(ui.Container):
    def __init__(self, member: discord.Member):
        super().__init__()
        self.accent_color = discord.Color.blurple()
        
        self.add_item(ui.TextDisplay("### 👤 User Avatar"))
        self.add_item(ui.Separator())
        
        details_text = (
            f"**User:** {member.mention}\n"
            f"**Username:** `{member.name}`\n"
            f"**ID:** `{member.id}`"
        )
        details_display = ui.TextDisplay(details_text)
        avatar_thumbnail = ui.Thumbnail(media=member.display_avatar.url)
        
        avatar_section = ui.Section(details_display, accessory=avatar_thumbnail)
        self.add_item(avatar_section)
        self.add_item(ui.Separator())
        
        action_row = ui.ActionRow()
        link_button = ui.Button(label="Open High-Res Avatar", url=member.display_avatar.url, style=discord.ButtonStyle.link)
        action_row.add_item(link_button)
        self.add_item(action_row)


class Tools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.max_duration_seconds = 15 * 60  # 15 minutes

    @commands.hybrid_command(name="ytmp3", aliases=["mp3", "download"])
    @commands.cooldown(1, 10, commands.BucketType.user)  # Prevent spamming
    async def ytmp3(self, ctx, url: str):
        """Converts a YouTube video to an MP3 audio file and sends it to you."""
        await ctx.defer()

        # Loose validation to support all YouTube subdomains (m., music., etc.) and share links
        if not ("youtube.com" in url.lower() or "youtu.be" in url.lower()):
            await ctx.reply(ErrorMessages.YT_INVALID_URL)
            return

        # Common yt-dlp options for metadata extraction
        ydl_opts_info = {
            'extract_flat': True,
            'skip_download': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, url, download=False)
                
            duration = info.get('duration')
            if duration and duration > self.max_duration_seconds:
                await ctx.reply(ErrorMessages.YT_TOO_LONG)
                return
        except Exception as e:
            logger.error(f"Failed to extract video info: {e}")
            await ctx.reply(ErrorMessages.YT_INVALID_URL)
            return

        # Prepare temporary directory for download
        tmpdir = await asyncio.to_thread(tempfile.mkdtemp)
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }

        try:
            # Download and convert
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await asyncio.to_thread(ydl.download, [url])
            
            files = os.listdir(tmpdir)
            mp3_file = None
            for f in files:
                if f.endswith('.mp3'):
                    mp3_file = os.path.join(tmpdir, f)
                    break

            if not mp3_file or not os.path.exists(mp3_file):
                raise FileNotFoundError("MP3 file not found after conversion.")

            # Check filesize to make sure it is under the Discord limit
            file_size = os.path.getsize(mp3_file)
            max_size = 25 * 1024 * 1024  # 25 MB
            if file_size > max_size:
                await ctx.reply(f"{Emojis.WARNING} The converted audio file is too large (`{file_size / (1024*1024):.1f}MB`) to upload to Discord.")
                return

            with open(mp3_file, 'rb') as f:
                discord_file = discord.File(f, filename=os.path.basename(mp3_file))
                await ctx.reply(file=discord_file)

        except Exception as e:
            logger.error(f"Failed to convert YouTube to MP3: {e}")
            await ctx.reply(ErrorMessages.YT_DOWNLOAD_FAILED)
        finally:
            # Cleanup temp directory
            await asyncio.to_thread(shutil.rmtree, tmpdir, ignore_errors=True)

    @commands.hybrid_command(name="avatar", aliases=["av", "pfp"])
    @commands.guild_only()
    async def avatar(self, ctx, member: discord.Member = None):
        """Displays the avatar of a user in a clean V2 system card."""
        member = member or ctx.author
        
        view = ToolLayoutView()
        container = AvatarContainer(member)
        view.add_item(container)
        
        await ctx.reply(view=view)

async def setup(bot):
    await bot.add_cog(Tools(bot))
