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
                "CREATE TABLE IF NOT EXISTS guild_settings (guild_id INTEGER PRIMARY KEY, prefix TEXT NOT NULL DEFAULT '!', cbc INTEGER, log_channel INTEGER, llm_primary TEXT NOT NULL DEFAULT 'gemini', llm_backup1 TEXT NOT NULL DEFAULT 'openai', llm_backup2 TEXT NOT NULL DEFAULT 'anthropic', llm_backup3 TEXT NOT NULL DEFAULT 'deepseek', llm_timeout INTEGER NOT NULL DEFAULT 15, show_model INTEGER NOT NULL DEFAULT 1, reply_ping INTEGER NOT NULL DEFAULT 1)"
            )

            # --- Telemetry Tables ---
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS command_telemetry ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "guild_id INTEGER, "
                "channel_id INTEGER, "
                "user_id INTEGER, "
                "command_name TEXT NOT NULL, "
                "is_slash INTEGER DEFAULT 0, "
                "execution_time_ms INTEGER, "
                "success INTEGER DEFAULT 1, "
                "timestamp TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS ai_telemetry ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "guild_id INTEGER, "
                "channel_id INTEGER, "
                "user_id INTEGER, "
                "model_name TEXT NOT NULL, "
                "provider TEXT NOT NULL, "
                "input_tokens INTEGER, "
                "output_tokens INTEGER, "
                "estimated_cost REAL, "
                "latency_ms INTEGER, "
                "context_messages_count INTEGER, "
                "finish_reason TEXT, "
                "trigger_type TEXT, "
                "prompt_chars INTEGER, "
                "response_chars INTEGER, "
                "failover_occurred INTEGER DEFAULT 0, "
                "failover_reason TEXT, "
                "timestamp TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS error_telemetry ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "guild_id INTEGER, "
                "channel_id INTEGER, "
                "user_id INTEGER, "
                "command_name TEXT NOT NULL, "
                "error_type TEXT NOT NULL, "
                "error_message TEXT NOT NULL, "
                "traceback TEXT NOT NULL, "
                "timestamp TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS guild_telemetry ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "guild_id INTEGER NOT NULL, "
                "event_type TEXT NOT NULL, "
                "member_count INTEGER NOT NULL, "
                "timestamp TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS game_telemetry ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "guild_id INTEGER, "
                "channel_id INTEGER, "
                "game_name TEXT NOT NULL, "
                "player1_id INTEGER NOT NULL, "
                "player2_id INTEGER NOT NULL, "
                "winner_id INTEGER, "
                "turns_count INTEGER, "
                "duration_seconds INTEGER, "
                "timestamp TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS media_telemetry ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "guild_id INTEGER, "
                "user_id INTEGER, "
                "url TEXT, "
                "duration_seconds INTEGER, "
                "file_size_bytes INTEGER, "
                "status TEXT NOT NULL, "
                "timestamp TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS user_telemetry ("
                "user_id INTEGER PRIMARY KEY, "
                "first_seen TEXT DEFAULT CURRENT_TIMESTAMP, "
                "last_seen TEXT DEFAULT CURRENT_TIMESTAMP, "
                "total_commands_run INTEGER DEFAULT 1)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS system_telemetry ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "cpu_usage_pct REAL, "
                "ram_usage_pct REAL, "
                "disk_usage_pct REAL, "
                "websocket_latency_ms INTEGER, "
                "sqlite_db_size_bytes INTEGER, "
                "uptime_seconds INTEGER, "
                "timestamp TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS settings_audit_telemetry ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "guild_id INTEGER NOT NULL, "
                "user_id INTEGER NOT NULL, "
                "setting_key TEXT NOT NULL, "
                "old_value TEXT, "
                "new_value TEXT, "
                "timestamp TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS api_latency_telemetry ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "service_name TEXT NOT NULL, "
                "endpoint TEXT NOT NULL, "
                "http_status INTEGER, "
                "latency_ms INTEGER, "
                "success INTEGER DEFAULT 1, "
                "timestamp TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS activity_heatmap_telemetry ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "guild_id INTEGER NOT NULL, "
                "channel_id INTEGER NOT NULL, "
                "message_count INTEGER DEFAULT 0, "
                "bot_responses INTEGER DEFAULT 0, "
                "hour_bucket TEXT NOT NULL, "
                "timestamp TEXT DEFAULT CURRENT_TIMESTAMP, "
                "UNIQUE(guild_id, channel_id, hour_bucket))"
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
            if "show_model" not in columns:
                logger.info("Migration: Adding show_model column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN show_model INTEGER NOT NULL DEFAULT 1")
                migrated = True
            if "reply_ping" not in columns:
                logger.info("Migration: Adding reply_ping column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN reply_ping INTEGER NOT NULL DEFAULT 1")
                migrated = True
                
            if migrated:
                await self.db.commit()

        async with self.db.cursor() as cursor:
            await cursor.execute("PRAGMA table_info(command_telemetry)")
            ct_cols = [row[1] for row in await cursor.fetchall()]
            if ct_cols:
                ct_migrated = False
                if "channel_id" not in ct_cols:
                    logger.info("Migration: Adding channel_id column to command_telemetry")
                    await cursor.execute("ALTER TABLE command_telemetry ADD COLUMN channel_id INTEGER")
                    ct_migrated = True
                if "is_slash" not in ct_cols:
                    logger.info("Migration: Adding is_slash column to command_telemetry")
                    await cursor.execute("ALTER TABLE command_telemetry ADD COLUMN is_slash INTEGER DEFAULT 0")
                    ct_migrated = True
                if "execution_time_ms" not in ct_cols:
                    logger.info("Migration: Adding execution_time_ms column to command_telemetry")
                    await cursor.execute("ALTER TABLE command_telemetry ADD COLUMN execution_time_ms INTEGER")
                    ct_migrated = True
                if "success" not in ct_cols:
                    logger.info("Migration: Adding success column to command_telemetry")
                    await cursor.execute("ALTER TABLE command_telemetry ADD COLUMN success INTEGER DEFAULT 1")
                    ct_migrated = True
                if ct_migrated:
                    await self.db.commit()

    # --- Guild Settings Management ---
    
    async def get_all_guild_settings(self) -> List[Tuple]:
        """Fetches all guild settings from the database during bot startup."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "SELECT guild_id, prefix, cbc, llm_primary, llm_backup1, llm_backup2, llm_backup3, llm_timeout, log_channel, show_model, reply_ping "
                "FROM guild_settings"
            )
            return await cursor.fetchall()

    async def initialize_default_guild_settings(self, guild_id: int) -> None:
        """Inserts default settings for a newly joined or unconfigured guild."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT OR IGNORE INTO guild_settings (guild_id, prefix, cbc, log_channel, llm_primary, llm_backup1, llm_backup2, llm_backup3, llm_timeout, show_model, reply_ping) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    guild_id, 
                    DefaultSettings.PREFIX, 
                    DefaultSettings.CBC, 
                    DefaultSettings.LOG_CHANNEL, 
                    DefaultSettings.LLM_PRIMARY, 
                    DefaultSettings.LLM_BACKUP1, 
                    DefaultSettings.LLM_BACKUP2, 
                    DefaultSettings.LLM_BACKUP3, 
                    DefaultSettings.LLM_TIMEOUT,
                    DefaultSettings.SHOW_MODEL,
                    DefaultSettings.REPLY_PING
                )
            )
            await self.db.commit()

    async def update_guild_setting(self, guild_id: int, key: str, value) -> None:
        """Updates a specific guild setting column dynamically."""
        allowed_keys = {
            "prefix", "cbc", "log_channel", "llm_primary", "llm_backup1", 
            "llm_backup2", "llm_backup3", "llm_timeout", "show_model", "reply_ping"
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

    # --- Telemetry Storage Methods ---

    async def log_command_execution(
        self, 
        guild_id: Optional[int], 
        channel_id: Optional[int], 
        user_id: int, 
        command_name: str, 
        is_slash: bool = False, 
        execution_time_ms: int = 0, 
        success: bool = True
    ) -> None:
        """Logs command execution metrics to command_telemetry."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO command_telemetry (guild_id, channel_id, user_id, command_name, is_slash, execution_time_ms, success) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (guild_id, channel_id, user_id, command_name, 1 if is_slash else 0, execution_time_ms, 1 if success else 0)
            )
            await self.db.commit()

    async def log_ai_transaction(
        self,
        guild_id: Optional[int],
        channel_id: Optional[int],
        user_id: int,
        model_name: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        estimated_cost: float,
        latency_ms: int,
        context_messages_count: int = 0,
        finish_reason: Optional[str] = None,
        trigger_type: Optional[str] = None,
        prompt_chars: int = 0,
        response_chars: int = 0,
        failover_occurred: bool = False,
        failover_reason: Optional[str] = None
    ) -> None:
        """Logs detailed LLM API transaction metrics to ai_telemetry."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO ai_telemetry ("
                "guild_id, channel_id, user_id, model_name, provider, input_tokens, output_tokens, "
                "estimated_cost, latency_ms, context_messages_count, finish_reason, trigger_type, "
                "prompt_chars, response_chars, failover_occurred, failover_reason"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    guild_id, channel_id, user_id, model_name, provider, input_tokens, output_tokens,
                    estimated_cost, latency_ms, context_messages_count, finish_reason, trigger_type,
                    prompt_chars, response_chars, 1 if failover_occurred else 0, failover_reason
                )
            )
            await self.db.commit()

    async def log_error(
        self,
        guild_id: Optional[int],
        channel_id: Optional[int],
        user_id: int,
        command_name: str,
        error_type: str,
        error_message: str,
        traceback: str
    ) -> None:
        """Logs uncaught command errors and tracebacks to error_telemetry."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO error_telemetry (guild_id, channel_id, user_id, command_name, error_type, error_message, traceback) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (guild_id, channel_id, user_id, command_name, error_type, error_message, traceback)
            )
            await self.db.commit()

    async def log_guild_event(self, guild_id: int, event_type: str, member_count: int) -> None:
        """Logs guild join/leave events to guild_telemetry."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO guild_telemetry (guild_id, event_type, member_count) VALUES (?, ?, ?)",
                (guild_id, event_type, member_count)
            )
            await self.db.commit()

    async def log_game_result(
        self,
        guild_id: Optional[int],
        channel_id: Optional[int],
        game_name: str,
        player1_id: int,
        player2_id: int,
        winner_id: Optional[int],
        turns_count: int,
        duration_seconds: int
    ) -> None:
        """Logs match statistics to game_telemetry."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO game_telemetry (guild_id, channel_id, game_name, player1_id, player2_id, winner_id, turns_count, duration_seconds) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (guild_id, channel_id, game_name, player1_id, player2_id, winner_id, turns_count, duration_seconds)
            )
            await self.db.commit()

    async def log_media_download(
        self,
        guild_id: Optional[int],
        user_id: int,
        url: Optional[str],
        duration_seconds: Optional[int],
        file_size_bytes: Optional[int],
        status: str
    ) -> None:
        """Logs media conversion/download status to media_telemetry."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO media_telemetry (guild_id, user_id, url, duration_seconds, file_size_bytes, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (guild_id, user_id, url, duration_seconds, file_size_bytes, status)
            )
            await self.db.commit()

    async def log_user_activity(self, user_id: int) -> None:
        """Upserts user activity to user_telemetry for active user tracking."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO user_telemetry (user_id, last_seen, total_commands_run) VALUES (?, CURRENT_TIMESTAMP, 1) "
                "ON CONFLICT(user_id) DO UPDATE SET last_seen = CURRENT_TIMESTAMP, total_commands_run = total_commands_run + 1",
                (user_id,)
            )
            await self.db.commit()

    async def log_system_status(
        self,
        cpu_usage_pct: float,
        ram_usage_pct: float,
        disk_usage_pct: float,
        websocket_latency_ms: int,
        sqlite_db_size_bytes: int,
        uptime_seconds: int
    ) -> None:
        """Logs system performance metrics to system_telemetry."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO system_telemetry (cpu_usage_pct, ram_usage_pct, disk_usage_pct, websocket_latency_ms, sqlite_db_size_bytes, uptime_seconds) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (cpu_usage_pct, ram_usage_pct, disk_usage_pct, websocket_latency_ms, sqlite_db_size_bytes, uptime_seconds)
            )
            await self.db.commit()

    async def log_settings_change(
        self,
        guild_id: int,
        user_id: int,
        setting_key: str,
        old_value: Optional[str],
        new_value: Optional[str]
    ) -> None:
        """Logs guild configuration edits to settings_audit_telemetry."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO settings_audit_telemetry (guild_id, user_id, setting_key, old_value, new_value) "
                "VALUES (?, ?, ?, ?, ?)",
                (guild_id, user_id, setting_key, old_value, new_value)
            )
            await self.db.commit()

    async def log_api_latency(
        self,
        service_name: str,
        endpoint: str,
        http_status: Optional[int],
        latency_ms: int,
        success: bool = True
    ) -> None:
        """Logs API endpoint latency metrics to api_latency_telemetry."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO api_latency_telemetry (service_name, endpoint, http_status, latency_ms, success) "
                "VALUES (?, ?, ?, ?, ?)",
                (service_name, endpoint, http_status, latency_ms, 1 if success else 0)
            )
            await self.db.commit()

    async def log_heatmap_activity(
        self,
        guild_id: int,
        channel_id: int,
        hour_bucket: str,
        is_bot_response: bool = False
    ) -> None:
        """Upserts message and bot response counts to activity_heatmap_telemetry for peak hour tracking."""
        async with self.db.cursor() as cursor:
            msg_inc = 0 if is_bot_response else 1
            bot_inc = 1 if is_bot_response else 0
            await cursor.execute(
                "INSERT INTO activity_heatmap_telemetry (guild_id, channel_id, message_count, bot_responses, hour_bucket) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(guild_id, channel_id, hour_bucket) DO UPDATE SET "
                "message_count = message_count + excluded.message_count, "
                "bot_responses = bot_responses + excluded.bot_responses",
                (guild_id, channel_id, msg_inc, bot_inc, hour_bucket)
            )
            await self.db.commit()
