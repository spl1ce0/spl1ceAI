# AI Subsystem (`cogs/ai/`)

This package manages all Large Language Model (LLM) communications, multi-tier provider failovers, multimodal file ingestion, and message response orchestration.

---

## 📁 Files & Structure

* **`cog.py` (`AI`)**: The Discord Cog front-end. Defines `/ask`, `/summarize`, `/summon`, and the `on_message` listener. Handles session lifecycles, duration timers, warning throttling, and real-time AI transaction telemetry logging (`ai_telemetry`).
* **`ai.py`**: The core AI processing engine containing model client abstraction classes, prompt builders, failover orchestrators, and latency/model tracking metadata.
* **`models.json`**: Model provider catalog defining supported model endpoints, providers (Google Gemini, OpenAI, Anthropic, xAI Grok), API formats, and capability flags.

---

## 🧩 Key Architecture Components (`ai.py`)

### 1. `ModelManager`
* Central router for all AI execution requests.
* Resolves the server's configured primary and fallback model stack from guild settings (`llm_primary`, `llm_fallback1`, `llm_fallback2`).
* Executes models sequentially within an `asyncio.wait_for` timeout window. If a model encounters a rate limit, service outage, or timeout, it automatically cascades down to the next fallback model.

### 2. `ContextManager`
* Extracts and standardizes conversation history from Discord channels.
* Multimodal payload ingestion:
  * **Images**: Reads raw bytes and attaches mime types for visual models.
  * **Code / Text Files (`.py`, `.json`, `.txt`, etc.)**: Reads UTF-8 content and injects it directly as contextual code blocks in the prompt.
  * **Recent History Attachment Limit (`HISTORY_ATTACHMENT_LIMIT = 3`)**: Automatically scans the last 3 history messages for attachments without causing bandwidth bloat.

### 3. `ResponseHandler`
* Manages formatting, model subtext injection (`show_model` setting), single-message delivery (<2000 character limit enforcement without splitting), and Discord reply routing.
* Respects server configuration flags such as author ping preferences (`reply_ping` setting).

---

## 🔄 Supported Model Providers & Classes

| Provider | Class | Protocol / SDK |
| :--- | :--- | :--- |
| **Google Gemini** | `GeminiModel` | `google-genai` native SDK |
| **OpenAI** | `OpenAIModel` | `openai.AsyncOpenAI` (Chat Completions & Responses API) |
| **Anthropic Claude** | `AnthropicModel` | `anthropic.AsyncAnthropic` |
| **xAI Grok** | `GrokModel` | `xai-sdk` (OpenAI compatibility layer) |
