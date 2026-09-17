import discord
from discord import ui
import logging

logger = logging.getLogger(__name__)


class InspectUserModal(ui.Modal, title="Inspect User"):
    user_input = ui.TextInput(
        label="User ID or @Mention",
        placeholder="e.g. 123456789012345678 or @Username",
        required=True,
        max_length=64
    )

    def __init__(self, bot, parent_view, back_target: str = "users"):
        super().__init__()
        self.bot = bot
        self.parent_view = parent_view
        self.back_target = back_target

    async def on_submit(self, interaction: discord.Interaction):
        raw_val = self.user_input.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        if not raw_val.isdigit():
            await interaction.response.send_message("❌ Please provide a valid numeric User ID or mention.", ephemeral=True)
            return

        user_id = int(raw_val)
        await self.parent_view.render_user_dossier(user_id, back_target=self.back_target)
        await interaction.response.edit_message(
            view=self.parent_view,
            attachments=self.parent_view.get_current_files()
        )


class InspectGuildModal(ui.Modal, title="Inspect Server"):
    guild_input = ui.TextInput(
        label="Server ID",
        placeholder="e.g. 987654321098765432",
        required=True,
        max_length=32
    )

    def __init__(self, bot, parent_view, back_target: str = "servers"):
        super().__init__()
        self.bot = bot
        self.parent_view = parent_view
        self.back_target = back_target

    async def on_submit(self, interaction: discord.Interaction):
        raw_val = self.guild_input.value.strip()
        if not raw_val.isdigit():
            await interaction.response.send_message("❌ Please provide a valid numeric Server ID.", ephemeral=True)
            return

        guild_id = int(raw_val)
        await self.parent_view.render_server_dossier(guild_id, back_target=self.back_target)
        await interaction.response.edit_message(
            view=self.parent_view,
            attachments=self.parent_view.get_current_files()
        )


class BlacklistModal(ui.Modal, title="Blacklist User"):
    reason_input = ui.TextInput(
        label="Reason for Blacklisting",
        placeholder="e.g. AI token spam, malicious prompt injection, abuse",
        required=False,
        default="Telemetry abuse or token rate limit violation",
        max_length=200
    )

    def __init__(self, bot, user_id: int, parent_view, back_target: str = "users"):
        super().__init__()
        self.bot = bot
        self.user_id = user_id
        self.parent_view = parent_view
        self.back_target = back_target

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value.strip() or "Abuse"
        try:
            await self.bot.db_manager.add_user_blacklist(self.user_id, reason=reason, blacklisted_by=interaction.user.id)
            await self.parent_view.render_user_dossier(self.user_id, back_target=self.back_target)
            await interaction.response.edit_message(
                view=self.parent_view,
                attachments=self.parent_view.get_current_files()
            )
        except Exception as e:
            logger.error(f"Failed to blacklist user {self.user_id}: {e}")
            await interaction.response.send_message(f"❌ Failed to blacklist user: {e}", ephemeral=True)
