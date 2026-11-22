# Core Utilities (`cogs/utils/`)

This package contains shared system infrastructure, asynchronous database managers, global constants, and exception definitions.

---

## 📁 Files & Structure

* **`db.py` (`DatabaseManager`)**: Asynchronous SQLite manager using `asqlite`. Handles database initialization, table creation, migrations, server settings persistence, telemetry recording, and state storage.
* **`constants.py`**: Global UI constants, custom emojis (`Emojis`), domain URLs (`URLs`), onboarding copy (`WelcomeMessages`), error message formatters (`ErrorMessages`), and default configuration values (`DefaultSettings`).
* **`cards.py` (`NotificationCardView`)**: Discord Components V2 notification card framework providing notification builders (`build_confirmation_card`, `build_info_card`, `build_warning_card`, `build_progress_card`), onboarding cards (`build_guild_welcome_card`, `build_invite_card`, `build_support_card`), and unified async dispatchers (`send_confirmation`, `send_info`, `send_warning`) with color-accented containers and action buttons.
* **`exceptions.py`**: Custom domain exceptions inheriting from `BotError` across AI (`AIError`, `AIQuotaReachedError`), Economy (`EconomyError`, `InsufficientBalanceError`, `DailyAlreadyClaimedError`), and Tools (`ToolError`, `InvalidURLError`, `MediaTooLongError`, `MediaDownloadError`).

---

## 🗄️ Database Tables (`bot.db`)

`bot.py` opens `asqlite.connect("bot.db")`, so the file is created in the process working directory (the repo root when you run `python3 bot.py` from there).

| Table Name | Description | Key Columns |
| :--- | :--- | :--- |
| **`guild_settings`** | Server configuration. New rows come from `DefaultSettings.get_defaults_dict()`, not from the `CREATE TABLE` defaults. Hosted model choice does not read `llm_*`; see `cogs/ai/README.md`. | `guild_id`, `prefix`, `cbc`, `log_channel`, `llm_primary`, `llm_backup1`, `llm_backup2`, `llm_backup3`, `llm_timeout`, `reply_ping`, `is_premium`, `custom_prompt`, `byok_gemini_key`, `byok_xai_key`, `byok_openai_key`, `byok_anthropic_key`, `byok_deepseek_key`, `byok_glm_key`, `byok_primary_model`, `byok_fallback_model`, `byok_enabled`, `footer_show_icon`, `footer_show_name`, `footer_show_tokens`, `footer_show_latency` |
| **`guild_weekly_usage`** | Weekly token and image generation consumption tracking per server. | `guild_id`, `week_start`, `total_tokens`, `input_tokens`, `output_tokens`, `prompt_count`, `image_count`, `last_image_ts`, `created_at`, `updated_at` |
| **`ai_summon`** | Active AI channel listening sessions. | `channel_id`, `expiry` |
| **`ai_usage`** | Daily token consumption tracking. | `day`, `request_count`, `input_tokens`, `output_tokens` |
| **`system_state`** | Ephemeral system state (e.g. restart/update metadata). | `key`, `value` |
| **`command_telemetry`** | Execution latency and success metrics for commands. | `id`, `guild_id`, `channel_id`, `user_id`, `command_name`, `is_slash`, `execution_time_ms`, `success`, `timestamp` |
| **`ai_telemetry`** | Per-request AI metadata. `prompt_text` is added by a `PRAGMA table_info` migration when missing. | `id`, `guild_id`, `channel_id`, `user_id`, `model_name`, `provider`, `input_tokens`, `output_tokens`, `estimated_cost`, `latency_ms`, `context_messages_count`, `finish_reason`, `trigger_type`, `prompt_chars`, `response_chars`, `failover_occurred`, `failover_reason`, `prompt_text`, `timestamp` |
| **`error_telemetry`** | Uncaught command and event exceptions with full tracebacks. | `id`, `guild_id`, `channel_id`, `user_id`, `command_name`, `error_type`, `error_message`, `traceback`, `timestamp` |
| **`system_telemetry`** | Hardware and scale samples. The analytics cog writes a row every 5 minutes, not once an hour. | `id`, `cpu_usage_pct`, `ram_usage_pct`, `disk_usage_pct`, `websocket_latency_ms`, `sqlite_db_size_bytes`, `uptime_seconds`, `guild_count`, `total_members_count`, `timestamp` |
| **`user_telemetry`** | User activity, first seen, and lifetime engagement. | `user_id`, `first_seen`, `last_seen`, `total_commands_run` |
| **`guild_telemetry`** | Server join and leave event history. | `id`, `guild_id`, `event_type`, `member_count`, `timestamp` |
| **`game_telemetry`** | Generic match rows written by `log_game_result`. Connect 4's end-of-game path calls `record_c4_match` instead, which is not defined, so finished Connect 4 games do not land here today. | `id`, `guild_id`, `channel_id`, `game_name`, `player1_id`, `player2_id`, `winner_id`, `turns_count`, `duration_seconds`, `timestamp` |
| **`blackjack_hand_telemetry`** | One row per settled blackjack hand (`record_blackjack_hand`). | `id`, `guild_id`, `table_id`, `table_name`, `user_id`, `bet_amount`, `payout_amount`, `net_profit`, `result_type`, `player_cards`, `player_val`, `dealer_cards`, `dealer_val`, `is_doubled`, `is_split`, `is_blackjack`, `timestamp` |
| **`media_telemetry`** | Schema and `log_media_download` exist. `cogs/tools.py` does not call that method, so `/ytmp3` does not insert rows. | `id`, `guild_id`, `user_id`, `url`, `duration_seconds`, `file_size_bytes`, `status`, `timestamp` |
| **`settings_audit_telemetry`** | Audit trail of server configuration edits. | `id`, `guild_id`, `user_id`, `setting_key`, `old_value`, `new_value`, `timestamp` |
| **`api_latency_telemetry`** | Table and `log_api_latency` exist. No cog calls `log_api_latency`, so this table stays empty unless something else writes it. | `id`, `service_name`, `endpoint`, `http_status`, `latency_ms`, `success`, `timestamp` |
| **`activity_heatmap_telemetry`** | Hourly channel message volume and bot replies. | `id`, `guild_id`, `channel_id`, `message_count`, `bot_responses`, `hour_bucket`, `timestamp` |
| **`user_economy`** | Global user wallet balance, daily reward claims, streak, and lifetime betting volume. | `user_id`, `balance`, `daily_last_claimed`, `daily_streak`, `total_wagered`, `total_won`, `created_at`, `updated_at` |
| **`blackjack_stats`** | Deep aggregated statistics for Blackjack players. | `user_id`, `wagered`, `won`, `hands_played`, `hands_won`, `hands_lost`, `hands_pushed`, `blackjacks`, `biggest_win` |
| **`guild_subscriptions`** | Polar customer and subscription status per server. `variant_id` is in the `CREATE TABLE`. `price_id` is added later if missing. | `guild_id`, `customer_id`, `subscription_id`, `status`, `user_id`, `variant_id`, `price_id`, `current_period_end`, `cancel_at_period_end`, `created_at`, `updated_at` |
| **`user_blacklist`** | Global command/AI block list loaded into `bot.blacklist_cache` at startup. | `user_id`, `reason`, `blacklisted_by`, `timestamp` |

There is no `c4_stats` table. These calls have no matching `DatabaseManager` method: `get_c4_leaderboards`, `get_user_c4_stats`, `record_c4_match`, `get_wealth_leaderboard` (games), and `update_subscription_status` (Polar `subscription.updated` / `canceled` / `revoked`).

---

## 💡 Developer Guidelines

* **Database Engine & WAL Mode**: SQLite operates in `WAL` (Write-Ahead Logging) mode (`PRAGMA journal_mode=WAL;`) with a 5000ms busy timeout, allowing concurrent asynchronous reads and non-blocking writes.
* **Performance indexes** created in `initialize()`: `idx_user_economy_balance`, `idx_blackjack_stats_won`, `idx_command_telemetry_ts`, `idx_ai_telemetry_ts`, `idx_error_telemetry_ts`, `idx_game_telemetry_ts`, `idx_command_telemetry_user`, `idx_ai_telemetry_user`.
* **Database Migrations**: When adding new columns to `guild_settings`, always write a dynamic `PRAGMA table_info` check in `DatabaseManager.initialize()` in `db.py` to prevent errors when upgrading existing deployments.
* **Forensic Audit Exporters & Telemetry Queries**: `DatabaseManager` includes full transcript dumpers (`export_user_complete_audit_log`, `export_guild_complete_audit_log`), paginated telemetry queries (`get_user_ai_history_paginated`, `get_user_command_history_paginated`, `get_guild_ai_history_paginated`, `get_guild_command_history_paginated`), paginated user directory lookups (`get_users_paginated`), multi-timeframe server growth aggregators (`get_server_growth_history`), and multi-dimension guild audit aggregation (`get_guild_audit_dossier` with top active channels and users) for zero-truncation developer auditing.
* **Settings Cache & Querying**: `self.bot.settings_cache` mirrors `guild_settings` in memory. Any modification via `db_manager.update_guild_setting` must also update `bot.settings_cache[guild.id]`. Guild settings can be queried on-demand via `db_manager.get_guild_settings(guild_id)` or bulk loaded during bot initialization via `db_manager.get_all_guild_settings()`.
