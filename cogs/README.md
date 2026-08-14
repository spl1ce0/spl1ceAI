# Cogs Directory (`cogs/`)

This directory contains all the Discord command cogs and extensions loaded by `bot.py` during startup.

---

## 📁 Sub-Packages

* **[`ai/`](./ai/README.md)**: Large Language Model subsystem (multi-provider failover pipeline, multimodal context preparation, vision & code attachment processing).
* **[`games/`](./games/README.md)**: Interactive Connect 4 game engine with Monte Carlo Tree Search (MCTS) AI and ActionRow button UI.
* **[`utils/`](./utils/README.md)**: Core utilities, asynchronous database management (`DatabaseManager`), exception hierarchies, and shared constants.

---

## 📄 Top-Level Cogs

| Cog File | Class Name | Key Commands / Listeners | Description |
| :--- | :--- | :--- | :--- |
| **`analytics.py`** | `Analytics` | Background loop | Collects hourly system hardware metrics (CPU, RAM, Disk, latency), guild count, and command execution stats to `health_telemetry`. |
| **`dev.py`** | `Dev` | `!alive`, `!ext`, `!update`, `!restart`, `!commands`, `!logs` | Owner-only maintenance commands, extension hot-reloading, tree syncing, update shell script runner, and interactive log viewer (`discord.log`, `ai.log`). |
| **`errors.py`** | `ErrorHandler` | `on_app_command_error`, `on_command_error` | Central error handler translating exceptions into user-friendly embeds/messages and recording crash telemetry in `error_telemetry`. |
| **`fun.py`** | `Fun` | `/sealion`, `/anoomals`, `/ban`, `/quote` | Random TikTok video scrapers/downloaders (`yt-dlp`), fake ban UI container card, and dynamic image quote card generation (Pillow + Pilmoji). |
| **`logs.py`** | `Logs` | `on_message_delete`, `on_raw_message_delete`, `on_message_edit` | Audit logging sending rich embeds to configured server `logs_channel`. |
| **`settings.py`** | `Settings` | `/settings` | Interactive server dashboard UI managing prefix, chatbot channel (`cbc`), logs channel, fallback model stack, model tag display, and author ping settings. |
| **`tools.py`** | `Tools` | `/ytmp3`, `/avatar` | YouTube audio extractor (`yt-dlp` to MP3) and high-resolution user avatar inspector with direct CDN links. |

---

## 💡 Developer Guidelines for Adding New Cogs

1. Create your cog file in this directory with a class inheriting from `commands.Cog`.
2. Implement the async setup entry point at the bottom of the file:
   ```python
   async def setup(bot):
       await bot.add_cog(YourCogName(bot))
   ```
3. Register the extension string in `bot.py` under the `initial_extensions` list.
4. Update this `README.md` file with your new cog's details.
