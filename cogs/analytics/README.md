# Analytics Subsystem (`cogs/analytics/`)

This package powers the bot owner's telemetry and intelligence suite, providing deep operational visibility across infrastructure, servers, users, AI consumption, commands, errors, and real-time hardware diagnostics.

---

## 📁 Architecture & Directory Structure

```
cogs/analytics/
├── __init__.py                  # Extension setup entrypoint
├── cog.py                       # Analytics(commands.Cog): CLI dispatcher, telemetry collectors, background tasks
├── views.py                     # AnalyticsLayoutView: central layout router, navigation stack, and attachment handler
├── charts.py                    # Matplotlib (Agg backend) charts: uptime, server growth (1d/1w/1m/1y), 24h AI traffic, 24h error counts
└── containers/                  # Discord Components V2 UI Containers
    ├── __init__.py              # Container exports
    ├── home.py                  # Minimal analytics home: core pulse (Servers, Users, 24h dynamic sparkline) & navigation rows
    ├── servers.py               # Servers overview with 1D/1W/1M/1Y growth chart, paginated server list with 1-click inspect, dossier, settings audit, and server AI logs
    ├── users.py                 # Users overview, paginated user list with 1-click inspect, dossier, global blacklist control, and user AI logs
    ├── uptime.py                # Dedicated 24h uptime subpage with incident logs & discordstatus.com style segmented sparkline chart
    ├── ai.py                    # AI token consumption, real-money costs ($), model distribution, and failover incident logs
    ├── system.py                # Real-time VPS diagnostics (psutil CPU, RAM, Disk, SQLite DB size, WebSocket ping)
    ├── errors.py                # Uncaught exception telemetry, 24h error frequency chart, and full traceback modal/inspector
    ├── activity.py              # Two containers: command counts (slash vs prefix, slowest commands) and the hourly message heatmap
    └── modals.py                # Interactive Discord modal inputs (InspectGuildModal, InspectUserModal, BlacklistModal)
```

---

## 🧭 Navigation & Subpage Schema

```
Home (!analytics)
├── Servers (button "Servers →")
│   ├── Server list (current bot.guilds, not departed guilds)
│   └── Server dossier (plan, token totals, top 3 channels and top 3 users from a top-5 query)
│       ├── Settings card (prefix, stored llm_primary, log channel, custom prompt preview)
│       ├── AI query log
│       └── Command history
├── Users (button "Users →")
│   ├── User list (user_telemetry)
│   └── User dossier (blacklist flag, command/AI totals)
│       └── Mutual servers counted with guild.get_member only (cache; members intent is off)
│       ├── Blacklist / unblacklist modal
│       ├── AI query log
│       └── Command history
├── Uptime (button "Uptime Details →")
│   └── 24h uptime from system_telemetry samples (the collector loop is every 5 minutes)
├── AI Engine
│   └── 24h tokens, model mix, latency, failover rows, traffic chart.
│       The dollar figure on this page is (input/1e6 * 0.15) + (output/1e6 * 0.60).
│       It is not the sum of ai_telemetry.estimated_cost.
├── System / VPS
│   └── psutil CPU, RAM, disk, SQLite file size, gateway latency
├── Errors & Logs
│   └── Exception counts, 24h chart, traceback view
├── Commands & Activity
│   └── 24h command counts, slash vs prefix split, slowest commands
└── Heatmap & Traffic
    └── Hourly message and bot-reply counts from activity_heatmap_telemetry
```

---

## ⚡ Developer Commands

* `analytics` (prefix aliases `telemetry`, `dev_stats`): owner-only hybrid command. Opens the dashboard.
* Category shortcuts handled in `Analytics.analytics`: `user`/`u` plus an id, `server`/`guild`/`s`/`g` (id optional; current guild if omitted), `servers`/`guilds`, `users`, `uptime`/`up`, `ai`/`llm`, `sys`/`system`/`hardware`/`hw`, `errors`/`error`/`err`, `commands`/`traffic`/`cmd`, `heatmap`/`heat`. Anything else renders home.
* `inspect` and `inspectguild` are owner hybrid commands in `cogs/dev.py`. They build the same `AnalyticsLayoutView` dossiers. `inspectguild` accepts `this` for the current guild. Prefix aliases are listed on those decorators (`audituser`, `guilddossier`, and the others next to `name=`).
