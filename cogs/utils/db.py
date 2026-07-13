import logging
from typing import Optional, List, Tuple
from cogs.utils.constants import DefaultSettings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages all database interactions for Spl1ceAI to decouple database queries from cogs/views."""
    
    def __init__(self, db_conn):
        self.db = db_conn

    async def initialize(self) -> None:
        """Creates tables and runs columns migrations if needed."""
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
                "CREATE TABLE IF NOT EXISTS guild_settings (guild_id INTEGER PRIMARY KEY, prefix TEXT NOT NULL DEFAULT '!', cbc INTEGER, log_channel INTEGER, llm_primary TEXT NOT NULL DEFAULT 'gemini', llm_backup1 TEXT NOT NULL DEFAULT 'openai', llm_backup2 TEXT NOT NULL DEFAULT 'anthropic', llm_backup3 TEXT NOT NULL DEFAULT 'deepseek', llm_timeout INTEGER NOT NULL DEFAULT 15)"
            )
            await self.db.commit()

        async with self.db.cursor() as cursor:
            await cursor.execute("PRAGMA table_info(guild_settings)")
            columns = [row[1] for row in await cursor.fetchall()]
            
            migrated = False
            if "llm_primary" not in columns:
                logger.info("Migration: Adding llm_primary column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN llm_primary TEXT NOT NULL DEFAULT 'gemini'")
                migrated = True
            if "llm_backup1" not in columns:
                logger.info("Migration: Adding llm_backup1 column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN llm_backup1 TEXT NOT NULL DEFAULT 'openai'")
                migrated = True
            if "llm_backup2" not in columns:
                logger.info("Migration: Adding llm_backup2 column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN llm_backup2 TEXT NOT NULL DEFAULT 'anthropic'")
                migrated = True
            if "llm_backup3" not in columns:
                logger.info("Migration: Adding llm_backup3 column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN llm_backup3 TEXT NOT NULL DEFAULT 'deepseek'")
                migrated = True
            if "log_channel" not in columns:
                logger.info("Migration: Adding log_channel column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN log_channel INTEGER")
                migrated = True
            if "llm_timeout" not in columns:
                logger.info("Migration: Adding llm_timeout column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN llm_timeout INTEGER NOT NULL DEFAULT 15")
                migrated = True
                
            if migrated:
                await self.db.commit()

    # --- Guild Settings Management ---
    
    async def get_all_guild_settings(self) -> List[Tuple]:
        """Fetches all guild settings from the database during bot startup."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "SELECT guild_id, prefix, cbc, llm_primary, llm_backup1, llm_backup2, llm_backup3, llm_timeout, log_channel "
                "FROM guild_settings"
            )
            return await cursor.fetchall()

    async def initialize_default_guild_settings(self, guild_id: int) -> None:
        """Inserts default settings for a newly joined or unconfigured guild."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT OR IGNORE INTO guild_settings (guild_id, prefix, cbc, log_channel, llm_primary, llm_backup1, llm_backup2, llm_backup3, llm_timeout) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    guild_id, 
                    DefaultSettings.PREFIX, 
                    DefaultSettings.CBC, 
                    DefaultSettings.LOG_CHANNEL, 
                    DefaultSettings.LLM_PRIMARY, 
                    DefaultSettings.LLM_BACKUP1, 
                    DefaultSettings.LLM_BACKUP2, 
                    DefaultSettings.LLM_BACKUP3, 
                    DefaultSettings.LLM_TIMEOUT
                )
            )
            await self.db.commit()

    async def update_guild_setting(self, guild_id: int, key: str, value) -> None:
        """Updates a specific guild setting column dynamically."""
        allowed_keys = {
            "prefix", "cbc", "log_channel", "llm_primary", "llm_backup1", 
            "llm_backup2", "llm_backup3", "llm_timeout"
        }
        if key not in allowed_keys:
            raise ValueError(f"Invalid guild setting key: {key}")

        async with self.db.cursor() as cursor:
            query = (
                f"INSERT INTO guild_settings (guild_id, {key}) VALUES (?, ?) "
                f"ON CONFLICT(guild_id) DO UPDATE SET {key} = excluded.{key}"
            )
            await cursor.execute(query, (guild_id, value))
            await self.db.commit()

    # --- AI Usage & Summon Management ---

    async def get_all_summons(self) -> List[Tuple[int, float]]:
        """Fetches all currently active summons from database."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT channel_id, expiry FROM ai_summon")
            return await cursor.fetchall()

    async def save_summon(self, channel_id: int, expiry: float) -> None:
        """Saves a new active channel summon."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT OR REPLACE INTO ai_summon (channel_id, expiry) VALUES (?, ?)",
                (channel_id, expiry)
            )
            await self.db.commit()

    async def delete_summon(self, channel_id: int) -> None:
        """Deletes an expired or cancelled channel summon."""
        async with self.db.cursor() as cursor:
            await cursor.execute("DELETE FROM ai_summon WHERE channel_id = ?", (channel_id,))
            await self.db.commit()

    async def get_daily_usage(self, day: str) -> Optional[Tuple[int, int]]:
        """Fetches input and output token usage for a given date."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT input_tokens, output_tokens, request_count FROM ai_usage WHERE day = ?", (day,))
            row = await cursor.fetchone()
            if row:
                return row[0], row[1], row[2]  # input_tokens, output_tokens, request_count
            return None

    async def record_ai_usage(self, day: str, input_tokens: int, output_tokens: int) -> None:
        """Records token consumption for a user query."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO ai_usage (day, request_count, input_tokens, output_tokens) VALUES (?, 1, ?, ?) "
                "ON CONFLICT(day) DO UPDATE SET request_count = request_count + 1, "
                "input_tokens = input_tokens + excluded.input_tokens, "
                "output_tokens = output_tokens + excluded.output_tokens",
                (day, input_tokens, output_tokens)
            )
            await self.db.commit()

    # --- System State (Restart Info) Management ---

    async def get_system_state(self, key: str) -> Optional[str]:
        """Gets value from system_state table."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT value FROM system_state WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return row[0] if row else None

    async def save_system_state(self, key: str, value: str) -> None:
        """Saves value into system_state table."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                (key, value)
            )
            await self.db.commit()

    async def delete_system_state(self, key: str) -> None:
        """Deletes value from system_state table."""
        async with self.db.cursor() as cursor:
            await cursor.execute("DELETE FROM system_state WHERE key = ?", (key,))
            await self.db.commit()
