# Core Utilities (`cogs/utils/`)

This package contains shared system infrastructure, asynchronous database managers, global constants, and exception definitions.

---

## 📁 Files & Structure

* **`db.py` (`DatabaseManager`)**: Asynchronous SQLite manager using `asqlite`. Handles database initialization, table creation, migrations, server settings persistence, telemetry recording, and state storage.
* **`constants.py`**: Global UI constants, custom emojis (`Emojis`), error message formatters (`ErrorMessages`), and default configuration values (`DefaultSettings`).
* **`exceptions.py`**: Custom domain exceptions inheriting from `BotError` (e.g. `AIQuotaReachedError`, `AIRateLimitError`, `AISafetyBlockedError`, `AIServiceUnavailableError`, `AIConfigurationError`).

---

## 🗄️ Database Tables (`bot.db`)

| Table Name | Description | Key Columns |
| :--- | :--- | :--- |
| **`guild_settings`** | Server-specific configuration, tier flags, custom prompts, BYOK keys, and response footer toggles. | `guild_id`, `prefix`, `cbc`, `log_channel`, `llm_primary`, `llm_backup1`, `llm_backup2`, `llm_backup3`, `llm_timeout`, `show_model`, `reply_ping`, `is_premium`, `custom_prompt`, `byok_gemini_key`, `byok_xai_key`, `byok_openai_key`, `byok_anthropic_key`, `footer_show_icon`, `footer_show_name`, `footer_show_tokens`, `footer_show_latency` |
| **`guild_weekly_usage`** | Weekly token and image generation consumption tracking per server. | `guild_id`, `week_start`, `total_tokens`, `input_tokens`, `output_tokens`, `prompt_count`, `image_count`, `last_image_ts`, `created_at`, `updated_at` |
| **`ai_summon`** | Active AI channel listening sessions. | `channel_id`, `expiry` |
| **`ai_usage`** | Daily token consumption tracking. | `day`, `request_count`, `input_tokens`, `output_tokens` |
| **`system_state`** | Ephemeral system state (e.g. restart/update metadata). | `key`, `value` |
| **`command_telemetry`** | Execution latency and success metrics for commands. | `id`, `guild_id`, `channel_id`, `user_id`, `command_name`, `is_slash`, `execution_time_ms`, `success`, `timestamp` |
| **`ai_telemetry`** | Granular AI request metadata, tokens, cost, and failover reasons. | `id`, `model_name`, `provider`, `input_tokens`, `output_tokens`, `estimated_cost`, `latency_ms`, `failover_occurred`, `failover_reason`, `timestamp` |
| **`error_telemetry`** | Uncaught command and event exceptions with full tracebacks. | `id`, `guild_id`, `channel_id`, `user_id`, `command_name`, `error_type`, `error_message`, `traceback`, `timestamp` |
| **`system_telemetry`** | Hourly hardware health & scale metrics (CPU, RAM, Disk, bot latency, DB size, uptime, guild count, total members). | `id`, `cpu_usage_pct`, `ram_usage_pct`, `disk_usage_pct`, `websocket_latency_ms`, `sqlite_db_size_bytes`, `uptime_seconds`, `guild_count`, `total_members_count`, `timestamp` |
| **`user_telemetry`** | User activity, first seen, and lifetime engagement. | `user_id`, `first_seen`, `last_seen`, `total_commands_run` |
| **`guild_telemetry`** | Server join and leave event history. | `id`, `guild_id`, `event_type`, `member_count`, `timestamp` |
| **`game_telemetry`** | Match statistics for Connect 4 matches. | `id`, `guild_id`, `channel_id`, `game_name`, `player1_id`, `player2_id`, `winner_id`, `turns_count`, `duration_seconds`, `timestamp` |
| **`media_telemetry`** | YouTube audio download and conversion history. | `id`, `guild_id`, `user_id`, `url`, `duration_seconds`, `file_size_bytes`, `status`, `timestamp` |
| **`settings_audit_telemetry`** | Audit trail of server configuration edits. | `id`, `guild_id`, `user_id`, `setting_key`, `old_value`, `new_value`, `timestamp` |
| **`activity_heatmap_telemetry`** | Hourly channel message volume and bot replies. | `id`, `guild_id`, `channel_id`, `message_count`, `bot_responses`, `hour_bucket`, `timestamp` |
| **`user_economy`** | Global user wallet balance, daily reward claims, streak, and lifetime betting volume. | `user_id`, `balance`, `daily_last_claimed`, `daily_streak`, `total_wagered`, `total_won`, `created_at`, `updated_at` |
| **`blackjack_stats`** | Deep aggregated statistics for Blackjack players. | `user_id`, `wagered`, `won`, `hands_played`, `hands_won`, `hands_lost`, `hands_pushed`, `blackjacks`, `biggest_win` |
| **`guild_weekly_usage`** | Weekly AI token usage, prompt counts, and image counts per server. | `guild_id`, `week_start`, `total_tokens`, `input_tokens`, `output_tokens`, `prompt_count`, `image_count`, `last_image_ts`, `created_at`, `updated_at` |
| **`guild_subscriptions`** | Stripe customer and subscription status per server. | `guild_id`, `customer_id`, `subscription_id`, `status`, `user_id`, `price_id`, `current_period_end`, `cancel_at_period_end`, `created_at`, `updated_at` |

---

## 💡 Developer Guidelines

* **Database Engine & WAL Mode**: SQLite operates in `WAL` (Write-Ahead Logging) mode (`PRAGMA journal_mode=WAL;`) with a 5000ms busy timeout, allowing concurrent asynchronous reads and non-blocking writes.
* **Performance Indexes**: Frequently sorted/filtered tables have dedicated indexes (e.g. `idx_user_economy_balance`, `idx_blackjack_stats_won`, `idx_command_telemetry_ts`, `idx_ai_telemetry_ts`) to ensure instant leaderboards and telemetry aggregation.
* **Database Migrations**: When adding new columns to `guild_settings`, always write a dynamic `PRAGMA table_info` check in `DatabaseManager.initialize()` in `db.py` to prevent errors when upgrading existing deployments.
* **Forensic Audit Exporters**: `DatabaseManager` includes full transcript dumpers (`export_user_complete_audit_log`, `export_guild_complete_audit_log`) and paginated telemetry queries (`get_user_ai_history_paginated`, `get_user_command_history_paginated`, `get_guild_ai_history_paginated`, `get_guild_command_history_paginated`) for zero-truncation developer auditing.
* **Settings Cache**: `self.bot.settings_cache` mirrors `guild_settings` in memory. Any modification via `db_manager.update_guild_setting` must also update `bot.settings_cache[guild.id]`.
