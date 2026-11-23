import os
import tempfile
import unittest

import asqlite

from cogs.utils.constants import DefaultSettings
from cogs.utils.db import DatabaseManager


class TestDatabaseManagerGuildDefaults(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmpdir.name, "test_bot.db")
        self.conn = await asqlite.connect(self.db_path)
        self.db_manager = DatabaseManager(self.conn)
        await self.db_manager.initialize()

    async def asyncTearDown(self):
        await self.conn.close()
        self._tmpdir.cleanup()

    async def test_initialize_default_guild_settings_inserts_row(self):
        guild_id = 987654321012345678

        await self.db_manager.initialize_default_guild_settings(guild_id)

        stored = await self.db_manager.get_guild_settings(guild_id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored, DefaultSettings.get_defaults_dict())

    async def test_initialize_default_guild_settings_is_idempotent(self):
        guild_id = 111222333444555666

        await self.db_manager.initialize_default_guild_settings(guild_id)
        await self.db_manager.update_guild_setting(guild_id, "prefix", "?")
        await self.db_manager.initialize_default_guild_settings(guild_id)

        stored = await self.db_manager.get_guild_settings(guild_id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored["prefix"], "?")


if __name__ == "__main__":
    unittest.main()
