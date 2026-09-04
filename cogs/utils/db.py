import logging
import datetime
import time
from typing import Optional, List, Tuple
from cogs.utils.constants import DefaultSettings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages all database interactions for Spl1ceAI to decouple database queries from cogs/views."""
    
    def __init__(self, db_conn):
        self.db = db_conn

    async def initialize(self) -> None:
        """Creates tables, applies performance indices, and runs columns migrations if needed."""
        async with self.db.cursor() as cursor:
            # --- High-Concurrency Performance PRAGMAs ---
            await cursor.execute("PRAGMA journal_mode=WAL")
            await cursor.execute("PRAGMA synchronous=NORMAL")
            await cursor.execute("PRAGMA foreign_keys=ON")
            await cursor.execute("PRAGMA busy_timeout=5000")

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
                "CREATE TABLE IF NOT EXISTS guild_weekly_usage ("
                "guild_id INTEGER, "
                "week_start TEXT, "
                "total_tokens INTEGER DEFAULT 0, "
                "input_tokens INTEGER DEFAULT 0, "
                "output_tokens INTEGER DEFAULT 0, "
                "prompt_count INTEGER DEFAULT 0, "
                "image_count INTEGER DEFAULT 0, "
                "last_image_ts REAL DEFAULT 0, "
                "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
                "updated_at TEXT DEFAULT CURRENT_TIMESTAMP, "
                "PRIMARY KEY (guild_id, week_start))"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS guild_subscriptions ("
                "guild_id INTEGER PRIMARY KEY, "
                "customer_id TEXT, "
                "subscription_id TEXT, "
                "status TEXT, "
                "user_id INTEGER, "
                "variant_id TEXT, "
                "current_period_end TEXT, "
                "cancel_at_period_end INTEGER DEFAULT 0, "
                "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
                "updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"
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
                "CREATE TABLE IF NOT EXISTS blackjack_hand_telemetry ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "guild_id INTEGER, "
                "table_id TEXT, "
                "table_name TEXT, "
                "user_id INTEGER NOT NULL, "
                "bet_amount REAL NOT NULL, "
                "payout_amount REAL NOT NULL, "
                "net_profit REAL NOT NULL, "
                "result_type TEXT NOT NULL, "
                "player_cards TEXT, "
                "player_val INTEGER, "
                "dealer_cards TEXT, "
                "dealer_val INTEGER, "
                "is_doubled INTEGER DEFAULT 0, "
                "is_split INTEGER DEFAULT 0, "
                "is_blackjack INTEGER DEFAULT 0, "
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
                "guild_count INTEGER DEFAULT 0, "
                "total_members_count INTEGER DEFAULT 0, "
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
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS user_economy ("
                "user_id INTEGER PRIMARY KEY, "
                "balance REAL NOT NULL DEFAULT 1000.0, "
                "daily_last_claimed TEXT, "
                "daily_streak INTEGER NOT NULL DEFAULT 0, "
                "total_wagered REAL NOT NULL DEFAULT 0.0, "
                "total_won REAL NOT NULL DEFAULT 0.0, "
                "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
                "updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS blackjack_stats ("
                "user_id INTEGER PRIMARY KEY, "
                "wagered REAL NOT NULL DEFAULT 0.0, "
                "won REAL NOT NULL DEFAULT 0.0, "
                "hands_played INTEGER NOT NULL DEFAULT 0, "
                "hands_won INTEGER NOT NULL DEFAULT 0, "
                "hands_lost INTEGER NOT NULL DEFAULT 0, "
                "hands_pushed INTEGER NOT NULL DEFAULT 0, "
                "blackjacks INTEGER NOT NULL DEFAULT 0, "
                "biggest_win REAL NOT NULL DEFAULT 0.0)"
            )
            await cursor.execute(
                "CREATE TABLE IF NOT EXISTS user_blacklist ("
                "user_id INTEGER PRIMARY KEY, "
                "reason TEXT, "
                "blacklisted_by INTEGER, "
                "timestamp TEXT DEFAULT CURRENT_TIMESTAMP)"
            )

            # --- Performance Indexes ---
            await cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_economy_balance ON user_economy (balance DESC)")
            await cursor.execute("CREATE INDEX IF NOT EXISTS idx_blackjack_stats_won ON blackjack_stats (won DESC)")
            await cursor.execute("CREATE INDEX IF NOT EXISTS idx_command_telemetry_ts ON command_telemetry (timestamp)")
            await cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_telemetry_ts ON ai_telemetry (timestamp)")
            await cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_telemetry_ts ON error_telemetry (timestamp)")
            await cursor.execute("CREATE INDEX IF NOT EXISTS idx_game_telemetry_ts ON game_telemetry (timestamp)")
            await cursor.execute("CREATE INDEX IF NOT EXISTS idx_command_telemetry_user ON command_telemetry (user_id)")
            await cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_telemetry_user ON ai_telemetry (user_id)")

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
            if "is_premium" not in columns:
                logger.info("Migration: Adding is_premium column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN is_premium INTEGER NOT NULL DEFAULT 0")
                migrated = True
            if "custom_prompt" not in columns:
                logger.info("Migration: Adding custom_prompt column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN custom_prompt TEXT")
                migrated = True
            if "byok_gemini_key" not in columns:
                logger.info("Migration: Adding byok_gemini_key column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN byok_gemini_key TEXT")
                migrated = True
            if "byok_xai_key" not in columns:
                logger.info("Migration: Adding byok_xai_key column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN byok_xai_key TEXT")
                migrated = True
            if "byok_openai_key" not in columns:
                logger.info("Migration: Adding byok_openai_key column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN byok_openai_key TEXT")
                migrated = True
            if "byok_anthropic_key" not in columns:
                logger.info("Migration: Adding byok_anthropic_key column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN byok_anthropic_key TEXT")
                migrated = True
            if "byok_deepseek_key" not in columns:
                logger.info("Migration: Adding byok_deepseek_key column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN byok_deepseek_key TEXT")
                migrated = True
            if "byok_glm_key" not in columns:
                logger.info("Migration: Adding byok_glm_key column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN byok_glm_key TEXT")
                migrated = True
            if "byok_primary_model" not in columns:
                logger.info("Migration: Adding byok_primary_model column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN byok_primary_model TEXT")
                migrated = True
            if "byok_fallback_model" not in columns:
                logger.info("Migration: Adding byok_fallback_model column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN byok_fallback_model TEXT")
                migrated = True
            if "footer_show_icon" not in columns:
                logger.info("Migration: Adding footer_show_icon column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN footer_show_icon INTEGER NOT NULL DEFAULT 1")
                migrated = True
            if "footer_show_name" not in columns:
                logger.info("Migration: Adding footer_show_name column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN footer_show_name INTEGER NOT NULL DEFAULT 1")
                migrated = True
            if "footer_show_tokens" not in columns:
                logger.info("Migration: Adding footer_show_tokens column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN footer_show_tokens INTEGER NOT NULL DEFAULT 1")
                migrated = True
            if "footer_show_latency" not in columns:
                logger.info("Migration: Adding footer_show_latency column to guild_settings")
                await cursor.execute("ALTER TABLE guild_settings ADD COLUMN footer_show_latency INTEGER NOT NULL DEFAULT 1")
                migrated = True
                
            if migrated:
                await self.db.commit()

        async with self.db.cursor() as cursor:
            await cursor.execute("PRAGMA table_info(guild_subscriptions)")
            sub_cols = [row[1] for row in await cursor.fetchall()]
            if sub_cols:
                sub_migrated = False
                if "variant_id" not in sub_cols:
                    logger.info("Migration: Adding variant_id column to guild_subscriptions")
                    await cursor.execute("ALTER TABLE guild_subscriptions ADD COLUMN variant_id TEXT")
                    sub_migrated = True
                if "price_id" not in sub_cols:
                    logger.info("Migration: Adding price_id column to guild_subscriptions")
                    await cursor.execute("ALTER TABLE guild_subscriptions ADD COLUMN price_id TEXT")
                    sub_migrated = True
                if sub_migrated:
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

        async with self.db.cursor() as cursor:
            await cursor.execute("PRAGMA table_info(system_telemetry)")
            st_cols = [row[1] for row in await cursor.fetchall()]
            if st_cols:
                st_migrated = False
                if "guild_count" not in st_cols:
                    logger.info("Migration: Adding guild_count column to system_telemetry")
                    await cursor.execute("ALTER TABLE system_telemetry ADD COLUMN guild_count INTEGER DEFAULT 0")
                    st_migrated = True
                if "total_members_count" not in st_cols:
                    logger.info("Migration: Adding total_members_count column to system_telemetry")
                    await cursor.execute("ALTER TABLE system_telemetry ADD COLUMN total_members_count INTEGER DEFAULT 0")
                    st_migrated = True
                if st_migrated:
                    await self.db.commit()

        async with self.db.cursor() as cursor:
            await cursor.execute("PRAGMA table_info(ai_telemetry)")
            ai_cols = [row[1] for row in await cursor.fetchall()]
            if ai_cols and "prompt_text" not in ai_cols:
                logger.info("Migration: Adding prompt_text column to ai_telemetry")
                await cursor.execute("ALTER TABLE ai_telemetry ADD COLUMN prompt_text TEXT")
                await self.db.commit()

    # --- Guild Settings Management ---
    
    async def get_all_guild_settings(self) -> List[Any]:
        """Fetches all guild settings from the database during bot startup."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT * FROM guild_settings")
            return await cursor.fetchall()

    async def initialize_default_guild_settings(self, guild_id: int) -> None:
        """Inserts default settings for a newly joined or unconfigured guild."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT OR IGNORE INTO guild_settings (guild_id, prefix, cbc, log_channel, llm_primary, llm_backup1, llm_backup2, llm_backup3, llm_timeout, show_model, reply_ping, footer_show_icon, footer_show_name, footer_show_tokens, footer_show_latency) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                    DefaultSettings.REPLY_PING,
                    DefaultSettings.FOOTER_SHOW_ICON,
                    DefaultSettings.FOOTER_SHOW_NAME,
                    DefaultSettings.FOOTER_SHOW_TOKENS,
                    DefaultSettings.FOOTER_SHOW_LATENCY
                )
            )
            await self.db.commit()

    async def update_guild_setting(self, guild_id: int, key: str, value) -> None:
        """Updates a specific guild setting column dynamically."""
        allowed_keys = {
            "prefix", "cbc", "log_channel", "llm_primary", "llm_backup1", 
            "llm_backup2", "llm_backup3", "llm_timeout", "show_model", "reply_ping",
            "is_premium", "custom_prompt", "byok_gemini_key", "byok_xai_key", 
            "byok_openai_key", "byok_anthropic_key", "byok_deepseek_key", "byok_glm_key",
            "byok_primary_model", "byok_fallback_model",
            "footer_show_icon", "footer_show_name", "footer_show_tokens", "footer_show_latency"
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

    @staticmethod
    def _get_current_week_start() -> str:
        """Returns the YYYY-MM-DD string for Monday of the current UTC week."""
        now = datetime.datetime.now(datetime.timezone.utc)
        monday = now - datetime.timedelta(days=now.weekday())
        return monday.strftime("%Y-%m-%d")

    @staticmethod
    def _get_next_week_reset_ts() -> int:
        """Returns the UNIX timestamp for 00:00:00 UTC of next Monday."""
        now = datetime.datetime.now(datetime.timezone.utc)
        monday = now - datetime.timedelta(days=now.weekday())
        next_monday = monday + datetime.timedelta(days=7)
        next_monday_midnight = datetime.datetime(next_monday.year, next_monday.month, next_monday.day, 0, 0, 0, tzinfo=datetime.timezone.utc)
        return int(next_monday_midnight.timestamp())

    @staticmethod
    def _parse_timestamp_to_unix(ts_val) -> float:
        """Robustly parses a timestamp from float, int, or ISO string to UNIX float."""
        if not ts_val:
            return 0.0
        if isinstance(ts_val, (int, float)):
            return float(ts_val)
        if isinstance(ts_val, str):
            try:
                return float(ts_val)
            except ValueError:
                pass
            try:
                dt_str = ts_val.replace("Z", "+00:00")
                if "+" not in dt_str and "T" in dt_str:
                    dt_str += "+00:00"
                elif "+" not in dt_str and " " in dt_str:
                    dt_str = dt_str.replace(" ", "T") + "+00:00"
                dt_obj = datetime.datetime.fromisoformat(dt_str)
                return dt_obj.timestamp()
            except Exception:
                return 0.0
        return 0.0

    async def get_guild_weekly_ai_usage(self, guild_id: int) -> dict:
        """Fetches weekly token, prompt, and image usage for a server."""
        week_start = self._get_current_week_start()
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "SELECT total_tokens, input_tokens, output_tokens, prompt_count, image_count, last_image_ts "
                "FROM guild_weekly_usage WHERE guild_id = ? AND week_start = ?",
                (guild_id, week_start)
            )
            row = await cursor.fetchone()
            next_reset_ts = self._get_next_week_reset_ts()
            if row:
                last_img_ts = self._parse_timestamp_to_unix(row[5])
                next_img_ts = int(last_img_ts + 14 * 86400) if last_img_ts > 0 else 0
                return {
                    "week_start": week_start,
                    "total_tokens": int(row[0] or 0),
                    "input_tokens": int(row[1] or 0),
                    "output_tokens": int(row[2] or 0),
                    "prompt_count": int(row[3] or 0),
                    "image_count": int(row[4] or 0),
                    "last_image_ts": last_img_ts,
                    "next_reset_ts": next_reset_ts,
                    "next_image_reset_ts": next_img_ts
                }
            return {
                "week_start": week_start,
                "total_tokens": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "prompt_count": 0,
                "image_count": 0,
                "last_image_ts": 0.0,
                "next_reset_ts": next_reset_ts,
                "next_image_reset_ts": 0
            }

    async def record_guild_ai_usage(self, guild_id: int, input_tokens: int, output_tokens: int, is_image: bool = False) -> None:
        """Records token and image consumption for a server's weekly quota."""
        week_start = self._get_current_week_start()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        total_tokens = input_tokens + output_tokens
        img_increment = 1 if is_image else 0
        
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO guild_weekly_usage (guild_id, week_start, total_tokens, input_tokens, output_tokens, prompt_count, image_count, last_image_ts, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(guild_id, week_start) DO UPDATE SET "
                "total_tokens = total_tokens + excluded.total_tokens, "
                "input_tokens = input_tokens + excluded.input_tokens, "
                "output_tokens = output_tokens + excluded.output_tokens, "
                "prompt_count = prompt_count + 1, "
                "image_count = image_count + excluded.image_count, "
                "last_image_ts = CASE WHEN excluded.image_count > 0 THEN excluded.last_image_ts ELSE last_image_ts END, "
                "updated_at = CURRENT_TIMESTAMP",
                (guild_id, week_start, total_tokens, input_tokens, output_tokens, img_increment, now_iso if is_image else None)
            )
            await self.db.commit()

    async def check_ai_quota_allowance(self, guild_id: Optional[int], guild_settings: dict, is_image: bool = False) -> Tuple[bool, Optional[str], dict]:
        """Validates whether the server has sufficient quota for text or image generation."""
        if not guild_id:
            return True, None, {}
        
        has_byok = bool(
            guild_settings.get("byok_gemini_key") or 
            guild_settings.get("byok_xai_key") or 
            guild_settings.get("byok_openai_key") or 
            guild_settings.get("byok_anthropic_key")
        )
        usage = await self.get_guild_weekly_ai_usage(guild_id)
        if has_byok:
            return True, None, usage
        
        is_premium = bool(guild_settings.get("is_premium", 0))
        
        if is_image:
            if is_premium:
                if usage["image_count"] >= 5:
                    return False, f"Server has reached the Premium weekly limit of 5 image generations (20/month). Resets <t:{usage['next_reset_ts']}:R>.", usage
            else:
                last_img = float(usage.get("last_image_ts", 0.0) or 0.0)
                if last_img > 0:
                    time_since = time.time() - last_img
                    fourteen_days = 14 * 86400
                    if time_since < fourteen_days:
                        res_ts = int(last_img + fourteen_days)
                        return False, f"Free plan allows 1 AI image generation every 2 weeks. Available again <t:{res_ts}:R>.", usage
        else:
            token_limit = DefaultSettings.PREMIUM_WEEKLY_TOKEN_LIMIT if is_premium else DefaultSettings.FREE_WEEKLY_TOKEN_LIMIT
            if usage["total_tokens"] >= token_limit:
                tier_name = "Premium (1M)" if is_premium else "Free (100k)"
                return False, f"Server has reached the weekly {tier_name} token quota ({usage['total_tokens']:,} / {token_limit:,}). Resets <t:{usage['next_reset_ts']}:R>.", usage
        
        return True, None, usage

    # --- Subscription Management ---

    async def get_subscription(self, guild_id: int) -> Optional[dict]:
        """Fetches subscription details for a guild."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "SELECT customer_id, subscription_id, status, user_id, variant_id, current_period_end, cancel_at_period_end "
                "FROM guild_subscriptions WHERE guild_id = ?",
                (guild_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "customer_id": row[0],
                    "subscription_id": row[1],
                    "status": row[2],
                    "user_id": row[3],
                    "variant_id": row[4],
                    "current_period_end": row[5],
                    "cancel_at_period_end": bool(row[6])
                }
            return None

    async def save_subscription(
        self, 
        guild_id: int, 
        customer_id: str, 
        subscription_id: str, 
        status: str, 
        user_id: int = 0, 
        variant_id: str = "", 
        current_period_end: str = ""
    ) -> None:
        """Saves or updates guild subscription state."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO guild_subscriptions (guild_id, customer_id, subscription_id, status, user_id, variant_id, current_period_end, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(guild_id) DO UPDATE SET "
                "customer_id = excluded.customer_id, "
                "subscription_id = excluded.subscription_id, "
                "status = excluded.status, "
                "user_id = excluded.user_id, "
                "variant_id = excluded.variant_id, "
                "current_period_end = excluded.current_period_end, "
                "updated_at = CURRENT_TIMESTAMP",
                (guild_id, customer_id, subscription_id, status, user_id, variant_id, current_period_end)
            )
            await self.db.commit()

    async def delete_subscription(self, guild_id: int) -> None:
        """Deletes guild subscription record."""
        async with self.db.cursor() as cursor:
            await cursor.execute("DELETE FROM guild_subscriptions WHERE guild_id = ?", (guild_id,))
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
        failover_reason: Optional[str] = None,
        prompt_text: Optional[str] = None
    ) -> None:
        """Logs detailed LLM API transaction metrics to ai_telemetry."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO ai_telemetry ("
                "guild_id, channel_id, user_id, model_name, provider, input_tokens, output_tokens, "
                "estimated_cost, latency_ms, context_messages_count, finish_reason, trigger_type, "
                "prompt_chars, response_chars, failover_occurred, failover_reason, prompt_text"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    guild_id, channel_id, user_id, model_name, provider, input_tokens, output_tokens,
                    estimated_cost, latency_ms, context_messages_count, finish_reason, trigger_type,
                    prompt_chars, response_chars, 1 if failover_occurred else 0, failover_reason,
                    prompt_text[:1000] if prompt_text else None
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
        uptime_seconds: int,
        guild_count: int = 0,
        total_members_count: int = 0
    ) -> None:
        """Logs system performance and community scale metrics to system_telemetry."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO system_telemetry (cpu_usage_pct, ram_usage_pct, disk_usage_pct, websocket_latency_ms, sqlite_db_size_bytes, uptime_seconds, guild_count, total_members_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (cpu_usage_pct, ram_usage_pct, disk_usage_pct, websocket_latency_ms, sqlite_db_size_bytes, uptime_seconds, guild_count, total_members_count)
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

    # --- Analytics & Reporting Queries ---

    async def get_analytics_home_summary(self) -> dict:
        """Fetches aggregated high-level statistics for the Analytics Home view."""
        async with self.db.cursor() as cursor:
            # 1. User stats
            await cursor.execute("SELECT COUNT(*) FROM user_telemetry")
            total_users = (await cursor.fetchone())[0] or 0

            await cursor.execute("SELECT COUNT(*) FROM user_telemetry WHERE last_seen >= datetime('now', '-1 day')")
            active_users_24h = (await cursor.fetchone())[0] or 0

            await cursor.execute("SELECT COUNT(*) FROM user_telemetry WHERE first_seen >= datetime('now', '-1 day')")
            new_users_24h = (await cursor.fetchone())[0] or 0

            # 2. Guild events in last 7 days
            await cursor.execute("SELECT COUNT(*) FROM guild_telemetry WHERE event_type = 'join' AND timestamp >= datetime('now', '-7 days')")
            joins_7d = (await cursor.fetchone())[0] or 0

            await cursor.execute("SELECT COUNT(*) FROM guild_telemetry WHERE event_type = 'leave' AND timestamp >= datetime('now', '-7 days')")
            leaves_7d = (await cursor.fetchone())[0] or 0

            # 3. Last 24 hourly snapshots
            await cursor.execute(
                "SELECT cpu_usage_pct, ram_usage_pct, websocket_latency_ms, guild_count, total_members_count, timestamp "
                "FROM system_telemetry WHERE timestamp >= datetime('now', '-24 hours') ORDER BY timestamp ASC"
            )
            hourly_snapshots = await cursor.fetchall()

            # 4. Total commands in last 24h
            await cursor.execute("SELECT COUNT(*) FROM command_telemetry WHERE timestamp >= datetime('now', '-1 day')")
            commands_24h = (await cursor.fetchone())[0] or 0

            return {
                "total_registered_users": total_users,
                "active_users_24h": active_users_24h,
                "new_users_24h": new_users_24h,
                "joins_7d": joins_7d,
                "leaves_7d": leaves_7d,
                "hourly_snapshots": hourly_snapshots,
                "commands_24h": commands_24h
            }

    async def get_guild_analytics_summary(self, limit: int = 10) -> dict:
        """Fetches recent guild events and summary."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "SELECT guild_id, event_type, member_count, timestamp "
                "FROM guild_telemetry ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            recent_events = await cursor.fetchall()

            await cursor.execute("SELECT COUNT(*) FROM guild_telemetry WHERE event_type = 'join'")
            total_joins = (await cursor.fetchone())[0] or 0

            await cursor.execute("SELECT COUNT(*) FROM guild_telemetry WHERE event_type = 'leave'")
            total_leaves = (await cursor.fetchone())[0] or 0

            return {
                "recent_events": recent_events,
                "total_joins": total_joins,
                "total_leaves": total_leaves
            }

    async def get_user_analytics_summary(self, limit: int = 10) -> dict:
        """Fetches top active users and registration trends."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "SELECT user_id, total_commands_run, first_seen, last_seen "
                "FROM user_telemetry ORDER BY total_commands_run DESC LIMIT ?",
                (limit,)
            )
            top_users = await cursor.fetchall()

            await cursor.execute("SELECT COUNT(*) FROM user_telemetry WHERE first_seen >= datetime('now', '-7 days')")
            new_users_7d = (await cursor.fetchone())[0] or 0

            return {
                "top_users": top_users,
                "new_users_7d": new_users_7d
            }

    async def get_ai_analytics_summary(self) -> dict:
        """Fetches AI engine metrics, model breakdown, failovers, and hourly traffic."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT COUNT(*), SUM(input_tokens), SUM(output_tokens), AVG(latency_ms), AVG(context_messages_count) FROM ai_telemetry WHERE timestamp >= datetime('now', '-24 hours')")
            row = await cursor.fetchone()
            reqs_24h = row[0] or 0
            in_tokens_24h = row[1] or 0
            out_tokens_24h = row[2] or 0
            avg_latency = int(row[3] or 0)
            avg_context = round(row[4] or 0.0, 1)

            await cursor.execute("SELECT COUNT(*) FROM ai_telemetry WHERE failover_occurred = 1 AND timestamp >= datetime('now', '-24 hours')")
            failovers_24h = (await cursor.fetchone())[0] or 0

            await cursor.execute(
                "SELECT model_name, provider, COUNT(*), AVG(latency_ms) "
                "FROM ai_telemetry WHERE timestamp >= datetime('now', '-24 hours') "
                "GROUP BY model_name, provider ORDER BY COUNT(*) DESC LIMIT 6"
            )
            model_counts = await cursor.fetchall()

            await cursor.execute(
                "SELECT trigger_type, COUNT(*) FROM ai_telemetry "
                "WHERE timestamp >= datetime('now', '-24 hours') "
                "GROUP BY trigger_type ORDER BY COUNT(*) DESC"
            )
            trigger_counts = await cursor.fetchall()

            await cursor.execute(
                "SELECT model_name, failover_reason, timestamp FROM ai_telemetry "
                "WHERE failover_occurred = 1 AND timestamp >= datetime('now', '-24 hours') "
                "ORDER BY timestamp DESC LIMIT 4"
            )
            recent_failovers = await cursor.fetchall()

            await cursor.execute(
                "SELECT strftime('%Y-%m-%d %H:00', timestamp), COUNT(*), SUM(input_tokens + output_tokens) "
                "FROM ai_telemetry WHERE timestamp >= datetime('now', '-24 hours') "
                "GROUP BY strftime('%Y-%m-%d %H:00', timestamp) ORDER BY timestamp ASC"
            )
            hourly_traffic = await cursor.fetchall()

            return {
                "requests_24h": reqs_24h,
                "input_tokens_24h": in_tokens_24h,
                "output_tokens_24h": out_tokens_24h,
                "avg_latency_ms": avg_latency,
                "avg_context_msgs": avg_context,
                "failovers_24h": failovers_24h,
                "model_counts": model_counts,
                "trigger_counts": trigger_counts,
                "recent_failovers": recent_failovers,
                "hourly_traffic": hourly_traffic
            }

    async def get_guild_monthly_ai_usage(self, guild_id: int) -> dict:
        """Fetches the current calendar month's AI spend, token consumption, and model breakdown for a guild."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "SELECT COALESCE(SUM(estimated_cost), 0.0), COUNT(*), COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0) "
                "FROM ai_telemetry "
                "WHERE guild_id = ? AND timestamp >= datetime('now', 'start of month')",
                (guild_id,)
            )
            row = await cursor.fetchone()
            total_cost, total_prompts, total_in, total_out = row if row else (0.0, 0, 0, 0)

            await cursor.execute(
                "SELECT model_name, COUNT(*), COALESCE(SUM(estimated_cost), 0.0) "
                "FROM ai_telemetry "
                "WHERE guild_id = ? AND timestamp >= datetime('now', 'start of month') "
                "GROUP BY model_name ORDER BY COUNT(*) DESC LIMIT 5",
                (guild_id,)
            )
            top_models = await cursor.fetchall()

            return {
                "total_cost": float(total_cost or 0.0),
                "total_prompts": int(total_prompts or 0),
                "total_input_tokens": int(total_in or 0),
                "total_output_tokens": int(total_out or 0),
                "top_models": top_models
            }

    async def get_error_analytics_summary(self, limit: int = 8) -> dict:
        """Fetches error breakdown and recent traces."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT COUNT(*) FROM error_telemetry WHERE timestamp >= datetime('now', '-24 hours')")
            errors_24h = (await cursor.fetchone())[0] or 0

            await cursor.execute("SELECT error_type, COUNT(*) FROM error_telemetry WHERE timestamp >= datetime('now', '-24 hours') GROUP BY error_type ORDER BY COUNT(*) DESC LIMIT 5")
            top_errors = await cursor.fetchall()

            await cursor.execute("SELECT command_name, error_type, error_message, timestamp FROM error_telemetry ORDER BY timestamp DESC LIMIT ?", (limit,))
            recent_errors = await cursor.fetchall()

            return {
                "errors_24h": errors_24h,
                "top_errors": top_errors,
                "recent_errors": recent_errors
            }

    async def get_command_analytics_summary(self, limit: int = 8) -> dict:
        """Fetches command popularity and performance statistics."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT COUNT(*) FROM command_telemetry WHERE timestamp >= datetime('now', '-24 hours')")
            total_24h = (await cursor.fetchone())[0] or 0

            await cursor.execute("SELECT COUNT(*) FROM command_telemetry WHERE is_slash = 1 AND timestamp >= datetime('now', '-24 hours')")
            slash_24h = (await cursor.fetchone())[0] or 0

            await cursor.execute("SELECT command_name, COUNT(*) FROM command_telemetry WHERE timestamp >= datetime('now', '-24 hours') GROUP BY command_name ORDER BY COUNT(*) DESC LIMIT ?", (limit,))
            top_commands = await cursor.fetchall()

            await cursor.execute("SELECT command_name, AVG(execution_time_ms) FROM command_telemetry WHERE execution_time_ms IS NOT NULL AND timestamp >= datetime('now', '-24 hours') GROUP BY command_name ORDER BY AVG(execution_time_ms) DESC LIMIT 5")
            slowest_commands = await cursor.fetchall()

            return {
                "total_24h": total_24h,
                "slash_24h": slash_24h,
                "top_commands": top_commands,
                "slowest_commands": slowest_commands
            }

    async def get_game_analytics_summary(self, limit: int = 8) -> dict:
        """Fetches Connect 4 game statistics."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT COUNT(*), AVG(turns_count), AVG(duration_seconds) FROM game_telemetry")
            row = await cursor.fetchone()
            total_games = row[0] or 0
            avg_turns = round(row[1] or 0, 1)
            avg_duration = int(row[2] or 0)

            await cursor.execute("SELECT game_name, player1_id, player2_id, winner_id, turns_count, duration_seconds, timestamp FROM game_telemetry ORDER BY timestamp DESC LIMIT ?", (limit,))
            recent_games = await cursor.fetchall()

            return {
                "total_games": total_games,
                "avg_turns": avg_turns,
                "avg_duration": avg_duration,
                "recent_games": recent_games
            }

    async def get_media_analytics_summary(self, limit: int = 8) -> dict:
        """Fetches YouTube audio downloader statistics."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT COUNT(*), SUM(file_size_bytes) FROM media_telemetry")
            row = await cursor.fetchone()
            total_downloads = row[0] or 0
            total_bytes = row[1] or 0

            await cursor.execute("SELECT COUNT(*) FROM media_telemetry WHERE status = 'success'")
            successful_downloads = (await cursor.fetchone())[0] or 0

            await cursor.execute("SELECT user_id, duration_seconds, file_size_bytes, status, timestamp FROM media_telemetry ORDER BY timestamp DESC LIMIT ?", (limit,))
            recent_downloads = await cursor.fetchall()

            return {
                "total_downloads": total_downloads,
                "successful_downloads": successful_downloads,
                "total_bytes": total_bytes,
                "recent_downloads": recent_downloads
            }

    async def get_audit_analytics_summary(self, limit: int = 8) -> dict:
        """Fetches guild settings audit logs."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT COUNT(*) FROM settings_audit_telemetry")
            total_edits = (await cursor.fetchone())[0] or 0

            await cursor.execute("SELECT guild_id, user_id, setting_key, old_value, new_value, timestamp FROM settings_audit_telemetry ORDER BY timestamp DESC LIMIT ?", (limit,))
            recent_audits = await cursor.fetchall()

            return {
                "total_edits": total_edits,
                "recent_audits": recent_audits
            }

    async def get_heatmap_analytics_summary(self) -> dict:
        """Fetches server peak hour activity distribution."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT hour_bucket, SUM(message_count), SUM(bot_responses) FROM activity_heatmap_telemetry GROUP BY hour_bucket ORDER BY SUM(message_count) DESC LIMIT 6")
            peak_hours = await cursor.fetchall()

            return {
                "peak_hours": peak_hours
            }

    # ==========================================
    # --- USER ECONOMY & CASINO SYSTEM ---
    # ==========================================

    async def get_user_economy(self, user_id: int) -> dict:
        """Fetches user wallet and streak data. Creates new wallet with 1000.0€ if user is new."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "SELECT balance, daily_last_claimed, daily_streak, total_wagered, total_won FROM user_economy WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                await cursor.execute(
                    "INSERT INTO user_economy (user_id, balance, daily_streak, total_wagered, total_won) VALUES (?, 1000.0, 0, 0.0, 0.0)",
                    (user_id,)
                )
                await self.db.commit()
                return {
                    "user_id": user_id,
                    "balance": 1000.0,
                    "daily_last_claimed": None,
                    "daily_streak": 0,
                    "total_wagered": 0.0,
                    "total_won": 0.0
                }
            return {
                "user_id": user_id,
                "balance": float(row[0]),
                "daily_last_claimed": row[1],
                "daily_streak": int(row[2]),
                "total_wagered": float(row[3]),
                "total_won": float(row[4])
            }

    async def check_daily_status(self, user_id: int) -> Tuple[bool, Optional[int]]:
        """Checks whether a user is eligible to claim their daily bonus right now."""
        economy = await self.get_user_economy(user_id)
        last_claimed_str = economy.get("daily_last_claimed")
        if not last_claimed_str:
            return True, None

        import datetime
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        try:
            last_claimed_dt = datetime.datetime.fromisoformat(last_claimed_str.replace("Z", "+00:00"))
            if last_claimed_dt.tzinfo is None:
                last_claimed_dt = last_claimed_dt.replace(tzinfo=datetime.timezone.utc)
            diff = (now_dt - last_claimed_dt).total_seconds()
            if diff < 86400:
                next_claim_dt = last_claimed_dt + datetime.timedelta(days=1)
                return False, int(next_claim_dt.timestamp())
            return True, None
        except Exception:
            return True, None

    async def claim_daily(self, user_id: int) -> Tuple[bool, dict]:
        """Claims daily bonus (100€ base + 5€ per streak day). Enforces 24-hour cooldown."""
        import datetime
        economy = await self.get_user_economy(user_id)
        last_claimed_str = economy.get("daily_last_claimed")
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        current_streak = economy.get("daily_streak", 0)

        if last_claimed_str:
            try:
                last_claimed_dt = datetime.datetime.fromisoformat(last_claimed_str.replace("Z", "+00:00"))
                if last_claimed_dt.tzinfo is None:
                    last_claimed_dt = last_claimed_dt.replace(tzinfo=datetime.timezone.utc)
                diff = (now_dt - last_claimed_dt).total_seconds()
                
                # If claimed within the last 24 hours (86,400s), user cannot claim yet
                if diff < 86400:
                    next_claim_dt = last_claimed_dt + datetime.timedelta(days=1)
                    return False, {
                        "balance": economy["balance"],
                        "streak": current_streak,
                        "next_claim_timestamp": int(next_claim_dt.timestamp())
                    }
                
                # If claimed between 24h and 48h (172,800s), increment streak; otherwise reset streak to 1
                if diff <= 172800:
                    new_streak = current_streak + 1
                else:
                    new_streak = 1
            except Exception:
                new_streak = 1
        else:
            new_streak = 1

        reward = 100.0 + (5.0 * (new_streak - 1))
        new_balance = economy["balance"] + reward
        now_iso = now_dt.isoformat()

        async with self.db.cursor() as cursor:
            await cursor.execute(
                "UPDATE user_economy SET balance = ?, daily_last_claimed = ?, daily_streak = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (new_balance, now_iso, new_streak, user_id)
            )
            await self.db.commit()

        next_claim_dt = now_dt + datetime.timedelta(days=1)
        return True, {
            "reward": reward,
            "new_balance": new_balance,
            "streak": new_streak,
            "next_claim_timestamp": int(next_claim_dt.timestamp())
        }

    async def adjust_user_balance(self, user_id: int, delta: float) -> float:
        """Safely adjusts a user's wallet balance. Returns updated balance."""
        economy = await self.get_user_economy(user_id)
        new_balance = max(0.0, economy["balance"] + delta)
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "UPDATE user_economy SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (new_balance, user_id)
            )
            await self.db.commit()
        return new_balance

    async def get_blackjack_stats(self, user_id: int) -> dict:
        """Fetches blackjack-specific performance metrics for a user."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "SELECT wagered, won, hands_played, hands_won, hands_lost, hands_pushed, blackjacks, biggest_win FROM blackjack_stats WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return {
                    "user_id": user_id,
                    "wagered": 0.0,
                    "won": 0.0,
                    "hands_played": 0,
                    "hands_won": 0,
                    "hands_lost": 0,
                    "hands_pushed": 0,
                    "blackjacks": 0,
                    "biggest_win": 0.0
                }
            return {
                "user_id": user_id,
                "wagered": float(row[0]),
                "won": float(row[1]),
                "hands_played": int(row[2]),
                "hands_won": int(row[3]),
                "hands_lost": int(row[4]),
                "hands_pushed": int(row[5]),
                "blackjacks": int(row[6]),
                "biggest_win": float(row[7])
            }

    async def record_blackjack_hand(
        self,
        user_id: int,
        bet_amount: float,
        payout_amount: float,
        result_type: str,
        is_blackjack: bool = False,
        guild_id: Optional[int] = None,
        table_id: Optional[str] = None,
        table_name: Optional[str] = None,
        player_cards: Optional[str] = None,
        player_val: Optional[int] = None,
        dealer_cards: Optional[str] = None,
        dealer_val: Optional[int] = None,
        is_doubled: bool = False,
        is_split: bool = False
    ) -> None:
        """Updates user_economy, blackjack_stats, and logs blackjack_hand_telemetry."""
        profit = payout_amount - bet_amount
        won_inc = 1 if result_type in ('win', 'blackjack') else 0
        loss_inc = 1 if result_type == 'loss' else 0
        push_inc = 1 if result_type == 'push' else 0
        bj_inc = 1 if is_blackjack else 0

        async with self.db.cursor() as cursor:
            # 1. Update user_economy (bet was already deducted at deal time, add payout_amount to balance)
            await cursor.execute(
                "INSERT INTO user_economy (user_id, balance, total_wagered, total_won) "
                "VALUES (?, 1000.0 + ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "balance = MAX(0.0, balance + ?), "
                "total_wagered = total_wagered + ?, "
                "total_won = total_won + ?, "
                "updated_at = CURRENT_TIMESTAMP",
                (user_id, profit, bet_amount, payout_amount, payout_amount, bet_amount, payout_amount)
            )

            # 2. Update blackjack_stats
            await cursor.execute(
                "INSERT INTO blackjack_stats (user_id, wagered, won, hands_played, hands_won, hands_lost, hands_pushed, blackjacks, biggest_win) "
                "VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET "
                "wagered = wagered + ?, "
                "won = won + ?, "
                "hands_played = hands_played + 1, "
                "hands_won = hands_won + ?, "
                "hands_lost = hands_lost + ?, "
                "hands_pushed = hands_pushed + ?, "
                "blackjacks = blackjacks + ?, "
                "biggest_win = MAX(biggest_win, ?)",
                (
                    user_id, bet_amount, payout_amount, won_inc, loss_inc, push_inc, bj_inc, payout_amount,
                    bet_amount, payout_amount, won_inc, loss_inc, push_inc, bj_inc, payout_amount
                )
            )

            # 3. Log granular hand telemetry
            await cursor.execute(
                "INSERT INTO blackjack_hand_telemetry ("
                "guild_id, table_id, table_name, user_id, bet_amount, payout_amount, net_profit, "
                "result_type, player_cards, player_val, dealer_cards, dealer_val, "
                "is_doubled, is_split, is_blackjack"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    guild_id, table_id, table_name, user_id, bet_amount, payout_amount, profit,
                    result_type, player_cards, player_val, dealer_cards, dealer_val,
                    1 if is_doubled else 0, 1 if is_split else 0, 1 if is_blackjack else 0
                )
            )
            await self.db.commit()

    async def get_user_recent_hands(self, user_id: int, limit: int = 10) -> list[dict]:
        """Fetches the most recent hands played by a user."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "SELECT id, table_name, bet_amount, payout_amount, net_profit, result_type, "
                "player_cards, player_val, dealer_cards, dealer_val, is_doubled, is_split, "
                "is_blackjack, timestamp "
                "FROM blackjack_hand_telemetry WHERE user_id = ? "
                "ORDER BY id DESC LIMIT ?",
                (user_id, limit)
            )
            rows = await cursor.fetchall()
            return [
                {
                    "id": r[0],
                    "table_name": r[1],
                    "bet_amount": float(r[2]),
                    "payout_amount": float(r[3]),
                    "net_profit": float(r[4]),
                    "result_type": r[5],
                    "player_cards": r[6],
                    "player_val": r[7],
                    "dealer_cards": r[8],
                    "dealer_val": r[9],
                    "is_doubled": bool(r[10]),
                    "is_split": bool(r[11]),
                    "is_blackjack": bool(r[12]),
                    "timestamp": r[13]
                }
                for r in rows
            ]

    async def get_blackjack_leaderboards(self, limit: int = 5) -> dict:
        """Fetches top casino players by balance, total won, and blackjacks."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "SELECT user_id, balance, total_won FROM user_economy ORDER BY balance DESC LIMIT ?",
                (limit,)
            )
            top_balance = await cursor.fetchall()

            await cursor.execute(
                "SELECT user_id, won, hands_won, biggest_win FROM blackjack_stats ORDER BY won DESC LIMIT ?",
                (limit,)
            )
            top_winners = await cursor.fetchall()

            await cursor.execute(
                "SELECT user_id, blackjacks, hands_played FROM blackjack_stats WHERE blackjacks > 0 ORDER BY blackjacks DESC LIMIT ?",
                (limit,)
            )
            top_blackjacks = await cursor.fetchall()

            return {
                "top_balance": top_balance,
                "top_winners": top_winners,
                "top_blackjacks": top_blackjacks
            }

    # --- User Blacklist & Intelligence Dossier ---

    async def get_all_blacklisted_users(self) -> set[int]:
        """Fetches all blacklisted user IDs for in-memory caching."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT user_id FROM user_blacklist")
            rows = await cursor.fetchall()
            return {r[0] for r in rows}

    async def blacklist_user(self, user_id: int, reason: str = "Violated bot usage policies", admin_id: int = 0) -> None:
        """Globally blacklists a user from interacting with the bot."""
        async with self.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO user_blacklist (user_id, reason, blacklisted_by) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET reason = excluded.reason, blacklisted_by = excluded.blacklisted_by",
                (user_id, reason, admin_id)
            )
            await self.db.commit()

    async def unblacklist_user(self, user_id: int) -> None:
        """Removes a user from the global blacklist."""
        async with self.db.cursor() as cursor:
            await cursor.execute("DELETE FROM user_blacklist WHERE user_id = ?", (user_id,))
            await self.db.commit()

    async def get_user_audit_dossier(self, user_id: int) -> dict:
        """Aggregates deep intelligence on a user across all telemetry streams, commands, and AI queries."""
        async with self.db.cursor() as cursor:
            # 1. User Telemetry Profile
            await cursor.execute("SELECT first_seen, last_seen, total_commands_run FROM user_telemetry WHERE user_id = ?", (user_id,))
            u_row = await cursor.fetchone()
            profile = {
                "first_seen": u_row[0] if u_row else None,
                "last_seen": u_row[1] if u_row else None,
                "total_commands": u_row[2] if u_row else 0
            }

            # 2. Economy Profile
            await cursor.execute("SELECT balance, total_wagered, total_won, daily_streak FROM user_economy WHERE user_id = ?", (user_id,))
            e_row = await cursor.fetchone()
            profile["economy"] = {
                "balance": e_row[0] if e_row else 1000.0,
                "total_wagered": e_row[1] if e_row else 0.0,
                "total_won": e_row[2] if e_row else 0.0,
                "daily_streak": e_row[3] if e_row else 0
            }

            # 3. Blacklist Status
            await cursor.execute("SELECT reason, blacklisted_by, timestamp FROM user_blacklist WHERE user_id = ?", (user_id,))
            b_row = await cursor.fetchone()
            profile["blacklist"] = {
                "is_blacklisted": bool(b_row),
                "reason": b_row[0] if b_row else None,
                "blacklisted_by": b_row[1] if b_row else None,
                "timestamp": b_row[2] if b_row else None
            }

            # 4. Recent Command Executions (Last 10)
            await cursor.execute(
                "SELECT command_name, guild_id, channel_id, execution_time_ms, success, timestamp "
                "FROM command_telemetry WHERE user_id = ? ORDER BY id DESC LIMIT 10",
                (user_id,)
            )
            profile["recent_commands"] = await cursor.fetchall()

            # 5. Recent AI Queries & Prompts (Last 10)
            await cursor.execute(
                "SELECT model_name, provider, prompt_text, input_tokens, output_tokens, latency_ms, guild_id, channel_id, timestamp "
                "FROM ai_telemetry WHERE user_id = ? ORDER BY id DESC LIMIT 10",
                (user_id,)
            )
            profile["recent_ai"] = await cursor.fetchall()

            # 6. AI Aggregates
            await cursor.execute(
                "SELECT COUNT(*), SUM(input_tokens), SUM(output_tokens) FROM ai_telemetry WHERE user_id = ?",
                (user_id,)
            )
            ai_agg = await cursor.fetchone()
            profile["ai_total_queries"] = ai_agg[0] if ai_agg and ai_agg[0] else 0
            profile["ai_total_tokens"] = (ai_agg[1] or 0) + (ai_agg[2] or 0) if ai_agg else 0

            # 7. Recent Errors (Last 5)
            await cursor.execute(
                "SELECT command_name, error_type, error_message, guild_id, timestamp "
                "FROM error_telemetry WHERE user_id = ? ORDER BY id DESC LIMIT 5",
                (user_id,)
            )
            profile["recent_errors"] = await cursor.fetchall()

            return profile

    async def get_user_ai_history_paginated(self, user_id: int, page: int = 1, page_size: int = 5) -> Tuple[List[Tuple], int, int]:
        """Fetches paginated AI prompt logs for a specific user."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT COUNT(*) FROM ai_telemetry WHERE user_id = ?", (user_id,))
            total_count = (await cursor.fetchone())[0]
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            page = max(1, min(page, total_pages))
            offset = (page - 1) * page_size

            await cursor.execute(
                "SELECT model_name, provider, prompt_text, input_tokens, output_tokens, latency_ms, guild_id, channel_id, timestamp, estimated_cost "
                "FROM ai_telemetry WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (user_id, page_size, offset)
            )
            rows = await cursor.fetchall()
            return rows, total_count, total_pages

    async def get_user_command_history_paginated(self, user_id: int, page: int = 1, page_size: int = 8) -> Tuple[List[Tuple], int, int]:
        """Fetches paginated command execution logs for a specific user."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT COUNT(*) FROM command_telemetry WHERE user_id = ?", (user_id,))
            total_count = (await cursor.fetchone())[0]
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            page = max(1, min(page, total_pages))
            offset = (page - 1) * page_size

            await cursor.execute(
                "SELECT command_name, guild_id, channel_id, is_slash, execution_time_ms, success, timestamp "
                "FROM command_telemetry WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (user_id, page_size, offset)
            )
            rows = await cursor.fetchall()
            return rows, total_count, total_pages

    async def export_user_complete_audit_log(self, user_id: int, user_display: str = "Unknown") -> str:
        """Generates a complete forensic text transcript of every action ever taken by a user."""
        dossier = await self.get_user_audit_dossier(user_id)
        
        async with self.db.cursor() as cursor:
            # All commands
            await cursor.execute(
                "SELECT command_name, guild_id, channel_id, is_slash, execution_time_ms, success, timestamp "
                "FROM command_telemetry WHERE user_id = ? ORDER BY id ASC",
                (user_id,)
            )
            all_cmds = await cursor.fetchall()

            # All AI queries
            await cursor.execute(
                "SELECT model_name, provider, prompt_text, input_tokens, output_tokens, latency_ms, guild_id, channel_id, timestamp, estimated_cost "
                "FROM ai_telemetry WHERE user_id = ? ORDER BY id ASC",
                (user_id,)
            )
            all_ai = await cursor.fetchall()

            # All errors
            await cursor.execute(
                "SELECT command_name, error_type, error_message, traceback, guild_id, timestamp "
                "FROM error_telemetry WHERE user_id = ? ORDER BY id ASC",
                (user_id,)
            )
            all_errors = await cursor.fetchall()

        lines = [
            "=" * 70,
            f"FORENSIC AUDIT DOSSIER — USER {user_id} ({user_display})",
            "=" * 70,
            f"Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
            f"First Seen: {dossier.get('first_seen') or 'N/A'}",
            f"Last Seen: {dossier.get('last_seen') or 'N/A'}",
            f"Total Commands Run: {dossier.get('total_commands', 0):,}",
            f"Total AI Queries: {dossier.get('ai_total_queries', 0):,}",
            f"Total Tokens Consumed: {dossier.get('ai_total_tokens', 0):,}",
            f"Wallet Balance: {dossier.get('economy', {}).get('balance', 1000.0):,.2f}€",
            f"Blacklist Status: {'BLACKLISTED' if dossier.get('blacklist', {}).get('is_blacklisted') else 'CLEAR'}",
            "",
            "-" * 70,
            f"COMPLETE AI PROMPT & QUERY HISTORY ({len(all_ai)} records)",
            "-" * 70
        ]

        for i, (mname, prov, ptext, itok, otok, lat, gid, cid, ts, cost) in enumerate(all_ai, start=1):
            lines.append(f"[{i:04d}] {ts} UTC | Guild: {gid} | Channel: {cid} | Model: {mname} ({prov})")
            lines.append(f"       Tokens: In={itok or 0}, Out={otok or 0} | Latency: {lat}ms | Cost: ${cost or 0.0:.5f}")
            lines.append(f"       PROMPT: {ptext or '[No text captured]'}")
            lines.append("")

        lines.extend([
            "-" * 70,
            f"COMPLETE COMMAND EXECUTION HISTORY ({len(all_cmds)} records)",
            "-" * 70
        ])
        for i, (cname, gid, cid, is_slash, ex_time, succ, ts) in enumerate(all_cmds, start=1):
            slash_str = "Slash" if is_slash else "Prefix"
            status_str = "SUCCESS" if succ else "FAILED"
            lines.append(f"[{i:04d}] {ts} UTC | {status_str} | {slash_str} '{cname}' ({ex_time}ms) | Guild: {gid} | Channel: {cid}")

        if all_errors:
            lines.extend([
                "",
                "-" * 70,
                f"UNCAUGHT ERROR & CRASH LOG ({len(all_errors)} records)",
                "-" * 70
            ])
            for i, (cname, etype, emsg, tb, gid, ts) in enumerate(all_errors, start=1):
                lines.append(f"[{i:04d}] {ts} UTC | Command: '{cname}' | Error: {etype}: {emsg} | Guild: {gid}")
                if tb:
                    lines.append(f"       Traceback:\n{tb}")
                lines.append("")

        return "\n".join(lines)

    async def get_guild_audit_dossier(self, guild_id: int) -> dict:
        """Aggregates deep forensic intelligence for a specific Discord server."""
        async with self.db.cursor() as cursor:
            # 1. Guild Settings
            await cursor.execute("SELECT prefix, cbc, log_channel, is_premium, llm_primary, custom_prompt FROM guild_settings WHERE guild_id = ?", (guild_id,))
            s_row = await cursor.fetchone()
            settings = {
                "prefix": s_row[0] if s_row else "!",
                "cbc": s_row[1] if s_row else None,
                "log_channel": s_row[2] if s_row else None,
                "is_premium": bool(s_row[3]) if s_row else False,
                "llm_primary": s_row[4] if s_row else "gemini",
                "custom_prompt": s_row[5] if s_row else None
            }

            # 2. Join Event
            await cursor.execute("SELECT timestamp, member_count FROM guild_telemetry WHERE guild_id = ? AND event_type = 'join' ORDER BY id ASC LIMIT 1", (guild_id,))
            join_row = await cursor.fetchone()

            # 3. Usage Aggregates
            await cursor.execute("SELECT COUNT(*) FROM command_telemetry WHERE guild_id = ?", (guild_id,))
            total_commands = (await cursor.fetchone())[0]

            await cursor.execute("SELECT COUNT(*), SUM(input_tokens), SUM(output_tokens) FROM ai_telemetry WHERE guild_id = ?", (guild_id,))
            ai_row = await cursor.fetchone()
            total_ai = ai_row[0] if ai_row else 0
            total_tokens = ((ai_row[1] or 0) + (ai_row[2] or 0)) if ai_row else 0

            # 4. Top Active Users in Guild
            await cursor.execute(
                "SELECT user_id, COUNT(*) as cnt FROM command_telemetry WHERE guild_id = ? GROUP BY user_id ORDER BY cnt DESC LIMIT 5",
                (guild_id,)
            )
            top_users = await cursor.fetchall()

            # 5. Recent AI Queries in Guild
            await cursor.execute(
                "SELECT user_id, model_name, prompt_text, input_tokens, output_tokens, latency_ms, channel_id, timestamp "
                "FROM ai_telemetry WHERE guild_id = ? ORDER BY id DESC LIMIT 5",
                (guild_id,)
            )
            recent_ai = await cursor.fetchall()

            # 6. Recent Commands in Guild
            await cursor.execute(
                "SELECT user_id, command_name, channel_id, execution_time_ms, success, timestamp "
                "FROM command_telemetry WHERE guild_id = ? ORDER BY id DESC LIMIT 5",
                (guild_id,)
            )
            recent_cmds = await cursor.fetchall()

            return {
                "guild_id": guild_id,
                "settings": settings,
                "joined_at": join_row[0] if join_row else None,
                "initial_members": join_row[1] if join_row else None,
                "total_commands": total_commands,
                "total_ai_queries": total_ai,
                "total_tokens": total_tokens,
                "top_users": top_users,
                "recent_ai": recent_ai,
                "recent_commands": recent_cmds
            }

    async def get_guild_ai_history_paginated(self, guild_id: int, page: int = 1, page_size: int = 5) -> Tuple[List[Tuple], int, int]:
        """Fetches paginated AI prompt logs for an entire server."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT COUNT(*) FROM ai_telemetry WHERE guild_id = ?", (guild_id,))
            total_count = (await cursor.fetchone())[0]
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            page = max(1, min(page, total_pages))
            offset = (page - 1) * page_size

            await cursor.execute(
                "SELECT user_id, model_name, provider, prompt_text, input_tokens, output_tokens, latency_ms, channel_id, timestamp, estimated_cost "
                "FROM ai_telemetry WHERE guild_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (guild_id, page_size, offset)
            )
            rows = await cursor.fetchall()
            return rows, total_count, total_pages

    async def get_guild_command_history_paginated(self, guild_id: int, page: int = 1, page_size: int = 8) -> Tuple[List[Tuple], int, int]:
        """Fetches paginated command execution logs for an entire server."""
        async with self.db.cursor() as cursor:
            await cursor.execute("SELECT COUNT(*) FROM command_telemetry WHERE guild_id = ?", (guild_id,))
            total_count = (await cursor.fetchone())[0]
            total_pages = max(1, (total_count + page_size - 1) // page_size)
            page = max(1, min(page, total_pages))
            offset = (page - 1) * page_size

            await cursor.execute(
                "SELECT user_id, command_name, channel_id, is_slash, execution_time_ms, success, timestamp "
                "FROM command_telemetry WHERE guild_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                (guild_id, page_size, offset)
            )
            rows = await cursor.fetchall()
            return rows, total_count, total_pages

    async def export_guild_complete_audit_log(self, guild_id: int, guild_name: str = "Unknown") -> str:
        """Generates a complete forensic text transcript of every action ever taken inside a server."""
        dossier = await self.get_guild_audit_dossier(guild_id)

        async with self.db.cursor() as cursor:
            await cursor.execute(
                "SELECT user_id, command_name, channel_id, is_slash, execution_time_ms, success, timestamp "
                "FROM command_telemetry WHERE guild_id = ? ORDER BY id ASC",
                (guild_id,)
            )
            all_cmds = await cursor.fetchall()

            await cursor.execute(
                "SELECT user_id, model_name, provider, prompt_text, input_tokens, output_tokens, latency_ms, channel_id, timestamp, estimated_cost "
                "FROM ai_telemetry WHERE guild_id = ? ORDER BY id ASC",
                (guild_id,)
            )
            all_ai = await cursor.fetchall()

            await cursor.execute(
                "SELECT user_id, command_name, error_type, error_message, traceback, timestamp "
                "FROM error_telemetry WHERE guild_id = ? ORDER BY id ASC",
                (guild_id,)
            )
            all_errors = await cursor.fetchall()

        lines = [
            "=" * 70,
            f"FORENSIC SERVER AUDIT DOSSIER — GUILD {guild_id} ('{guild_name}')",
            "=" * 70,
            f"Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()}",
            f"Invited / Bot Joined: {dossier.get('joined_at') or 'N/A'}",
            f"Plan Status: {'PREMIUM 👑' if dossier.get('settings', {}).get('is_premium') else 'FREE'}",
            f"Total Server Commands: {dossier.get('total_commands', 0):,}",
            f"Total AI Queries: {dossier.get('total_ai_queries', 0):,}",
            f"Total Tokens: {dossier.get('total_tokens', 0):,}",
            "",
            "-" * 70,
            f"SERVER AI PROMPTS & CHAT LOGS ({len(all_ai)} records)",
            "-" * 70
        ]

        for i, (uid, mname, prov, ptext, itok, otok, lat, cid, ts, cost) in enumerate(all_ai, start=1):
            lines.append(f"[{i:04d}] {ts} UTC | User: {uid} | Channel: {cid} | Model: {mname} ({prov})")
            lines.append(f"       Tokens: In={itok or 0}, Out={otok or 0} | Latency: {lat}ms | Cost: ${cost or 0.0:.5f}")
            lines.append(f"       PROMPT: {ptext or '[No text captured]'}")
            lines.append("")

        lines.extend([
            "-" * 70,
            f"SERVER COMMAND EXECUTION HISTORY ({len(all_cmds)} records)",
            "-" * 70
        ])
        for i, (uid, cname, cid, is_slash, ex_time, succ, ts) in enumerate(all_cmds, start=1):
            slash_str = "Slash" if is_slash else "Prefix"
            status_str = "SUCCESS" if succ else "FAILED"
            lines.append(f"[{i:04d}] {ts} UTC | User: {uid} | {status_str} | {slash_str} '{cname}' ({ex_time}ms) | Channel: {cid}")

        if all_errors:
            lines.extend([
                "",
                "-" * 70,
                f"SERVER ERROR & CRASH LOG ({len(all_errors)} records)",
                "-" * 70
            ])
            for i, (uid, cname, etype, emsg, tb, ts) in enumerate(all_errors, start=1):
                lines.append(f"[{i:04d}] {ts} UTC | User: {uid} | Command: '{cname}' | Error: {etype}: {emsg}")
                if tb:
                    lines.append(f"       Traceback:\n{tb}")
                lines.append("")

        return "\n".join(lines)
