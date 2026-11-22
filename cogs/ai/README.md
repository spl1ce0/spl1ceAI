# AI Subsystem (`cogs/ai/`)

This package manages LLM calls, the hosted two-model failover list, weekly token quotas, Bring Your Own Key (BYOK) routing, and message replies.

---

## 📁 Files & Structure

* **`cog.py` (`AI`)**: Discord cog. Slash names are `quota`, `ask`, `summarize`, and `summon`. Prefix aliases: `quota` → `usage`, `aiquota`, `budget`; `ask` → `llm`, `ai`; `summarize` → `tldr`, `aint_readin_allat`. Also listens on `on_message`. Checks weekly quotas and writes `ai_telemetry`.
* **`ai.py`**: Provider clients, prompt assembly (including a server custom prompt when Premium or BYOK applies), the failover loop in `ModelManager.execute`, per-model token/image cost fields from `models.json`, and reply chunking.
* **`models.json`**: Catalog of provider, model id, vision/search/image flags, and prices. Providers present in the file: Google Gemini, OpenAI, Anthropic, xAI, DeepSeek, and Z.ai GLM. The hosted order is the top-level `pipeline` array.

---

## 🛡️ Failover pipeline

`ModelManager.execute` walks a list inside `asyncio.wait_for`. Safety and configuration errors abort the loop. Timeouts, rate limits, and other service errors try the next name.

Hosted servers (BYOK off, or BYOK on without a primary/fallback selection) use `models.json` → `pipeline`:

1. `gemini-3.8-flash`
2. `gemini-3.7-flash`

Both entries set `supports_vision` and `supports_search`. Whether search is actually attached depends on that provider client's code path, not on the flag alone.

`guild_settings.llm_primary` and `llm_backup1`–`llm_backup3` are stored and shown on the analytics settings card. `execute` does not read them. `/settings` does not edit them. New guilds are filled from `DefaultSettings` (`llm_backup2` defaults to `grok-4.3`, `llm_backup3` to `disabled`), which can differ from the `CREATE TABLE` defaults in `db.py`.

### Image generation

If the model text contains `[GENERATE_IMAGE: ...]`, `Model._generate_image` calls xAI `grok-imagine-image` when the Grok OpenAI-compatible client exists (`XAI_API_KEY` or `GROK_API_KEY`). On failure, `GeminiModel` tries `gemini-2.5-flash-image` and `OpenAIModel` tries `gpt-image-2`. DeepSeek and GLM catalog rows set `supports_image_gen` to false, so those models do not enter this path. Claude rows omit the flag, which defaults to false.

### BYOK two-model list

With `byok_enabled` and at least one stored provider key, `/settings` can set `byok_primary_model` and `byok_fallback_model`. The menu lists catalog models for providers that have a key on that guild (Gemini, xAI, OpenAI, Anthropic, DeepSeek, GLM). Those two names replace `pipeline` for that request. The per-call timeout starts at `llm_timeout` (default 15 seconds) and adds 90 seconds when the selected model has `supports_image_gen`.

---

## 💳 Quota & Monetization Tiers

Limits below are the constants and branches in `DefaultSettings`, `check_ai_quota_allowance`, and `cogs/ai/cog.py`. The `2.99€` figure is the in-bot label, not a price this repo sends to Polar.

| Feature | Free (`is_premium` off, BYOK not active) | Premium (`is_premium`) | BYOK |
| :--- | :--- | :--- | :--- |
| **Weekly tokens** | 100,000 (`FREE_WEEKLY_TOKEN_LIMIT`) | 1,000,000 (`PREMIUM_WEEKLY_TOKEN_LIMIT`) | Quota check returns early when `byok_enabled` is on and any stored provider key is non-empty |
| **Reset** | Monday 00:00 UTC (`DatabaseManager._get_current_week_start` / `_get_next_week_reset_ts`) | Same | Not metered by this bot |
| **Models** | `models.json` `pipeline` | Same pipeline | `byok_primary_model` then `byok_fallback_model` when those columns are set |
| **History depth** | 5 messages on `/ask`, 15 on mention/reply chat | 30 in both paths | See the note under this table |
| **Vision** | Off | On | See the note under this table |
| **Images** | 1 generation, then a 14-day wait from `last_image_ts` | 7 per week (`PREMIUM_IMAGE_GEN_LIMIT_WEEKLY`) | Not metered when the BYOK quota short-circuit applies |
| **Custom instructions** | Ignored | `custom_prompt` is appended | Appended when the same BYOK short-circuit is true |

History depth and `enable_vision` use a different check than the quota short-circuit. In `/ask` and `on_message` they turn on when `is_premium` is set **or** `byok_gemini_key`, `byok_xai_key`, `byok_openai_key`, or `byok_anthropic_key` is non-empty. That check does not read `byok_enabled`, `byok_deepseek_key`, or `byok_glm_key`. A DeepSeek-only or GLM-only guild can be unmetered and still stay on the free history/vision limits.

The counters above are what `check_ai_quota_allowance` enforces. Several Discord cards describe different image allowances and were not changed here:

* `cogs/billing/cog.py` Premium page: "30 image gens/month". Free page: "5–10 message context window" and "2 image gens/month".
* `cogs/settings.py` plan page: Premium "20 image gens/month", and the same free-plan lines as billing.
* `cogs/errors.py` `build_quota_card`: "20 images/month".

Free history is 5 messages on `/ask` and 15 on chatbot mentions, not a 5–10 window. Free images are one generation, then 14 days, not two per month. Max completion length is `DEFAULT_MAX_OUTPUT_TOKENS` (2048). Hosted Gemini models attach Google Search grounding whenever `supports_search` is true, including on the free tier. That tool attachment was read from `GeminiModel._execute_query` and was not checked against a live API response.

---

## 🎯 Message Trigger Mechanics

1. **Chatbot channel (`guild_settings.cbc`)**: replies only to @mentions of the bot and to replies to the bot. Other chatter is ignored. System messages and messages with neither text nor attachments are ignored before that check.
2. **`/summon`**: default duration `10m`. `parse_time` accepts `<number><s|m|h>`. The row is stored in `ai_summon` and in memory. The same mention/reply rule applies until expiry, then the bot posts the session token total from `InfoMessages.summon_ended`.
3. **Everywhere else**: no `on_message` reply. `/ask` and `/summarize` still run. `/ask` is guild-only and takes a question plus an optional image attachment (the attachment is only sent to the model when vision is enabled).

---

## 🧩 Key Architecture Components (`ai.py`)

### 1. `ModelManager`
* Walks the hosted `pipeline` or the BYOK pair inside `asyncio.wait_for`, as described above.
* Appends `custom_prompt` only when Premium or the BYOK quota short-circuit is true.
* Requests up to `DEFAULT_MAX_OUTPUT_TOKENS` (2,048) completion tokens.

### 2. `ContextManager`
* History length is chosen by the cog (5, 15, or 30). `_get_chat_history` stops once a message is older than 45 minutes (`max_age_minutes=45`) because `channel.history` is newest-first.
* Authors are resolved to `discord.Member` when the guild cache or `fetch_member` succeeds, so the prompt can use the server display name.
* Lines look like `[User: DisplayName] (replying to OtherName): text` or `[You (BotName)]: text`. The replied-to body is not copied in again.
* `enable_vision` gates image bytes. Text files are still read as UTF-8. Image suffixes include `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.heic`, `.bmp`. Text suffixes include `.txt`, `.py`, `.js`, `.ts`, `.json`, `.csv`, `.md`, `.html`, `.css`, `.yml`, `.yaml`, `.ini`, `.xml`, `.log`, `.sh`, `.bat`, `.sql`, plus `text/*`, JSON, and JavaScript content types.
* `HISTORY_ATTACHMENT_LIMIT = 3` limits how many recent history messages are scanned for attachments when vision is on.

### 3. `ResponseHandler`
* `split_text_into_chunks` defaults to 1,950 characters and tries to keep fenced code blocks intact, then keeps the footer inside Discord's 2,000-character message limit.
* The last chunk can append a footer from `footer_show_icon`, `footer_show_name`, `footer_show_tokens`, and `footer_show_latency`. Those columns default to off.
* Discord reply routing for both interactions and messages.
