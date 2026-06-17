import discord
from discord import ui
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)


class PrefixModal(ui.Modal, title="Change Server Prefix"):
    prefix_input = ui.TextInput(
        label="New Command Prefix",
        placeholder="Enter prefix (e.g. !, ?, =)",
        default="=",
        max_length=10,
        required=True
    )

    def __init__(self, prefix, guild_id, view):
        super().__init__()
        self.prefix_input.default = prefix
        self.guild_id = guild_id
        self.view = view


    async def on_submit(self, interaction: discord.Interaction):
        new_prefix = self.prefix_input.value
        
        # Save prefix to database
        async with self.view.bot.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO guild_settings (guild_id, prefix) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET prefix = excluded.prefix",
                (self.guild_id, new_prefix)
            )
            await self.view.bot.db.commit()

        self.view.bot.settings_cache.setdefault(self.guild_id, {"prefix": "=", "cbc": None})["prefix"] = new_prefix
        self.view.guild_settings = self.view.bot.settings_cache[self.guild_id]
        
        self.view._main_menu_view()
        await interaction.response.edit_message(view=self.view)


class TimeoutModal(ui.Modal, title="Change Model Timeout"):
    timeout_input = ui.TextInput(
        label="Timeout (seconds)",
        placeholder="Enter number of seconds (e.g. 5, 10, 15)",
        default="15",
        max_length=3,
        required=True
    )

    def __init__(self, timeout, guild_id, view):
        super().__init__()
        self.timeout_input.default = str(timeout)
        self.guild_id = guild_id
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        value = self.timeout_input.value.strip()
        try:
            new_timeout = int(value)
            if new_timeout < 3 or new_timeout > 60:
                raise ValueError("Timeout must be between 3 and 60 seconds.")
        except ValueError as e:
            await interaction.response.send_message(f"❌ Invalid input: {e}", ephemeral=True)
            return
            
        async with self.view.bot.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO guild_settings (guild_id, llm_timeout) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET llm_timeout = excluded.llm_timeout",
                (self.guild_id, new_timeout)
            )
            await self.view.bot.db.commit()

        self.view.bot.settings_cache.setdefault(self.guild_id, {})["llm_timeout"] = new_timeout
        self.view.guild_settings["llm_timeout"] = new_timeout
        
        self.view._pipeline_view()
        await interaction.response.edit_message(view=self.view)




class CBCSelect(ui.Select):
    PAGE_SIZE = 23

    def __init__(self, guild, bot, selected_id=None, page=0):
        self.bot = bot
        self.guild = guild
        self.page = page
        self.selected_id = None
        if selected_id:
            self.selected_id = int(selected_id)
            
        self.channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]

        options, placeholder = self._make_options()

        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)

    def _make_options(self):
        total_channels = len(self.channels)
        page_start = self.page * self.PAGE_SIZE
        page_end = page_start + self.PAGE_SIZE
        page_channels = self.channels[page_start:page_end]

        options = []
        if page_start > 0:
            options.append(discord.SelectOption(label="◀ Previous Page", value="__prev__"))

        for ch in page_channels:
            options.append(discord.SelectOption(label="# " + ch.name, value=str(ch.id)))

        if page_end < total_channels:
            options.append(discord.SelectOption(label="Next Page ▶", value="__next__"))

        placeholder = "Select a channel..."
        if self.selected_id:
            selected_channel = self.guild.get_channel(self.selected_id)
            if selected_channel is not None:
                placeholder = "# " + selected_channel.name

        return options, placeholder

    async def callback(self, interaction: discord.Interaction):
        try:
            value = self.values[0]
        except:
            value = None

        if value in ("__prev__", "__next__"):
            if value == "__prev__" and self.page > 0:
                self.page -= 1
            elif value == "__next__":
                total = len(self.channels)
                if (self.page + 1) * self.PAGE_SIZE < total:
                    self.page += 1

            new_options, new_placeholder = self._make_options()
            self.options = new_options
            self.placeholder = new_placeholder
            try:
                await interaction.response.edit_message(view=self.view)
            except Exception:
                await interaction.response.defer()
            return

        try:
            selected = int(value)
        except Exception:
            await interaction.response.defer()
            return

        # UPDATE DATABASE
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO guild_settings (guild_id, cbc) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET cbc = excluded.cbc",
                (self.guild.id, selected)
            )
            await self.bot.db.commit()

        self.bot.settings_cache.setdefault(self.guild.id, {"prefix": "=", "cbc": None})["cbc"] = selected
        self.selected_id = selected
        self.options, self.placeholder = self._make_options()
        try:
            await interaction.response.edit_message(view=self.view)
        except Exception:
            await interaction.response.defer()

        


class SettingsContainer(ui.Container):
    ICON = "⚙️"

    def __init__(self, guild_settings, guild, bot):
        super().__init__()
        self.guild_settings = guild_settings
        self.guild = guild
        self.bot = bot
        self._make_container()


    def _make_container(self):
        ################
        # TITLE DISPLAY
        titleString = f"## {self.ICON} Server Settings"
        titleDisplay = ui.TextDisplay(titleString)
        self.add_item(titleDisplay)
        ################

        self.add_item(ui.Separator())

        ################
        # PREFIX SECTION
        prefix = self.guild_settings.get("prefix", "!")
        prefix_display = ui.TextDisplay(
            f"**Command Prefix:** `{prefix}`\n"
            f"-# The prefix used to trigger commands in the server."
        )
        prefix_button = ui.Button(label="edit", style=discord.ButtonStyle.gray)
        prefix_button.callback = self.prefix_change
        prefix_section = ui.Section(prefix_display, accessory=prefix_button)
        self.add_item(prefix_section)
        ################

        self.add_item(ui.Separator())

        ################
        # CHATBOT CHANNEL SECTION
        cbc = self.guild_settings.get("cbc") if self.guild_settings else None
        cbc_state = "off" if cbc is None else "on"
        
        if cbc is not None:
            channel = self.guild.get_channel(cbc)
            cbc_value = f"#{channel.name}" if channel else f"#{cbc}"
        else:
            cbc_value = "`disabled`"
            
        cbc_textdisplay = ui.TextDisplay(
            f"**Chat Bot Channel**\n"
            f"-# The channel where the bot automatically responds to all chat messages."
        )
        cbc_button = ui.Button(label=cbc_state, style=discord.ButtonStyle.gray)
        cbc_button.callback = self.cbc_toggle
        cbc_section = ui.Section(cbc_textdisplay, accessory=cbc_button)
        self.add_item(cbc_section)
        ################

        ################
        # CHATBOT CHANNEL SELECT (paginated inside select)
        if cbc is not None:
            cbc_select = CBCSelect(guild=self.guild, bot=self.bot, selected_id=cbc)
            cbc_actionrow = ui.ActionRow()
            cbc_actionrow.add_item(cbc_select)
            self.add_item(cbc_actionrow)
        ################

        self.add_item(ui.Separator())

        ################
        # AI PIPELINE SECTION
        primary = self.guild_settings.get("llm_primary", "gemini")
        backup1 = self.guild_settings.get("llm_backup1", "openai")
        backup2 = self.guild_settings.get("llm_backup2", "anthropic")
        
        names_emojis = {
            "gemini": "<:sAI_gemini:1515921338106380369>",
            "openai": "<:sAI_chatgpt:1515922050739601418>",
            "anthropic": "<:sAI_claude:1515922404671754411>",
            "deepseek": "<:sAI_deepseek:1515922761732849664>",
            "grok": "<:sAI_grok:1516602717290893383>"
        }
        
        active_chain = [names_emojis.get(primary)]
        if backup1 != "disabled":
            active_chain.append(names_emojis.get(backup1))
        if backup2 != "disabled":
            active_chain.append(names_emojis.get(backup2))
        
        pipeline_str = " ➔ ".join(active_chain)
        
        pipeline_display = ui.TextDisplay(
            f"**AI Fallback Chain:** {pipeline_str}\n"
            f"-# The fallback order of AI models used to handle user messages."
        )
        pipeline_button = ui.Button(label="configure", style=discord.ButtonStyle.gray)
        pipeline_button.callback = self.pipeline_configure
        pipeline_section = ui.Section(pipeline_display, accessory=pipeline_button)
        self.add_item(pipeline_section)
        ################


    async def prefix_change(self, interaction: discord.Interaction):
        prefix = self.guild_settings.get("prefix", "!")
        await interaction.response.send_modal(PrefixModal(prefix, self.guild.id, self.view))


    async def pipeline_configure(self, interaction: discord.Interaction):
        view = self.view
        view._pipeline_view()
        await interaction.response.edit_message(view=view)


    async def cbc_toggle(self, interaction: discord.Interaction):
        current_cbc = self.guild_settings.get("cbc") if self.guild_settings else None

        if current_cbc is None:
            default = None
            for ch in self.guild.channels:
                if isinstance(ch, discord.TextChannel):
                    default = ch.id
                    break

            if default is None:
                await interaction.response.send_message("No text channel available to enable chat-bot channel.", ephemeral=True)
                return
            new_cbc = default
        else:
            new_cbc = None

        # UPDATE DATABASE
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO guild_settings (guild_id, cbc) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET cbc = excluded.cbc",
                (self.guild.id, new_cbc)
            )
            await self.bot.db.commit()

        self.bot.settings_cache.setdefault(self.guild.id, {"prefix": "=", "cbc": None})["cbc"] = new_cbc
        if self.guild_settings is not None:
            self.guild_settings["cbc"] = new_cbc

        view = self.view
        view._main_menu_view()

        await interaction.response.edit_message(view=view)
        


class SettingsView(ui.LayoutView):

    def __init__(self, guild_settings, guild, bot, *, timeout = 180):
        super().__init__(timeout=timeout)
        self.guild_settings = guild_settings
        self.guild = guild
        self.bot = bot
        self._main_menu_view()


    def _main_menu_view(self):
        menu_container = SettingsContainer(self.guild_settings, self.guild, self.bot)

        self.clear_items()
        self.add_item(menu_container)


    def _pipeline_view(self):
        pipeline_container = AIPipelineContainer(self.guild_settings, self.guild, self.bot)
        self.clear_items()
        self.add_item(pipeline_container)


class AIPipelineContainer(ui.Container):
    ICON = "⚙️"

    def __init__(self, guild_settings, guild, bot):
        super().__init__()
        self.guild_settings = guild_settings
        self.guild = guild
        self.bot = bot
        self._make_container()

    def _make_container(self):
        titleDisplay = ui.TextDisplay(f"## {self.ICON} AI Fallback Chain")
        self.add_item(titleDisplay)
        
        self.add_item(ui.Separator())
        
        descriptionDisplay = ui.TextDisplay(
            "-# Configure the AI fallback chain. \n-# The bot starts with the Primary model, and falls back to subsequent backups if an API key is missing or a service fails."
        )
        self.add_item(descriptionDisplay)

        self.add_item(ui.Separator())

        # Display the current pipeline select menus
        primary = self.guild_settings.get("llm_primary", "gemini")
        backup1 = self.guild_settings.get("llm_backup1", "openai")
        backup2 = self.guild_settings.get("llm_backup2", "anthropic")

        # Spacer using your custom empty emoji to center the arrow
        arrow_spacer = "<:empty:1454324278010056744>" * 9

        primary_select = PrimarySelect(self.guild, self.bot, primary)
        primary_row = ui.ActionRow()
        primary_row.add_item(primary_select)
        self.add_item(primary_row)

        self.add_item(ui.TextDisplay(f"{arrow_spacer}**▼**"))
        backup1_select = Backup1Select(self.guild, self.bot, backup1)
        backup1_row = ui.ActionRow()
        backup1_row.add_item(backup1_select)
        self.add_item(backup1_row)

        self.add_item(ui.TextDisplay(f"{arrow_spacer}**▼**"))
        backup2_select = Backup2Select(self.guild, self.bot, backup2)
        backup2_row = ui.ActionRow()
        backup2_row.add_item(backup2_select)
        self.add_item(backup2_row)

        self.add_item(ui.Separator())

        # Timeout setting section
        llm_timeout = self.guild_settings.get("llm_timeout", 15)
        timeout_display = ui.TextDisplay(
            f"**Timeout per Model:** `{llm_timeout}s`\n"
            f"-# The maximum time (in seconds) the bot waits for each model to respond before falling back to the next."
        )
        timeout_button = ui.Button(label="edit timeout", style=discord.ButtonStyle.gray)
        timeout_button.callback = self.timeout_change
        timeout_section = ui.Section(timeout_display, accessory=timeout_button)
        self.add_item(timeout_section)

        self.add_item(ui.Separator())

        # Back button
        back_button = ui.Button(label="◀ Back", style=discord.ButtonStyle.gray)
        back_button.callback = self.back_to_settings
        back_row = ui.ActionRow()
        back_row.add_item(back_button)
        self.add_item(back_row)

    async def timeout_change(self, interaction: discord.Interaction):
        llm_timeout = self.guild_settings.get("llm_timeout", 15)
        await interaction.response.send_modal(TimeoutModal(llm_timeout, self.guild.id, self.view))

    async def back_to_settings(self, interaction: discord.Interaction):
        view = self.view
        view._main_menu_view()
        await interaction.response.edit_message(view=view)


class PrimarySelect(ui.Select):
    def __init__(self, guild, bot, selected):
        self.bot = bot
        self.guild = guild
        
        ai_cog = self.bot.get_cog("AI")
        gemini_desc = f"Gemini ({ai_cog.model_name})" if ai_cog else "Google Gemini Flash Lite"
        openai_desc = f"ChatGPT ({ai_cog.openai_model})" if ai_cog else "OpenAI GPT-4o-mini"
        anthropic_desc = f"Claude ({ai_cog.anthropic_model})" if ai_cog else "Anthropic Claude 3 Haiku"
        deepseek_desc = f"DeepSeek ({ai_cog.deepseek_model})" if ai_cog else "DeepSeek Coder/Chat V3"
        grok_desc = f"Grok ({ai_cog.grok_model})" if ai_cog else "xAI Grok 2"
        
        options = [
            discord.SelectOption(label="Gemini", value="gemini", description=gemini_desc, emoji="<:sAI_gemini:1515921338106380369>"),
            discord.SelectOption(label="ChatGPT", value="openai", description=openai_desc, emoji="<:sAI_chatgpt:1515922050739601418>"),
            discord.SelectOption(label="Claude", value="anthropic", description=anthropic_desc, emoji="<:sAI_claude:1515922404671754411>"),
            discord.SelectOption(label="DeepSeek", value="deepseek", description=deepseek_desc, emoji="<:sAI_deepseek:1515922761732849664>"),
            discord.SelectOption(label="Grok", value="grok", description=grok_desc, emoji="<:sAI_grok:1516602717290893383>")
        ]
        
        placeholder = "Select Primary AI..."
        for opt in options:
            if opt.value == selected:
                opt.default = True
                placeholder = opt.label

        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO guild_settings (guild_id, llm_primary) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET llm_primary = excluded.llm_primary",
                (self.guild.id, selected)
            )
            await self.bot.db.commit()

        self.bot.settings_cache.setdefault(self.guild.id, {})["llm_primary"] = selected
        self.view.guild_settings["llm_primary"] = selected
        
        self.view._pipeline_view()
        await interaction.response.edit_message(view=self.view)


class Backup1Select(ui.Select):
    def __init__(self, guild, bot, selected):
        self.bot = bot
        self.guild = guild
        
        ai_cog = self.bot.get_cog("AI")
        gemini_desc = f"Gemini ({ai_cog.model_name})" if ai_cog else "Google Gemini Flash Lite"
        openai_desc = f"ChatGPT ({ai_cog.openai_model})" if ai_cog else "OpenAI GPT-4o-mini"
        anthropic_desc = f"Claude ({ai_cog.anthropic_model})" if ai_cog else "Anthropic Claude 3 Haiku"
        deepseek_desc = f"DeepSeek ({ai_cog.deepseek_model})" if ai_cog else "DeepSeek Coder/Chat V3"
        grok_desc = f"Grok ({ai_cog.grok_model})" if ai_cog else "xAI Grok 2"
        
        options = [
            discord.SelectOption(label="Gemini", value="gemini", description=gemini_desc, emoji="<:sAI_gemini:1515921338106380369>"),
            discord.SelectOption(label="ChatGPT", value="openai", description=openai_desc, emoji="<:sAI_chatgpt:1515922050739601418>"),
            discord.SelectOption(label="Claude", value="anthropic", description=anthropic_desc, emoji="<:sAI_claude:1515922404671754411>"),
            discord.SelectOption(label="DeepSeek", value="deepseek", description=deepseek_desc, emoji="<:sAI_deepseek:1515922761732849664>"),
            discord.SelectOption(label="Grok", value="grok", description=grok_desc, emoji="<:sAI_grok:1516602717290893383>"),
            discord.SelectOption(label="Disabled", value="disabled", description="Disable 1st Backup", emoji="❌")
        ]
        
        placeholder = "Select 1st Backup..."
        for opt in options:
            if opt.value == selected:
                opt.default = True
                placeholder = opt.label

        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO guild_settings (guild_id, llm_backup1) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET llm_backup1 = excluded.llm_backup1",
                (self.guild.id, selected)
            )
            await self.bot.db.commit()

        self.bot.settings_cache.setdefault(self.guild.id, {})["llm_backup1"] = selected
        self.view.guild_settings["llm_backup1"] = selected
        
        self.view._pipeline_view()
        await interaction.response.edit_message(view=self.view)


class Backup2Select(ui.Select):
    def __init__(self, guild, bot, selected):
        self.bot = bot
        self.guild = guild
        
        ai_cog = self.bot.get_cog("AI")
        gemini_desc = f"Gemini ({ai_cog.model_name})" if ai_cog else "Google Gemini Flash Lite"
        openai_desc = f"ChatGPT ({ai_cog.openai_model})" if ai_cog else "OpenAI GPT-4o-mini"
        anthropic_desc = f"Claude ({ai_cog.anthropic_model})" if ai_cog else "Anthropic Claude 3 Haiku"
        deepseek_desc = f"DeepSeek ({ai_cog.deepseek_model})" if ai_cog else "DeepSeek Coder/Chat V3"
        grok_desc = f"Grok ({ai_cog.grok_model})" if ai_cog else "xAI Grok 2"
        
        options = [
            discord.SelectOption(label="Gemini", value="gemini", description=gemini_desc, emoji="<:sAI_gemini:1515921338106380369>"),
            discord.SelectOption(label="ChatGPT", value="openai", description=openai_desc, emoji="<:sAI_chatgpt:1515922050739601418>"),
            discord.SelectOption(label="Claude", value="anthropic", description=anthropic_desc, emoji="<:sAI_claude:1515922404671754411>"),
            discord.SelectOption(label="DeepSeek", value="deepseek", description=deepseek_desc, emoji="<:sAI_deepseek:1515922761732849664>"),
            discord.SelectOption(label="Grok", value="grok", description=grok_desc, emoji="<:sAI_grok:1516602717290893383>"),
            discord.SelectOption(label="Disabled", value="disabled", description="Disable 2nd Backup", emoji="❌")
        ]
        
        placeholder = "Select 2nd Backup..."
        for opt in options:
            if opt.value == selected:
                opt.default = True
                placeholder = opt.label

        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO guild_settings (guild_id, llm_backup2) VALUES (?, ?) "
                "ON CONFLICT(guild_id) DO UPDATE SET llm_backup2 = excluded.llm_backup2",
                (self.guild.id, selected)
            )
            await self.bot.db.commit()

        self.bot.settings_cache.setdefault(self.guild.id, {})["llm_backup2"] = selected
        self.view.guild_settings["llm_backup2"] = selected
        
        self.view._pipeline_view()
        await interaction.response.edit_message(view=self.view)







class Settings(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @commands.hybrid_command(name="settings", aliases=["config"])
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def settings(self, ctx):
        guild_id = ctx.guild.id
        if guild_id not in self.bot.settings_cache:
            self.bot.settings_cache[guild_id] = {
                "prefix": "!",
                "cbc": None,
                "llm_primary": "gemini",
                "llm_backup1": "openai",
                "llm_backup2": "anthropic"
            }
        view = SettingsView(self.bot.settings_cache[guild_id], ctx.guild, self.bot)
        await ctx.reply(view=view)


async def setup(bot):
    await bot.add_cog(Settings(bot))