import asyncio
import logging
from logging import handlers
from typing import List, Optional

import discord
from aiohttp import ClientSession
from discord.ext import commands

TEST_GUILD_ID = 1027212609608491148

log = logging.getLogger(__name__)


class Spl1ceAI(commands.AutoShardedBot):
    def __init__(
        self,
        *args,
        initial_extensions: List[str],
        # db_pool: asyncpg.Pool,
        web_client: ClientSession,
        testing_guild_id: Optional[int] = None,
        **kwargs,
    ):

        super().__init__(
            command_prefix=commands.when_mentioned_or("!"), *args, **kwargs
        )
        # self.db_pool = db_pool
        self.web_client = web_client
        self.testing_guild_id = testing_guild_id
        self.initial_extensions = initial_extensions

    async def setup_hook(self) -> None:
        # here, we are loading extensions prior to sync to ensure we are syncing interactions defined in those extensions.

        for extension in self.initial_extensions:
            log.info(f"Extension {extension} loaded")
            await self.load_extension(extension)

        #'''
        if self.testing_guild_id:
            guild = discord.Object(self.testing_guild_id)

            self.tree.copy_global_to(guild=guild)

            await self.tree.sync(guild=guild)
        #'''

        # This would also be a good place to connect to our database and
        # load anything that should be in memory prior to handling events.

    async def start(self) -> None:
        with open("token.txt", "r") as file:
            token = file.read()
            await super().start(token, reconnect=True)


async def main():
    # logging

    # for this example, we're going to set up a rotating file logger.
    # for more info on setting up logging,
    # see https://discordpy.readthedocs.io/en/latest/logging.html and https://docs.python.org/3/howto/logging.html

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    handler = logging.handlers.RotatingFileHandler(
        filename="discord.log",
        encoding="utf-8",
        maxBytes=32 * 1024 * 1024,  # 32 MiB
        backupCount=5,  # Rotate through 5 files
    )

    dt_fmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(
        "[{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
    )
    handler.setFormatter(formatter)
    # logger.addHandler(handler)

    # Alternatively, you could use:
    discord.utils.setup_logging(handler=handler, formatter=formatter, root=True)

    # One of the reasons to take over more of the process though
    # is to ensure use with other libraries or tools which also require their own cleanup.

    # Here we have a web client and a database pool, both of which do cleanup at exit.
    # We also have our bot, which depends on both of these.
    # A web client session is used to

    # if i need a database, add the following
    #
    # asyncpg.create_pool(user='postgres', command_timeout=30) as pool:

    async with ClientSession() as client:
        # starting the bot

        # intents
        intents = discord.Intents.default()
        intents.message_content = True
        exts = ["cogs.games", "cogs.dev", "cogs.troll"]

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
