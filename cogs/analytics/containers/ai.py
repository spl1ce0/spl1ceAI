import datetime
from typing import Optional
import discord
from discord import ui
from cogs.utils.constants import Emojis
from ..charts import generate_ai_traffic_chart


class AnalyticsAIContainer(ui.Container):
    """Page 4.0: AI Engine Intelligence, Costs, Latency & Failovers."""
    def __init__(self, bot, data: dict, file: Optional[discord.File] = None):
        super().__init__()
        self.bot = bot
        self.file = file

        # Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        header_section = ui.Section(
            ui.TextDisplay("## AI Engine Intelligence\n-# Token volume, provider distribution, API costs, and failover health."),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        reqs = data.get("requests_24h", 0)
        in_tok = data.get("input_tokens_24h", 0)
        out_tok = data.get("output_tokens_24h", 0)
        total_tok = in_tok + out_tok
        avg_lat = data.get("avg_latency_ms", 0)
        avg_ctx = data.get("avg_context_msgs", 0.0)
        failovers = data.get("failovers_24h", 0)
        success_rate = ((reqs - failovers) / reqs * 100) if reqs > 0 else 100.0

        est_cost = (in_tok / 1_000_000 * 0.15) + (out_tok / 1_000_000 * 0.60)

        overview_text = (
            f"**Total Queries (24h):** `{reqs:,}` requests • **Success Rate:** `{success_rate:.1f}%`\n"
            f"**Token Volume:** `{in_tok:,}` in • `{out_tok:,}` out (`{total_tok:,}` total)\n"
            f"**Estimated 24h API Cost:** `~${est_cost:.4f}`\n"
            f"**Average Latency:** `{avg_lat:,} ms` • **Context History:** `avg {avg_ctx} msgs`"
        )
        self.add_item(ui.TextDisplay(overview_text))
        self.add_item(ui.Separator())

        if self.file:
            self.add_item(ui.MediaGallery(discord.MediaGalleryItem(media=self.file)))
            self.add_item(ui.Separator())

        # Model & Provider Breakdown
        model_lines = []
        for mname, mprovider, mcount, mlat in data.get("model_counts", []):
            pct = (mcount / reqs * 100) if reqs > 0 else 0.0
            avg_m_lat = int(mlat or 0)
            model_lines.append(f"• `{mname}` ({mprovider.title()}): **{mcount:,}** runs ({pct:.1f}%) • `{avg_m_lat} ms`")

        model_str = "\n".join(model_lines) if model_lines else "*No AI queries recorded in the last 24h.*"
        self.add_item(ui.TextDisplay(f"**Model Breakdown:**\n{model_str}"))
        self.add_item(ui.Separator())

        # Trigger Breakdown
        trigger_lines = []
        for ttype, tcount in data.get("trigger_counts", []):
            tpct = (tcount / reqs * 100) if reqs > 0 else 0.0
            trigger_lines.append(f"• `{ttype}`: **{tcount:,}** ({tpct:.1f}%)")
        trigger_str = " • ".join(trigger_lines) if trigger_lines else "*No trigger data.*"
        self.add_item(ui.TextDisplay(f"**Interaction Channels:**\n{trigger_str}"))
        self.add_item(ui.Separator())

        # Failover Incident Log
        failover_lines = []
        for mname, freason, ts in data.get("recent_failovers", []):
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = f"<t:{int(dt_obj.timestamp())}:R>"
            except Exception:
                time_str = ts
            failover_lines.append(f"⚠️ `{mname}` failover: {freason} • {time_str}")

        failover_str = "\n".join(failover_lines) if failover_lines else "• All AI providers operational — zero failovers in 24h."
        self.add_item(ui.TextDisplay(f"**Failover Incident Log:**\n{failover_str}"))
        self.add_item(ui.Separator())

        # Action Buttons (Refresh)
        nav_row = ui.ActionRow()
        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)
        self.add_item(nav_row)

    @classmethod
    async def create(cls, view):
        data = await view.bot.db_manager.get_ai_analytics_summary()
        chart_buf = generate_ai_traffic_chart(data.get("hourly_traffic", []))
        chart_file = discord.File(chart_buf, filename="ai_traffic.png")
        return cls(view.bot, data, file=chart_file)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_ai()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())
