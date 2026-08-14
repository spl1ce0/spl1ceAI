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
| **`guild_settings`** | Server-specific configuration and model failover stack. | `guild_id`, `prefix`, `cbc`, `log_channel`, `llm_primary`, `llm_backup1`, `llm_backup2`, `llm_backup3`, `llm_timeout`, `show_model`, `reply_ping` |
| **`ai_summon`** | Active AI channel listening sessions. | `channel_id`, `expiry` |
| **`ai_usage`** | Daily token consumption tracking. | `day`, `request_count`, `input_tokens`, `output_tokens` |
| **`system_state`** | Ephemeral system state (e.g. restart/update metadata). | `key`, `value` |
| **`command_telemetry`** | Execution latency and success metrics for commands. | `id`, `guild_id`, `channel_id`, `user_id`, `command_name`, `is_slash`, `execution_time_ms`, `success`, `timestamp` |
| **`ai_telemetry`** | Granular AI request metadata, tokens, cost, and failover reasons. | `id`, `model_name`, `provider`, `input_tokens`, `output_tokens`, `estimated_cost`, `latency_ms`, `failover_occurred`, `failover_reason`, `timestamp` |
| **`error_telemetry`** | Uncaught command and event exceptions with full tracebacks. | `id`, `guild_id`, `channel_id`, `user_id`, `command_name`, `error_type`, `error_message`, `traceback`, `timestamp` |
| **`health_telemetry`** | Hourly hardware health metrics (CPU, RAM, Disk, bot latency). | `id`, `cpu_percent`, `ram_used_mb`, `ram_total_mb`, `disk_used_gb`, `bot_latency_ms`, `guild_count`, `active_summons_count`, `timestamp` |

---

## 💡 Developer Guidelines

* **Database Migrations**: When adding new columns to `guild_settings`, always write a dynamic `PRAGMA table_info` check in `DatabaseManager.initialize()` in `db.py` to prevent errors when upgrading existing deployments.
* **Settings Cache**: `self.bot.settings_cache` mirrors `guild_settings` in memory. Any modification via `db_manager.update_guild_setting` must also update `bot.settings_cache[guild.id]`.
