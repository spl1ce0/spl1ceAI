# Analytics Subsystem (`cogs/analytics/`)

This package powers the bot owner's telemetry and intelligence suite, providing deep operational visibility across infrastructure, servers, users, AI consumption, commands, errors, and real-time hardware diagnostics.

---

## 📁 Architecture & Directory Structure

```
cogs/analytics/
├── __init__.py                  # Extension setup entrypoint
├── cog.py                       # Analytics(commands.Cog): CLI dispatcher, telemetry collectors, background tasks
├── views.py                     # AnalyticsLayoutView: central layout router, navigation stack, and attachment handler
├── charts.py                    # Matplotlib dark-mode chart generators (uptime sparkline, AI hourly traffic)
└── containers/                  # Discord Components V2 UI Containers
    ├── __init__.py              # Container exports
    ├── home.py                  # Minimal analytics home: core pulse (Servers, Users, 24h Uptime) & navigation rows
    ├── servers.py               # Servers overview, paginated server list, server dossier, settings audit, and server AI logs
    ├── users.py                 # Users overview, paginated user list, user dossier, global blacklist control, and user AI logs
    ├── uptime.py                # Dedicated 24h uptime subpage with incident logs & visual sparkline chart
    ├── ai.py                    # AI token consumption, real-money costs ($), model distribution, and failover incident logs
    ├── system.py                # Real-time VPS diagnostics (psutil CPU, RAM, Disk, SQLite DB size, WebSocket ping)
    ├── errors.py                # Uncaught exception telemetry, top error types, and full traceback modal/inspector
    ├── activity.py              # Command executions, slash vs prefix ratio, slowest commands, and hourly activity heatmap
    └── modals.py                # Interactive Discord modal inputs (InspectGuildModal, InspectUserModal, BlacklistModal)
```

---

## 🧭 Navigation & Subpage Schema

```
Home (!analytics)
├── 🏢 Servers Suite ([ Servers → ])
│   ├── 📋 Server List (Paginated directory of all guilds)
│   └── 🔍 Server Dossier (Plan, token consumption, top 3 active channels, top 3 active users)
│       ├── ⚙️ Server Settings Audit (Prefix, system prompt snippet, primary/backup models, logs channel)
│       ├── 🤖 AI Query Logs (Paginated list of AI prompts executed in server with latency & tokens)
│       └── 📜 Command History (Paginated execution log of all commands in server)
├── 👥 Users Suite ([ Users → ])
│   ├── 📋 User List (Paginated directory of all registered users from telemetry)
│   └── 🔍 User Dossier (Mutual guilds, blacklist status, token volume)
│       ├── 🚫 Blacklist / Unblacklist (Instant toggle with reason modal)
│       ├── 🤖 AI Query Logs (Paginated prompts submitted by user)
│       └── 📜 Command History (Paginated command executions by user)
├── ⏱️ Uptime Subpage ([ 24h Sparkline ])
│   └── Detailed 24h uptime percentage, downtime incident history, and dark-mode sparkline chart
├── 🤖 AI Subpage
│   └── 24h token volume, real-money costs ($), model distribution, latency breakdown, and traffic chart
├── ⚡ System Subpage
│   └── Real-time VPS diagnostics (CPU, RAM, Disk, DB size, WebSocket latency)
├── 🚨 Errors Subpage
│   └── Top exception breakdown and full traceback inspector
└── 📊 Activity Subpage
    └── Command execution metrics, slash vs prefix ratio, slowest commands, and hourly activity heatmap
```

---

## ⚡ Developer Commands

* `!analytics`: Opens the interactive Developer Analytics Dashboard.
* `!analytics [category] [target]`: Direct shortcut navigation (e.g. `!analytics server 123456789`, `!analytics user 987654321`, `!analytics ai`, `!analytics system`).
* `!inspect <user>`: Directly renders the User Dossier container in `cogs/dev.py`.
* `!inspectguild <guild_id>`: Directly renders the Server Dossier container in `cogs/dev.py`.
