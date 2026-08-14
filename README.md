<div align="center">

# 🤖 spl1ceAI

**An advanced, multi-provider AI Discord bot with automatic failovers, multimodal file processing, interactive mini-games, and deep telemetry.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/Discord.py-2.6%2B-5865F2.svg?style=for-the-badge&logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)
[![SQLite](https://img.shields.io/badge/SQLite-asqlite-003B57.svg?style=for-the-badge&logo=sqlite&logoColor=white)](https://github.com/Rapptz/asqlite)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

[Features](#-key-features) • [Quickstart](#-quickstart--self-hosting) • [Configuration](#%EF%B8%8F-configuration) • [Architecture](#-codebase-architecture) • [Agentic Engineering](#-agent-instructions)

</div>

---

## ✨ Key Features

### 🧠 Multi-Provider AI Failover Engine
* **Zero-Downtime Cascading:** Supports **Google Gemini**, **OpenAI (GPT-4o/o3)**, **Anthropic Claude**, and **xAI Grok**. If a primary model encounters a rate limit, timeout, or service disruption, the request automatically falls back to secondary models in the server's configured priority stack.
* **Multimodal Attachment Ingestion:** Automatically reads and converts image attachments (`.png`, `.jpg`, `.webp`) and parses text/code attachments (`.py`, `.json`, `.txt`, `.md`, `.csv`, etc.) from current messages and recent chat history.
* **Channel Summoning & Listening:** Summon the AI to chat continuously in a channel (`/summon [duration]`) or designate a persistent auto-reply channel (`/settings` ➔ Chatbot Channel).

### 🎮 Interactive Connect 4 (with MCTS AI)
* **PvP & PvE Modes:** Challenge friends or battle a built-in AI opponent powered by **Monte Carlo Tree Search (MCTS)** with **Upper Confidence Bound for Trees (UCT)** running asynchronously via multiprocessing.
* **Modern UI:** Built with Discord ActionRow buttons and custom board emojis.

### ⚙️ Interactive Server Settings Dashboard
* Control bot behavior per-guild using Discord UI components (`/settings`):
  * Custom command prefixes.
  * Dedicated chatbot and server audit log channels.
  * Customizable primary and multi-tier fallback model hierarchy.
  * Model attribution tag toggles and reply ping preferences.

### 📊 Deep Telemetry & Diagnostics
* **Hardware & Health Metrics:** Hourly automated background logging tracking CPU, RAM, Disk usage, WebSocket ping, and active guild stats.
* **AI Cost & Performance Analytics:** Granular token usage tracking, response latencies, and failover occurrence logging.
* **Central Error Tracking:** Catches unhandled exceptions and logs complete stack traces to SQLite database telemetry tables.

### 🛠️ Developer & Admin Tools
* Owner-only command suite (`!ext reload/load/unload`, `!sync`, `!update`, `!restart`).
* Interactive in-Discord log viewer with paginated UI and log-file switcher (`discord.log` / `ai.log`).

---

## 🚀 Quickstart & Self-Hosting

### Prerequisites
* **Python 3.10+**
* A [Discord Bot Token](https://discord.com/developers/applications) with **Message Content**, **Server Members**, and **Presence** gateway intents enabled.
* API keys for at least one supported AI provider (e.g. Google Gemini, OpenAI, Anthropic, or xAI).

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/spl1ceAI.git
cd spl1ceAI
```

### 2. Set Up Virtual Environment & Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Secrets
Copy the template and fill in your keys:
```bash
cp .env.example .env
nano .env
```

### 4. Run the Bot
```bash
python3 bot.py
```

---

## ⚙️ Configuration (`.env`)

| Variable | Description | Required |
| :--- | :--- | :---: |
| `DISCORD_TOKEN` | Discord Bot Application Token | **Yes** |
| `GEMINI_API_KEY` | Google Gemini API Key | Optional* |
| `OPENAI_API_KEY` | OpenAI Platform API Key | Optional* |
| `ANTHROPIC_API_KEY` | Anthropic Console API Key | Optional* |
| `XAI_API_KEY` | xAI Grok API Key | Optional* |

*\* Note: At least one AI provider key must be configured for AI features to function.*

---

## 🏗️ Codebase Architecture

```text
spl1ceAI/
├── bot.py                  # Bot entry point, extension loader, and DB lifecycle
├── requirements.txt        # Pinned Python package dependencies
├── AGENTS.md               # Strict architecture guidelines for AI coding agents
├── cogs/
│   ├── README.md           # Overview of all cogs and registration guidelines
│   ├── ai/                 # Core AI subsystem (models.json, ModelManager, ContextManager)
│   ├── games/              # Connect 4 game engine (MCTS AI & UI Views)
│   ├── utils/              # DatabaseManager (asqlite), constants, exceptions
│   ├── analytics.py        # Automated hardware & health telemetry background loop
│   ├── dev.py              # Developer management, extension reloading, interactive logs
│   ├── errors.py           # Global error handler and database telemetry logger
│   ├── fun.py              # Entertainment commands (TikTok scraper, Quote card generator)
│   ├── logs.py             # Server audit logging (deletions, edits)
│   ├── settings.py         # Interactive UI server configuration dashboard
│   └── tools.py            # Utility commands (YouTube MP3 converter, avatar viewer)
```

For detailed internal documentation on specific components, visit the respective directory README files linked above.

---

## 🤖 Agent Instructions

This repository is engineered to be **agent-friendly**. If you are an AI coding assistant working on this codebase:
* Read and adhere strictly to **[`AGENTS.md`](./AGENTS.md)** before proposing or applying code changes.
* Maintain the "Happy Path" command pattern and bubble custom exceptions to `cogs/errors.py`.
* Ensure that any new or modified feature is reflected in the corresponding directory's `README.md`.

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.
