import discord
from discord.ext import commands
import yt_dlp
import asyncio
import random
import logging
import tempfile
import os
import json
import time

logger = logging.getLogger(__name__)

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.collection_url = "https://www.tiktok.com/@lukysgaming/collection/seelion-7603137602169932566"
        self.common_ydl_opts = {
            'no_warnings': True,
            'quiet': True,
            'extractor_args': {
                'tiktok': {
                    'api_hostname': 'api22-normal-c-useast2a.tiktokv.com'
                }
            }
        }

    @commands.hybrid_command(name="sealion")
    async def sealion(self, ctx):
        """Sends a random sealion video from lukysgaming's collection!"""
        await ctx.defer()
        
        typing_context = ctx.typing() if ctx.interaction is None else asyncio.Lock()
        
        async with typing_context:
            try:
                ydl_opts_info = {
                **self.common_ydl_opts,
                'extract_flat': True,
                }
                
                with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                    info = await asyncio.to_thread(ydl.extract_info, self.collection_url, download=False)
                    
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
                logger.error(f"Sealion command failed: {e}")
                await ctx.reply(f"Something went wrong while fetching the sealion! 🦭\n`{e}`")

async def setup(bot):
    await bot.add_cog(Fun(bot))
