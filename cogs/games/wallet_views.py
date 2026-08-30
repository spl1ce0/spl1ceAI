import discord
import discord.ui as ui
import typing
import logging

from cogs.utils.constants import Emojis

logger = logging.getLogger(__name__)


class WalletContainer(ui.Container):
    def __init__(self, target_user: discord.User, economy: dict, can_claim: bool, next_claim_ts: typing.Optional[int], is_owner: bool, parent_view):
        super().__init__()
        self.target_user = target_user
        self.economy = economy
        self.can_claim = can_claim
        self.next_claim_ts = next_claim_ts
        self.is_owner = is_owner
        self.parent_view = parent_view
        self._make_container()

    def _make_container(self):
        # 1. Header
        self.add_item(ui.TextDisplay(f"# Wallet\n-# {self.target_user.display_name}"))
        self.add_item(ui.Separator())

        # 2. Balance Card
        balance = self.economy.get("balance", 0.0)
        total_won = self.economy.get("total_won", 0.0)
        total_wagered = self.economy.get("total_wagered", 0.0)

        balance_text = (
            f"**Balance**\n"
            f"**{balance:,.2f}€**\n"
            f"-# Lifetime Won: +{total_won:,.2f}€  •  Total Spent: {total_wagered:,.2f}€"
        )
        self.add_item(ui.TextDisplay(balance_text))
        self.add_item(ui.Separator())

        # 3. Daily Reward Section
        streak = self.economy.get("daily_streak", 0)
        if self.is_owner:
            if self.can_claim:
                daily_display = ui.TextDisplay(
                    f"**Daily Reward:** 🔥\n"
                    f"Claim now!"
                )
                claim_btn = ui.Button(label="Claim", emoji="🎁", style=discord.ButtonStyle.success)
                claim_btn.callback = self.parent_view._on_claim_daily
                self.add_item(ui.Section(daily_display, accessory=claim_btn))
            else:
                next_str = f"Next claim <t:{self.next_claim_ts}:R>" if self.next_claim_ts else "Claimed today"
                daily_display = ui.TextDisplay(
                    f"**Daily Reward:** 🔥\n"
                    f"{next_str}"
                )
                claimed_btn = ui.Button(label="Claim", emoji="🎁", style=discord.ButtonStyle.gray, disabled=True)
                self.add_item(ui.Section(daily_display, accessory=claimed_btn))
        else:
            self.add_item(ui.TextDisplay(f"**Daily Reward:** 🔥\n-# Streak: {streak} days"))

        # 4. Action Row Navigation
        self.add_item(ui.Separator())
        action_row = ui.ActionRow()

        leaderboard_btn = ui.Button(label="Leaderboard", emoji="🏆", style=discord.ButtonStyle.gray)
        leaderboard_btn.callback = self.parent_view._on_view_leaderboard
        action_row.add_item(leaderboard_btn)

        self.add_item(action_row)


class LeaderboardContainer(ui.Container):
    def __init__(self, leaderboard_data: list, bot, parent_view):
        super().__init__()
        self.leaderboard_data = leaderboard_data
        self.bot = bot
        self.parent_view = parent_view
        self._make_container()

    def _make_container(self):
        # 1. Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self.parent_view._on_back_to_wallet
        header_section = ui.Section(
            ui.TextDisplay("# Wealth Leaderboard\n-# Top Wealthiest Members"),
            accessory=back_btn
        )
        self.add_item(header_section)
        self.add_item(ui.Separator())

        if not self.leaderboard_data:
            self.add_item(ui.TextDisplay("*No users registered in economy yet.*"))
        else:
            lines = []
            medals = ["🥇", "🥈", "🥉"]
            for idx, entry in enumerate(self.leaderboard_data[:10]):
                user_id = entry["user_id"]
                user = self.bot.get_user(user_id)
                name = f"**{user.display_name}**" if user else f"<@{user_id}>"
                rank_str = medals[idx] if idx < 3 else f"`#{idx + 1}`"
                lines.append(f"{rank_str} {name} — **{entry['balance']:,.2f}€**")

            self.add_item(ui.TextDisplay("\n".join(lines)))


class WalletView(ui.LayoutView):
    def __init__(self, bot, author: discord.User, target_user: discord.User):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.target_user = target_user
        self.current_tab = "wallet"

    async def render_wallet(self, interaction: typing.Optional[discord.Interaction] = None):
        self.current_tab = "wallet"
        economy = await self.bot.db_manager.get_user_economy(self.target_user.id)
        can_claim, next_ts = await self.bot.db_manager.check_daily_status(self.target_user.id)
        is_owner = (self.author.id == self.target_user.id)

        self.clear_items()
        container = WalletContainer(
            self.target_user,
            economy,
            can_claim,
            next_ts,
            is_owner,
            self
        )
        self.add_item(container)

        if interaction:
            await interaction.response.edit_message(view=self)

    async def render_leaderboard(self, interaction: discord.Interaction):
        self.current_tab = "leaderboard"
        leaderboard = await self.bot.db_manager.get_wealth_leaderboard(limit=10)

        self.clear_items()
        container = LeaderboardContainer(leaderboard, self.bot, self)
        self.add_item(container)

        await interaction.response.edit_message(view=self)

    async def _on_claim_daily(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ You cannot claim someone else's daily reward!", ephemeral=True)
            return

        success, res = await self.bot.db_manager.claim_daily(self.author.id)
        if success:
            reward = res["reward"]
            streak = res["streak"]
            await self.render_wallet()
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                f"🎉 **Daily Reward Claimed!**\n• Received: **+{reward:,.2f}€**\n• Streak: 🔥 **{streak} days**",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("⏱️ You have already claimed your daily reward today!", ephemeral=True)

    async def _on_view_leaderboard(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ This is not your menu.", ephemeral=True)
            return
        await self.render_leaderboard(interaction)

    async def _on_back_to_wallet(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ This is not your menu.", ephemeral=True)
            return
        await self.render_wallet(interaction)
