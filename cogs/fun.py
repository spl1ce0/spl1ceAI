import discord
from discord.ext import commands
import yt_dlp
import asyncio
import random
import logging
import tempfile
import os
import io
import re
from PIL import Image, ImageDraw, ImageFont
import numpy as np
try:
    from pilmoji import Pilmoji
    HAS_PILMOJI = True
except ImportError:
    HAS_PILMOJI = False
from discord import ui
from discord.ext.commands import MemberConverter
from cogs.utils.constants import Emojis

logger = logging.getLogger(__name__)



class FakeBanContainer(ui.Container):
    
    BANNED_EMOJI = Emojis.BANNED

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



class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sealion_collection_url = "https://www.tiktok.com/@lukysgaming/collection/seelion-7603137602169932566"
        self.anoomals_collection_url = "https://www.tiktok.com/@lukysgaming/collection/anoomols-7629020086997371670"
        self.common_ydl_opts = {
            'no_warnings': True,
            'quiet': True,
            'extractor_args': {
                'tiktok': {
                    'api_hostname': 'api22-normal-c-useast2a.tiktokv.com'
                }
            }
        }

    async def _send_random_tiktok(self, ctx, collection_url: str, command_name: str, emoji: str):
        await ctx.defer()
        
        typing_context = ctx.typing() if ctx.interaction is None else asyncio.Lock()
        
        async with typing_context:
            try:
                ydl_opts_info = {
                    **self.common_ydl_opts,
                    'extract_flat': True,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                    info = await asyncio.to_thread(ydl.extract_info, collection_url, download=False)
                    
                if 'entries' not in info:
                    return await ctx.reply("Could not find any videos in the collection! 😢")
                
                urls = [entry.get('url') or f"https://www.tiktok.com/video/{entry['id']}" for entry in info['entries']]
                random.shuffle(urls)

                MAX_ATTEMPTS = min(len(urls), 3)
                last_error = ""

                for attempt in range(MAX_ATTEMPTS):
                    video_url = urls[attempt]
                    
                    try:
                        with yt_dlp.YoutubeDL(self.common_ydl_opts) as ydl:
                            real_info = await asyncio.to_thread(ydl.extract_info, video_url, download=False)
                            duration = real_info.get('duration')
                        
                        with tempfile.TemporaryDirectory() as tmpdir:
                            target_mb = 7
                            audio_bitrate_kbps = 96
                            
                            if duration:
                                total_bits = target_mb * 8 * 1024 * 1024
                                audio_bits = audio_bitrate_kbps * 1000 * duration
                                video_bitrate_kbps = max(int((total_bits - audio_bits) / duration / 1000), 100)
                            else:
                                video_bitrate_kbps = 1000 

                            ydl_opts_temp = {
                                **self.common_ydl_opts,
                                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                                'merge_output_format': 'mp4',
                                'outtmpl': f'{tmpdir}/video_%(id)s.%(ext)s',
                                'postprocessor_args': {
                                    'ffmpeg': [
                                        '-c:v', 'libx264',
                                        '-profile:v', 'baseline',   
                                        '-level', '3.0',
                                        '-pix_fmt', 'yuv420p',
                                        '-r', '30',
                                        '-b:v', f'{video_bitrate_kbps}k',
                                        '-maxrate', f'{video_bitrate_kbps}k',
                                        '-bufsize', f'{video_bitrate_kbps * 2}k',
                                        '-preset', 'veryfast',
                                        '-c:a', 'aac',
                                        '-b:a', f'{audio_bitrate_kbps}k',
                                        '-movflags', '+faststart',
                                    ]
                                },
                            }
                            
                            with yt_dlp.YoutubeDL(ydl_opts_temp) as ydl:
                                await asyncio.to_thread(ydl.download, [video_url])
                            
                            files = [f for f in os.listdir(tmpdir) if not f.endswith('.part')]
                            if not files:
                                continue
                            
                            actual_filename = files[0]
                            video_path = os.path.join(tmpdir, actual_filename)
                            
                            with open(video_path, 'rb') as f:
                                discord_file = discord.File(f, filename="tiktok.mp4")
                                await ctx.reply(file=discord_file)
                                return 
                                
                    except Exception as e:
                        last_error = str(e)
                        logger.warning(f"Attempt {attempt + 1} failed for {video_url}: {e}")
                        continue

                await ctx.reply(f"All {MAX_ATTEMPTS} attempts failed. Last error: `{last_error}`")
                        
            except Exception as e:
                logger.error(f"{command_name.capitalize()} command failed: {e}")
                await ctx.reply(f"Something went wrong while fetching the {command_name}! {emoji}\n`{e}`")

    @commands.hybrid_command(name="sealion")
    async def sealion(self, ctx):
        """Sends a random sealion video from lukysgaming's collection!"""
        await self._send_random_tiktok(
            ctx, 
            self.sealion_collection_url, 
            command_name="sealion", 
            emoji="🦭"
        )

    @commands.hybrid_command(name="anoomals", aliases=["anoomols"])
    async def anoomals(self, ctx):
        """Sends a random anoomals video from lukysgaming's collection!"""
        await self._send_random_tiktok(
            ctx, 
            self.anoomals_collection_url, 
            command_name="anoomals", 
            emoji="🐾"
        )


    
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

    async def _fetch_target_message(self, ctx, query: str = None) -> discord.Message:
        if not query:
            if ctx.message.reference and ctx.message.reference.message_id:
                return await ctx.channel.fetch_message(ctx.message.reference.message_id)
            raise commands.BadArgument("Please provide a message ID, a message link, or reply to a message.")

        # Check if it is a Discord message link
        pattern = r"https?://(?:ptb\.|canary\.)?discord\.com/channels/\d+/(\d+)/(\d+)"
        match = re.match(pattern, query.strip())
        if match:
            channel_id = int(match.group(1))
            message_id = int(match.group(2))
            try:
                channel = ctx.guild.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
                return await channel.fetch_message(message_id)
            except Exception:
                raise commands.BadArgument("Could not fetch the message from the provided link. Make sure the bot has access to that channel.")
        
        # Check if it is a digit string (message ID)
        if query.strip().isdigit():
            try:
                return await ctx.channel.fetch_message(int(query.strip()))
            except Exception:
                raise commands.BadArgument("Could not find a message with that ID in this channel.")
                
        raise commands.BadArgument("Invalid message ID or link format.")

    async def _download_image(self, url: str) -> Image.Image:
        try:
            async with self.bot.web_client.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    return Image.open(io.BytesIO(data))
        except Exception as e:
            logger.warning(f"Failed to download image from {url}: {e}")
        # Return a fallback colored square
        fallback = Image.new("RGB", (600, 600), (45, 125, 220))
        return fallback

    def _generate_quote_card(self, avatar, quote_text, quote_author, reply_author=None, reply_content=None) -> io.BytesIO:
        canvas_w = 1200
        canvas_h = 600
        canvas = Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        # 1. Process Avatar (resize to 600x600, apply horizontal gradient)
        avatar = avatar.convert("RGB").resize((600, 600), Image.Resampling.LANCZOS)
        
        mask_arr = np.zeros((600, 600), dtype=np.uint8)
        for x in range(600):
            if x < 100:
                val = 255
            elif x < 500:
                val = int(255 * (1.0 - (x - 100) / 400.0))
            else:
                val = 0
            mask_arr[:, x] = val
        mask = Image.fromarray(mask_arr, mode="L")
        canvas.paste(avatar, (0, 0), mask)

        # 2. Setup Fonts
        candidates_reg = [
            "/usr/share/fonts/TTF/LiterationSansNerdFont-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
        ]
        candidates_bold = [
            "/usr/share/fonts/TTF/LiterationSansNerdFont-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Bold.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf",
        ]
        candidates_italic = [
            "/usr/share/fonts/TTF/LiterationSansNerdFont-Italic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Oblique.ttf",
            "/usr/share/fonts/TTF/LiberationSans-Italic.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansOblique.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Italic.ttf",
            "C:\\Windows\\Fonts\\ariali.ttf",
        ]

        def get_font(candidates, size):
            for path in candidates:
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    continue
            logger.warning("No scalable system fonts found. Falling back to default Pillow font.")
            return ImageFont.load_default()

        font_reply = get_font(candidates_italic, 20)
        font_quote = get_font(candidates_reg, 34)
        font_author = get_font(candidates_bold, 26)

        # 3. Text wrap helper
        def wrap_text(text, font, max_width):
            words = text.split()
            lines = []
            current_line = []
            for word in words:
                current_line.append(word)
                line_str = " ".join(current_line)
                width = draw.textlength(line_str, font=font)
                if width > max_width:
                    if len(current_line) == 1:
                        lines.append(line_str)
                        current_line = []
                    else:
                        current_line.pop()
                        lines.append(" ".join(current_line))
                        current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))
            return lines

        wrapped_quote_lines = wrap_text(f'“{quote_text}”', font_quote, 500)

        # 4. Calculate total height for centering
        reply_height = 24 if reply_author else 0
        reply_spacing = 15 if reply_author else 0
        
        quote_line_height = int(34 * 1.3)
        quote_height = len(wrapped_quote_lines) * quote_line_height
        
        author_height = 30
        author_spacing = 25
        
        total_height = reply_height + reply_spacing + quote_height + author_spacing + author_height
        
        # Center vertically
        start_y = (canvas_h - total_height) // 2
        text_x = 650

        # 5. Draw
        current_y = start_y

        if HAS_PILMOJI:
            with Pilmoji(canvas) as pilmoji:
                # Draw reply preview if available
                if reply_author:
                    reply_str = f"↱ @{reply_author}: {reply_content}"
                    if len(reply_str) > 55:
                        reply_str = reply_str[:52] + "..."
                    pilmoji.text((text_x, current_y), reply_str, font=font_reply, fill=(160, 160, 160))
                    current_y += reply_height + reply_spacing

                # Draw quote text
                for line in wrapped_quote_lines:
                    pilmoji.text((text_x, current_y), line, font=font_quote, fill=(255, 255, 255))
                    current_y += quote_line_height

                # Draw author info
                current_y += author_spacing
                author_str = f"— {quote_author}"
                pilmoji.text((text_x, current_y), author_str, font=font_author, fill=(240, 240, 240))
        else:
            # Draw reply preview if available
            if reply_author:
                reply_str = f"↱ @{reply_author}: {reply_content}"
                if len(reply_str) > 55:
                    reply_str = reply_str[:52] + "..."
                draw.text((text_x, current_y), reply_str, font=font_reply, fill=(160, 160, 160))
                current_y += reply_height + reply_spacing

            # Draw quote text
            for line in wrapped_quote_lines:
                draw.text((text_x, current_y), line, font=font_quote, fill=(255, 255, 255))
                current_y += quote_line_height

            # Draw author info
            current_y += author_spacing
            author_str = f"— {quote_author}"
            draw.text((text_x, current_y), author_str, font=font_author, fill=(240, 240, 240))

        # Convert to grayscale
        canvas = canvas.convert("L")

        # Save to bytes buffer
        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        buf.seek(0)
        return buf

    @commands.hybrid_command(name="quote")
    async def quote(self, ctx, message_id_or_link: str = None):
        """Generates a beautiful quote card image of a message."""
        await ctx.defer()
        
        try:
            target_msg = await self._fetch_target_message(ctx, message_id_or_link)
        except commands.BadArgument as e:
            await ctx.reply(str(e))
            return
        except Exception as e:
            await ctx.reply(f"An error occurred while fetching the message: `{e}`")
            return

        def restore_custom_emojis(clean_text, raw_text):
            if not clean_text or not raw_text:
                return clean_text
            custom_emojis = re.findall(r'<(a?):([a-zA-Z0-9_]+):([0-9]+)>', raw_text)
            placeholders = {}
            for idx, (animated, name, emoji_id) in enumerate(custom_emojis):
                prefix = "a" if animated else ""
                full_tag = f"<{prefix}:{name}:{emoji_id}>"
                placeholder = f"__CUSTOM_EMOJI_PLACEHOLDER_{idx}__"
                if full_tag in clean_text:
                    clean_text = clean_text.replace(full_tag, placeholder)
                    placeholders[placeholder] = full_tag
            for animated, name, emoji_id in custom_emojis:
                prefix = "a" if animated else ""
                full_tag = f"<{prefix}:{name}:{emoji_id}>"
                clean_text = clean_text.replace(f":{name}:", full_tag)
            for placeholder, full_tag in placeholders.items():
                clean_text = clean_text.replace(placeholder, full_tag)
            return clean_text

        author = target_msg.author
        quote_text = target_msg.clean_content or ""
        quote_text = restore_custom_emojis(quote_text, target_msg.content)
            
        if not quote_text and target_msg.attachments:
            quote_text = "*(Image/Attachment)*"
        elif not quote_text:
            quote_text = "*(No text)*"

        avatar_url = author.display_avatar.with_format("png").with_size(1024).url
        avatar = await self._download_image(avatar_url)

        reply_author = None
        reply_content = None
        if target_msg.reference and target_msg.reference.message_id:
            try:
                ref_msg = target_msg.reference.resolved
                if not isinstance(ref_msg, discord.Message):
                    ref_channel = ctx.guild.get_channel(target_msg.reference.channel_id) or await self.bot.fetch_channel(target_msg.reference.channel_id)
                    ref_msg = await ref_channel.fetch_message(target_msg.reference.message_id)
                
                reply_author = ref_msg.author.display_name
                reply_content = ref_msg.clean_content or ""
                reply_content = restore_custom_emojis(reply_content, ref_msg.content)
                    
                if not reply_content and ref_msg.attachments:
                    reply_content = "*(Attachment)*"
            except Exception as e:
                logger.warning(f"Failed to fetch reply reference: {e}")

        try:
            image_bytes = await asyncio.to_thread(
                self._generate_quote_card,
                avatar=avatar,
                quote_text=quote_text,
                quote_author=author.display_name,
                reply_author=reply_author,
                reply_content=reply_content
            )
            
            discord_file = discord.File(image_bytes, filename="quote.png")
            await ctx.reply(file=discord_file)
        except Exception as e:
            logger.exception("Failed to generate quote card image")
            await ctx.reply(f"{Emojis.ERROR} Failed to generate quote card image: `{e}`")


async def setup(bot):
    await bot.add_cog(Fun(bot))
