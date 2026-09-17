import os
import time
import logging
import datetime
from typing import Optional
import psutil
import discord
from discord.ext import commands, tasks
from discord.ext.commands import Context
from cogs.utils.constants import Emojis
from .views import AnalyticsLayoutView

logger = logging.getLogger(__name__)


class Analytics(commands.Cog):
    """Developer telemetry, real-time analytics hub, and host monitoring."""
    def __init__(self, bot):
        self.bot = bot
        self.system_telemetry_loop.start()

    def cog_unload(self):
        self.system_telemetry_loop.cancel()

    # --- Telemetry Event Listeners ---

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Logs when the bot joins a server."""
        try:
            await self.bot.db_manager.log_guild_event(guild.id, "join", guild.member_count or 0)
        except Exception as e:
            logger.error(f"Failed to log guild join event: {e}")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        """Logs when the bot leaves a server."""
        try:
            await self.bot.db_manager.log_guild_event(guild.id, "leave", guild.member_count or 0)
        except Exception as e:
            logger.error(f"Failed to log guild leave event: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Logs message activity to activity_heatmap_telemetry for peak hour analysis."""
        if not message.guild or not message.channel:
            return

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        hour_str = f"{now_dt.hour:02d}:00 - {(now_dt.hour + 1) % 24:02d}:00 UTC"
        is_bot = message.author.bot

        try:
            await self.bot.db_manager.log_heatmap_activity(
                guild_id=message.guild.id,
                channel_id=message.channel.id,
                hour_bucket=hour_str,
                is_bot_response=is_bot
            )
        except Exception as e:
            logger.error(f"Failed to log heatmap telemetry: {e}")

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        """Records command start time to calculate execution latency."""
        ctx.telemetry_start_time = time.perf_counter()

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        """Logs successful command completion metrics."""
        if ctx.cog and ctx.cog.qualified_name in ["Dev", "Analytics", "ErrorHandler"]:
            return

        guild_id = ctx.guild.id if ctx.guild else None
        channel_id = ctx.channel.id if ctx.channel else None
        user_id = ctx.author.id
        command_name = ctx.command.qualified_name
        is_slash = ctx.interaction is not None

        start_time = getattr(ctx, "telemetry_start_time", None)
        execution_time_ms = int((time.perf_counter() - start_time) * 1000) if start_time else 0

        try:
            await self.bot.db_manager.log_command_execution(
                guild_id=guild_id,
                channel_id=channel_id,
                user_id=user_id,
                command_name=command_name,
                is_slash=is_slash,
                execution_time_ms=execution_time_ms,
                success=True
            )
            await self.bot.db_manager.log_user_activity(user_id)
        except Exception as e:
            logger.error(f"Failed to log command execution telemetry: {e}")

    @tasks.loop(minutes=5)
    async def system_telemetry_loop(self):
        """Periodically logs system health metrics to system_telemetry."""
        try:
            cpu_pct = psutil.cpu_percent()
            ram_pct = psutil.virtual_memory().percent
            disk_pct = psutil.disk_usage('/').percent
            ws_latency = int(self.bot.latency * 1000)

            db_size = 0
            db_path = "bot.db"
            if os.path.exists(db_path):
                db_size = os.path.getsize(db_path)

            uptime_seconds = 0
            if hasattr(self.bot, "start_time"):
                uptime_seconds = int((datetime.datetime.now(datetime.timezone.utc) - self.bot.start_time).total_seconds())

            guild_cnt = len(self.bot.guilds)
            total_members = sum(g.member_count for g in self.bot.guilds if g.member_count)

            await self.bot.db_manager.log_system_status(
                cpu_usage_pct=cpu_pct,
                ram_usage_pct=ram_pct,
                disk_usage_pct=disk_pct,
                websocket_latency_ms=ws_latency,
                sqlite_db_size_bytes=db_size,
                uptime_seconds=uptime_seconds,
                guild_count=guild_cnt,
                total_members_count=total_members
            )
        except Exception as e:
            logger.error(f"Failed to log system status telemetry: {e}")

    @system_telemetry_loop.before_loop
    async def before_system_telemetry(self):
        await self.bot.wait_until_ready()

    # --- Interactive Analytics Hub Command ---

    @commands.hybrid_command(name="analytics", aliases=["telemetry", "dev_stats"])
    @commands.is_owner()
    async def analytics(self, ctx: Context, category: Optional[str] = None, target: Optional[str] = None):
        """Displays the developer telemetry hub with instant shortcuts."""
        view = AnalyticsLayoutView(self.bot)
        cat_lower = (category or "").lower().strip()

        if cat_lower in ["user", "u"] and target:
            # Direct User Dossier Lookup
            raw_uid = target.replace("<@", "").replace(">", "").replace("!", "").strip()
            if raw_uid.isdigit():
                await view.render_user_dossier(int(raw_uid))
            else:
                await view.render_users()
        elif cat_lower in ["server", "guild", "s", "g"]:
            # Direct Server Dossier Lookup (defaults to current guild if none provided)
            target_gid = None
            if target and target.strip().isdigit():
                target_gid = int(target.strip())
            elif ctx.guild:
                target_gid = ctx.guild.id

            if target_gid:
                await view.render_server_dossier(target_gid)
            else:
                await view.render_servers()
        elif cat_lower in ["servers", "guilds"]:
            await view.render_server_list(page=1)
        elif cat_lower in ["users"]:
            await view.render_user_list(page=1)
        elif cat_lower in ["uptime", "up"]:
            await view.render_uptime()
        elif cat_lower in ["ai", "llm"]:
            await view.render_ai()
        elif cat_lower in ["sys", "system", "hardware", "hw"]:
            await view.render_system()
        elif cat_lower in ["errors", "error", "err"]:
            await view.render_errors()
        elif cat_lower in ["commands", "traffic", "cmd"]:
            await view.render_commands()
        elif cat_lower in ["heatmap", "heat"]:
            await view.render_heatmap()
        else:
            await view.render_home()

        files = view.get_current_files()
        if files:
            await ctx.reply(view=view, files=files)
        else:
            await ctx.reply(view=view)
