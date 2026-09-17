from typing import Optional, List
import discord
from discord import ui
from cogs.utils.constants import Emojis
from .containers import (
    AnalyticsHomeContainer,
    AnalyticsServersContainer,
    ServerListContainer,
    ServerDossierContainer,
    ServerSettingsAuditContainer,
    ServerAIQueriesContainer,
    ServerCommandHistoryContainer,
    AnalyticsUsersContainer,
    UserListContainer,
    UserDossierContainer,
    UserAIQueriesContainer,
    UserCommandHistoryContainer,
    AnalyticsUptimeContainer,
    AnalyticsAIContainer,
    AnalyticsSystemContainer,
    AnalyticsErrorsContainer,
    ErrorTracebackContainer,
    AnalyticsCommandsContainer,
    AnalyticsHeatmapContainer,
)


class AnalyticsLayoutView(ui.LayoutView):
    """Interactive Discord Components V2 LayoutView router for all analytics suites."""
    def __init__(self, bot, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message(f"{Emojis.ERROR} This analytics dashboard is developer-only.", ephemeral=True)
            return False
        return True

    def get_current_files(self) -> List[discord.File]:
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

    # --- Level 0: Main Hub ---
    async def render_home(self):
        self.clear_items()
        container = await AnalyticsHomeContainer.create(self)
        self.add_item(container)

    # --- Branch 1: Servers Suite ---
    async def render_servers(self, timeframe: str = "1d"):
        self.clear_items()
        container = await AnalyticsServersContainer.create(self, timeframe=timeframe)
        self.add_item(container)

    async def render_server_list(self, page: int = 1):
        self.clear_items()
        container = ServerListContainer.create(self, page=page, page_size=5)
        self.add_item(container)

    async def render_server_dossier(self, guild_id: int, back_target: str = "servers"):
        self.clear_items()
        dossier = await self.bot.db_manager.get_guild_audit_dossier(guild_id)
        target_guild = self.bot.get_guild(guild_id)
        container = ServerDossierContainer(self.bot, guild_id, dossier, target_guild=target_guild, back_target=back_target)
        self.add_item(container)

    async def render_server_settings(self, guild_id: int):
        self.clear_items()
        dossier = await self.bot.db_manager.get_guild_audit_dossier(guild_id)
        container = ServerSettingsAuditContainer(self.bot, guild_id, dossier)
        self.add_item(container)

    async def render_server_ai_queries(self, guild_id: int, page: int = 1):
        self.clear_items()
        rows, total_count, total_pages = await self.bot.db_manager.get_guild_ai_history_paginated(guild_id, page=page, page_size=5)
        container = ServerAIQueriesContainer(self.bot, guild_id, rows, page, total_pages, total_count)
        self.add_item(container)

    async def render_server_commands(self, guild_id: int, page: int = 1):
        self.clear_items()
        rows, total_count, total_pages = await self.bot.db_manager.get_guild_command_history_paginated(guild_id, page=page, page_size=8)
        container = ServerCommandHistoryContainer(self.bot, guild_id, rows, page, total_pages, total_count)
        self.add_item(container)

    # --- Branch 2: Users Suite ---
    async def render_users(self):
        self.clear_items()
        container = await AnalyticsUsersContainer.create(self)
        self.add_item(container)

    async def render_user_list(self, page: int = 1):
        self.clear_items()
        container = await UserListContainer.create(self, page=page, page_size=5)
        self.add_item(container)

    async def render_user_dossier(self, user_id: int, back_target: str = "users"):
        self.clear_items()
        dossier = await self.bot.db_manager.get_user_audit_dossier(user_id)
        target_user = self.bot.get_user(user_id)
        if not target_user:
            try:
                target_user = await self.bot.fetch_user(user_id)
            except Exception:
                target_user = None
        container = UserDossierContainer(self.bot, user_id, dossier, target_user=target_user, back_target=back_target)
        self.add_item(container)

    async def render_user_ai_queries(self, user_id: int, page: int = 1):
        self.clear_items()
        rows, total_count, total_pages = await self.bot.db_manager.get_user_ai_history_paginated(user_id, page=page, page_size=5)
        container = UserAIQueriesContainer(self.bot, user_id, rows, page, total_pages, total_count)
        self.add_item(container)

    async def render_user_commands(self, user_id: int, page: int = 1):
        self.clear_items()
        rows, total_count, total_pages = await self.bot.db_manager.get_user_command_history_paginated(user_id, page=page, page_size=8)
        container = UserCommandHistoryContainer(self.bot, user_id, rows, page, total_pages, total_count)
        self.add_item(container)

    # --- Branch 3: Uptime Suite ---
    async def render_uptime(self):
        self.clear_items()
        container = await AnalyticsUptimeContainer.create(self)
        self.add_item(container)

    # --- Branch 4: AI Engine Suite ---
    async def render_ai(self):
        self.clear_items()
        container = await AnalyticsAIContainer.create(self)
        self.add_item(container)

    # --- Branch 5: System & VPS Diagnostics ---
    async def render_system(self):
        self.clear_items()
        container = await AnalyticsSystemContainer.create(self)
        self.add_item(container)

    # --- Branch 6: Reliability & Errors ---
    async def render_errors(self):
        self.clear_items()
        container = await AnalyticsErrorsContainer.create(self)
        self.add_item(container)

    async def render_error_traceback(self):
        self.clear_items()
        container = await ErrorTracebackContainer.create(self)
        self.add_item(container)

    # --- Branch 7 & 8: Commands & Heatmap ---
    async def render_commands(self):
        self.clear_items()
        container = await AnalyticsCommandsContainer.create(self)
        self.add_item(container)

    async def render_heatmap(self):
        self.clear_items()
        container = await AnalyticsHeatmapContainer.create(self)
        self.add_item(container)
