# Cogs Directory (`cogs/`)

This directory contains all the Discord command cogs and extensions loaded by `bot.py` during startup.

---

## 📁 Sub-Packages

* **[`ai/`](./ai/README.md)**: Large Language Model subsystem (multi-provider failover pipeline, multimodal context preparation, vision & code attachment processing, customizable response footers).
* **[`analytics/`](./analytics/README.md)**: Comprehensive developer intelligence and telemetry suite (servers/users dossiers, paginated lists, AI prompt queries, real-time VPS diagnostics, uptime sparkline charts, error tracebacks, and activity heatmaps).
* **[`billing/`](./billing/README.md)**: Premium subscription checkout and portal management via Polar.sh with comparative plan paginator.
* **[`games/`](./games/README.md)**: Connect 4 (MCTS opponent, local PvP, in-process matchmaking) and a Blackjack table engine with button UI.
* **[`utils/`](./utils/README.md)**: Core utilities, asynchronous database management (`DatabaseManager`), exception hierarchies, notification card framework (`NotificationCardView`), and shared constants.

---

## 📄 Top-Level Cogs

| Cog File | Class Name | Key Commands / Listeners | Description |
| :--- | :--- | :--- | :--- |
| **`dev.py`** | `Dev` | Prefix groups `!extensions` (`!ext`) `reload`/`load`/`unload`, `!update bot`/`!update web`, `!restart`, `!commands remove`/`clear`/`sync`, `!logs`, `!set_premium`. Hybrids: `inspect`, `inspectguild`, `testwelcome`, `blacklist`, `unblacklist`, `givemoney` | Owner-only maintenance. `inspect` / `inspectguild` render analytics dossiers. `!commands` with no subcommand does not list commands. `!logs` pages `discord.log` or `ai.log`. |
| **`errors.py`** | `ErrorHandler` | `on_app_command_error`, `on_command_error` | Turns command errors into Components V2 `ErrorCardView` cards (relative-time cooldown text, incident IDs on unexpected errors) and writes `error_telemetry`. |
| **`fun.py`** | `Fun` | `are_you_alive`, `sealion`, `anoomals` (prefix alias `anoomols`), `ban`, `quote` | Liveness check, TikTok collection downloads via `yt-dlp` (FFmpeg), a fake ban card, and quote images (Pillow + Pilmoji). |
| **`help.py`** | `Help` | `help` (prefix aliases `h`, `cmds`, `bothelp`) | Two-level command browser. The `dev` category is hidden unless `bot.is_owner` is true for the invoker. |
| **`logs.py`** | `Logs` | `on_raw_message_delete`, `on_message_edit` | Posts Components V2 cards to `guild_settings.log_channel`. There is no `on_message_delete` listener and no `logs_channel` column. Uncached deletes still get a short card. |
| **`settings.py`** | `Settings` | `settings` (prefix alias `config`) | Prefix, chatbot channel, log channel, reply ping, BYOK toggle and provider-key modal, BYOK primary/fallback models, system-instructions editor, and footer toggles. Changes are written with `update_guild_setting` and `settings_audit_telemetry`. This UI does not edit `llm_primary` / `llm_backup*`. |
| **`tools.py`** | `Tools` | `ytmp3` (prefix aliases `mp3`, `download`), `avatar` (`av`, `pfp`), `invite` (`addbot`, `add`), `support` (`helpdesk`, `community`) | YouTube to MP3 via `yt-dlp` + FFmpeg (`FFmpegExtractAudio`, 192 kbps), avatar card, invite card, support card. |
| **`dashboard_api.py`** | Module (not a cog) | `GET /api/settings/schema`, `GET /api/bot/guilds`, `GET/POST /api/guilds/{guild_id}/settings`, `GET /api/guilds/{guild_id}/quota` | Imported by `PolarWebhookServer` when the billing cog starts. It is not in `initial_extensions`. Routes sit on the same aiohttp app as the Polar webhook. |

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

Slash command names are the `name=` on each hybrid or slash command. Values in `aliases=` are prefix aliases only. The extensions loaded from `bot.py` are `cogs.games`, `cogs.dev`, `cogs.fun`, `cogs.ai`, `cogs.settings`, `cogs.logs`, `cogs.tools`, `cogs.errors`, `cogs.analytics`, `cogs.billing`, and `cogs.help`.
