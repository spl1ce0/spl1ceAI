# AI Subsystem (`cogs/ai/`)

This package manages all Large Language Model (LLM) communications, fixed 3-tier disaster-recovery failover pipelines, weekly token quotas, Bring Your Own Key (BYOK) routing, and message response orchestration.

---

## 📁 Files & Structure

* **`cog.py` (`AI`)**: The Discord Cog front-end. Defines `/quota` (`/usage`), `/ask`, `/summarize`, `/summon`, and the `on_message` listener. Handles session lifecycles, duration timers, weekly token quota checks (Free Snapshot Tier vs Premium Guild Plan vs BYOK), and real-time AI transaction telemetry logging (`ai_telemetry`).
* **`ai.py`**: The core AI processing engine containing model client abstraction classes, prompt builders with custom server persona injection, 3-tier disaster-resilient failover orchestrators, per-model token/image cost calculators, and latency/model tracking metadata.
* **`models.json`**: Model catalog defining supported endpoints, providers (Google Gemini, OpenAI, Anthropic, xAI Grok), API formats, and capability flags.

---

## 🛡️ Dynamic Config-Driven Failover Pipeline

Standard queries are automatically routed through a 2-tier pipeline defined in `models.json` (`pipeline` list):

1. 🥇 **Primary Brain:** `gemini-3.7-flash` (Google) — Fast, natural human conversation with live Google Search grounding.
2. 🥈 **Tier 2 Fallback:** `gemini-3.6-flash` (Google) — High-throughput backup with vision and search.

### 🔑 Custom BYOK 2-Model Pipeline
Servers using **Bring Your Own Key (BYOK)** can configure their own custom 2-model pipeline (Primary & Fallback) in `/settings`. The selection menu dynamically filters and displays only models matching the server's linked API keys (Gemini, xAI Grok, OpenAI, Anthropic, DeepSeek, GLM).

---

## 💳 Quota & Monetization Tiers

| Feature | 🆓 Free Snapshot Plan (0.00€) | 👑 Premium Guild Plan (2.99€/mo) | 🔑 BYOK Mode (Bring Your Own Key) |
| :--- | :--- | :--- | :--- |
| **Weekly Token Pool** | **100,000 tokens / week** | **1,000,000 tokens / week** | **Unlimited / Unmetered** |
| **Reset Cycle** | Mondays 00:00 UTC | Mondays 00:00 UTC | N/A (Billed to user's key) |
| **AI Model Brain** | `gemini-3.7-flash` | `gemini-3.7-flash` | Selected / Configured provider |
| **Context Window** | 5 msgs (`/ask`) • 15 msgs (chat) | 30 msgs everywhere | 30 msgs everywhere |
| **Vision (Images)** | ❌ Disabled (Text-only) | ✅ Full image attachment analysis | ✅ Full image attachment analysis |
| **Image Generation** | 1 image every 2 weeks | 5 images / week (20/month) | Unlimited |
| **Custom Persona** | Default `spl1ceAI` persona | Custom system prompt (via `/settings`) | Custom system prompt (via `/settings`) |

---

## 🎯 Message Trigger Mechanics

1. **Inside ChatBot Channel (`cbc`)**:
   * Automatically replies **only to direct @mentions and message replies to the bot**. Unrelated channel chatter is ignored.
2. **Outside ChatBot Channel**:
   * The bot remains completely idle unless an admin or user runs `/summon` (starts an active listening session that replies to mentions/replies) or a user invokes the explicit `/ask` command.

---

## 🧩 Key Architecture Components (`ai.py`)

### 1. `ModelManager`
* Central router for all AI execution requests.
* Executes the 3-tier disaster pipeline sequentially within an `asyncio.wait_for` timeout window.
* Automatically injects custom server prompts when enabled.

### 2. `ContextManager`
* Extracts and standardizes conversation history with tier-aware depth (5, 15, or 30 messages) and active session age cutoff (45-minute recency window).
* Non-duplicative reply referencing (`[User] (replying to Target): message`) avoiding redundant quote token burn.
* Multimodal payload ingestion with `enable_vision` flag:
  * **Images**: Reads raw bytes and attaches mime types for visual models when vision is enabled (Premium & BYOK).
  * **Code / Text Files (`.py`, `.json`, `.txt`, etc.)**: Reads UTF-8 content and injects it directly as contextual code blocks in the prompt.
  * **Recent History Attachment Limit (`HISTORY_ATTACHMENT_LIMIT = 3`)**: Automatically scans the last 3 history messages for attachments when vision is active.

### 3. `ResponseHandler`
* Manages formatting, rich footer subtext injection (`show_model` setting with custom provider emoji, execution latency, and token consumption), hard 800-token completion limits (preventing runaway token burn), and Discord reply routing.
