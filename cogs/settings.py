import discord
from cogs.utils.constants import Emojis, DefaultSettings
from discord import ui
from discord.ext import commands
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# =========================================================================
# --- MODALS ---
# =========================================================================

class PrefixModal(ui.Modal, title="Change Prefix"):
    prefix_input = ui.TextInput(
        label="Command Prefix",
        placeholder="e.g. !, ?, =",
        default="=",
        max_length=10,
        required=True
    )

    def __init__(self, prefix, guild_id, parent_view):
        super().__init__()
        self.prefix_input.default = prefix
        self.guild_id = guild_id
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        new_prefix = self.prefix_input.value
        old_prefix = self.parent_view.bot.settings_cache.get(self.guild_id, {}).get("prefix", DefaultSettings.PREFIX)

        await self.parent_view.bot.db_manager.update_guild_setting(self.guild_id, "prefix", new_prefix)
        await self.parent_view.bot.db_manager.log_settings_change(self.guild_id, interaction.user.id, "prefix", str(old_prefix), str(new_prefix))

        self.parent_view.bot.settings_cache.setdefault(self.guild_id, {})["prefix"] = new_prefix
        self.parent_view.guild_settings["prefix"] = new_prefix

        self.parent_view.render_general()
        await interaction.response.edit_message(view=self.parent_view)


class CustomPromptModal(ui.Modal, title="Custom Persona / Prompt"):
    prompt_input = ui.TextInput(
        label="System Prompt Instructions",
        placeholder="Enter custom persona or instructions for this server...",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=False
    )

    def __init__(self, current_prompt, guild_id, parent_view):
        super().__init__()
        if current_prompt:
            self.prompt_input.default = current_prompt
        self.guild_id = guild_id
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        new_prompt = self.prompt_input.value.strip() if self.prompt_input.value else None
        guild_settings = self.parent_view.bot.settings_cache.get(self.guild_id, {})
        is_paid_or_byok = bool(
            guild_settings.get("is_premium") or 
            any(guild_settings.get(k) for k in ["byok_gemini_key", "byok_xai_key", "byok_openai_key", "byok_anthropic_key", "byok_deepseek_key", "byok_glm_key"])
        )
        if new_prompt and not is_paid_or_byok:
            await interaction.response.send_message(
                "Custom system prompts require Premium (2.99€/mo) or BYOK mode.",
                ephemeral=True
            )
            return

        old_prompt = guild_settings.get("custom_prompt")
        await self.parent_view.bot.db_manager.update_guild_setting(self.guild_id, "custom_prompt", new_prompt)
        await self.parent_view.bot.db_manager.log_settings_change(self.guild_id, interaction.user.id, "custom_prompt", str(old_prompt), str(new_prompt))

        self.parent_view.bot.settings_cache.setdefault(self.guild_id, {})["custom_prompt"] = new_prompt
        self.parent_view.guild_settings["custom_prompt"] = new_prompt

        self.parent_view.render_ai()
        await interaction.response.edit_message(view=self.parent_view)


class BYOKModal(ui.Modal, title="Link Custom API Keys"):
    gemini_key = ui.TextInput(
        label="Google Gemini Key",
        placeholder="Google AI Studio key (or leave blank)",
        required=False,
        max_length=200
    )
    xai_key = ui.TextInput(
        label="xAI Grok Key",
        placeholder="xAI API key (or leave blank)",
        required=False,
        max_length=200
    )
    openai_key = ui.TextInput(
        label="OpenAI Key",
        placeholder="OpenAI API key (or leave blank)",
        required=False,
        max_length=200
    )
    anthropic_key = ui.TextInput(
        label="Anthropic Claude Key",
        placeholder="Anthropic API key (or leave blank)",
        required=False,
        max_length=200
    )
    deepseek_key = ui.TextInput(
        label="DeepSeek Key",
        placeholder="DeepSeek API key (or leave blank)",
        required=False,
        max_length=200
    )

    def __init__(self, guild_settings: dict, guild_id: int, parent_view):
        super().__init__()
        self.guild_id = guild_id
        self.parent_view = parent_view
        if guild_settings.get("byok_gemini_key"):
            self.gemini_key.default = guild_settings["byok_gemini_key"]
        if guild_settings.get("byok_xai_key"):
            self.xai_key.default = guild_settings["byok_xai_key"]
        if guild_settings.get("byok_openai_key"):
            self.openai_key.default = guild_settings["byok_openai_key"]
        if guild_settings.get("byok_anthropic_key"):
            self.anthropic_key.default = guild_settings["byok_anthropic_key"]
        if guild_settings.get("byok_deepseek_key"):
            self.deepseek_key.default = guild_settings["byok_deepseek_key"]

    async def on_submit(self, interaction: discord.Interaction):
        g_key = self.gemini_key.value.strip() if self.gemini_key.value else None
        x_key = self.xai_key.value.strip() if self.xai_key.value else None
        o_key = self.openai_key.value.strip() if self.openai_key.value else None
        a_key = self.anthropic_key.value.strip() if self.anthropic_key.value else None
        d_key = self.deepseek_key.value.strip() if self.deepseek_key.value else None

        key_updates = [
            ("byok_gemini_key", g_key),
            ("byok_xai_key", x_key),
            ("byok_openai_key", o_key),
            ("byok_anthropic_key", a_key),
            ("byok_deepseek_key", d_key)
        ]

        for col, val in key_updates:
            old_val = self.parent_view.guild_settings.get(col)
            await self.parent_view.bot.db_manager.update_guild_setting(self.guild_id, col, val)
            await self.parent_view.bot.db_manager.log_settings_change(self.guild_id, interaction.user.id, col, str(old_val), str(val))
            self.parent_view.bot.settings_cache.setdefault(self.guild_id, {})[col] = val
            self.parent_view.guild_settings[col] = val
        if hasattr(self.parent_view, "render_plan") and getattr(self.parent_view, "plan_page_idx", None) is not None and getattr(self.parent_view, "plan_page_idx", None) == 2:
            await self.parent_view.render_plan(interaction, page_idx=2)
        elif hasattr(self.parent_view, "render_byok_settings"):
            self.parent_view.render_byok_settings()
            await interaction.response.edit_message(view=self.parent_view)
        elif hasattr(self.parent_view, "render_ai"):
            self.parent_view.render_ai()
            await interaction.response.edit_message(view=self.parent_view)
        elif hasattr(self.parent_view, "switch_page"):
            self.parent_view.switch_page(2)
            await interaction.response.edit_message(view=self.parent_view)
        else:
            await interaction.response.defer()


# =========================================================================
# --- CHANNEL SELECTS ---
# =========================================================================

class CBCSelect(ui.Select):
    PAGE_SIZE = 23

    def __init__(self, guild: discord.Guild, bot, selected_id=None, page: int = 0):
        self.guild = guild
        self.bot = bot
        self.selected_id = selected_id
        self.page = page

        text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]
        total_channels = len(text_channels)
        start_idx = page * self.PAGE_SIZE
        end_idx = start_idx + self.PAGE_SIZE
        page_channels = text_channels[start_idx:end_idx]

        options = []
        if page > 0:
            options.append(discord.SelectOption(
                label=f"< Previous ({page}/{((total_channels-1)//self.PAGE_SIZE)+1})",
                value="action_prev_page",
                description="View previous page"
            ))

        for ch in page_channels:
            is_default = (ch.id == selected_id)
            options.append(discord.SelectOption(
                label=f"#{ch.name}"[:100],
                value=str(ch.id),
                default=is_default,
                description=f"ID: {ch.id}"
            ))

        if end_idx < total_channels:
            options.append(discord.SelectOption(
                label=f"Next > ({page+2}/{((total_channels-1)//self.PAGE_SIZE)+1})",
                value="action_next_page",
                description="View next page"
            ))

        if not options:
            options.append(discord.SelectOption(label="No text channels available", value="none"))

        super().__init__(placeholder="Select ChatBot channel...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        selected_val = self.values[0]

        if selected_val == "action_prev_page":
            self.view.render_ai(cbc_page=self.page - 1)
            await interaction.response.edit_message(view=self.view)
            return
        elif selected_val == "action_next_page":
            self.view.render_ai(cbc_page=self.page + 1)
            await interaction.response.edit_message(view=self.view)
            return

        if selected_val == "none":
            await interaction.response.defer()
            return

        new_cbc = int(selected_val)
        old_cbc = self.view.guild_settings.get("cbc")

        await self.bot.db_manager.update_guild_setting(self.guild.id, "cbc", new_cbc)
        await self.bot.db_manager.log_settings_change(self.guild.id, interaction.user.id, "cbc", str(old_cbc), str(new_cbc))

        self.bot.settings_cache.setdefault(self.guild.id, {})["cbc"] = new_cbc
        self.view.guild_settings["cbc"] = new_cbc

        self.view.render_ai(cbc_page=self.page)
        await interaction.response.edit_message(view=self.view)


class LogChannelSelect(ui.Select):
    PAGE_SIZE = 23

    def __init__(self, guild: discord.Guild, bot, selected_id=None, page: int = 0):
        self.guild = guild
        self.bot = bot
        self.selected_id = selected_id
        self.page = page

        text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]
        total_channels = len(text_channels)
        start_idx = page * self.PAGE_SIZE
        end_idx = start_idx + self.PAGE_SIZE
        page_channels = text_channels[start_idx:end_idx]

        options = []
        if page > 0:
            options.append(discord.SelectOption(
                label=f"< Previous ({page}/{((total_channels-1)//self.PAGE_SIZE)+1})",
                value="action_prev_page",
                description="View previous page"
            ))

        for ch in page_channels:
            is_default = (ch.id == selected_id)
            options.append(discord.SelectOption(
                label=f"#{ch.name}"[:100],
                value=str(ch.id),
                default=is_default,
                description=f"ID: {ch.id}"
            ))

        if end_idx < total_channels:
            options.append(discord.SelectOption(
                label=f"Next > ({page+2}/{((total_channels-1)//self.PAGE_SIZE)+1})",
                value="action_next_page",
                description="View next page"
            ))

        if not options:
            options.append(discord.SelectOption(label="No text channels available", value="none"))

        super().__init__(placeholder="Select Chat Logs channel...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        selected_val = self.values[0]

        if selected_val == "action_prev_page":
            self.view.render_logs(log_page=self.page - 1)
            await interaction.response.edit_message(view=self.view)
            return
        elif selected_val == "action_next_page":
            self.view.render_logs(log_page=self.page + 1)
            await interaction.response.edit_message(view=self.view)
            return

        if selected_val == "none":
            await interaction.response.defer()
            return

        new_log = int(selected_val)
        old_log = self.view.guild_settings.get("log_channel")

        await self.bot.db_manager.update_guild_setting(self.guild.id, "log_channel", new_log)
        await self.bot.db_manager.log_settings_change(self.guild.id, interaction.user.id, "log_channel", str(old_log), str(new_log))

        self.bot.settings_cache.setdefault(self.guild.id, {})["log_channel"] = new_log
        self.view.guild_settings["log_channel"] = new_log

        self.view.render_logs(log_page=self.page)
        await interaction.response.edit_message(view=self.view)


# =========================================================================
# --- CATEGORY CONTAINERS ---
# =========================================================================

class GeneralSettingsContainer(ui.Container):
    def __init__(self, guild_settings: dict, guild: discord.Guild, bot, parent_view):
        super().__init__()
        self.guild_settings = guild_settings
        self.guild = guild
        self.bot = bot
        self.parent_view = parent_view
        self._make_container()

    def _make_container(self):
        titleDisplay = ui.TextDisplay("## Server Settings")
        self.add_item(titleDisplay)
        self.add_item(self.parent_view.create_nav_row("general"))
        self.add_item(ui.Separator())

        prefix = self.guild_settings.get("prefix", "!")
        prefix_display = ui.TextDisplay(
            f"**Command Prefix:** `{prefix}`\n"
            f"-# Prefix used to trigger bot commands."
        )
        prefix_btn = ui.Button(emoji=Emojis.EDIT, style=discord.ButtonStyle.gray)
        prefix_btn.callback = self.prefix_change
        self.add_item(ui.Section(prefix_display, accessory=prefix_btn))

    async def prefix_change(self, interaction: discord.Interaction):
        prefix = self.guild_settings.get("prefix", "!")
        await interaction.response.send_modal(PrefixModal(prefix, self.guild.id, self.parent_view))


def get_model_emoji(model_id: str) -> str:
    """Helper to return provider emoji for a given model ID."""
    m = (model_id or "").lower()
    if "gemini" in m or "google" in m:
        return Emojis.GEMINI
    elif "gpt" in m or "openai" in m or "chatgpt" in m:
        return Emojis.CHATGPT
    elif "claude" in m or "anthropic" in m:
        return Emojis.CLAUDE
    elif "grok" in m or "xai" in m:
        return Emojis.GROK
    elif "deepseek" in m:
        return Emojis.DEEPSEEK
    elif "glm" in m or "zhipu" in m:
        return "🇨🇳"
    return "🤖"


class AISettingsContainer(ui.Container):
    def __init__(self, guild_settings: dict, guild: discord.Guild, bot, parent_view, cbc_page: int = 0):
        super().__init__()
        self.guild_settings = guild_settings
        self.guild = guild
        self.bot = bot
        self.parent_view = parent_view
        self.cbc_page = cbc_page
        self._make_container()

    def _make_container(self):
        titleDisplay = ui.TextDisplay("## Server Settings")
        self.add_item(titleDisplay)
        self.add_item(self.parent_view.create_nav_row("ai"))
        self.add_item(ui.Separator())

        # 1. ChatBot Channel
        cbc = self.guild_settings.get("cbc")
        cbc_state = "off" if cbc is None else "on"

        cbc_display = ui.TextDisplay(
            f"**Chat Bot Channel**\n"
            f"-# Responds automatically to messages in this channel."
        )
        cbc_button = ui.Button(emoji=Emojis.ON if cbc_state == "on" else Emojis.OFF, style=discord.ButtonStyle.gray)
        cbc_button.callback = self.cbc_toggle
        self.add_item(ui.Section(cbc_display, accessory=cbc_button))

        if cbc is not None:
            cbc_select = CBCSelect(guild=self.guild, bot=self.bot, selected_id=cbc, page=self.cbc_page)
            select_row = ui.ActionRow()
            select_row.add_item(cbc_select)
            self.add_item(select_row)

        self.add_item(ui.Separator())

        # 2. Custom Persona / Prompt
        has_byok = bool(
            self.guild_settings.get("byok_gemini_key") or 
            self.guild_settings.get("byok_xai_key") or 
            self.guild_settings.get("byok_openai_key") or 
            self.guild_settings.get("byok_anthropic_key") or
            self.guild_settings.get("byok_deepseek_key") or
            self.guild_settings.get("byok_glm_key")
        )

        prompt_display = ui.TextDisplay(
            f"**Custom Persona / Prompt**\n"
            f"-# Set a custom system instruction or personality for the AI."
        )
        prompt_button = ui.Button(emoji=Emojis.EDIT, style=discord.ButtonStyle.gray)
        prompt_button.callback = self.custom_prompt_configure
        self.add_item(ui.Section(prompt_display, accessory=prompt_button))
        self.add_item(ui.Separator())

        # 3. Bring Your Own Key (BYOK) Submenu
        byok_display = ui.TextDisplay(
            f"**Bring Your Own Key (BYOK)**\n"
            f"-# Use your own API keys for unmetered AI usage and custom models."
        )
        byok_button = ui.Button(emoji=Emojis.ARROW, style=discord.ButtonStyle.gray)
        byok_button.callback = self.byok_submenu_open
        self.add_item(ui.Section(byok_display, accessory=byok_button))
        self.add_item(ui.Separator())

        # 4. AI Response Footer (Submenu)
        footer_display = ui.TextDisplay(
            f"**AI Reply Footer**\n"
            f"-# Customize the metadata displayed in AI response footers."
        )
        footer_button = ui.Button(emoji=Emojis.ARROW, style=discord.ButtonStyle.gray)
        footer_button.callback = self.footer_submenu_open
        self.add_item(ui.Section(footer_display, accessory=footer_button))
        self.add_item(ui.Separator())

        # 5. Reply Ping
        reply_ping = self.guild_settings.get("reply_ping", 1)
        ping_state = "on" if reply_ping == 1 else "off"
        ping_display = ui.TextDisplay(
            f"**Reply Ping**\n"
            f"-# Mentions the user when replying."
        )
        ping_button = ui.Button(emoji=Emojis.ON if ping_state == "on" else Emojis.OFF, style=discord.ButtonStyle.gray)
        ping_button.callback = self.reply_ping_toggle
        self.add_item(ui.Section(ping_display, accessory=ping_button))

    async def cbc_toggle(self, interaction: discord.Interaction):
        current_cbc = self.guild_settings.get("cbc")
        if current_cbc is None:
            default = next((ch.id for ch in self.guild.channels if isinstance(ch, discord.TextChannel)), None)
            new_cbc = default
        else:
            new_cbc = None

        await self.bot.db_manager.update_guild_setting(self.guild.id, "cbc", new_cbc)
        await self.bot.db_manager.log_settings_change(self.guild.id, interaction.user.id, "cbc", str(current_cbc), str(new_cbc))

        self.bot.settings_cache.setdefault(self.guild.id, {})["cbc"] = new_cbc
        self.guild_settings["cbc"] = new_cbc

        self.parent_view.render_ai(cbc_page=self.cbc_page)
        await interaction.response.edit_message(view=self.parent_view)

    async def custom_prompt_configure(self, interaction: discord.Interaction):
        current_prompt = self.guild_settings.get("custom_prompt")
        await interaction.response.send_modal(CustomPromptModal(current_prompt, self.guild.id, self.parent_view))

    async def byok_submenu_open(self, interaction: discord.Interaction):
        self.parent_view.render_byok_settings()
        await interaction.response.edit_message(view=self.parent_view)

    async def footer_submenu_open(self, interaction: discord.Interaction):
        self.parent_view.render_footer_settings()
        await interaction.response.edit_message(view=self.parent_view)

    async def reply_ping_toggle(self, interaction: discord.Interaction):
        current_ping = self.guild_settings.get("reply_ping", 1)
        new_ping = 0 if current_ping == 1 else 1

        await self.bot.db_manager.update_guild_setting(self.guild.id, "reply_ping", new_ping)
        await self.bot.db_manager.log_settings_change(self.guild.id, interaction.user.id, "reply_ping", str(current_ping), str(new_ping))

        self.bot.settings_cache.setdefault(self.guild.id, {})["reply_ping"] = new_ping
        self.guild_settings["reply_ping"] = new_ping

        self.parent_view.render_ai(cbc_page=self.cbc_page)
        await interaction.response.edit_message(view=self.parent_view)


class LogsSettingsContainer(ui.Container):
    def __init__(self, guild_settings: dict, guild: discord.Guild, bot, parent_view, log_page: int = 0):
        super().__init__()
        self.guild_settings = guild_settings
        self.guild = guild
        self.bot = bot
        self.parent_view = parent_view
        self.log_page = log_page
        self._make_container()

    def _make_container(self):
        titleDisplay = ui.TextDisplay("## Server Settings")
        self.add_item(titleDisplay)
        self.add_item(self.parent_view.create_nav_row("logs"))
        self.add_item(ui.Separator())

        log_channel = self.guild_settings.get("log_channel")
        log_state = "off" if log_channel is None else "on"
        channel_name = f"#{self.guild.get_channel(log_channel).name}" if (log_channel and self.guild.get_channel(log_channel)) else "`disabled`"

        log_display = ui.TextDisplay(
            f"**Chat Logs Channel:** {channel_name}\n"
            f"-# Channel where message edits and deletions are logged."
        )
        log_button = ui.Button(emoji=Emojis.ON if log_state == "on" else Emojis.OFF, style=discord.ButtonStyle.gray)
        log_button.callback = self.log_toggle
        self.add_item(ui.Section(log_display, accessory=log_button))

        if log_channel is not None:
            log_select = LogChannelSelect(guild=self.guild, bot=self.bot, selected_id=log_channel, page=self.log_page)
            select_row = ui.ActionRow()
            select_row.add_item(log_select)
            self.add_item(select_row)

    async def log_toggle(self, interaction: discord.Interaction):
        current_log = self.guild_settings.get("log_channel")
        if current_log is None:
            default = next((ch.id for ch in self.guild.channels if isinstance(ch, discord.TextChannel)), None)
            new_log = default
        else:
            new_log = None

        await self.bot.db_manager.update_guild_setting(self.guild.id, "log_channel", new_log)
        await self.bot.db_manager.log_settings_change(self.guild.id, interaction.user.id, "log_channel", str(current_log), str(new_log))

        self.parent_view.render_logs(log_page=self.log_page)
        await interaction.response.edit_message(view=self.parent_view)


class FooterSettingsContainer(ui.Container):
    def __init__(self, guild_settings: dict, guild: discord.Guild, bot, parent_view):
        super().__init__()
        self.guild_settings = guild_settings
        self.guild = guild
        self.bot = bot
        self.parent_view = parent_view
        self._make_container()

    def _make_container(self):
        # 1. Header with < Back button
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back
        header_section = ui.Section(
            ui.TextDisplay("## AI Reply Footer\n-# Customize the elements displayed on AI replies."),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        # 1. Model Provider Icon
        icon_on = self.guild_settings.get("footer_show_icon", 1) == 1
        icon_disp = ui.TextDisplay(
            f"**Model Provider Icon**\n"
            f"-# Shows the AI provider logo emoji (e.g. {Emojis.GEMINI}, {Emojis.GROK})."
        )
        icon_btn = ui.Button(emoji=Emojis.ON if icon_on else Emojis.OFF, style=discord.ButtonStyle.gray)
        icon_btn.callback = self._toggle_icon
        self.add_item(ui.Section(icon_disp, accessory=icon_btn))
        self.add_item(ui.Separator())

        # 2. Model Name
        name_on = self.guild_settings.get("footer_show_name", 1) == 1
        name_disp = ui.TextDisplay(
            f"**Model Name**\n"
            f"-# Shows the clean model name (e.g. Gemini 3.7 Flash)."
        )
        name_btn = ui.Button(emoji=Emojis.ON if name_on else Emojis.OFF, style=discord.ButtonStyle.gray)
        name_btn.callback = self._toggle_name
        self.add_item(ui.Section(name_disp, accessory=name_btn))
        self.add_item(ui.Separator())

        # 3. Tokens Used
        tokens_on = self.guild_settings.get("footer_show_tokens", 1) == 1
        tokens_disp = ui.TextDisplay(
            f"**Tokens Consumed**\n"
            f"-# Displays total input + output tokens for the response."
        )
        tokens_btn = ui.Button(emoji=Emojis.ON if tokens_on else Emojis.OFF, style=discord.ButtonStyle.gray)
        tokens_btn.callback = self._toggle_tokens
        self.add_item(ui.Section(tokens_disp, accessory=tokens_btn))
        self.add_item(ui.Separator())

        # 4. Latency Time
        latency_on = self.guild_settings.get("footer_show_latency", 1) == 1
        latency_disp = ui.TextDisplay(
            f"**Response Latency**\n"
            f"-# Displays AI execution duration in milliseconds or seconds."
        )
        latency_btn = ui.Button(emoji=Emojis.ON if latency_on else Emojis.OFF, style=discord.ButtonStyle.gray)
        latency_btn.callback = self._toggle_latency
        self.add_item(ui.Section(latency_disp, accessory=latency_btn))
        self.add_item(ui.Separator())

        # Live Simulated Preview
        parts = []
        if icon_on and name_on:
            parts.append(f"{Emojis.GEMINI} Gemini 3.7 Flash")
        elif icon_on:
            parts.append(f"{Emojis.GEMINI}")
        elif name_on:
            parts.append("Gemini 3.7 Flash")

        if tokens_on:
            parts.append("345 tokens")
        if latency_on:
            parts.append("1.2s")

        preview_footer = f"-# {' • '.join(parts)}" if parts else "-# *(Footer disabled - nothing shown)*"
        preview_text = (
            f"**Live Preview:**\n"
            f"{preview_footer}"
        )
        self.add_item(ui.TextDisplay(preview_text))

    async def _on_back(self, interaction: discord.Interaction):
        self.parent_view.render_ai()
        await interaction.response.edit_message(view=self.parent_view)

    async def _toggle_icon(self, interaction: discord.Interaction):
        curr = self.guild_settings.get("footer_show_icon", 1)
        new_val = 0 if curr == 1 else 1
        await self._save_setting(interaction, "footer_show_icon", curr, new_val)

    async def _toggle_name(self, interaction: discord.Interaction):
        curr = self.guild_settings.get("footer_show_name", 1)
        new_val = 0 if curr == 1 else 1
        await self._save_setting(interaction, "footer_show_name", curr, new_val)

    async def _toggle_tokens(self, interaction: discord.Interaction):
        curr = self.guild_settings.get("footer_show_tokens", 1)
        new_val = 0 if curr == 1 else 1
        await self._save_setting(interaction, "footer_show_tokens", curr, new_val)

    async def _toggle_latency(self, interaction: discord.Interaction):
        curr = self.guild_settings.get("footer_show_latency", 1)
        new_val = 0 if curr == 1 else 1
        await self._save_setting(interaction, "footer_show_latency", curr, new_val)

    async def _save_setting(self, interaction: discord.Interaction, key: str, old_val: int, new_val: int):
        await self.bot.db_manager.update_guild_setting(self.guild.id, key, new_val)
        await self.bot.db_manager.log_settings_change(self.guild.id, interaction.user.id, key, str(old_val), str(new_val))
        self.bot.settings_cache.setdefault(self.guild.id, {})[key] = new_val
        self.guild_settings[key] = new_val
        self.parent_view.render_footer_settings()
        await interaction.response.edit_message(view=self.parent_view)


class BYOKSettingsContainer(ui.Container):
    def __init__(self, guild_settings: dict, guild: discord.Guild, bot, parent_view):
        super().__init__()
        self.guild_settings = guild_settings
        self.guild = guild
        self.bot = bot
        self.parent_view = parent_view
        self._make_container()

    def _get_available_models(self) -> dict:
        """Returns dict of {model_id: (display_name, provider)} based strictly on configured BYOK keys."""
        allowed_providers = set()
        if self.guild_settings.get("byok_gemini_key"): allowed_providers.add("gemini")
        if self.guild_settings.get("byok_xai_key"): allowed_providers.add("grok")
        if self.guild_settings.get("byok_openai_key"): allowed_providers.add("openai")
        if self.guild_settings.get("byok_anthropic_key"): allowed_providers.add("anthropic")
        if self.guild_settings.get("byok_deepseek_key"): allowed_providers.add("deepseek")
        if self.guild_settings.get("byok_glm_key"): allowed_providers.add("glm")

        models_data = {}
        ai_cog = self.bot.get_cog("AI")
        if ai_cog and hasattr(ai_cog, "model_manager") and ai_cog.model_manager.models:
            for mid, m in ai_cog.model_manager.models.items():
                if m.provider in allowed_providers:
                    models_data[mid] = (m.display_name, m.provider)
        else:
            import json, os
            cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai", "models.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for mid, m in data.items():
                        if mid in ["default_instruction", "pipeline"]: continue
                        if m.get("provider") in allowed_providers:
                            models_data[mid] = (m.get("name", mid), m.get("provider"))

        return models_data

    def _make_container(self):
        # 1. Header with < Back button (ui.Section)
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back
        header_section = ui.Section(
            ui.TextDisplay("## Bring Your Own Key (BYOK)"),
            accessory=back_btn
        )
        self.add_item(header_section)

        # Small description
        self.add_item(ui.TextDisplay("-# Link your own LLM provider keys for unmetered model usage and custom failover."))
        self.add_item(ui.Separator())

        # Section 1: Toggle section
        byok_enabled = self.guild_settings.get("byok_enabled", 1) == 1
        toggle_state = "on" if byok_enabled else "off"
        toggle_disp = ui.TextDisplay(
            "**BYOK Status**\n"
            "-# Route AI queries through your linked API keys."
        )
        toggle_btn = ui.Button(emoji=Emojis.ON if toggle_state == "on" else Emojis.OFF, style=discord.ButtonStyle.gray)
        toggle_btn.callback = self._on_toggle_byok
        self.add_item(ui.Section(toggle_disp, accessory=toggle_btn))
        self.add_item(ui.Separator())

        # Section 2: Edit keys section
        linked_keys = []
        if self.guild_settings.get("byok_gemini_key"): linked_keys.append("Gemini")
        if self.guild_settings.get("byok_xai_key"): linked_keys.append("Grok")
        if self.guild_settings.get("byok_openai_key"): linked_keys.append("OpenAI")
        if self.guild_settings.get("byok_anthropic_key"): linked_keys.append("Claude")
        if self.guild_settings.get("byok_deepseek_key"): linked_keys.append("DeepSeek")
        if self.guild_settings.get("byok_glm_key"): linked_keys.append("GLM")

        keys_summary = f"Linked: {', '.join(linked_keys)}" if linked_keys else "No API keys linked yet"
        keys_disp = ui.TextDisplay(
            f"**Provider API Keys**\n"
            f"-# {keys_summary}."
        )
        keys_btn = ui.Button(emoji=Emojis.EDIT, style=discord.ButtonStyle.gray)
        keys_btn.callback = self._on_edit_keys
        self.add_item(ui.Section(keys_disp, accessory=keys_btn))
        self.add_item(ui.Separator())

        # Section 3: Edit the 2 model fallback stack directly on page
        available_models = self._get_available_models()
        if not available_models:
            stack_disp = ui.TextDisplay(
                "**Model Fallback Stack**\n"
                "-# Link at least one provider API key above to configure fallback models."
            )
            self.add_item(stack_disp)
            return

        current_primary = self.guild_settings.get("byok_primary_model")
        current_fallback = self.guild_settings.get("byok_fallback_model")

        first_mid = list(available_models.keys())[0]
        if current_primary not in available_models:
            current_primary = first_mid
        if current_fallback not in available_models:
            current_fallback = list(available_models.keys())[1] if len(available_models) > 1 else first_mid

        stack_disp = ui.TextDisplay("**Model Fallback Stack**")
        self.add_item(stack_disp)

        primary_options = []
        for mid, (name, prov) in available_models.items():
            primary_options.append(
                discord.SelectOption(
                    label=name,
                    value=mid,
                    description=f"Provider: {prov.title()}",
                    emoji=get_model_emoji(mid),
                    default=(mid == current_primary)
                )
            )

        primary_select = discord.ui.Select(
            placeholder="Select Primary Model (Tier 1)...",
            options=primary_options[:25],
            custom_id="byok_primary_select"
        )
        primary_select.callback = self._on_select_primary
        self.add_item(ui.ActionRow(primary_select))

        self.add_item(ui.TextDisplay(f"{Emojis.EMPTY * 10}⭣"))

        fallback_options = []
        for mid, (name, prov) in available_models.items():
            fallback_options.append(
                discord.SelectOption(
                    label=name,
                    value=mid,
                    description=f"Provider: {prov.title()}",
                    emoji=get_model_emoji(mid),
                    default=(mid == current_fallback)
                )
            )

        fallback_select = discord.ui.Select(
            placeholder="Select Fallback Model (Tier 2)...",
            options=fallback_options[:25],
            custom_id="byok_fallback_select"
        )
        fallback_select.callback = self._on_select_fallback
        self.add_item(ui.ActionRow(fallback_select))

    async def _on_back(self, interaction: discord.Interaction):
        self.parent_view.render_ai()
        await interaction.response.edit_message(view=self.parent_view)

    async def _on_toggle_byok(self, interaction: discord.Interaction):
        curr = self.guild_settings.get("byok_enabled", 1)
        new_val = 0 if curr == 1 else 1

        await self.bot.db_manager.update_guild_setting(self.guild.id, "byok_enabled", new_val)
        await self.bot.db_manager.log_settings_change(self.guild.id, interaction.user.id, "byok_enabled", str(curr), str(new_val))
        self.bot.settings_cache.setdefault(self.guild.id, {})["byok_enabled"] = new_val
        self.guild_settings["byok_enabled"] = new_val

        self.parent_view.render_byok_settings()
        await interaction.response.edit_message(view=self.parent_view)

    async def _on_edit_keys(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BYOKModal(self.guild_settings, self.guild.id, self.parent_view))

    async def _on_select_primary(self, interaction: discord.Interaction):
        new_val = interaction.data["values"][0]
        old_val = self.guild_settings.get("byok_primary_model")
        await self.bot.db_manager.update_guild_setting(self.guild.id, "byok_primary_model", new_val)
        await self.bot.db_manager.log_settings_change(self.guild.id, interaction.user.id, "byok_primary_model", str(old_val), str(new_val))
        self.bot.settings_cache.setdefault(self.guild.id, {})["byok_primary_model"] = new_val
        self.guild_settings["byok_primary_model"] = new_val

        self.parent_view.render_byok_settings()
        await interaction.response.edit_message(view=self.parent_view)

    async def _on_select_fallback(self, interaction: discord.Interaction):
        new_val = interaction.data["values"][0]
        old_val = self.guild_settings.get("byok_fallback_model")
        await self.bot.db_manager.update_guild_setting(self.guild.id, "byok_fallback_model", new_val)
        await self.bot.db_manager.log_settings_change(self.guild.id, interaction.user.id, "byok_fallback_model", str(old_val), str(new_val))
        self.bot.settings_cache.setdefault(self.guild.id, {})["byok_fallback_model"] = new_val
        self.guild_settings["byok_fallback_model"] = new_val

        self.parent_view.render_byok_settings()
        await interaction.response.edit_message(view=self.parent_view)


class PlanSettingsContainer(ui.Container):
    def __init__(self, guild_settings: dict, guild: discord.Guild, bot, parent_view, is_premium: bool, has_byok: bool, checkout_url: Optional[str] = None, portal_url: Optional[str] = None, page_idx: int = 1):
        super().__init__()
        self.guild_settings = guild_settings
        self.guild = guild
        self.bot = bot
        self.parent_view = parent_view
        self.is_premium = is_premium
        self.has_byok = has_byok
        self.checkout_url = checkout_url
        self.portal_url = portal_url
        self.page_idx = max(0, min(2, page_idx))
        self._make_container()

    def _make_container(self):
        # 1. Title & Server Name + Nav Category Row
        self.add_item(ui.TextDisplay(f"## Server Settings\n-# {self.guild.name}"))
        self.add_item(self.parent_view.create_nav_row("plan"))
        self.add_item(ui.Separator())

        # Determine active status per plan
        is_free_current = (not self.is_premium and not self.has_byok)
        is_premium_current = self.is_premium
        is_byok_current = (self.has_byok and not self.is_premium)

        # 2. Page Content Rendering
        if self.page_idx == 0:
            # --- PAGE 1: FREE PLAN ---
            curr_tag = " (Current)" if is_free_current else ""
            content = (
                f"## Free Plan{curr_tag}\n"
                f"**0.00€ / month**\n\n"
                f"✅ 100k tokens/week\n"
                f"✅ 5–10 message context window\n"
                f"✅ 2 image gens/month\n"
                f"✅ Websearch\n"
                f"❌ Vision\n"
                f"❌ Custom system instructions"
            )
        elif self.page_idx == 1:
            # --- PAGE 2: PREMIUM PLAN ---
            curr_tag = " (Current)" if is_premium_current else ""
            content = (
                f"## Premium Plan{curr_tag}\n"
                f"**2.99€ / month**\n\n"
                f"✅ 1M tokens/week\n"
                f"✅ 30 message context window\n"
                f"✅ 20 image gens/month\n"
                f"✅ Websearch\n"
                f"✅ Vision\n"
                f"✅ Custom system instructions"
            )
        else:
            # --- PAGE 3: BYOK ---
            curr_tag = " (Current)" if is_byok_current else ""
            content = (
                f"## Bring Your Own Key{curr_tag}\n"
                f"**0.00€ / month**\n\n"
                f"✅ ∞ tokens/week\n"
                f"✅ 30 message context window\n"
                f"✅ ∞ image gens/week\n"
                f"✅ Websearch\n"
                f"✅ Vision\n"
                f"✅ Custom system instructions\n"
                f"✅ Customizable settings"
            )

        self.add_item(ui.TextDisplay(content))
        self.add_item(ui.Separator())

        # 3. Dynamic 3-Button Navigation Row: [ ◀ ] [ Action Button ] [ ▶ ]
        nav_row = ui.ActionRow()

        # Prev Button
        prev_btn = ui.Button(
            label="◀",
            style=discord.ButtonStyle.gray,
            disabled=(self.page_idx == 0)
        )
        async def _on_prev(interaction: discord.Interaction):
            await self.parent_view.switch_plan_page(interaction, self.page_idx - 1)
        prev_btn.callback = _on_prev
        nav_row.add_item(prev_btn)

        # Center Action Button
        if self.page_idx == 0:
            status_label = "Current Plan" if is_free_current else "Default Plan"
            action_btn = ui.Button(
                label=status_label,
                style=discord.ButtonStyle.gray,
                disabled=True
            )
            nav_row.add_item(action_btn)
        elif self.page_idx == 1:
            if not self.is_premium:
                final_checkout = self.checkout_url or "https://polar.sh"
                upgrade_btn = ui.Button(
                    label="👑 Upgrade",
                    url=final_checkout,
                    style=discord.ButtonStyle.link
                )
                nav_row.add_item(upgrade_btn)
            else:
                final_portal = self.portal_url or "https://polar.sh/spl1ceai/portal"
                portal_btn = ui.Button(
                    label="Manage Billing",
                    url=final_portal,
                    style=discord.ButtonStyle.link
                )
                nav_row.add_item(portal_btn)
        else:
            byok_label = "⚙️ Manage Keys" if self.has_byok else "⚙️ Setup Keys"
            byok_btn = ui.Button(
                label=byok_label,
                style=discord.ButtonStyle.gray
            )
            async def _on_byok_click(interaction: discord.Interaction):
                await interaction.response.send_modal(BYOKModal(self.guild_settings, self.guild.id, self.parent_view))
            byok_btn.callback = _on_byok_click
            nav_row.add_item(byok_btn)

        # Next Button
        next_btn = ui.Button(
            label="▶",
            style=discord.ButtonStyle.gray,
            disabled=(self.page_idx == 2)
        )
        async def _on_next(interaction: discord.Interaction):
            await self.parent_view.switch_plan_page(interaction, self.page_idx + 1)
        next_btn.callback = _on_next
        nav_row.add_item(next_btn)

        self.add_item(nav_row)


# =========================================================================
# --- MAIN VIEW ---
# =========================================================================

class SettingsView(ui.LayoutView):

    def __init__(self, guild_settings: dict, guild: discord.Guild, bot, *, timeout=None):
        super().__init__(timeout=timeout)
        self.guild_settings = guild_settings
        self.guild = guild
        self.bot = bot
        self.plan_checkout_url = None
        self.plan_portal_url = None
        self.plan_page_idx = 1
        self.render_general()

    def create_nav_row(self, active_cat: str) -> ui.ActionRow:
        row = ui.ActionRow()

        categories = [
            ("General", "general"),
            ("AI", "ai"),
            ("Chat Logs", "logs"),
            ("Server Plan", "plan"),
        ]

        for label, cat_key in categories:
            is_active = (cat_key == active_cat)
            style = discord.ButtonStyle.blurple if is_active else discord.ButtonStyle.gray
            btn = ui.Button(label=label, style=style)

            if cat_key == "general":
                btn.callback = self._on_nav_general
            elif cat_key == "ai":
                btn.callback = self._on_nav_ai
            elif cat_key == "logs":
                btn.callback = self._on_nav_logs
            elif cat_key == "plan":
                btn.callback = self._on_nav_plan

            row.add_item(btn)

        return row

    async def _on_nav_general(self, interaction: discord.Interaction):
        self.render_general()
        await interaction.response.edit_message(view=self)

    async def _on_nav_ai(self, interaction: discord.Interaction):
        self.render_ai()
        await interaction.response.edit_message(view=self)

    async def _on_nav_logs(self, interaction: discord.Interaction):
        self.render_logs()
        await interaction.response.edit_message(view=self)

    async def _on_nav_plan(self, interaction: discord.Interaction):
        await self.render_plan(interaction)

    def render_general(self):
        self.clear_items()
        container = GeneralSettingsContainer(self.guild_settings, self.guild, self.bot, self)
        self.add_item(container)

    def render_ai(self, cbc_page: int = 0):
        self.clear_items()
        container = AISettingsContainer(self.guild_settings, self.guild, self.bot, self, cbc_page=cbc_page)
        self.add_item(container)

    def render_footer_settings(self):
        self.clear_items()
        container = FooterSettingsContainer(self.guild_settings, self.guild, self.bot, self)
        self.add_item(container)

    def render_byok_settings(self):
        self.clear_items()
        container = BYOKSettingsContainer(self.guild_settings, self.guild, self.bot, self)
        self.add_item(container)

    def render_logs(self, log_page: int = 0):
        self.clear_items()
        container = LogsSettingsContainer(self.guild_settings, self.guild, self.bot, self, log_page=log_page)
        self.add_item(container)

    async def render_plan(self, interaction: discord.Interaction, page_idx: typing.Optional[int] = None):
        if page_idx is not None:
            self.plan_page_idx = page_idx

        if not self.plan_checkout_url:
            billing_cog = self.bot.get_cog("Billing")
            if billing_cog and hasattr(billing_cog, "billing_service") and billing_cog.billing_service.is_configured:
                try:
                    self.plan_checkout_url = await billing_cog.billing_service.create_checkout_session(
                        guild_id=self.guild.id,
                        user_id=interaction.user.id,
                        guild_name=self.guild.name,
                        user_name=str(interaction.user)
                    )
                    sub = await self.bot.db_manager.get_subscription(self.guild.id)
                    if sub and sub.get("customer_id"):
                        self.plan_portal_url = billing_cog.billing_service.get_customer_portal_url(sub["customer_id"])
                    else:
                        self.plan_portal_url = "https://polar.sh/spl1ceai/portal"
                except Exception as e:
                    logger.error(f"Error getting billing links in settings: {e}")
                    self.plan_portal_url = "https://polar.sh/spl1ceai/portal"

        is_premium = bool(self.guild_settings.get("is_premium", 0))
        has_byok = bool(
            self.guild_settings.get("byok_gemini_key") or 
            self.guild_settings.get("byok_xai_key") or 
            self.guild_settings.get("byok_openai_key") or 
            self.guild_settings.get("byok_anthropic_key") or
            self.guild_settings.get("byok_deepseek_key") or
            self.guild_settings.get("byok_glm_key")
        )

        self.clear_items()
        container = PlanSettingsContainer(
            self.guild_settings,
            self.guild,
            self.bot,
            self,
            is_premium,
            has_byok,
            checkout_url=self.plan_checkout_url,
            portal_url=self.plan_portal_url,
            page_idx=self.plan_page_idx
        )
        self.add_item(container)
        await interaction.response.edit_message(view=self)

    async def switch_plan_page(self, interaction: discord.Interaction, page_idx: int):
        await self.render_plan(interaction, page_idx=page_idx)


class Settings(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @commands.hybrid_command(name="settings", aliases=["config"])
    @commands.guild_only()
    async def settings(self, ctx: commands.Context):
        """Opens the interactive server configuration panel."""
        guild_id = ctx.guild.id
        if guild_id not in self.bot.settings_cache:
            self.bot.settings_cache[guild_id] = {
                "prefix": DefaultSettings.PREFIX,
                "cbc": DefaultSettings.CBC,
                "llm_primary": DefaultSettings.LLM_PRIMARY,
                "llm_backup1": DefaultSettings.LLM_BACKUP1,
                "llm_backup2": DefaultSettings.LLM_BACKUP2,
                "llm_backup3": DefaultSettings.LLM_BACKUP3,
                "llm_timeout": DefaultSettings.LLM_TIMEOUT,
                "show_model": DefaultSettings.SHOW_MODEL,
                "reply_ping": DefaultSettings.REPLY_PING,
                "is_premium": DefaultSettings.IS_PREMIUM,
                "custom_prompt": DefaultSettings.CUSTOM_PROMPT,
                "byok_gemini_key": DefaultSettings.BYOK_GEMINI_KEY,
                "byok_xai_key": DefaultSettings.BYOK_XAI_KEY,
                "byok_openai_key": DefaultSettings.BYOK_OPENAI_KEY,
                "byok_anthropic_key": DefaultSettings.BYOK_ANTHROPIC_KEY,
                "byok_deepseek_key": DefaultSettings.BYOK_DEEPSEEK_KEY,
                "byok_glm_key": DefaultSettings.BYOK_GLM_KEY,
                "byok_primary_model": DefaultSettings.BYOK_PRIMARY_MODEL,
                "byok_fallback_model": DefaultSettings.BYOK_FALLBACK_MODEL,
                "byok_enabled": DefaultSettings.BYOK_ENABLED,
                "footer_show_icon": DefaultSettings.FOOTER_SHOW_ICON,
                "footer_show_name": DefaultSettings.FOOTER_SHOW_NAME,
                "footer_show_tokens": DefaultSettings.FOOTER_SHOW_TOKENS,
                "footer_show_latency": DefaultSettings.FOOTER_SHOW_LATENCY,
            }
        view = SettingsView(self.bot.settings_cache[guild_id], ctx.guild, self.bot)
        await ctx.reply(view=view)


async def setup(bot):
    await bot.add_cog(Settings(bot))
