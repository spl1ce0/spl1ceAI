<div align="center">

# 🤖 spl1ceAI

**A multi-model Discord AI bot built for speed, reliability, and fun.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/Discord.py-2.6%2B-5865F2.svg?style=for-the-badge&logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)
[![SQLite](https://img.shields.io/badge/SQLite-asqlite-003B57.svg?style=for-the-badge&logo=sqlite&logoColor=white)](https://github.com/Rapptz/asqlite)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

</div>

---

## 📖 About

**spl1ceAI** is a self-hostable Discord bot designed to make chatting with AI seamless in your server.

Instead of relying on a single API that might go down or hit rate limits, it uses an automatic failover system across multiple providers (Gemini, OpenAI, Claude, and Grok). If your primary model is busy or down, it instantly falls back to the next one without interrupting the conversation.

On top of AI chat, it includes interactive games like Connect 4 (with an AI opponent), media tools, server logging, and an in-Discord settings dashboard.

---

## ✨ Features

* **Multi-Provider AI Fallback:** Seamlessly switches between Gemini, OpenAI, Claude, and Grok if a model is unavailable or rate-limited.
* **Multimodal Chat:** Understands images, screenshots, and text/code files (`.py`, `.json`, `.txt`, etc.) uploaded in chat or recent history.
* **Channel Summoning:** Make the bot listen and participate in a channel (`/summon [duration]`) or set a permanent chatbot channel.
* **Connect 4:** Play against friends or challenge an AI opponent with interactive buttons.
* **Media & Utility Tools:** Download audio from YouTube (`/ytmp3`), inspect high-res user avatars (`/avatar`), generate quote images (`/quote`), and more.
* **Interactive Settings:** Configure prefixes, model priority, channels, and preferences directly via `/settings`.
* **Telemetry & Logging:** Automated health monitoring (CPU, RAM, latency) and audit logs for deleted/edited messages.

---

## 🚀 Quickstart

### Prerequisites
* **Python 3.10+**
* A [Discord Bot Token](https://discord.com/developers/applications) with **Message Content**, **Server Members**, and **Presence** gateway intents enabled.
* At least one AI API key (Gemini, OpenAI, Anthropic, or xAI).

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-username/spl1ceAI.git
cd spl1ceAI

# 2. Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
nano .env

# 5. Run the bot
python3 bot.py
```

---

## ⚙️ Configuration (`.env`)

| Variable | Description |
| :--- | :--- |
| `DISCORD_TOKEN` | Your Discord bot token (Required) |
| `GEMINI_API_KEY` | Google Gemini API key (Optional) |
| `OPENAI_API_KEY` | OpenAI API key (Optional) |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key (Optional) |
| `XAI_API_KEY` | xAI Grok API key (Optional) |

---

## 🤝 Contributing

Contributions, bug reports, and feature suggestions are always welcome!

1. **Fork the repo** and create your branch (`git checkout -b feature/cool-feature`).
2. **Make your changes** and verify they work cleanly.
3. **Commit your changes** (`git commit -m 'feat: add cool feature'`).
4. **Push to your branch** (`git push origin feature/cool-feature`).
5. **Open a Pull Request**.

Feel free to open an **Issue** if you spot a bug or have an idea for a new feature.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

