import datetime
from typing import Optional
import discord
from discord import ui
from cogs.utils.constants import Emojis
from ..charts import generate_errors_chart


class AnalyticsErrorsContainer(ui.Container):
    """Page 6.0: Error & Exception Telemetry Tracker."""
    def __init__(self, bot, data: dict, file: Optional[discord.File] = None):
        super().__init__()
        self.bot = bot
        self.data = data
        self.file = file

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay("## Reliability & Error Tracker\n-# Real-time exception telemetry and command error analysis."),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        total_errors = data.get("errors_24h", data.get("total_errors_24h", 0))

        overview_text = (
            f"**Exceptions (24h):** `{total_errors:,}` incidents\n"
            f"-# Uncaught exceptions and runtime command failures captured by telemetry."
        )
        self.add_item(ui.TextDisplay(overview_text))
        self.add_item(ui.Separator())

        if self.file:
            self.add_item(ui.MediaGallery(discord.MediaGalleryItem(media=self.file)))
            self.add_item(ui.Separator())

        # Top Error Types Breakdown
        error_types = data.get("top_errors", data.get("top_error_types", []))
        type_lines = []
        for etype, cnt in error_types[:5]:
            type_lines.append(f"• `{etype}`: **{cnt:,}** occurrences")
        type_str = "\n".join(type_lines) if type_lines else "*No errors recorded in the last 24h.*"
        self.add_item(ui.TextDisplay(f"**Top Exception Types:**\n{type_str}"))
        self.add_item(ui.Separator())

        # Recent Errors List
        recent_errors = data.get("recent_errors", [])
        recent_lines = []
        for cname, etype, emsg, ts in recent_errors[:4]:
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = f"<t:{int(dt_obj.timestamp())}:R>"
            except Exception:
                time_str = ts
            msg_snippet = f'"{emsg[:70]}..."' if emsg else "*[No message]*"
            recent_lines.append(f"• `!{cname}` &bull; `{etype}`: {msg_snippet} - {time_str}")

        recent_str = "\n".join(recent_lines) if recent_lines else "• All systems clear — zero uncaught exceptions in 24h."
        self.add_item(ui.TextDisplay(f"**Recent Error Incidents:**\n{recent_str}"))
        self.add_item(ui.Separator())

        # Navigation Action Rows
        nav_row = ui.ActionRow()

        tb_btn = ui.Button(label="View Latest Traceback 🔍", style=discord.ButtonStyle.gray, disabled=(total_errors == 0))
        tb_btn.callback = self._on_traceback_click
        nav_row.add_item(tb_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    @classmethod
    async def create(cls, view):
        data = await view.bot.db_manager.get_error_analytics_summary()
        chart_buf = generate_errors_chart(data.get("hourly_errors", []))
        chart_file = discord.File(chart_buf, filename="errors_chart.png")
        return cls(view.bot, data, file=chart_file)

    async def _on_traceback_click(self, interaction: discord.Interaction):
        await self.view.render_error_traceback()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_errors()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class ErrorTracebackContainer(ui.Container):
    """Page 6.1: Full Traceback Inspector for the most recent crash."""
    def __init__(self, bot, error_row: Optional[tuple] = None):
        super().__init__()
        self.bot = bot

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back to Errors", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay("## Crash Traceback Inspector\n-# Forensic inspection of the most recent uncaught exception."),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        if error_row:
            cname, etype, emsg, tb, ts = error_row[:5]
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = f"<t:{int(dt_obj.timestamp())}:R>"
            except Exception:
                time_str = ts

            meta_text = (
                f"**Command:** `!{cname}` • **Type:** `{etype}`\n"
                f"**Message:** `{emsg}`\n"
                f"**Occurred:** {time_str}"
            )
            self.add_item(ui.TextDisplay(meta_text))

            tb_text = tb if tb else "No traceback recorded."
            if len(tb_text) > 1500:
                tb_text = tb_text[-1500:]
            self.add_item(ui.TextDisplay(f"```py\n{tb_text}\n```"))
        else:
            self.add_item(ui.TextDisplay("*No error tracebacks logged in the database.*"))

        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()
        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)
        self.add_item(nav_row)

    @classmethod
    async def create(cls, view):
        async with view.bot.db_manager.db.cursor() as cursor:
            await cursor.execute(
                "SELECT command_name, error_type, error_message, traceback, timestamp "
                "FROM error_telemetry ORDER BY id DESC LIMIT 1"
            )
            row = await cursor.fetchone()
        return cls(view.bot, row)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_errors()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_error_traceback()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())
