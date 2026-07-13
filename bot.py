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
from cogs.utils.constants import DefaultSettings

load_dotenv()

TEST_GUILD_ID = 1027212609608491148

log = logging.getLogger(__name__)


async def get_prefix(bot, message):
        if not message.guild:
            return commands.when_mentioned_or(DefaultSettings.PREFIX)(bot, message)
        
        custom_prefix = bot.settings_cache.get(message.guild.id, {}).get("prefix", DefaultSettings.PREFIX)
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
        self.db_manager = None
        self.settings_cache = {}

    async def setup_hook(self) -> None:
        self.db = await asqlite.connect("bot.db")
        from cogs.utils.db import DatabaseManager
        self.db_manager = DatabaseManager(self.db)
        
        await self.db_manager.initialize()

        restart_info_str = await self.db_manager.get_system_state('restart_info')
        if restart_info_str:
            restart_data = json.loads(restart_info_str)
            self.loop.create_task(self.handle_restart_reaction(restart_data))
            await self.db_manager.delete_system_state('restart_info')

        rows = await self.db_manager.get_all_guild_settings()
        for row in rows:
            self.settings_cache[row[0]] = {
                "prefix": row[1],
                "cbc": row[2],
                "llm_primary": row[3],
                "llm_backup1": row[4],
                "llm_backup2": row[5],
                "llm_backup3": row[6],
                "llm_timeout": row[7],
                "log_channel": row[8]
            }

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
        for guild in self.guilds:
            if guild.id not in self.settings_cache:
                log.info(f"Initializing default settings for guild: {guild.name} ({guild.id})")
                await self.db_manager.initialize_default_guild_settings(guild.id)
                self.settings_cache[guild.id] = {
                    "prefix": DefaultSettings.PREFIX,
                    "cbc": DefaultSettings.CBC,
                    "llm_primary": DefaultSettings.LLM_PRIMARY,
                    "llm_backup1": DefaultSettings.LLM_BACKUP1,
                    "llm_backup2": DefaultSettings.LLM_BACKUP2,
                    "llm_backup3": DefaultSettings.LLM_BACKUP3,
                    "llm_timeout": DefaultSettings.LLM_TIMEOUT,
                    "log_channel": DefaultSettings.LOG_CHANNEL
                }


    async def on_guild_join(self, guild: discord.Guild) -> None:
        log.info(f"Joined new guild: {guild.name} ({guild.id})")
        await self.db_manager.initialize_default_guild_settings(guild.id)
        self.settings_cache[guild.id] = {
            "prefix": DefaultSettings.PREFIX,
            "cbc": DefaultSettings.CBC,
            "llm_primary": DefaultSettings.LLM_PRIMARY,
            "llm_backup1": DefaultSettings.LLM_BACKUP1,
            "llm_backup2": DefaultSettings.LLM_BACKUP2,
            "llm_backup3": DefaultSettings.LLM_BACKUP3,
            "llm_timeout": DefaultSettings.LLM_TIMEOUT,
            "log_channel": DefaultSettings.LOG_CHANNEL
        }

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

    # Separate AI chatbot related logs into ai.log
    ai_logger = logging.getLogger("cogs.ai")
    ai_logger.setLevel(logging.INFO)
    ai_logger.propagate = False
    ai_handler = logging.handlers.RotatingFileHandler(
        filename="ai.log",
        encoding="utf-8",
        maxBytes=32 * 1024 * 1024,
        backupCount=5,
    )
    ai_handler.setFormatter(formatter)
    ai_logger.addHandler(ai_handler)


    async with ClientSession() as client:
        # starting the bot

        # intents
        intents = discord.Intents.default()
        intents.message_content = True
        exts = ["cogs.games", "cogs.dev", "cogs.fun", "cogs.ai", "cogs.settings", "cogs.logs", "cogs.tools"]

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
