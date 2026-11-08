<div align="center">

# 🤖 spl1ceAI

**A Discord bot with a personality and fun features.**

[![Python](https://img.shields.io/badge/Python-3.13%2B-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Discord.py](https://img.shields.io/badge/Discord.py-2.6%2B-5865F2.svg?style=for-the-badge&logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)
[![SQLite](https://img.shields.io/badge/SQLite-asqlite-003B57.svg?style=for-the-badge&logo=sqlite&logoColor=white)](https://github.com/Rapptz/asqlite)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)

</div>

---

## 📖 About

**spl1ceAI** is a Discord bot with AI related features, including an AI chatbot (powered by the support of several models from different providers), a Connect 4 agent with different difficulty levels, more minigames and tools.

It is designed to be self-hostable by anyone and easy to operate.

---

## ✨ Features

* **Hosted AI fallback:** The default pipeline in `cogs/ai/models.json` tries `gemini-3.8-flash`, then `gemini-3.7-flash`, when the first model times out or returns a retryable error. OpenAI, Anthropic, xAI, DeepSeek, and Z.ai GLM are used when a server enables Bring Your Own Key (BYOK) and selects those models.
* **Multimodal chat:** Premium servers, and servers with a stored Gemini, xAI, OpenAI, or Anthropic key, can send images plus text files (`.py`, `.json`, `.txt`, and the other extensions checked in `ContextManager`). Free servers stay text-only.
* **Channel summoning:** `/summon` listens in the current channel for a duration (default `10m`; also `30s`, `1h`, and similar). A chatbot channel set in `/settings` stays on. In both cases the bot replies to @mentions and replies to itself.
* **Connect 4:** Play a friend in-channel, queue across servers, or play an MCTS opponent from the button UI.
* **Media and utility tools:** `/ytmp3` extracts YouTube audio with `yt-dlp` and FFmpeg (15-minute cap, 25 MB Discord upload cap). `/avatar`, `/invite`, and `/support` live in the tools cog. `/quote` is a fun-cog image card.
* **Interactive settings:** `/settings` edits the prefix, chatbot channel, log channel, reply pings, BYOK keys, a two-model BYOK stack, custom system instructions, and reply-footer toggles. The hosted model order stays in `models.json`.
* **Telemetry and logging:** The owner command `!analytics` samples CPU, RAM, disk, and gateway latency. Deleted and edited messages are copied to the configured log channel.

---

## 🚀 Quickstart

### Prerequisites
* **Python 3.13+.** `requirements.txt` pins `audioop-lts==0.2.2`, and that release declares `Requires-Python >=3.13`. On Python 3.12.3, `pip install -r requirements.txt --dry-run` stopped there and did not resolve the rest of the file. The bot sources themselves use `list[tuple]` and `set[int]` (syntax from 3.9 onward). `discord.py` is pinned at `2.6.4`.
* A [Discord Bot Token](https://discord.com/developers/applications) with the **Message Content** intent enabled. `bot.py` turns on `intents.message_content` and does not enable the Server Members or Presence intents.
* `GEMINI_API_KEY` if you want the hosted Gemini pipeline to run. Other provider keys are optional and are used for BYOK or for image-generation fallbacks.
* **FFmpeg** on `PATH` for `/ytmp3` and the TikTok download commands (`/sealion`, `/anoomals`). It is not a pip package.

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/spl1ce0/spl1ceAI.git
cd spl1ceAI

# 2. Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
# .env.example is a starting file only. Add the keys in the table below
# that the example does not list (Polar, DeepSeek, GLM, and the aliases).
cp .env.example .env
nano .env

# 5. Run the bot
python3 bot.py
```

---

## ⚙️ Configuration (`.env`)

Names below are the ones `os.getenv` actually reads. `.env.example` is older: it still lists `PORT` and `LEMONSQUEEZY_*`, and it omits Polar, DeepSeek, and GLM. The process does not read `PORT` or any `LEMONSQUEEZY_*` variable. The billing HTTP server binds `DefaultSettings.WEBHOOK_PORT` (`8080` in `cogs/utils/constants.py`).

| Variable | Description |
| :--- | :--- |
| `DISCORD_TOKEN` | Discord bot token. Required. The process exits the start path if this is missing. |
| `GEMINI_API_KEY` | Google Gemini key for the hosted pipeline. |
| `GEMINI_PROXY_URL` or `GEMINI_BASE_URL` | Optional Gemini client base URL. `GEMINI_PROXY_URL` is checked first. |
| `OPENAI_API_KEY` | OpenAI key (BYOK and the OpenAI image fallback). |
| `ANTHROPIC_API_KEY` | Anthropic key (BYOK). |
| `XAI_API_KEY` or `GROK_API_KEY` | xAI key. `XAI_API_KEY` is checked first. Used for Grok chat and `grok-imagine-image`. |
| `DEEPSEEK_API_KEY` | DeepSeek key (BYOK). |
| `GLM_API_KEY`, `ZHIPU_API_KEY`, or `ZAI_API_KEY` | Z.ai / GLM key. Checked in that order. |
| `POLAR_ACCESS_TOKEN` or `POLAR_API_KEY` | Polar.sh API token for checkout and subscription sync. |
| `POLAR_PRODUCT_ID` | Polar product used when creating a checkout. |
| `POLAR_WEBHOOK_SECRET` | Standard Webhooks signing secret. If it is unset, signature verification is skipped and the webhook handler accepts the body. |
| `POLAR_ORGANIZATION_SLUG` | Portal slug. Defaults to `spl1ceai` when unset. |

The in-bot Premium label is `2.99€` (`DefaultSettings.PREMIUM_PRICE_EUR`). What customers are charged is the price of `POLAR_PRODUCT_ID` in Polar, which this repository does not set.

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

