# Cogs Directory (`cogs/`)

This directory contains all the Discord command cogs and extensions loaded by `bot.py` during startup.

---

## 📁 Sub-Packages

* **[`ai/`](./ai/README.md)**: Large Language Model subsystem (multi-provider failover pipeline, multimodal context preparation, vision & code attachment processing, customizable response footers).
* **[`billing/`](./billing/README.md)**: Premium subscription checkout and portal management via Polar.sh with comparative plan paginator.
* **[`games/`](./games/README.md)**: Interactive Connect 4 game engine with Monte Carlo Tree Search (MCTS) AI, Blackjack casino engine, and ActionRow button UI.
* **[`utils/`](./utils/README.md)**: Core utilities, asynchronous database management (`DatabaseManager`), exception hierarchies, and shared constants.

---

## 📄 Top-Level Cogs

| Cog File | Class Name | Key Commands / Listeners | Description |
| :--- | :--- | :--- | :--- |
| **`analytics.py`** | `Analytics` | Background loop, `on_message`, `on_command_completion` | Collects 5-minute system hardware metrics, hourly activity heatmap traffic, guild events, and command execution stats. |
| **`dev.py`** | `Dev` | `!alive`, `!ext`, `!update`, `!restart`, `!commands`, `!logs`, `!analytics`, `!inspect`, `!inspectguild`, `!blacklist`, `!unblacklist`, `/givemoney` | Owner-only maintenance commands, extension hot-reloading, tree syncing, interactive log viewer, telemetry dashboard, user & guild intelligence dossiers, paginated prompt history browsers, forensic text log exporter, global blacklist controls, and wallet balance adjustments. |
| **`errors.py`** | `ErrorHandler` | `on_app_command_error`, `on_command_error` | Central error handler translating exceptions into Discord Components V2 `ErrorCardView` container cards with actionable buttons, dynamic countdowns, incident IDs, and telemetry recording in `error_telemetry`. |
| **`fun.py`** | `Fun` | `/sealion`, `/anoomals`, `/ban`, `/quote` | Random TikTok video scrapers/downloaders (`yt-dlp`), fake ban UI container card, and dynamic image quote card generation (Pillow + Pilmoji). |
| **`help.py`** | `Help` | `/help` (`/h`, `/cmds`, `/bothelp`) | Dynamic 2-level interactive command center with category browsing, detailed command inspector, permissions badging, and owner-only dev category filtering. |
| **`logs.py`** | `Logs` | `on_message_delete`, `on_raw_message_delete`, `on_message_edit` | Audit logging sending rich embeds to configured server `logs_channel`. |
| **`settings.py`** | `Settings` | `/settings` | Interactive server dashboard UI managing prefix, chatbot channel (`cbc`), logs channel, fallback model stack, granular AI reply footer customization submenu, and author ping settings with audit telemetry trail (`settings_audit_telemetry`). |
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
