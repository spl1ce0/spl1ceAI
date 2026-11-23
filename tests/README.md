# Tests (`tests/`)

Automated unit tests using Python's built-in `unittest` module.

## Files

* **`test_command_limits.py`**: Walks every cog under `cogs/` and validates all hybrid/app commands, parameters, choices, and serialized payloads against Discord's length and naming limits.
* **`test_db.py`**: Runs `DatabaseManager.initialize()` and `initialize_default_guild_settings()` against a temporary SQLite database via `asqlite` to verify default guild row insertion and idempotency.
* **`test_idea.py`**: Covers title/body formatting, GitHub REST API issue & label handling (`cogs/utils/github.py`), owner-only gating and replies for `!idea` (`cogs/dev.py`), and `ErrorHandler` integration (`cogs/errors.py`) with mocked HTTP calls.

## Running

```bash
python3 -m unittest discover -s tests -v
```
