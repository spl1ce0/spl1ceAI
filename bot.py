import asyncio
import logging
import json
import time
from logging import handlers
from typing import List, Optional

import discord
import asqlite
from aiohttp import ClientSession
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()

TEST_GUILD_ID = 1027212609608491148

log = logging.getLogger(__name__)


async def get_prefix(bot, message):
        if not message.guild:
            return commands.when_mentioned_or("!")(bot, message)
        
        custom_prefix = bot.settings_cache.get(message.guild.id, {}).get("prefix", "!")
        return commands.when_mentioned_or(custom_prefix)(bot, message)

class Spl1ceAI(commands.AutoShardedBot):
    def __init__(
        self,
        *args,
        initial_extensions: List[str],
        web_client: ClientSession,
        testing_guild_id: Optional[int] = None,
        **kwargs,
    ):

        super().__init__(
            command_prefix=get_prefix,
            *args, 
            **kwargs
        )
        self.web_client = web_client
        self.testing_guild_id = testing_guild_id
        self.initial_extensions = initial_extensions
        self.db: asqlite.Connection = None
        self.settings_cache = {}

    async def setup_hook(self) -> None:
        self.db = await asqlite.connect("bot.db")
        
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS system_state (key TEXT PRIMARY KEY, value TEXT)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS ai_summon (channel_id INTEGER PRIMARY KEY, expiry REAL)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS ai_usage (day TEXT PRIMARY KEY, request_count INTEGER DEFAULT 0, input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS guild_settings ( guild_id INTEGER PRIMARY KEY, prefix TEXT NOT NULL DEFAULT '!', cbc INTEGER)"
            )
            await self.db.commit()

        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT value FROM system_state WHERE key = 'restart_info'")
            row = await cursor.fetchone()
            
            if row:
                restart_data = json.loads(row[0])
                self.loop.create_task(self.handle_restart_reaction(restart_data))
                await cursor.execute("DELETE FROM system_state WHERE key = 'restart_info'")
                await self.db.commit()


            await cursor.execute("SELECT guild_id, prefix, cbc FROM guild_settings")
            rows = await cursor.fetchall()
            for row in rows:
                self.settings_cache[row[0]] = {"prefix": row[1], "cbc": row[2]}

        for extension in self.initial_extensions:
            log.info(f"Extension {extension} loaded")
            await self.load_extension(extension)
        

    async def handle_restart_reaction(self, data):
        """Re-fetches the restart message once the bot is ready to react and report time."""
        await self.wait_until_ready()
        
        channel = self.get_channel(data['channel_id'])
        if channel:
            try:
                message = await channel.fetch_message(data['message_id'])
                try:
                    await message.remove_reaction('🔄', self.user)
                except Exception:
                    pass
                
                await message.add_reaction('✅')
                
                end_time = time.time()
                duration = end_time - data['start_time']
                await channel.send(f"🚀 Back online! Boot time: `{duration:.2f}s`", reference=message)
            except Exception as e:
                log.error(f"Failed to react to restart message: {e}")


    async def on_ready(self) -> None:
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        async with self.db.cursor() as cursor:
            for guild in self.guilds:
                if guild.id not in self.settings_cache:
                    log.info(f"Initializing default settings for guild: {guild.name} ({guild.id})")
                    await cursor.execute(
                        "INSERT OR IGNORE INTO guild_settings (guild_id, prefix, cbc) VALUES (?, ?, ?)",
                        (guild.id, "!", None)
                    )
                    self.settings_cache[guild.id] = {"prefix": "!", "cbc": None}
            await self.db.commit()


    async def on_guild_join(self, guild: discord.Guild) -> None:
        log.info(f"Joined new guild: {guild.name} ({guild.id})")
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT OR IGNORE INTO guild_settings (guild_id, prefix, cbc) VALUES (?, ?, ?)",
                (guild.id, "!", None)
            )
            await self.db.commit()
        self.settings_cache[guild.id] = {"prefix": "!", "cbc": None}

    async def close(self) -> None:
        if self.db:
            await self.db.close()
        await super().close()

    async def start(self) -> None:
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            log.error("DISCORD_TOKEN not found in environment variables.")
            return
        await super().start(token, reconnect=True)
        

async def main():
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    handler = logging.handlers.RotatingFileHandler(
        filename="discord.log",
        encoding="utf-8",
        maxBytes=32 * 1024 * 1024, 
        backupCount=5,  
    )

    dt_fmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
    )
    handler.setFormatter(formatter)
    # logger.addHandler(handler)

    discord.utils.setup_logging(handler=handler, formatter=formatter, root=True)


    async with ClientSession() as client:
        # starting the bot

        # intents
        intents = discord.Intents.default()
        intents.message_content = True
        exts = ["cogs.games", "cogs.dev", "cogs.fun", "cogs.ai", "cogs.settings"]

        async with Spl1ceAI(
            # db_pool=pool,
            web_client=client,
            initial_extensions=exts,
            intents=intents,
            testing_guild_id=TEST_GUILD_ID,
        ) as bot:
            await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
