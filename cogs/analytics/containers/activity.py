import discord
from discord import ui
from cogs.utils.constants import Emojis


class AnalyticsCommandsContainer(ui.Container):
    """Page 7.0: Command Telemetry, Top Commands & Execution Latencies."""
    def __init__(self, bot, data: dict):
        super().__init__()
        self.bot = bot

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay("## Commands & Feature Telemetry\n-# Latency breakdown, popular commands and invocation ratio."),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        total = data.get("total_commands_24h", data.get("total_24h", 0))
        slash_count = data.get("slash_commands_24h", data.get("slash_24h", 0))
        prefix_count = total - slash_count
        slash_pct = (slash_count / total * 100) if total > 0 else 0.0
        prefix_pct = (prefix_count / total * 100) if total > 0 else 0.0

        ratio_text = (
            f"**Total Executions (24h):** `{total:,}` commands\n"
            f"**Interface Split:** `{slash_pct:.0f}%` Slash (`{slash_count:,}`) • `{prefix_pct:.0f}%` Prefix (`{prefix_count:,}`)"
        )
        self.add_item(ui.TextDisplay(ratio_text))
        self.add_item(ui.Separator())

        # Top 5 Commands
        top_cmds = data.get("top_commands", [])
        top_lines = []
        for cname, cnt in top_cmds[:5]:
            pct = (cnt / total * 100) if total > 0 else 0.0
            top_lines.append(f"• `!{cname}`: **{cnt:,}** runs ({pct:.1f}%)")
        top_str = "\n".join(top_lines) if top_lines else "*No commands executed in the last 24h.*"
        self.add_item(ui.TextDisplay(f"**Top Executed Commands:**\n{top_str}"))
        self.add_item(ui.Separator())

        # Slowest Commands
        slowest = data.get("slowest_commands", [])
        slow_lines = []
        for cname, avg_lat in slowest[:4]:
            slow_lines.append(f"• `!{cname}`: `{int(avg_lat):,} ms` avg execution")
        slow_str = "\n".join(slow_lines) if slow_lines else "*No latency data.*"
        self.add_item(ui.TextDisplay(f"**Execution Bottlenecks (Slowest):**\n{slow_str}"))
        self.add_item(ui.Separator())

        # Action Button: Refresh
        nav_row = ui.ActionRow()
        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)
        self.add_item(nav_row)

    @classmethod
    async def create(cls, view):
        data = await view.bot.db_manager.get_command_analytics_summary()
        return cls(view.bot, data)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_commands()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class AnalyticsHeatmapContainer(ui.Container):
    """Page 8.0: Peak Traffic Hours & Activity Distribution."""
    def __init__(self, bot, data: dict):
        super().__init__()
        self.bot = bot

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay("## Activity Heatmap & Peak Hours\n-# Hourly message density and bot reply traffic."),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        hourly_rows = data.get("hourly_heatmap", [])
        total_msgs = sum(r[1] for r in hourly_rows) if hourly_rows else 0
        total_bot = sum(r[2] for r in hourly_rows) if hourly_rows else 0

        overview_text = (
            f"**24h Total Traffic:** `{total_msgs:,}` user messages • `{total_bot:,}` AI bot responses\n"
            f"-# Used to identify peak traffic periods vs ideal maintenance windows."
        )
        self.add_item(ui.TextDisplay(overview_text))
        self.add_item(ui.Separator())

        if hourly_rows:
            sorted_by_traffic = sorted(hourly_rows, key=lambda r: r[1] + r[2], reverse=True)
            peak = sorted_by_traffic[0]
            quiet = sorted_by_traffic[-1]

            peak_str = f"• **Peak Rush Hour:** `{peak[0]}` ({peak[1]} msgs, {peak[2]} bot replies)"
            quiet_str = f"• **Quietest Window:** `{quiet[0]}` ({quiet[1]} msgs) — *Optimal for reboots*"
            self.add_item(ui.TextDisplay(f"**Traffic Windows:**\n{peak_str}\n{quiet_str}"))
            self.add_item(ui.Separator())

            block_lines = []
            for h_bucket, m_cnt, b_cnt in hourly_rows[:6]:
                block_lines.append(f"• `{h_bucket}`: {m_cnt:,} msgs / {b_cnt:,} AI replies")
            self.add_item(ui.TextDisplay(f"**Hourly Samples (UTC):**\n" + "\n".join(block_lines)))
        else:
            self.add_item(ui.TextDisplay("*No heatmap activity recorded for the last 24h.*"))

        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()
        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)
        self.add_item(nav_row)

    @classmethod
    async def create(cls, view):
        data = await view.bot.db_manager.get_heatmap_analytics_summary()
        return cls(view.bot, data)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_heatmap()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())
