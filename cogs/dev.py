from discord.ext import commands as cmds
from discord.ext.commands import Context, GuildConverter

import discord
from cogs.utils.constants import Emojis
from discord import ui
import typing
from typing import Optional
import logging
import subprocess
import os
import asyncio
import time
import datetime
import json
import psutil
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


logger = logging.getLogger(__name__)


def calculate_uptime_stats(hourly_snapshots: list) -> tuple[float, int]:
    """Calculates overall 24h uptime percentage and total down minutes."""
    total_slots = 24
    PINGS_PER_HOUR = 12.0
    counts = [0] * total_slots
    now_dt = datetime.datetime.now(datetime.timezone.utc)

    for row in hourly_snapshots:
        ts_val = row[5] if len(row) > 5 else row[-1]
        try:
            dt_str = str(ts_val).replace("Z", "+00:00")
            if "+" not in dt_str and "T" in dt_str:
                dt_str += "+00:00"
            elif "+" not in dt_str and " " in dt_str:
                dt_str = dt_str.replace(" ", "T") + "+00:00"
            dt_obj = datetime.datetime.fromisoformat(dt_str)
            hours_ago = int((now_dt - dt_obj).total_seconds() // 3600)
            if 0 <= hours_ago < total_slots:
                slot_idx = (total_slots - 1) - hours_ago
                counts[slot_idx] += 1
        except Exception:
            pass

    current_hour_expected = max(1.0, (now_dt.minute // 5) + 1.0)
    ratios = [0.0] * total_slots
    for i in range(total_slots):
        if i == total_slots - 1:
            c = max(1, counts[i])
            ratios[i] = min(1.0, c / current_hour_expected)
        else:
            ratios[i] = min(1.0, counts[i] / PINGS_PER_HOUR)

    if not hourly_snapshots:
        ratios = [1.0] * total_slots

    uptime_pct = (sum(ratios) / total_slots) * 100.0
    down_minutes = max(0, int(round((1.0 - (uptime_pct / 100.0)) * 24 * 60)))
    return uptime_pct, down_minutes


def generate_uptime_chart(hourly_snapshots: list) -> tuple[io.BytesIO, float]:
    """Generates a sleek dark-mode 24h uptime bar chart with 0% to 100% intra-hour color gradient."""
    import matplotlib.colors as mcolors

    total_slots = 24
    PINGS_PER_HOUR = 12.0
    counts = [0] * total_slots
    now_dt = datetime.datetime.now(datetime.timezone.utc)

    for row in hourly_snapshots:
        ts_val = row[5] if len(row) > 5 else row[-1]
        try:
            dt_str = str(ts_val).replace("Z", "+00:00")
            if "+" not in dt_str and "T" in dt_str:
                dt_str += "+00:00"
            elif "+" not in dt_str and " " in dt_str:
                dt_str = dt_str.replace(" ", "T") + "+00:00"
            dt_obj = datetime.datetime.fromisoformat(dt_str)
            hours_ago = int((now_dt - dt_obj).total_seconds() // 3600)
            if 0 <= hours_ago < total_slots:
                slot_idx = (total_slots - 1) - hours_ago
                counts[slot_idx] += 1
        except Exception:
            pass

    current_hour_expected = max(1.0, (now_dt.minute // 5) + 1.0)
    ratios = [0.0] * total_slots
    for i in range(total_slots):
        if i == total_slots - 1:
            c = max(1, counts[i])
            ratios[i] = min(1.0, c / current_hour_expected)
        else:
            ratios[i] = min(1.0, counts[i] / PINGS_PER_HOUR)

    if not hourly_snapshots:
        ratios = [1.0] * total_slots

    overall_uptime_pct = (sum(ratios) / total_slots) * 100.0

    # Smooth gradient from Red (#ED4245) to Yellow (#FEE75C) to Green (#57F287)
    cmap = mcolors.LinearSegmentedColormap.from_list("uptime_cmap", ["#ED4245", "#FEE75C", "#57F287"])
    colors = [cmap(r) for r in ratios]
    heights = [max(0.25, r) for r in ratios]

    fig, ax = plt.subplots(figsize=(6.5, 1.4), dpi=180)
    fig.patch.set_facecolor('#2B2D31')
    ax.set_facecolor('#2B2D31')

    x = list(range(total_slots))
    ax.bar(x, heights, color=colors, width=0.72, edgecolor='none')

    ax.set_ylim(0, 1.2)
    ax.set_xlim(-0.8, 23.8)
    ax.set_xticks([0, 12, 23])
    ax.set_xticklabels(['24h ago', '12h ago', 'Now'], color='#949BA4', fontsize=9)
    ax.set_yticks([])

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(left=False, bottom=False, pad=4)

    buf = io.BytesIO()
    plt.tight_layout(pad=0.4)
    plt.savefig(buf, format='png', bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf, overall_uptime_pct


def generate_ai_traffic_chart(hourly_traffic: list) -> io.BytesIO:
    """Generates a sleek dark-mode 24h AI query volume bar chart in memory."""
    total_slots = 24
    query_counts = [0] * total_slots
    now_dt = datetime.datetime.now(datetime.timezone.utc)

    for row in hourly_traffic:
        ts_str = str(row[0])
        cnt = row[1] or 0
        try:
            dt_str = ts_str.replace(" ", "T") + ":00+00:00"
            dt_obj = datetime.datetime.fromisoformat(dt_str)
            hours_ago = int((now_dt - dt_obj).total_seconds() // 3600)
            if 0 <= hours_ago < total_slots:
                slot_idx = (total_slots - 1) - hours_ago
                query_counts[slot_idx] = cnt
        except Exception:
            pass

    fig, ax = plt.subplots(figsize=(6.5, 1.4), dpi=180)
    fig.patch.set_facecolor('#2B2D31')
    ax.set_facecolor('#2B2D31')

    x = list(range(total_slots))
    max_val = max(query_counts) if query_counts else 0
    bar_color = '#5865F2'

    ax.bar(x, query_counts, color=bar_color, width=0.72, edgecolor='none')
    ax.set_ylim(0, max(1, max_val * 1.25))
    ax.set_xlim(-0.8, 23.8)
    ax.set_xticks([0, 12, 23])
    ax.set_xticklabels(['24h ago', '12h ago', 'Now'], color='#949BA4', fontsize=9)
    ax.set_yticks([])

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(left=False, bottom=False, pad=4)

    buf = io.BytesIO()
    plt.tight_layout(pad=0.4)
    plt.savefig(buf, format='png', bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf


class Dev(cmds.Cog):

    def __init__(self, bot):
        self.bot = bot


    @cmds.hybrid_command(name="are_you_alive", aliases=["alive", "are_u_alive", "areualive"])
    async def alive(self, ctx):
        """Tells if the bot is alive."""

        await ctx.reply(f"Yes I'm alive, broski. {Emojis.YELLOW_LOOK}")


    @cmds.hybrid_command(name="analytics", aliases=["telemetry", "dev_stats"])
    @cmds.is_owner()
    async def analytics(self, ctx: Context):
        """Displays interactive developer analytics and telemetry hub."""
        view = AnalyticsLayoutView(self.bot)
        await view.render_home()
        files = view.get_current_files()
        if files:
            await ctx.reply(view=view, files=files)
        else:
            await ctx.reply(view=view)


    @cmds.group(name='extensions', aliases=['ext'])
    @cmds.is_owner()
    async def extensions(self, ctx: Context):
        pass


    @extensions.command(name='reload')
    @cmds.is_owner()
    async def extensions_reload(self, ctx: Context, *, extension: str):
        if extension == 'all':
            await self.reload_all(ctx)
            return

        try:
            await self.bot.reload_extension("cogs."+extension)
        except cmds.ExtensionError as e:
            await ctx.message.add_reaction(Emojis.ERROR)
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction(Emojis.SUCCESS)


    @extensions.command(name='load')
    @cmds.is_owner()
    async def extensions_load(self, ctx: Context, *, extension: str):
        if extension == 'all':
            await self.load_all(ctx)
            return
        
        try:
            await self.bot.load_extension("cogs."+extension)
        except cmds.ExtensionError as e:
            await ctx.message.add_reaction(Emojis.ERROR)
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction(Emojis.SUCCESS)
        

    @extensions.command(name='unload')
    @cmds.is_owner()
    async def extensions_unload(self, ctx: Context, *, extension: str):
        if extension == 'all':
            await self.unload_all(ctx)
            return

        try:
            await self.bot.unload_extension("cogs."+extension)
        except cmds.ExtensionError as e:
            await ctx.message.add_reaction(Emojis.ERROR)
            logger.error(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.message.add_reaction(Emojis.SUCCESS)
        

    async def reload_all(self, ctx: Context):
        """Reloads every extension."""
        extensions = list(self.bot.extensions.keys())

        reloaded = []
        failed = []

        for extension in extensions:
            try:
                await self.bot.reload_extension(extension)
                reloaded.append(extension)
            except Exception as e:
                failed.append(f"{extension} (Error: {e})")

        if failed:
            message_lines = [f"{Emojis.SUCCESS} Reloaded: {', '.join(reloaded) if reloaded else 'None'}"]
            message_lines.append(f"{Emojis.ERROR} Failed:")
            for failure in failed:
                message_lines.append(f"  - {failure}")
            await ctx.message.add_reaction(Emojis.ERROR)
            await ctx.reply("\n".join(message_lines))
            
        else:
            await ctx.message.add_reaction(Emojis.SUCCESS)
    

    async def load_all(self, ctx: Context):
        """Loads every extension in `bot.initial_extensions` that isn't already loaded."""
        extensions = [
            extention
            for extention in self.bot.initial_extensions
            if extention not in self.bot.extensions
        ]

        loaded = []
        failed = []

        for extension in extensions:
            try:
                await self.bot.load_extension(extension)
                loaded.append(extension)
            except Exception as e:
                failed.append(f"{extension} (Error: {e})")

        if failed:
            message_lines = [f"{Emojis.SUCCESS} Loaded: {', '.join(loaded) if loaded else 'None'}"]
            message_lines.append(f"{Emojis.ERROR} Failed:")
            for failure in failed:
                message_lines.append(f"  - {failure}")
            await ctx.message.add_reaction(Emojis.ERROR)
            await ctx.reply("\n".join(message_lines))
        else:
            await ctx.message.add_reaction(Emojis.SUCCESS)
    

    async def unload_all(self, ctx: Context):
        """Unloads every extension."""
        extensions = list(self.bot.extensions.keys())

        unloaded = []
        failed = []

        for extension in extensions:
            try:
                await self.bot.unload_extension(extension)
                unloaded.append(extension)
            except Exception as e:
                failed.append(f"{extension} (Error: {e})")

        if failed:
            message_lines = [f"{Emojis.SUCCESS} Unloaded: {', '.join(unloaded) if unloaded else 'None'}"]
            message_lines.append(f"{Emojis.ERROR} Failed:")
            for failure in failed:
                message_lines.append(f"  - {failure}")
            await ctx.message.add_reaction(Emojis.ERROR)
            await ctx.reply("\n".join(message_lines))
        else:
            await ctx.message.add_reaction(Emojis.SUCCESS)



    @cmds.command(name='update')
    @cmds.is_owner()
    async def update(self, ctx):
        """Runs the update.sh script to update the bot."""
        await ctx.message.add_reaction(Emojis.RELOAD)
        
        data = {
            'channel_id': ctx.channel.id,
            'message_id': ctx.message.id,
            'start_time': time.time()
        }
        await self.bot.db_manager.save_system_state('restart_info', json.dumps(data))
            
        try:
            await asyncio.create_subprocess_exec('./update.sh')
        except Exception as e:
            logger.error(f"Failed to start update process: {e}")
            await ctx.message.add_reaction(Emojis.ERROR)


    @cmds.command(name='restart')
    @cmds.is_owner()
    async def restart(self, ctx):
        """Restarts the bot by closing the connection and letting the service manager restart it."""
        await ctx.message.add_reaction(Emojis.RELOAD)
        
        data = {
            'channel_id': ctx.channel.id,
            'message_id': ctx.message.id,
            'start_time': time.time()
        }
        await self.bot.db_manager.save_system_state('restart_info', json.dumps(data))
            
        await asyncio.sleep(1)
        await self.bot.close()



    @cmds.group(name='commands')
    @cmds.is_owner()
    async def commands(self, ctx):
        pass
        
    
    @commands.command(name='remove')
    @cmds.is_owner()
    async def remove(self, ctx: Context, command: str, scope: Optional[str], guild: Optional[discord.Guild] = None):
        """Removes a command from the tree. If no guild is provided, removes it globally."""
        if scope == 'local':
            target = target or str(ctx.guild.id)
            guild = await GuildConverter().convert(ctx, target)
        elif scope == 'global':
            guild = None
        else:
            await ctx.message.add_reaction(Emojis.ERROR)
            return
        
        try:
            self.bot.tree.remove_command(command, guild=guild)
            await ctx.message.add_reaction(Emojis.SUCCESS)
        except Exception as e:
            logger.error(f"Remove command failed: {e}")
            await ctx.message.add_reaction(Emojis.ERROR)
        
    
    @commands.command(name='clear')
    @cmds.is_owner()
    async def clear(self, ctx: Context, scope: Optional[str], target: Optional[str] = None):
        """Clears commands from the tree. If no guild is provided, clears globally."""

        if scope == 'local':
            target = target or str(ctx.guild.id)
            guild = await GuildConverter().convert(ctx, target)
        elif scope == 'global':
            guild = None
        else:
            await ctx.message.add_reaction(Emojis.ERROR)
            return

        try:
            self.bot.tree.clear_commands(guild=guild)
            await ctx.message.add_reaction(Emojis.SUCCESS)
        except Exception as e:
            logger.error(f"Clear commands failed: {e}")
            await ctx.message.add_reaction(Emojis.ERROR)


    @commands.command(name='sync')
    @cmds.is_owner()
    async def sync(self, ctx: Context, scope: Optional[str] = None, target: Optional[str] = None):
        """Syncs commands to the tree."""
        if scope == 'local':
            target = target or str(ctx.guild.id)
            guild = await GuildConverter().convert(ctx, target)
        elif scope == 'global':
            guild = None
        else:
            await ctx.message.add_reaction(Emojis.ERROR)
            return
        
        try: 
            await self.bot.tree.sync(guild=guild)
            await ctx.message.add_reaction(Emojis.SUCCESS)
        except Exception as e:
            logger.error(f"Sync command failed: {e}")
            await ctx.message.add_reaction(Emojis.ERROR)
            
    @cmds.command(name='logs')
    @cmds.is_owner()
    async def logs(self, ctx: Context, arg1: typing.Union[int, str] = 20, arg2: typing.Union[int, str] = None):
        """Displays the latest logs in an interactive paginated container.
        
        Usage:
            !logs [lines] [ai|discord]
            !logs [ai|discord] [lines]
        """
        lines = 20
        log_filename = "discord.log"

        def parse_arg(arg):
            nonlocal lines, log_filename
            if isinstance(arg, int):
                lines = arg
            elif isinstance(arg, str):
                if arg.isdigit():
                    lines = int(arg)
                else:
                    val = arg.lower()
                    if val in ["ai", "chatbot", "ai.log"]:
                        log_filename = "ai.log"
                    elif val in ["discord", "bot", "discord.log"]:
                        log_filename = "discord.log"

        parse_arg(arg1)
        if arg2 is not None:
            parse_arg(arg2)

        view = LogPaginationView(self.bot, log_filename=log_filename, page_size=lines)
        await view.load_logs()
        view.current_page = view.total_pages - 1
        view.update_buttons()
        await ctx.reply(content=view.get_page_content(), view=view)


class LogFileSelect(discord.ui.Select):
    def __init__(self, current_file):
        options = [
            discord.SelectOption(
                label="discord.log", 
                value="discord.log", 
                description="Main bot system logs",
                emoji=Emojis.ROBOT
            ),
            discord.SelectOption(
                label="ai.log", 
                value="ai.log", 
                description="AI chatbot fallback & conversation logs",
                emoji=Emojis.BRAIN
            ),
        ]
        super().__init__(placeholder="Select log file...", min_values=1, max_values=1, options=options)
        for option in self.options:
            if option.value == current_file:
                option.default = True

    async def callback(self, interaction: discord.Interaction):
        view: LogPaginationView = self.view
        view.log_filename = self.values[0]
        await view.load_logs()
        view.current_page = view.total_pages - 1
        view.update_select_menu()
        view.update_buttons()
        await interaction.response.edit_message(content=view.get_page_content(), view=view)


class LogPaginationView(discord.ui.View):
    def __init__(self, bot, log_filename="discord.log", lines_history=1000, page_size=20, timeout=120):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.log_filename = log_filename
        self.lines_history = lines_history
        self.page_size = page_size
        self.lines = []
        self.current_page = 0
        self.total_pages = 0
        
        # Select menu component
        self.select_menu = None
        self.update_select_menu()
        
        # Pagination buttons
        self.older_btn = discord.ui.Button(label="◀ Older", style=discord.ButtonStyle.gray, row=1)
        self.older_btn.callback = self.older_callback
        
        self.refresh_btn = discord.ui.Button(emoji=Emojis.RELOAD, label="Refresh", style=discord.ButtonStyle.blurple, row=1)
        self.refresh_btn.callback = self.refresh_callback
        
        self.newer_btn = discord.ui.Button(label="Newer ▶", style=discord.ButtonStyle.gray, row=1)
        self.newer_btn.callback = self.newer_callback
        
        self.add_item(self.older_btn)
        self.add_item(self.refresh_btn)
        self.add_item(self.newer_btn)

    def update_select_menu(self):
        if self.select_menu:
            self.remove_item(self.select_menu)
        self.select_menu = LogFileSelect(self.log_filename)
        self.select_menu.row = 0
        self.add_item(self.select_menu)

    async def load_logs(self):
        def _read_file_sync(filename, history_limit):
            if not os.path.exists(filename):
                return [f"Log file '{filename}' not found."]
            try:
                with open(filename, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
                    return all_lines[-history_limit:]
            except Exception as e:
                return [f"Error reading log file: {e}"]

        self.lines = await asyncio.to_thread(_read_file_sync, self.log_filename, self.lines_history)
        
        self.total_pages = (len(self.lines) + self.page_size - 1) // self.page_size
        if self.total_pages == 0:
            self.total_pages = 1

    def get_page_content(self):
        start = self.current_page * self.page_size
        end = start + self.page_size
        page_lines = self.lines[start:end]
        
        content = "".join(page_lines)
        if len(content) > 1900:
            content = content[-1900:] + "\n[Truncated due to character limit]"
            
        return f"📄 **{self.log_filename} (Page {self.current_page + 1}/{self.total_pages})**\n```log\n{content}\n```"

    def update_buttons(self):
        self.older_btn.disabled = self.current_page <= 0
        self.newer_btn.disabled = self.current_page >= self.total_pages - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(f"{Emojis.ERROR} This menu is developer-only.", ephemeral=True)
            return False
        return True

    async def older_callback(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(content=self.get_page_content(), view=self)

    async def refresh_callback(self, interaction: discord.Interaction):
        await self.load_logs()
        if self.current_page >= self.total_pages:
            self.current_page = self.total_pages - 1
        if self.current_page < 0:
            self.current_page = 0
        self.update_buttons()
        await interaction.response.edit_message(content=self.get_page_content(), view=self)

    async def newer_callback(self, interaction: discord.Interaction):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(content=self.get_page_content(), view=self)


class AnalyticsLayoutView(ui.LayoutView):
    def __init__(self, bot, timeout=None):
        super().__init__(timeout=timeout)
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(f"{Emojis.ERROR} This dashboard is developer-only.", ephemeral=True)
            return False
        return True

    def get_current_files(self) -> list[discord.File]:
        if not self.children:
            return []
        container = self.children[0]
        if hasattr(container, "file") and container.file:
            try:
                container.file.fp.seek(0)
            except Exception:
                pass
            return [container.file]
        return []

    async def render_home(self):
        self.clear_items()
        container = await AnalyticsHomeContainer.create(self)
        self.add_item(container)

    async def render_guilds(self):
        self.clear_items()
        container = await AnalyticsGuildsContainer.create(self)
        self.add_item(container)

    async def render_users(self):
        self.clear_items()
        container = await AnalyticsUsersContainer.create(self)
        self.add_item(container)

    async def render_ai(self):
        self.clear_items()
        container = await AnalyticsAIContainer.create(self)
        self.add_item(container)

    async def render_hardware(self):
        self.clear_items()
        container = await AnalyticsHardwareContainer.create(self)
        self.add_item(container)

    async def render_errors(self):
        self.clear_items()
        container = await AnalyticsErrorsContainer.create(self)
        self.add_item(container)

    async def render_uptime(self):
        self.clear_items()
        container = await AnalyticsUptimeContainer.create(self)
        self.add_item(container)

    async def render_commands(self):
        self.clear_items()
        container = await AnalyticsCommandsContainer.create(self)
        self.add_item(container)

    async def render_connect4(self):
        self.clear_items()
        container = await AnalyticsConnect4Container.create(self)
        self.add_item(container)

    async def render_media(self):
        self.clear_items()
        container = await AnalyticsMediaContainer.create(self)
        self.add_item(container)

    async def render_audits(self):
        self.clear_items()
        container = await AnalyticsAuditsContainer.create(self)
        self.add_item(container)

    async def render_heatmap(self):
        self.clear_items()
        container = await AnalyticsHeatmapContainer.create(self)
        self.add_item(container)


class AnalyticsHomeContainer(ui.Container):
    def __init__(self, bot, stats: dict, guild_count: int, total_members: int, uptime_pct: float = 100.0, down_minutes: int = 0):
        super().__init__()
        self.bot = bot
        
        # Header
        self.add_item(ui.TextDisplay("### Analytics Dashboard\n-# Real-time metrics aggregated across SQLite telemetry streams."))
        self.add_item(ui.Separator())

        # Guilds Section with Action Button accessory
        guild_text = ui.TextDisplay(f"**Guilds:** {guild_count:,} Servers")
        guild_btn = ui.Button(emoji=Emojis.ARROW, style=discord.ButtonStyle.gray)
        guild_btn.callback = self._on_guilds_click
        self.add_item(ui.Section(guild_text, accessory=guild_btn))

        # Users Section with Action Button accessory
        user_text = ui.TextDisplay(f"**Users:** {total_members:,} Total Reach")
        user_btn = ui.Button(emoji=Emojis.ARROW, style=discord.ButtonStyle.gray)
        user_btn.callback = self._on_users_click
        self.add_item(ui.Section(user_text, accessory=user_btn))

        self.add_item(ui.Separator())

        # Uptime Section with Action Button accessory
        if down_minutes == 0:
            down_str = "No downtime in 24h"
        elif down_minutes < 60:
            down_str = f"Down for {down_minutes}min"
        else:
            d_hours, d_mins = divmod(down_minutes, 60)
            down_str = f"Down for {d_hours}h {d_mins}min" if d_mins else f"Down for {d_hours}h"

        uptime_display = ui.TextDisplay(f"**Uptime:** {uptime_pct:.0f}%\n-# {down_str}")
        uptime_btn = ui.Button(emoji=Emojis.ARROW, style=discord.ButtonStyle.gray)
        uptime_btn.callback = self._on_uptime_click
        self.add_item(ui.Section(uptime_display, accessory=uptime_btn))

        self.add_item(ui.Separator())

        # Navigation Row 1: Infrastructure
        nav_row1 = ui.ActionRow()

        ai_btn = ui.Button(label="AI Engine", style=discord.ButtonStyle.gray)
        ai_btn.callback = self._on_ai_click
        nav_row1.add_item(ai_btn)

        hw_btn = ui.Button(label="Hardware", style=discord.ButtonStyle.gray)
        hw_btn.callback = self._on_hardware_click
        nav_row1.add_item(hw_btn)

        cmd_btn = ui.Button(label="Commands", style=discord.ButtonStyle.gray)
        cmd_btn.callback = self._on_commands_click
        nav_row1.add_item(cmd_btn)

        err_btn = ui.Button(label="Errors", style=discord.ButtonStyle.gray)
        err_btn.callback = self._on_errors_click
        nav_row1.add_item(err_btn)

        self.add_item(nav_row1)

        # Navigation Row 2: Features & Tools
        nav_row2 = ui.ActionRow()

        c4_btn = ui.Button(label="Connect 4", style=discord.ButtonStyle.gray)
        c4_btn.callback = self._on_connect4_click
        nav_row2.add_item(c4_btn)

        aud_btn = ui.Button(label="Audits", style=discord.ButtonStyle.gray)
        aud_btn.callback = self._on_audits_click
        nav_row2.add_item(aud_btn)

        heat_btn = ui.Button(label="Heatmap", style=discord.ButtonStyle.gray)
        heat_btn.callback = self._on_heatmap_click
        nav_row2.add_item(heat_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row2.add_item(ref_btn)

        self.add_item(nav_row2)

    @classmethod
    async def create(cls, view: AnalyticsLayoutView):
        stats = await view.bot.db_manager.get_analytics_home_summary()
        guild_count = len(view.bot.guilds)
        total_members = sum(g.member_count for g in view.bot.guilds if g.member_count)
        snapshots = stats.get("hourly_snapshots", [])
        uptime_pct, down_minutes = calculate_uptime_stats(snapshots)
        return cls(view.bot, stats, guild_count, total_members, uptime_pct=uptime_pct, down_minutes=down_minutes)

    async def _on_guilds_click(self, interaction: discord.Interaction):
        await self.view.render_guilds()
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

    async def _on_hardware_click(self, interaction: discord.Interaction):
        await self.view.render_hardware()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_commands_click(self, interaction: discord.Interaction):
        await self.view.render_commands()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_errors_click(self, interaction: discord.Interaction):
        await self.view.render_errors()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_connect4_click(self, interaction: discord.Interaction):
        await self.view.render_connect4()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_media_click(self, interaction: discord.Interaction):
        await self.view.render_media()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_audits_click(self, interaction: discord.Interaction):
        await self.view.render_audits()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_heatmap_click(self, interaction: discord.Interaction):
        await self.view.render_heatmap()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class AnalyticsGuildsContainer(ui.Container):
    def __init__(self, bot, data: dict, current_guilds: int, total_members: int):
        super().__init__()
        self.bot = bot

        self.add_item(ui.TextDisplay("### Guild Analytics\n-# Real-time server count and join/leave history."))
        self.add_item(ui.Separator())

        overview_text = (
            f"**Current Status:** `{current_guilds:,}` Active Guilds • `{total_members:,}` Total Member Reach\n"
            f"**Lifetime Events:** `{data['total_joins']:,}` Joins • `{data['total_leaves']:,}` Leaves"
        )
        self.add_item(ui.TextDisplay(overview_text))
        self.add_item(ui.Separator())

        events_lines = []
        for gid, etype, mcount, ts in data.get("recent_events", []):
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                unix_ts = int(dt_obj.timestamp())
                time_str = f"<t:{unix_ts}:R>"
            except Exception:
                time_str = ts
            prefix_dot = "•"
            events_lines.append(f"{prefix_dot} **{etype.title()}** | Server `{gid}` ({mcount:,} members) - {time_str}")

        recent_str = "\n".join(events_lines) if events_lines else "*No guild events recorded yet.*"
        self.add_item(ui.TextDisplay(f"**Recent Join / Leave Events:**\n{recent_str}"))
        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()
        back_btn = ui.Button(label="Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        nav_row.add_item(back_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    @classmethod
    async def create(cls, view: AnalyticsLayoutView):
        data = await view.bot.db_manager.get_guild_analytics_summary(limit=8)
        current_guilds = len(view.bot.guilds)
        total_members = sum(g.member_count for g in view.bot.guilds if g.member_count)
        return cls(view.bot, data, current_guilds, total_members)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_guilds()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class AnalyticsUsersContainer(ui.Container):
    def __init__(self, bot, data: dict):
        super().__init__()
        self.bot = bot

        self.add_item(ui.TextDisplay("### User Analytics\n-# Lifetime active users and usage distribution."))
        self.add_item(ui.Separator())

        self.add_item(ui.TextDisplay(f"**Growth:** `{data['new_users_7d']:,}` New Users in last 7 days"))
        self.add_item(ui.Separator())

        top_users = data.get("top_users", [])
        user_lines = []
        for uid, cmd_count, fseen, lseen in top_users:
            user_lines.append(f"• <@{uid}> (`{uid}`): **{cmd_count:,}** commands")

        top_str = "\n".join(user_lines) if user_lines else "*No user activity recorded yet.*"
        self.add_item(ui.TextDisplay(f"**Top Active Users:**\n{top_str}"))
        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()
        back_btn = ui.Button(label="Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        nav_row.add_item(back_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    @classmethod
    async def create(cls, view: AnalyticsLayoutView):
        data = await view.bot.db_manager.get_user_analytics_summary(limit=8)
        return cls(view.bot, data)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_users()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class AnalyticsAIContainer(ui.Container):
    def __init__(self, bot, data: dict, file: Optional[discord.File] = None):
        super().__init__()
        self.bot = bot
        self.file = file

        self.add_item(ui.TextDisplay("### AI Engine Intelligence\n-# Real-time request volume, model latencies, failovers, and token analytics."))
        self.add_item(ui.Separator())

        reqs = data.get("requests_24h", 0)
        in_tok = data.get("input_tokens_24h", 0)
        out_tok = data.get("output_tokens_24h", 0)
        avg_lat = data.get("avg_latency_ms", 0)
        avg_ctx = data.get("avg_context_msgs", 0.0)
        failovers = data.get("failovers_24h", 0)
        success_rate = ((reqs - failovers) / reqs * 100) if reqs > 0 else 100.0

        overview_text = (
            f"**Total Queries:** `{reqs:,}` requests • **Success Rate:** `{success_rate:.1f}%`\n"
            f"**Token Volume:** `{in_tok:,}` in • `{out_tok:,}` out (`{in_tok + out_tok:,}` total)\n"
            f"**Average Latency:** `{avg_lat:,} ms` • **Context History:** `avg {avg_ctx} msgs`"
        )
        self.add_item(ui.TextDisplay(overview_text))
        self.add_item(ui.Separator())

        if self.file:
            self.add_item(ui.MediaGallery(discord.MediaGalleryItem(media=self.file)))
            self.add_item(ui.Separator())

        # Models Breakdown with Provider & Latency
        model_lines = []
        for mname, mprovider, mcount, mlat in data.get("model_counts", []):
            pct = (mcount / reqs * 100) if reqs > 0 else 0.0
            avg_m_lat = int(mlat or 0)
            model_lines.append(f"• `{mname}` ({mprovider.title()}): **{mcount:,}** runs ({pct:.1f}%) • `{avg_m_lat} ms`")

        model_str = "\n".join(model_lines) if model_lines else "*No AI queries recorded in the last 24h.*"
        self.add_item(ui.TextDisplay(f"**Model & Provider Breakdown:**\n{model_str}"))
        self.add_item(ui.Separator())

        # Trigger Distribution
        trigger_lines = []
        for ttype, tcount in data.get("trigger_counts", []):
            tpct = (tcount / reqs * 100) if reqs > 0 else 0.0
            trigger_lines.append(f"• `{ttype}`: **{tcount:,}** ({tpct:.1f}%)")
        trigger_str = " • ".join(trigger_lines) if trigger_lines else "*No trigger data.*"
        self.add_item(ui.TextDisplay(f"**Interaction Channels:**\n{trigger_str}"))
        self.add_item(ui.Separator())

        # Recent Failover Incidents
        failover_lines = []
        for mname, freason, ts in data.get("recent_failovers", []):
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = f"<t:{int(dt_obj.timestamp())}:R>"
            except Exception:
                time_str = ts
            failover_lines.append(f"• `{mname}`: *{freason}* - {time_str}")

        failover_str = "\n".join(failover_lines) if failover_lines else "• All models operational - `0` failovers in the last 24h."
        self.add_item(ui.TextDisplay(f"**Failover Incident Log:**\n{failover_str}"))
        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()
        back_btn = ui.Button(label="Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        nav_row.add_item(back_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    @classmethod
    async def create(cls, view: AnalyticsLayoutView):
        data = await view.bot.db_manager.get_ai_analytics_summary()
        chart_buf = generate_ai_traffic_chart(data.get("hourly_traffic", []))
        chart_file = discord.File(chart_buf, filename="ai_traffic_graph.png")
        return cls(view.bot, data, file=chart_file)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_ai()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class AnalyticsHardwareContainer(ui.Container):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

        self.add_item(ui.TextDisplay("### Hardware Health\n-# Real-time infrastructure diagnostics from psutil."))
        self.add_item(ui.Separator())

        cpu_pct = psutil.cpu_percent()
        ram_pct = psutil.virtual_memory().percent
        ram_used_mb = int(psutil.virtual_memory().used / (1024 * 1024))
        ram_total_mb = int(psutil.virtual_memory().total / (1024 * 1024))
        disk_pct = psutil.disk_usage('/').percent
        disk_used_gb = round(psutil.disk_usage('/').used / (1024 ** 3), 1)
        disk_total_gb = round(psutil.disk_usage('/').total / (1024 ** 3), 1)

        db_size_mb = 0.0
        if os.path.exists("bot.db"):
            db_size_mb = round(os.path.getsize("bot.db") / (1024 * 1024), 2)

        ws_latency = int(self.bot.latency * 1000)

        def _bar(pct):
            filled = int(pct / 10)
            return "█" * filled + "░" * (10 - filled)

        metrics_text = (
            f"**CPU Load:** {cpu_pct}% [{_bar(cpu_pct)}]\n"
            f"**RAM Usage:** {ram_pct}% ({ram_used_mb:,} / {ram_total_mb:,} MB) [{_bar(ram_pct)}]\n"
            f"**Disk Usage:** {disk_pct}% ({disk_used_gb} / {disk_total_gb} GB) [{_bar(disk_pct)}]\n"
            f"**Database Size:** {db_size_mb} MB (`bot.db`)\n"
            f"**Gateway Ping:** {ws_latency} ms"
        )
        self.add_item(ui.TextDisplay(metrics_text))
        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()
        back_btn = ui.Button(label="Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        nav_row.add_item(back_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    @classmethod
    async def create(cls, view: AnalyticsLayoutView):
        return cls(view.bot)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_hardware()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class AnalyticsErrorsContainer(ui.Container):
    def __init__(self, bot, data: dict):
        super().__init__()
        self.bot = bot

        self.add_item(ui.TextDisplay("### Error Tracker (24h)\n-# Uncaught command and event exceptions logged to database."))
        self.add_item(ui.Separator())

        total_24h = data.get("errors_24h", 0)
        type_lines = []
        for etype, ecount in data.get("top_errors", []):
            type_lines.append(f"• `{etype}`: **{ecount:,}** occurrences")
        type_str = "\n".join(type_lines) if type_lines else "*No errors recorded in the last 24h.*"

        self.add_item(ui.TextDisplay(f"**Total Exceptions:** {total_24h:,} in the last 24 hours\n\n**Top Exception Types:**\n{type_str}"))
        self.add_item(ui.Separator())

        recent_lines = []
        for cmd_name, etype, emsg, ts in data.get("recent_errors", []):
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                unix_ts = int(dt_obj.timestamp())
                time_str = f"<t:{unix_ts}:R>"
            except Exception:
                time_str = ts
            short_msg = (emsg[:50] + "...") if len(emsg) > 50 else emsg
            recent_lines.append(f"• `/{cmd_name}` ➔ `{etype}`: *{short_msg}* ({time_str})")
        recent_str = "\n".join(recent_lines) if recent_lines else "*No recent exceptions.*"

        self.add_item(ui.TextDisplay(f"**Recent Logged Traces:**\n{recent_str}"))
        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()
        back_btn = ui.Button(label="Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        nav_row.add_item(back_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    @classmethod
    async def create(cls, view: AnalyticsLayoutView):
        data = await view.bot.db_manager.get_error_analytics_summary(limit=6)
        return cls(view.bot, data)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_errors()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class AnalyticsUptimeContainer(ui.Container):
    def __init__(self, bot, stats: dict, file: Optional[discord.File] = None, uptime_pct: float = 100.0):
        super().__init__()
        self.bot = bot
        self.file = file

        self.add_item(ui.TextDisplay("### Uptime & Diagnostics\n-# Historical bot availability and system heartbeat checks."))
        self.add_item(ui.Separator())

        uptime_str = "0m"
        start_time_display = "Unknown"
        if hasattr(self.bot, "start_time"):
            diff = int((datetime.datetime.now(datetime.timezone.utc) - self.bot.start_time).total_seconds())
            days, rem = divmod(diff, 86400)
            hours, rem = divmod(rem, 3600)
            mins, _ = divmod(rem, 60)
            parts = []
            if days > 0: parts.append(f"{days}d")
            if hours > 0: parts.append(f"{hours}h")
            parts.append(f"{mins}m")
            uptime_str = " ".join(parts)
            start_ts = int(self.bot.start_time.timestamp())
            start_time_display = f"<t:{start_ts}:F> (<t:{start_ts}:R>)"

        details_text = (
            f"**Online Duration:** {uptime_str}\n"
            f"**Process Started:** {start_time_display}\n"
            f"**24h Availability:** {uptime_pct:.1f}% (5-minute heartbeat tracking)"
        )
        self.add_item(ui.TextDisplay(details_text))
        self.add_item(ui.Separator())

        if self.file:
            self.add_item(ui.MediaGallery(discord.MediaGalleryItem(media=self.file)))
            self.add_item(ui.Separator())

        nav_row = ui.ActionRow()
        back_btn = ui.Button(label="Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        nav_row.add_item(back_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    @classmethod
    async def create(cls, view: AnalyticsLayoutView):
        stats = await view.bot.db_manager.get_analytics_home_summary()
        snapshots = stats.get("hourly_snapshots", [])
        chart_buf, uptime_pct = generate_uptime_chart(snapshots)
        chart_file = discord.File(chart_buf, filename="uptime_graph_detailed.png")
        return cls(view.bot, stats, file=chart_file, uptime_pct=uptime_pct)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_uptime()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class AnalyticsCommandsContainer(ui.Container):
    def __init__(self, bot, data: dict):
        super().__init__()
        self.bot = bot

        self.add_item(ui.TextDisplay("### Command Analytics (24h)\n-# Command volume, invocation type, and execution latencies."))
        self.add_item(ui.Separator())

        total_24h = data.get("total_24h", 0)
        slash_24h = data.get("slash_24h", 0)
        prefix_24h = total_24h - slash_24h
        slash_pct = (slash_24h / total_24h * 100) if total_24h > 0 else 0.0

        overview_text = (
            f"**Total Commands:** {total_24h:,} executions\n"
            f"**Type Distribution:** {slash_pct:.1f}% Slash ({slash_24h:,}) • {100 - slash_pct:.1f}% Prefix ({prefix_24h:,})"
        )
        self.add_item(ui.TextDisplay(overview_text))
        self.add_item(ui.Separator())

        top_lines = []
        for cname, count in data.get("top_commands", []):
            pct = (count / total_24h * 100) if total_24h > 0 else 0.0
            top_lines.append(f"• `/{cname}`: **{count:,}** runs ({pct:.1f}%)")
        top_str = "\n".join(top_lines) if top_lines else "*No commands executed in the last 24h.*"
        self.add_item(ui.TextDisplay(f"**Top Commands:**\n{top_str}"))
        self.add_item(ui.Separator())

        slow_lines = []
        for cname, avg_ms in data.get("slowest_commands", []):
            slow_lines.append(f"• `/{cname}`: **{int(avg_ms):,} ms** avg")
        slow_str = "\n".join(slow_lines) if slow_lines else "*No execution times recorded.*"
        self.add_item(ui.TextDisplay(f"**Execution Bottlenecks (Slowest):**\n{slow_str}"))
        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()
        back_btn = ui.Button(label="Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        nav_row.add_item(back_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    @classmethod
    async def create(cls, view: AnalyticsLayoutView):
        data = await view.bot.db_manager.get_command_analytics_summary(limit=6)
        return cls(view.bot, data)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_commands()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class AnalyticsConnect4Container(ui.Container):
    def __init__(self, bot, data: dict):
        super().__init__()
        self.bot = bot

        self.add_item(ui.TextDisplay("### Connect 4 Match Analytics\n-# Lifetime match statistics, duration, and AI encounters."))
        self.add_item(ui.Separator())

        total_games = data.get("total_games", 0)
        avg_turns = data.get("avg_turns", 0)
        avg_duration = data.get("avg_duration", 0)

        overview_text = (
            f"**Lifetime Games:** `{total_games:,}` matches played\n"
            f"**Average Game Length:** `{avg_turns}` turns • `{avg_duration}` seconds"
        )
        self.add_item(ui.TextDisplay(overview_text))
        self.add_item(ui.Separator())

        recent_lines = []
        for gname, p1, p2, winner, turns, dur, ts in data.get("recent_games", []):
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = f"<t:{int(dt_obj.timestamp())}:R>"
            except Exception:
                time_str = ts
            winner_str = f"<@{winner}> won" if winner else "Draw / Forfeit"
            recent_lines.append(f"• <@{p1}> vs <@{p2}> | {winner_str} ({turns} turns, {dur}s) - {time_str}")

        recent_str = "\n".join(recent_lines) if recent_lines else "*No matches recorded yet.*"
        self.add_item(ui.TextDisplay(f"**Recent Matches:**\n{recent_str}"))
        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()
        back_btn = ui.Button(label="Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        nav_row.add_item(back_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    @classmethod
    async def create(cls, view: AnalyticsLayoutView):
        data = await view.bot.db_manager.get_game_analytics_summary(limit=6)
        return cls(view.bot, data)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_connect4()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class AnalyticsMediaContainer(ui.Container):
    def __init__(self, bot, data: dict):
        super().__init__()
        self.bot = bot

        self.add_item(ui.TextDisplay("### Media Downloader Analytics\n-# YouTube MP3 conversion volume, bandwidth, and health."))
        self.add_item(ui.Separator())

        total_dl = data.get("total_downloads", 0)
        succ_dl = data.get("successful_downloads", 0)
        total_mb = round(data.get("total_bytes", 0) / (1024 * 1024), 1)
        succ_rate = (succ_dl / total_dl * 100) if total_dl > 0 else 0.0

        overview_text = (
            f"**Total Conversions:** `{total_dl:,}` downloads\n"
            f"**Success Rate:** `{succ_rate:.1f}%` ({succ_dl:,} successful)\n"
            f"**Bandwidth Transferred:** `{total_mb:,} MB`"
        )
        self.add_item(ui.TextDisplay(overview_text))
        self.add_item(ui.Separator())

        recent_lines = []
        for uid, dur, fsize, status, ts in data.get("recent_downloads", []):
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = f"<t:{int(dt_obj.timestamp())}:R>"
            except Exception:
                time_str = ts
            fsize_mb = round((fsize or 0) / (1024 * 1024), 2)
            recent_lines.append(f"• <@{uid}>: `{status}` ({fsize_mb} MB, {dur or 0}s) - {time_str}")

        recent_str = "\n".join(recent_lines) if recent_lines else "*No media downloads recorded.*"
        self.add_item(ui.TextDisplay(f"**Recent Conversions:**\n{recent_str}"))
        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()
        back_btn = ui.Button(label="Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        nav_row.add_item(back_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    @classmethod
    async def create(cls, view: AnalyticsLayoutView):
        data = await view.bot.db_manager.get_media_analytics_summary(limit=6)
        return cls(view.bot, data)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_media()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class AnalyticsAuditsContainer(ui.Container):
    def __init__(self, bot, data: dict):
        super().__init__()
        self.bot = bot

        self.add_item(ui.TextDisplay("### Settings Audit Logs\n-# Historical record of guild configuration adjustments."))
        self.add_item(ui.Separator())

        total_edits = data.get("total_edits", 0)
        self.add_item(ui.TextDisplay(f"**Lifetime Configuration Changes:** `{total_edits:,}` edits"))
        self.add_item(ui.Separator())

        recent_lines = []
        for gid, uid, skey, old_val, new_val, ts in data.get("recent_audits", []):
            try:
                dt_obj = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                time_str = f"<t:{int(dt_obj.timestamp())}:R>"
            except Exception:
                time_str = ts
            recent_lines.append(f"• Server `{gid}` | <@{uid}> edited `{skey}`: `{old_val}` ➔ `{new_val}` - {time_str}")

        recent_str = "\n".join(recent_lines) if recent_lines else "*No settings audits recorded.*"
        self.add_item(ui.TextDisplay(f"**Recent Configuration Edits:**\n{recent_str}"))
        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()
        back_btn = ui.Button(label="Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        nav_row.add_item(back_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    @classmethod
    async def create(cls, view: AnalyticsLayoutView):
        data = await view.bot.db_manager.get_audit_analytics_summary(limit=6)
        return cls(view.bot, data)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_audits()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


class AnalyticsHeatmapContainer(ui.Container):
    def __init__(self, bot, data: dict):
        super().__init__()
        self.bot = bot

        self.add_item(ui.TextDisplay("### Activity Heatmap\n-# Peak traffic hours across active guild channels."))
        self.add_item(ui.Separator())

        hour_lines = []
        for hbucket, mcount, bcount in data.get("peak_hours", []):
            hour_lines.append(f"• **{hbucket}**: **{mcount:,}** messages ({bcount:,} bot replies)")

        hour_str = "\n".join(hour_lines) if hour_lines else "*No hourly heatmap data aggregated yet.*"
        self.add_item(ui.TextDisplay(f"**Busiest Hours of the Day:**\n{hour_str}"))
        self.add_item(ui.Separator())

        nav_row = ui.ActionRow()
        back_btn = ui.Button(label="Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_click
        nav_row.add_item(back_btn)

        ref_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        ref_btn.callback = self._on_refresh_click
        nav_row.add_item(ref_btn)

        self.add_item(nav_row)

    @classmethod
    async def create(cls, view: AnalyticsLayoutView):
        data = await view.bot.db_manager.get_heatmap_analytics_summary()
        return cls(view.bot, data)

    async def _on_back_click(self, interaction: discord.Interaction):
        await self.view.render_home()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())

    async def _on_refresh_click(self, interaction: discord.Interaction):
        await self.view.render_heatmap()
        await interaction.response.edit_message(view=self.view, attachments=self.view.get_current_files())


async def setup(bot):
    await bot.add_cog(Dev(bot))