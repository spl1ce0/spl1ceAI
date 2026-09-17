import discord
from discord import ui
from cogs.utils.constants import Emojis
from ..charts import calculate_uptime_stats


class AnalyticsHomeContainer(ui.Container):
    def __init__(self, bot, stats: dict, guild_count: int, total_members: int, uptime_pct: float = 100.0, down_minutes: int = 0):
        super().__init__()
        self.bot = bot

        # Header
        self.add_item(ui.TextDisplay("## Analytics"))
        self.add_item(ui.Separator())

        # 1. Guilds Pulse Section
        joins_7d = stats.get("joins_7d", 0)
        leaves_7d = stats.get("leaves_7d", 0)
        net_growth = joins_7d - leaves_7d
        growth_str = f"+{net_growth}" if net_growth >= 0 else f"{net_growth}"

        guild_text = ui.TextDisplay(
            f"**Servers:** `{guild_count:,}` Total Active\n"
            f"-# 7d Growth: {growth_str} net ({joins_7d} joins, {leaves_7d} leaves)"
        )
        guild_btn = ui.Button(label="Servers →", style=discord.ButtonStyle.gray)
        guild_btn.callback = self._on_guilds_click
        self.add_item(ui.Section(guild_text, accessory=guild_btn))

        # 2. Users Pulse Section
        total_registered = stats.get("total_registered_users", 0)
        dau = stats.get("active_users_24h", 0)
        new_users_24h = stats.get("new_users_24h", 0)

        user_text = ui.TextDisplay(
            f"**Users:** `{total_members:,}` Reach (`{total_registered:,}` registered)\n"
            f"-# DAU: {dau:,} active today • {new_users_24h:,} new"
        )
        user_btn = ui.Button(label="Users →", style=discord.ButtonStyle.gray)
        user_btn.callback = self._on_users_click
        self.add_item(ui.Section(user_text, accessory=user_btn))

        # 3. Uptime Pulse Section
        if down_minutes == 0:
            down_str = "0m downtime in 24h"
        elif down_minutes < 60:
            down_str = f"Down for {down_minutes}m in 24h"
        else:
            d_hours, d_mins = divmod(down_minutes, 60)
            down_str = f"Down for {d_hours}h {d_mins}m in 24h" if d_mins else f"Down for {d_hours}h in 24h"

        # 12-block 24h sparkline (each block = 2h)
        sparkline = "🟩" * 12
        uptime_display = ui.TextDisplay(
            f"**Uptime:** `{uptime_pct:.1f}%` • {sparkline}\n"
            f"-# {down_str}"
        )
        uptime_btn = ui.Button(label="Uptime Details →", style=discord.ButtonStyle.gray)
        uptime_btn.callback = self._on_uptime_click
        self.add_item(ui.Section(uptime_display, accessory=uptime_btn))

        self.add_item(ui.Separator())

        # Navigation Row 1: Infrastructure & Reliability
        nav_row1 = ui.ActionRow()

        ai_btn = ui.Button(label="AI Engine", style=discord.ButtonStyle.gray)
        ai_btn.callback = self._on_ai_click
        nav_row1.add_item(ai_btn)

        sys_btn = ui.Button(label="System / VPS", style=discord.ButtonStyle.gray)
        sys_btn.callback = self._on_system_click
        nav_row1.add_item(sys_btn)

        err_btn = ui.Button(label="Errors & Logs", style=discord.ButtonStyle.gray)
        err_btn.callback = self._on_errors_click
        nav_row1.add_item(err_btn)

        self.add_item(nav_row1)

        # Navigation Row 2: Traffic & Actions
        nav_row2 = ui.ActionRow()

        cmd_btn = ui.Button(label="Commands & Activity", style=discord.ButtonStyle.gray)
        cmd_btn.callback = self._on_commands_click
        nav_row2.add_item(cmd_btn)

        heat_btn = ui.Button(label="Heatmap & Traffic", style=discord.ButtonStyle.gray)
        heat_btn.callback = self._on_heatmap_click
        nav_row2.add_item(heat_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row2.add_item(ref_btn)

        self.add_item(nav_row2)

    @classmethod
    async def create(cls, view):
        stats = await view.bot.db_manager.get_analytics_home_summary()
        guild_count = len(view.bot.guilds)
        total_members = sum(g.member_count for g in view.bot.guilds if g.member_count)
        snapshots = stats.get("hourly_snapshots", [])
        uptime_pct, down_minutes = calculate_uptime_stats(snapshots)
        return cls(view.bot, stats, guild_count, total_members, uptime_pct=uptime_pct, down_minutes=down_minutes)

    async def _on_guilds_click(self, interaction: discord.Interaction):
        await self.view.render_servers()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_users_click(self, interaction: discord.Interaction):
        await self.view.render_users()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_uptime_click(self, interaction: discord.Interaction):
        await self.view.render_uptime()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_ai_click(self, interaction: discord.Interaction):
        await self.view.render_ai()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_system_click(self, interaction: discord.Interaction):
        await self.view.render_system()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_errors_click(self, interaction: discord.Interaction):
        await self.view.render_errors()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_commands_click(self, interaction: discord.Interaction):
        await self.view.render_commands()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_heatmap_click(self, interaction: discord.Interaction):
        await self.view.render_heatmap()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())
