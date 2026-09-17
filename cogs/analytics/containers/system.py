import os
import psutil
import discord
from discord import ui
from cogs.utils.constants import Emojis


class AnalyticsSystemContainer(ui.Container):
    """Page 5.0: Host Diagnostics & VPS System Health."""
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay("## Host & VPS Diagnostics\n-# Real-time hardware utilization, database footprint, and ping."),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        cpu_pct = psutil.cpu_percent()
        ram = psutil.virtual_memory()
        ram_pct = ram.percent
        ram_used_mb = int(ram.used / (1024 * 1024))
        ram_total_mb = int(ram.total / (1024 * 1024))

        disk = psutil.disk_usage('/')
        disk_pct = disk.percent
        disk_used_gb = round(disk.used / (1024 ** 3), 1)
        disk_total_gb = round(disk.total / (1024 ** 3), 1)

        db_size_mb = 0.0
        if os.path.exists("bot.db"):
            db_size_mb = round(os.path.getsize("bot.db") / (1024 * 1024), 2)

        ws_latency = int(self.bot.latency * 1000)

        def _bar(pct):
            filled = min(12, max(0, int(round((pct / 100.0) * 12))))
            return "█" * filled + "░" * (12 - filled)

        metrics_text = (
            f"**CPU Load:** `{cpu_pct:.1f}%` `[{_bar(cpu_pct)}]`\n"
            f"**RAM Usage:** `{ram_pct:.1f}%` ({ram_used_mb:,} / {ram_total_mb:,} MB) `[{_bar(ram_pct)}]`\n"
            f"**Disk Usage:** `{disk_pct:.1f}%` ({disk_used_gb} / {disk_total_gb} GB) `[{_bar(disk_pct)}]`\n"
            f"**Database Size:** `{db_size_mb} MB` (`bot.db`)\n"
            f"**Gateway Ping:** `{ws_latency} ms` (Discord WebSocket)"
        )
        self.add_item(ui.TextDisplay(metrics_text))
        self.add_item(ui.Separator())

        # Action Buttons (Refresh)
        nav_row = ui.ActionRow()
        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)
        self.add_item(nav_row)

    @classmethod
    async def create(cls, view):
        return cls(view.bot)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_system()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())
