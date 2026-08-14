# AGENTS.md

> **Notice for AI Coding Agents**: This document contains architectural rules, guidelines, and invariants for the `spl1ceAI` repository. You **MUST** read and follow these rules when developing or modifying code in this codebase.

---

## 🏗️ Architecture & Core Patterns

1. **Separation of Concerns**:
   * **Discord Cogs (`cogs/*.py`)**: Focus strictly on Discord interaction handling, user input parsing, and dispatching to business logic.
   * **Subsystems (`cogs/ai/`, `cogs/games/`, etc.)**: Implement core business logic, API integrations, and algorithms independently from Discord command boilerplates.
   * **Utilities (`cogs/utils/`)**: Contain database operations (`db.py`), shared constants/emojis (`constants.py`), and custom exception hierarchies (`exceptions.py`).

2. **The "Happy Path" Principle for Commands**:
   * Do **NOT** wrap command logic with duplicate `try/except` blocks for known domain errors (e.g. rate limits, safety blocks, quotas).
   * **Raise custom exceptions** (inheriting from `BotError` in `cogs/utils/exceptions.py`).
   * Let exceptions bubble up to the global error handler (**`cogs/errors.py`**), which is responsible for user-facing error formatting and telemetry logging.

3. **Settings & Cache Invariant**:
   * Guild configuration is cached in memory on the bot instance: `self.bot.settings_cache[guild_id]`.
   * When updating settings, **ALWAYS** update both the database (`self.bot.db_manager.update_guild_setting`) and the in-memory cache (`self.bot.settings_cache[guild_id]`).

4. **Database & Schema Migrations**:
   * Uses `asqlite` for asynchronous SQLite database access.
   * When adding new columns or tables, update `DatabaseManager.initialize()` in `cogs/utils/db.py` to include dynamic `PRAGMA table_info` migration checks to avoid breaking existing databases.

---

## 🛠️ Validation & Quality Checks

Before concluding any code change turn:
1. **Compile Check**: Run Python compilation across all modified files:
   ```bash
   python3 -m py_compile path/to/file.py
   ```
2. **Git Diff Inspection**: Verify with `git diff` that no unrelated comments, formatting, or files were altered.

---

## 📝 Mandatory Documentation Maintenance Rule

> [!IMPORTANT]
> **Strict Agent Requirement**: Whenever you add, modify, or remove features in any directory, you **MUST** update the corresponding `README.md` file in that folder to reflect the changes (e.g., updating method lists, data structures, or configuration schemas). Keep documentation concise, accurate, and structured.
