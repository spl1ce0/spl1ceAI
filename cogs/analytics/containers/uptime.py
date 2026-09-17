import datetime
from typing import Optional
import discord
from discord import ui
from cogs.utils.constants import Emojis
from ..charts import generate_uptime_chart, calculate_uptime_stats


class AnalyticsUptimeContainer(ui.Container):
    """Page 3.0: Detailed 24h Uptime & Availability Diagnostics."""
    def __init__(self, bot, hourly_snapshots: list, file: Optional[discord.File] = None):
        super().__init__()
        self.bot = bot
        self.file = file

        self.add_item(ui.TextDisplay("## Uptime & Availability"))
        self.add_item(ui.Separator())

        uptime_pct, down_minutes = calculate_uptime_stats(hourly_snapshots)

        if down_minutes == 0:
            status_desc = "🟢 **100% Online** • Zero downtime incidents in 24 hours."
        else:
            status_desc = f"⚠️ **{down_minutes} Minutes Downtime** observed across 24h."

        start_time_str = "Unknown"
        if hasattr(self.bot, "start_time"):
            start_time_str = f"<t:{int(self.bot.start_time.timestamp())}:R>"

        ws_latency = int(self.bot.latency * 1000)

        overview_text = (
            f"**24h Availability:** `{uptime_pct:.2f}%` • {status_desc}\n"
            f"**Current Session:** Online since {start_time_str}\n"
            f"**Gateway Ping:** `{ws_latency} ms` (WebSocket connection)"
        )
        self.add_item(ui.TextDisplay(overview_text))
        self.add_item(ui.Separator())

        if self.file:
            self.add_item(ui.MediaGallery(discord.MediaGalleryItem(media=self.file)))
            self.add_item(ui.Separator())

        # Action Buttons
        nav_row = ui.ActionRow()

        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        nav_row.add_item(back_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    @classmethod
    async def create(cls, view):
        stats = await view.bot.db_manager.get_analytics_home_summary()
        snapshots = stats.get("hourly_snapshots", [])
        chart_buf, _ = generate_uptime_chart(snapshots)
        chart_file = discord.File(chart_buf, filename="uptime_graph.png")
        return cls(view.bot, snapshots, file=chart_file)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_uptime()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())
