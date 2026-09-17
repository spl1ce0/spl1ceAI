import datetime
from typing import Optional, List, Tuple
import discord
from discord import ui
from cogs.utils.constants import Emojis
from .modals import InspectUserModal, BlacklistModal


class AnalyticsUsersContainer(ui.Container):
    """Page 2.0: Users Overview & Top Lifetime Users."""
    def __init__(self, bot, data: dict):
        super().__init__()
        self.bot = bot

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay("## Users Overview\n-# User acquisition, active user count, and top lifetime users."),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        new_7d = data.get("new_users_7d", 0)
        self.add_item(ui.TextDisplay(f"**Growth:** `{new_7d:,}` New Users acquired in the last 7 days"))
        self.add_item(ui.Separator())

        top_users = data.get("top_users", [])
        user_lines = []
        for uid, cmd_count, fseen, lseen in top_users[:6]:
            user_lines.append(f"• <@{uid}> (`{uid}`): **{cmd_count:,}** commands")

        top_str = "\n".join(user_lines) if user_lines else "*No user activity recorded yet.*"
        self.add_item(ui.TextDisplay(f"**Top Active Users:**\n{top_str}"))
        self.add_item(ui.Separator())

        # Navigation & Actions
        nav_row = ui.ActionRow()

        list_btn = ui.Button(label="User List 📋", style=discord.ButtonStyle.gray)
        list_btn.callback = self._on_user_list_click
        nav_row.add_item(list_btn)

        inspect_btn = ui.Button(label="Inspect User 🔍", style=discord.ButtonStyle.gray)
        inspect_btn.callback = self._on_inspect_click
        nav_row.add_item(inspect_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    @classmethod
    async def create(cls, view):
        data = await view.bot.db_manager.get_user_analytics_summary(limit=8)
        return cls(view.bot, data)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_user_list_click(self, interaction: discord.Interaction):
        await self.view.render_user_list(page=1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_inspect_click(self, interaction: discord.Interaction):
        await interaction.response.send_modal(InspectUserModal(self.bot, self.view, back_target="users"))

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_users()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class UserListContainer(ui.Container):
    """Page 2.0.1: Paginated list of every registered user with 1-click inspect."""
    def __init__(self, bot, rows: List[Tuple], page: int, total_pages: int, total_count: int):
        super().__init__()
        self.bot = bot
        self.page = page
        self.total_pages = total_pages

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay(f"## User Directory\n-# Page {page} of {total_pages} • {total_count:,} Total Registered Users"),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        if not rows:
            self.add_item(ui.TextDisplay("*No registered users found.*"))
        else:
            for uid, cmd_count, fseen, lseen in rows:
                fseen_str = "Never"
                if fseen:
                    try:
                        dt = datetime.datetime.fromisoformat(str(fseen).replace("Z", "+00:00"))
                        fseen_str = f"<t:{int(dt.timestamp())}:d>"
                    except Exception:
                        fseen_str = str(fseen)

                lseen_str = "Never"
                if lseen:
                    try:
                        dt = datetime.datetime.fromisoformat(str(lseen).replace("Z", "+00:00"))
                        lseen_str = f"<t:{int(dt.timestamp())}:R>"
                    except Exception:
                        lseen_str = str(lseen)

                user_display = ui.TextDisplay(
                    f"<@{uid}> (`{uid}`)\n"
                    f"-# ⚡ {cmd_count:,} commands • First seen: {fseen_str} • Last: {lseen_str}"
                )
                inspect_btn = ui.Button(label="Inspect", style=discord.ButtonStyle.gray)
                inspect_btn.callback = self._make_inspect_callback(uid)
                self.add_item(ui.Section(user_display, accessory=inspect_btn))

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

    def _make_inspect_callback(self, user_id: int):
        async def callback(interaction: discord.Interaction):
            await self.view.render_user_dossier(user_id, back_target="user_list")
            await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())
        return callback

    @classmethod
    async def create(cls, view, page: int = 1, page_size: int = 5):
        rows, total_count, total_pages = await view.bot.db_manager.get_users_paginated(page=page, page_size=page_size)
        return cls(view.bot, rows, page, total_pages, total_count)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_users()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_prev_click(self, interaction: discord.Interaction):
        await self.view.render_user_list(page=self.page - 1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_next_click(self, interaction: discord.Interaction):
        await self.view.render_user_list(page=self.page + 1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_user_list(page=self.page)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class UserDossierContainer(ui.Container):
    """Page 2.1: User Forensic Intelligence Dossier."""
    def __init__(self, bot, user_id: int, dossier: dict, target_user: Optional[discord.User] = None, back_target: str = "users"):
        super().__init__()
        self.bot = bot
        self.user_id = user_id
        self.dossier = dossier
        self.target_user = target_user
        self.back_target = back_target

        user_name = target_user.name if target_user else f"User ID {user_id}"

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay(f"## User Dossier: {user_name}\n-# Lifetime activity, mutual servers, and forensic command records."),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        # 1. Status & Badges
        is_bl = dossier.get("is_blacklisted", False)
        status_badge = "🚫 **BLACKLISTED**" if is_bl else "🟢 **ACTIVE & CLEAR**"

        total_cmds = dossier.get("total_commands", 0)
        total_ai = dossier.get("total_ai_queries", 0)
        total_tok = dossier.get("total_tokens", 0)

        fseen = dossier.get("first_seen")
        fseen_str = "Never"
        if fseen:
            try:
                dt = datetime.datetime.fromisoformat(str(fseen).replace("Z", "+00:00"))
                fseen_str = f"<t:{int(dt.timestamp())}:d>"
            except Exception:
                fseen_str = str(fseen)

        lseen = dossier.get("last_seen")
        lseen_str = "Never"
        if lseen:
            try:
                dt = datetime.datetime.fromisoformat(str(lseen).replace("Z", "+00:00"))
                lseen_str = f"<t:{int(dt.timestamp())}:R>"
            except Exception:
                lseen_str = str(lseen)

        # Mutual Guilds
        mutuals = [g.name for g in self.bot.guilds if g.get_member(user_id)]
        mutual_str = f"`{len(mutuals)}` ({', '.join(mutuals[:3])}...)" if mutuals else "*None (No shared servers)*"

        overview_text = (
            f"**User ID:** `{user_id}` • **Status:** {status_badge}\n"
            f"**Mutual Servers:** {mutual_str}\n"
            f"**Engagement History:** First seen {fseen_str} • Last active {lseen_str}\n"
            f"**Lifetime Activity:** `{total_cmds:,}` commands • `{total_ai:,}` AI prompts (`{total_tok:,}` tokens)"
        )
        self.add_item(ui.TextDisplay(overview_text))
        self.add_item(ui.Separator())

        # Action Buttons
        nav_row = ui.ActionRow()

        if is_bl:
            bl_btn = ui.Button(label="Unblacklist User 🟢", style=discord.ButtonStyle.green)
            bl_btn.callback = self._on_unblacklist_click
        else:
            bl_btn = ui.Button(label="Blacklist User 🚫", style=discord.ButtonStyle.red)
            bl_btn.callback = self._on_blacklist_click
        nav_row.add_item(bl_btn)

        ai_logs_btn = ui.Button(label="AI History 🤖", style=discord.ButtonStyle.gray)
        ai_logs_btn.callback = self._on_ai_history_click
        nav_row.add_item(ai_logs_btn)

        cmd_logs_btn = ui.Button(label="Command History 📜", style=discord.ButtonStyle.gray)
        cmd_logs_btn.callback = self._on_cmd_history_click
        nav_row.add_item(cmd_logs_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    async def _on_back_click(self, interaction: discord.Interaction):
        if self.back_target == "user_list":
            await self.view.render_user_list()
        else:
            await self.view.render_users()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_blacklist_click(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BlacklistModal(self.bot, self.user_id, self.view))

    async def _on_unblacklist_click(self, interaction: discord.Interaction):
        await self.bot.db_manager.unblacklist_user(self.user_id)
        if self.user_id in self.bot.blacklist_cache:
            self.bot.blacklist_cache.remove(self.user_id)
        await self.view.render_user_dossier(self.user_id, back_target=self.back_target)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_ai_history_click(self, interaction: discord.Interaction):
        await self.view.render_user_ai_queries(self.user_id, page=1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_cmd_history_click(self, interaction: discord.Interaction):
        await self.view.render_user_commands(self.user_id, page=1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_user_dossier(self.user_id, back_target=self.back_target)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class UserAIQueriesContainer(ui.Container):
    """Page 2.1.1: Paginated AI queries for a specific user."""
    def __init__(self, bot, user_id: int, rows: List[Tuple], page: int, total_pages: int, total_count: int):
        super().__init__()
        self.bot = bot
        self.user_id = user_id
        self.page = page
        self.total_pages = total_pages

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back to Dossier", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay(f"## User AI History\n-# Page {page} of {total_pages} • {total_count:,} Total Prompts"),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        entries = []
        for gid, mname, ptext, itok, otok, lat, cid, ts in rows:
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = f"<t:{int(dt_obj.timestamp())}:R>"
            except Exception:
                time_str = ts
            snippet = f'"{ptext[:120]}..."' if ptext else "*[No prompt recorded]*"
            tokens = (itok or 0) + (otok or 0)
            guild_obj = self.bot.get_guild(gid) if gid else None
            gname = guild_obj.name if guild_obj else f"Guild {gid}"
            entries.append(
                f"• In **{gname}** via `{mname}` • `{tokens:,}` tok • `{lat}ms` • {time_str}\n"
                f"  {snippet}"
            )

        content = "\n\n".join(entries) if entries else "*No AI queries recorded for this user.*"
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
        await self.view.render_user_dossier(self.user_id)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_prev_click(self, interaction: discord.Interaction):
        await self.view.render_user_ai_queries(self.user_id, page=self.page - 1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_next_click(self, interaction: discord.Interaction):
        await self.view.render_user_ai_queries(self.user_id, page=self.page + 1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_user_ai_queries(self.user_id, page=self.page)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class UserCommandHistoryContainer(ui.Container):
    """Page 2.1.2: Paginated command executions for a specific user."""
    def __init__(self, bot, user_id: int, rows: List[Tuple], page: int, total_pages: int, total_count: int):
        super().__init__()
        self.bot = bot
        self.user_id = user_id
        self.page = page
        self.total_pages = total_pages

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back to Dossier", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay(f"## User Command History\n-# Page {page} of {total_pages} • {total_count:,} Total Executions"),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        entries = []
        for gid, cname, lat, succ, ts in rows:
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = f"<t:{int(dt_obj.timestamp())}:R>"
            except Exception:
                time_str = ts
            status_icon = "🟢" if succ else "🔴"
            guild_obj = self.bot.get_guild(gid) if gid else None
            gname = guild_obj.name if guild_obj else f"Guild {gid}"
            entries.append(f"{status_icon} In **{gname}**: `!{cname}` ({lat}ms) • {time_str}")

        content = "\n".join(entries) if entries else "*No commands recorded for this user.*"
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
        await self.view.render_user_dossier(self.user_id)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_prev_click(self, interaction: discord.Interaction):
        await self.view.render_user_commands(self.user_id, page=self.page - 1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_next_click(self, interaction: discord.Interaction):
        await self.view.render_user_commands(self.user_id, page=self.page + 1)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_user_commands(self.user_id, page=self.page)
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())
