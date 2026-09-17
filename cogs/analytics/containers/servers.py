import datetime
from typing import Optional, List, Tuple
import discord
from discord import ui
from cogs.utils.constants import Emojis
from .modals import InspectGuildModal
from ..charts import generate_servers_chart


class AnalyticsServersContainer(ui.Container):
    """Page 1.0: Servers Overview, Growth Graph & Join/Leave Events."""
    def __init__(self, bot, data: dict, current_guilds: int, total_members: int, growth_data: list, timeframe: str = "1d", file: Optional[discord.File] = None):
        super().__init__()
        self.bot = bot
        self.timeframe = timeframe
        self.file = file

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay("## Servers Overview\n-# Guild installations, growth trajectory, and retention metrics."),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        total_joins = data.get("total_joins", 0)
        total_leaves = data.get("total_leaves", 0)
        net_all = total_joins - total_leaves
        net_str = f"+{net_all}" if net_all >= 0 else f"{net_all}"

        summary_text = (
            f"**Total Installed:** `{current_guilds:,}` Servers\n"
            f"**Total Reach:** `{total_members:,}` Users\n"
            f"**Historical Activity:** `{total_joins:,}` Joins • `{total_leaves:,}` Leaves (Net: `{net_str}`)"
        )
        self.add_item(ui.TextDisplay(summary_text))
        self.add_item(ui.Separator())

        # Server Growth Chart & Timeframe Filter Buttons
        if self.file:
            self.add_item(ui.MediaGallery(discord.MediaGalleryItem(media=self.file)))
            
            tf_row = ui.ActionRow()
            for tf in ["1d", "1w", "1m", "1y"]:
                btn = ui.Button(
                    label=tf.upper(),
                    style=discord.ButtonStyle.primary if tf == self.timeframe else discord.ButtonStyle.gray
                )
                btn.callback = self._make_tf_callback(tf)
                tf_row.add_item(btn)
            self.add_item(tf_row)
            self.add_item(ui.Separator())

        # Recent join / leave events
        recent_events = data.get("recent_events", [])
        event_lines = []
        for gid, etype, mcount, ts in recent_events[:5]:
            icon = "🟢" if etype == "join" else "🔴"
            guild_obj = self.bot.get_guild(gid)
            g_name = f"**{guild_obj.name}**" if guild_obj else f"Guild `{gid}`"
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = f"<t:{int(dt_obj.timestamp())}:R>"
            except Exception:
                time_str = ts
            event_lines.append(f"{icon} {etype.upper()}: {g_name} ({mcount:,} members) • {time_str}")

        event_str = "\n".join(event_lines) if event_lines else "*No server events recorded yet.*"
        self.add_item(ui.TextDisplay(f"**Recent Events:**\n{event_str}"))
        self.add_item(ui.Separator())

        # Action Buttons
        nav_row = ui.ActionRow()

        list_btn = ui.Button(label="Server List 📋", style=discord.ButtonStyle.gray)
        list_btn.callback = self._on_server_list_click
        nav_row.add_item(list_btn)

        inspect_btn = ui.Button(label="Inspect Server 🔍", style=discord.ButtonStyle.gray)
        inspect_btn.callback = self._on_inspect_click
        nav_row.add_item(inspect_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    def _make_tf_callback(self, tf: str):
        async def callback(interaction: discord.Interaction):
            await self.view.render_servers(timeframe=tf)
            await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())
        return callback

    @classmethod
    async def create(cls, view, timeframe: str = "1d"):
        data = await view.bot.db_manager.get_guild_analytics_summary(limit=8)
        current_guilds = len(view.bot.guilds)
        total_members = sum(g.member_count for g in view.bot.guilds if g.member_count)
        growth_data = await view.bot.db_manager.get_server_growth_history(timeframe=timeframe)

        chart_buf = generate_servers_chart(growth_data, timeframe=timeframe, current_count=current_guilds)
        chart_file = discord.File(chart_buf, filename="servers_growth.png")
        return cls(view.bot, data, current_guilds, total_members, growth_data, timeframe=timeframe, file=chart_file)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_server_list_click(self, interaction: discord.Interaction):
        await self.view.render_server_list(page=1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_inspect_click(self, interaction: discord.Interaction):
        await interaction.response.send_modal(InspectGuildModal(self.bot, self.view, back_target="servers"))

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_servers(timeframe=self.timeframe)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class ServerListContainer(ui.Container):
    """Page 1.0.1: Paginated list of every server the bot is in with 1-click inspect."""
    def __init__(self, bot, guilds: List[discord.Guild], page: int, total_pages: int, total_count: int):
        super().__init__()
        self.bot = bot
        self.page = page
        self.total_pages = total_pages

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay(f"## Server Directory\n-# Page {page} of {total_pages} • {total_count:,} Total Servers"),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        if not guilds:
            self.add_item(ui.TextDisplay("*No servers found.*"))
        else:
            for g in guilds:
                settings = self.bot.settings_cache.get(g.id, {})
                plan_str = "PREMIUM 👑" if settings.get("is_premium") else "BYOK ⚡" if settings.get("has_byok") else "FREE"
                owner_name = g.owner.name if g.owner else f"Owner ID {g.owner_id}"
                members = g.member_count or 0

                server_display = ui.TextDisplay(
                    f"**{g.name}** (`{g.id}`)\n"
                    f"-# 👥 {members:,} members • Owner: {owner_name} • Plan: `{plan_str}`"
                )
                inspect_btn = ui.Button(label="Inspect", style=discord.ButtonStyle.gray)
                inspect_btn.callback = self._make_inspect_callback(g.id)
                self.add_item(ui.Section(server_display, accessory=inspect_btn))

        self.add_item(ui.Separator())

        # Pagination Action Row
        nav_row = ui.ActionRow()

        prev_btn = ui.Button(label="◀ Prev", style=discord.ButtonStyle.gray, disabled=(page <= 1))
        prev_btn.callback = self._on_prev_click
        nav_row.add_item(prev_btn)

        page_btn = ui.Button(label=f"{page}/{total_pages}", style=discord.ButtonStyle.gray, disabled=True)
        nav_row.add_item(page_btn)

        next_btn = ui.Button(label="Next ▶", style=discord.ButtonStyle.gray, disabled=(page >= total_pages))
        next_btn.callback = self._on_next_click
        nav_row.add_item(next_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    def _make_inspect_callback(self, guild_id: int):
        async def callback(interaction: discord.Interaction):
            await self.view.render_server_dossier(guild_id, back_target="server_list")
            await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())
        return callback

    @classmethod
    def create(cls, view, page: int = 1, page_size: int = 5):
        all_guilds = sorted(view.bot.guilds, key=lambda g: g.member_count or 0, reverse=True)
        total_count = len(all_guilds)
        total_pages = max(1, (total_count + page_size - 1) // page_size)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * page_size
        page_guilds = all_guilds[offset:offset + page_size]
        return cls(view.bot, page_guilds, page, total_pages, total_count)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_servers()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_prev_click(self, interaction: discord.Interaction):
        await self.view.render_server_list(page=self.page - 1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_next_click(self, interaction: discord.Interaction):
        await self.view.render_server_list(page=self.page + 1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_server_list(page=self.page)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class ServerDossierContainer(ui.Container):
    """Page 1.1: Server Forensic Dossier."""
    def __init__(self, bot, guild_id: int, dossier: dict, target_guild: Optional[discord.Guild] = None, back_target: str = "servers"):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.dossier = dossier
        self.target_guild = target_guild
        self.back_target = back_target

        guild_name = target_guild.name if target_guild else f"Server ID {guild_id}"

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay(f"## Server Dossier: {guild_name}\n-# Forensic intelligence, usage volume, and channel stats."),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        # 1. Identity & Plan
        settings = dossier.get("settings", {})
        is_premium = settings.get("is_premium", False)
        plan_str = "PREMIUM 👑" if is_premium else "FREE"
        members = target_guild.member_count if target_guild else dossier.get("initial_members", 0)
        owner_str = f"<@{target_guild.owner_id}> (`{target_guild.owner_id}`)" if target_guild and target_guild.owner_id else "Unknown"

        joined_str = "Unknown"
        joined_val = dossier.get("joined_at")
        if joined_val:
            try:
                dt_j = datetime.datetime.fromisoformat(str(joined_val).replace("Z", "+00:00"))
                joined_str = f"<t:{int(dt_j.timestamp())}:R>"
            except Exception:
                joined_str = str(joined_val)

        total_cmds = dossier.get("total_commands", 0)
        total_ai = dossier.get("total_ai_queries", 0)
        total_tokens = dossier.get("total_tokens", 0)

        overview_text = (
            f"**Server ID:** `{guild_id}` • **Plan:** `{plan_str}`\n"
            f"**Owner:** {owner_str} • **Members:** `{members:,}`\n"
            f"**Bot Joined:** {joined_str}\n"
            f"**Lifetime Volume:** `{total_cmds:,}` commands • `{total_ai:,}` AI queries (`{total_tokens:,}` tokens)"
        )
        self.add_item(ui.TextDisplay(overview_text))
        self.add_item(ui.Separator())

        # 2. Top Active Channels
        top_channels = dossier.get("top_channels", [])
        channel_lines = []
        for cid, cnt in top_channels[:3]:
            ch_obj = target_guild.get_channel(cid) if target_guild else None
            ch_name = f"<#{cid}>" if ch_obj else f"Channel `{cid}`"
            channel_lines.append(f"• {ch_name}: **{cnt:,}** commands")
        top_ch_str = "\n".join(channel_lines) if channel_lines else "*No channel activity captured.*"
        self.add_item(ui.TextDisplay(f"**Top Active Channels:**\n{top_ch_str}"))
        self.add_item(ui.Separator())

        # 3. Top Active Users in this Server
        top_users = dossier.get("top_users", [])
        user_lines = []
        for uid, cnt in top_users[:3]:
            user_lines.append(f"• <@{uid}> (`{uid}`): **{cnt:,}** commands")
        top_u_str = "\n".join(user_lines) if user_lines else "*No user activity captured.*"
        self.add_item(ui.TextDisplay(f"**Top Active Users:**\n{top_u_str}"))
        self.add_item(ui.Separator())

        # Navigation Action Row
        nav_row = ui.ActionRow()

        settings_btn = ui.Button(label="Settings ⚙️", style=discord.ButtonStyle.gray)
        settings_btn.callback = self._on_settings_click
        nav_row.add_item(settings_btn)

        ai_logs_btn = ui.Button(label="AI Query Logs 🤖", style=discord.ButtonStyle.gray)
        ai_logs_btn.callback = self._on_ai_logs_click
        nav_row.add_item(ai_logs_btn)

        cmd_logs_btn = ui.Button(label="Command Logs 📜", style=discord.ButtonStyle.gray)
        cmd_logs_btn.callback = self._on_cmd_logs_click
        nav_row.add_item(cmd_logs_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    async def _on_back_click(self, interaction: discord.Interaction):
        if self.back_target == "server_list":
            await self.view.render_server_list()
        else:
            await self.view.render_servers()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_settings_click(self, interaction: discord.Interaction):
        await self.view.render_server_settings(self.guild_id)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_ai_logs_click(self, interaction: discord.Interaction):
        await self.view.render_server_ai_queries(self.guild_id, page=1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_cmd_logs_click(self, interaction: discord.Interaction):
        await self.view.render_server_commands(self.guild_id, page=1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_server_dossier(self.guild_id, back_target=self.back_target)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class ServerSettingsAuditContainer(ui.Container):
    """Page 1.1.1: Server Settings & Audit Log."""
    def __init__(self, bot, guild_id: int, dossier: dict):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay("## Server Settings & Audit\n-# Runtime configuration and custom system instructions."),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        settings = dossier.get("settings", {})
        prefix = settings.get("prefix", "!")
        llm = settings.get("llm_primary", "gemini")
        log_ch = settings.get("log_channel")
        log_str = f"<#{log_ch}>" if log_ch else "*None*"
        prompt = settings.get("custom_prompt")
        prompt_status = f"`{len(prompt)}` chars set" if prompt else "*Default (No custom instructions)*"

        config_text = (
            f"**Prefix:** `{prefix}` • **Primary Model:** `{llm}`\n"
            f"**Log Channel:** {log_str}\n"
            f"**System Instructions:** {prompt_status}"
        )
        self.add_item(ui.TextDisplay(config_text))

        if prompt:
            preview = prompt[:300] + "..." if len(prompt) > 300 else prompt
            self.add_item(ui.TextDisplay(f"```yaml\n{preview}\n```"))

        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()
        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)
        self.add_item(nav_row)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_server_dossier(self.guild_id)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_server_settings(self.guild_id)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class ServerAIQueriesContainer(ui.Container):
    """Page 1.1.2: Paginated AI query logs for a server."""
    def __init__(self, bot, guild_id: int, rows: List[Tuple], page: int, total_pages: int, total_count: int):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.page = page
        self.total_pages = total_pages

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay(f"## Server AI Query Logs\n-# Page {page} of {total_pages} • {total_count:,} Total Queries"),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        entries = []
        for uid, mname, ptext, itok, otok, lat, cid, ts in rows:
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = f"<t:{int(dt_obj.timestamp())}:R>"
            except Exception:
                time_str = ts
            snippet = f'"{ptext[:120]}..."' if ptext else "*[No prompt recorded]*"
            tokens = (itok or 0) + (otok or 0)
            entries.append(
                f"• <@{uid}> in <#{cid}> via `{mname}` • `{tokens:,}` tok • `{lat}ms` • {time_str}\n"
                f"  {snippet}"
            )

        content = "\n\n".join(entries) if entries else "*No AI queries recorded for this server.*"
        self.add_item(ui.TextDisplay(content))
        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()

        prev_btn = ui.Button(label="◀ Prev", style=discord.ButtonStyle.gray, disabled=(page <= 1))
        prev_btn.callback = self._on_prev_click
        nav_row.add_item(prev_btn)

        page_btn = ui.Button(label=f"{page}/{total_pages}", style=discord.ButtonStyle.gray, disabled=True)
        nav_row.add_item(page_btn)

        next_btn = ui.Button(label="Next ▶", style=discord.ButtonStyle.gray, disabled=(page >= total_pages))
        next_btn.callback = self._on_next_click
        nav_row.add_item(next_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_server_dossier(self.guild_id)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_prev_click(self, interaction: discord.Interaction):
        await self.view.render_server_ai_queries(self.guild_id, page=self.page - 1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_next_click(self, interaction: discord.Interaction):
        await self.view.render_server_ai_queries(self.guild_id, page=self.page + 1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_server_ai_queries(self.guild_id, page=self.page)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class ServerCommandHistoryContainer(ui.Container):
    """Page 1.1.3: Paginated command history for a server."""
    def __init__(self, bot, guild_id: int, rows: List[Tuple], page: int, total_pages: int, total_count: int):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.page = page
        self.total_pages = total_pages

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay(f"## Server Command History\n-# Page {page} of {total_pages} • {total_count:,} Total Commands"),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        entries = []
        for uid, cname, cid, lat, succ, ts in rows:
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = f"<t:{int(dt_obj.timestamp())}:R>"
            except Exception:
                time_str = ts
            status_icon = "🟢" if succ else "🔴"
            entries.append(f"{status_icon} <@{uid}> in <#{cid}>: `!{cname}` ({lat}ms) • {time_str}")

        content = "\n".join(entries) if entries else "*No commands recorded for this server.*"
        self.add_item(ui.TextDisplay(content))
        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()

        prev_btn = ui.Button(label="◀ Prev", style=discord.ButtonStyle.gray, disabled=(page <= 1))
        prev_btn.callback = self._on_prev_click
        nav_row.add_item(prev_btn)

        page_btn = ui.Button(label=f"{page}/{total_pages}", style=discord.ButtonStyle.gray, disabled=True)
        nav_row.add_item(page_btn)

        next_btn = ui.Button(label="Next ▶", style=discord.ButtonStyle.gray, disabled=(page >= total_pages))
        next_btn.callback = self._on_next_click
        nav_row.add_item(next_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_server_dossier(self.guild_id)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_prev_click(self, interaction: discord.Interaction):
        await self.view.render_server_commands(self.guild_id, page=self.page - 1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_next_click(self, interaction: discord.Interaction):
        await self.view.render_server_commands(self.guild_id, page=self.page + 1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_server_commands(self.guild_id, page=self.page)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())
