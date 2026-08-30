import asyncio
import datetime
import math
import uuid
import time
from typing import Optional, Dict, List
import discord
from discord import ui

from .blackjack import TableManager, BlackjackTable, TablePhase, BlackjackPlayer
from cogs.utils.constants import Emojis


class RadioOption:
    def __init__(self, label: str, value: str, description: Optional[str] = None, default: bool = False):
        self.label = label
        self.value = value
        self.description = description
        self.default = default

    def to_dict(self) -> dict:
        d = {'label': self.label, 'value': self.value, 'default': self.default}
        if self.description:
            d['description'] = self.description
        return d


class RadioGroup(ui.Item):
    def __init__(self, *, options: List[RadioOption], custom_id: Optional[str] = None, required: bool = True):
        super().__init__()
        self.options = options
        self.custom_id = custom_id or uuid.uuid4().hex
        self.required = required
        self.values: List[str] = []

    def to_component_dict(self) -> dict:
        return {
            'type': 21,
            'custom_id': self.custom_id,
            'required': self.required,
            'options': [opt.to_dict() if hasattr(opt, 'to_dict') else opt for opt in self.options]
        }

    def _refresh_component(self, component) -> None:
        pass

    def _handle_submit(self, interaction: discord.Interaction, component: dict, resolved: dict) -> None:
        self.values = component.get('values', [])
        if not self.values and 'value' in component:
            self.values = [component['value']]

    def _refresh_state(self, interaction: discord.Interaction, data: dict) -> None:
        self.values = data.get('values', [])
        if not self.values and 'value' in data:
            self.values = [data['value']]


class JoinCodeModal(ui.Modal, title="Join Private Table"):
    code_input = ui.TextInput(label="Room Code", placeholder="e.g. K9X2", min_length=4, max_length=4, required=True)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        code = self.code_input.value.strip().upper()
        table = TableManager().get_table_by_code(code)
        if not table:
            await interaction.response.send_message(f"❌ No private table found with code `{code}`.", ephemeral=True)
            return

        public_view = PublicTableView(self.bot, table)
        table.public_view = public_view
        await interaction.response.edit_message(view=public_view)
        public_view.message = interaction.message
        if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and interaction.message:
            self.bot._connection._view_store.add_view(public_view, interaction.message.id)


class CreateTableModal(ui.Modal, title="Create Blackjack Table"):
    table_name = ui.Label(
        text="Table Name",
        component=ui.TextInput(placeholder="e.g. High Rollers Club", max_length=32, required=False)
    )
    min_bet = ui.Label(
        text="Minimum Bet (€)",
        component=ui.TextInput(placeholder="10", default="10", max_length=6, required=True)
    )
    room_visibility = ui.Label(
        text="Room Visibility",
        component=RadioGroup(options=[
            RadioOption("Public Table (Listed in Browser)", "public", default=True),
            RadioOption("Private Table (Join by Code only)", "private")
        ])
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet_val_str = self.min_bet.component.value.strip()
            min_bet_val = float(bet_val_str)
            if min_bet_val <= 0:
                raise ValueError()
        except Exception:
            await interaction.response.send_message("❌ Invalid minimum bet amount.", ephemeral=True)
            return

        existing_table = TableManager().get_table_by_host(interaction.user.id)
        if existing_table:
            await interaction.response.send_message(
                f"❌ You are already hosting a table (**{existing_table.name}**)! You can only host one table at a time.",
                ephemeral=True
            )
            return

        name = self.table_name.component.value.strip() or f"{interaction.user.display_name}'s Table"

        raw_values = list(self.room_visibility.component.values)
        if not raw_values and hasattr(interaction, 'data') and 'components' in interaction.data:
            for row in interaction.data['components']:
                if row.get('type') == 18 and 'component' in row:
                    inner = row['component']
                    if inner.get('values'):
                        raw_values = list(inner['values'])
                    elif inner.get('value'):
                        raw_values = [inner['value']]
                elif row.get('type') == 1 and 'components' in row:
                    for inner in row['components']:
                        if inner.get('values'):
                            raw_values = list(inner['values'])
                        elif inner.get('value'):
                            raw_values = [inner['value']]
                elif row.get('values'):
                    raw_values = list(row['values'])
                elif row.get('value'):
                    raw_values = [row['value']]

        selected_type = str(raw_values[0]).strip().lower() if raw_values else "public"
        is_private = (selected_type == "private")

        table = TableManager().create_table(
            name=name,
            guild_id=interaction.guild.id if interaction.guild else None,
            channel_id=interaction.channel.id,
            host_id=interaction.user.id,
            bot=self.bot,
            is_private=is_private,
            min_bet=min_bet_val,
            max_seats=7
        )

        table.add_player(interaction.user.id, interaction.user.display_name)
        player = table.players[interaction.user.id]

        public_view = PublicTableView(self.bot, table)
        table.public_view = public_view
        await interaction.response.edit_message(view=public_view)
        public_view.message = interaction.message
        if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and interaction.message:
            self.bot._connection._view_store.add_view(public_view, interaction.message.id)

        # Send personal ephemeral seat view for host
        economy = await self.bot.db_manager.get_user_economy(interaction.user.id)
        seat_view = PlayerSeatView(self.bot, table, player, user_balance=economy["balance"])
        player.ephemeral_view = seat_view
        seat_msg = await interaction.followup.send(view=seat_view, ephemeral=True)
        seat_view.message = seat_msg
        if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and seat_msg:
            self.bot._connection._view_store.add_view(seat_view, seat_msg.id)


class CustomBetModal(ui.Modal, title="Enter Custom Bet"):
    bet_input = ui.TextInput(label="Bet Amount (€)", placeholder="e.g. 75", max_length=8, required=True)

    def __init__(self, bot, table: BlackjackTable, player_seat_view):
        super().__init__()
        self.bot = bot
        self.table = table
        self.player_seat_view = player_seat_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet_val = float(self.bet_input.value.strip())
            if bet_val < self.table.min_bet:
                await interaction.response.send_message(f"❌ Bet must be at least €{self.table.min_bet:.2f}.", ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message("❌ Invalid number.", ephemeral=True)
            return

        economy = await self.bot.db_manager.get_user_economy(interaction.user.id)
        bal = economy.get("balance", 0.0)

        self.table.clear_bet(interaction.user.id)
        ok, msg, current_bet = self.table.add_bet(interaction.user.id, bet_val, bal)

        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        await self.player_seat_view.refresh_message()
        await self.table.broadcast_updates()
        await interaction.response.send_message(f"✅ Bet set to **€{current_bet:.2f}**.", ephemeral=True)


# =========================================================================
# --- HOME & LOBBY CONTAINERS ---
# =========================================================================

class BlackjackHomeContainer(ui.Container):
    def __init__(self, bot, user: discord.User, economy: dict, is_eligible: bool, next_claim_ts: Optional[int], guild_id: Optional[int] = None):
        super().__init__()
        self.bot = bot
        self.user = user
        self.economy = economy
        self.is_eligible = is_eligible
        self.next_claim_ts = next_claim_ts
        self.guild_id = guild_id

        # 1. Header
        self.add_item(ui.TextDisplay("### 🎰 Blackjack"))
        self.add_item(ui.Separator())

        # 2. Balance Section with Wallet Accessory Button
        bal = economy.get("balance", 1000.0)
        user_name = getattr(self.user, "display_name", "Your")
        
        if is_eligible:
            daily_hint = "🎁 *Daily reward ready to claim!*"
        else:
            time_str = f"<t:{next_claim_ts}:R>" if next_claim_ts else "soon"
            daily_hint = f"-# Daily claimed • Next in {time_str}"

        bal_text = f"**{user_name}'s Balance**\n### **{bal:,.2f}€**\n{daily_hint}"
        wallet_btn = ui.Button(label="Wallet", emoji="💳", style=discord.ButtonStyle.gray)
        wallet_btn.callback = self._on_wallet

        self.add_item(ui.Section(ui.TextDisplay(bal_text), accessory=wallet_btn))
        self.add_item(ui.Separator())

        # 3. Action Row: Play, Host, Join, Leaderboard, Info
        nav_row = ui.ActionRow()

        play_btn = ui.Button(label="Play", style=discord.ButtonStyle.green)
        play_btn.callback = self._on_play
        nav_row.add_item(play_btn)

        host_btn = ui.Button(label="Host", style=discord.ButtonStyle.gray)
        host_btn.callback = self._on_host
        nav_row.add_item(host_btn)

        join_btn = ui.Button(label="Join", style=discord.ButtonStyle.gray)
        join_btn.callback = self._on_join
        nav_row.add_item(join_btn)

        lead_btn = ui.Button(emoji="🏆", style=discord.ButtonStyle.gray)
        lead_btn.callback = self._on_leaderboard
        nav_row.add_item(lead_btn)

        info_btn = ui.Button(emoji="ℹ️", style=discord.ButtonStyle.gray)
        info_btn.callback = self._on_info
        nav_row.add_item(info_btn)

        self.add_item(nav_row)

    async def _on_play(self, interaction: discord.Interaction):
        await self.view.render_browser(interaction.user, self.guild_id, page=0)
        await interaction.response.edit_message(view=self.view)

    async def _on_host(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateTableModal(self.bot))

    async def _on_join(self, interaction: discord.Interaction):
        await interaction.response.send_modal(JoinCodeModal(self.bot))

    async def _on_wallet(self, interaction: discord.Interaction):
        await self.view.render_wallet(interaction.user, self.guild_id)
        await interaction.response.edit_message(view=self.view)

    async def _on_leaderboard(self, interaction: discord.Interaction):
        await self.view.render_leaderboard(interaction.user, self.guild_id)
        await interaction.response.edit_message(view=self.view)

    async def _on_info(self, interaction: discord.Interaction):
        await self.view.render_info(interaction.user, self.guild_id)
        await interaction.response.edit_message(view=self.view)


class BlackjackBrowserContainer(ui.Container):
    PER_PAGE = 5

    def __init__(self, bot, user: discord.User, guild_id: Optional[int] = None, page: int = 0):
        super().__init__()
        self.bot = bot
        self.user = user
        self.guild_id = guild_id
        self.page = page

        # Title as Section with < Back button accessory on the right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back

        title_display = ui.TextDisplay("### 🌐 Table Browser\n-# Active public tables available to join.")
        self.add_item(ui.Section(title_display, accessory=back_btn))
        self.add_item(ui.Separator())

        # Fetch Tables (ensures system tables are active and provisioned)
        tables = TableManager().get_public_tables(guild_id, bot=self.bot)
        total_tables = len(tables)
        max_page = max(0, math.ceil(total_tables / self.PER_PAGE) - 1) if total_tables > 0 else 0
        self.page = max(0, min(self.page, max_page))

        start_idx = self.page * self.PER_PAGE
        page_tables = tables[start_idx : start_idx + self.PER_PAGE]

        if page_tables:
            for t in page_tables:
                is_full = t.seated_count >= t.max_seats
                if is_full:
                    join_btn = ui.Button(label="Full", style=discord.ButtonStyle.gray, disabled=True)
                else:
                    join_btn = ui.Button(label="Join", style=discord.ButtonStyle.green)
                    join_btn.callback = self._make_join_callback(t)

                # Format: **🥉 Bronze Table #1** \n -# Min €5 • 0/7 Seated      [Join]
                info_text = f"**{t.name}**\n-# Min €{t.min_bet:.0f} • {t.seated_count}/{t.max_seats} Seated"
                section = ui.Section(ui.TextDisplay(info_text), accessory=join_btn)
                self.add_item(section)
        else:
            self.add_item(ui.TextDisplay("*No active public tables. Click Host below to start one!*"))

        self.add_item(ui.Separator())

        # Pagination Row if multiple pages
        if max_page > 0:
            pag_row = ui.ActionRow()
            prev_btn = ui.Button(label="◀ Prev", style=discord.ButtonStyle.gray, disabled=(self.page == 0))
            prev_btn.callback = self._on_prev
            pag_row.add_item(prev_btn)

            page_info = ui.Button(label=f"Page {self.page + 1}/{max_page + 1}", style=discord.ButtonStyle.gray, disabled=True)
            pag_row.add_item(page_info)

            next_btn = ui.Button(label="Next ▶", style=discord.ButtonStyle.gray, disabled=(self.page >= max_page))
            next_btn.callback = self._on_next
            pag_row.add_item(next_btn)

            self.add_item(pag_row)

        # Bottom Action Row: Host, Join, Refresh (All Grey)
        bot_row = ui.ActionRow()

        host_btn = ui.Button(label="Host", style=discord.ButtonStyle.gray)
        host_btn.callback = self._on_host_table
        bot_row.add_item(host_btn)

        join_btn = ui.Button(label="Join", style=discord.ButtonStyle.gray)
        join_btn.callback = self._on_join_code
        bot_row.add_item(join_btn)

        refresh_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        refresh_btn.callback = self._on_refresh
        bot_row.add_item(refresh_btn)

        self.add_item(bot_row)

    def _make_join_callback(self, table: BlackjackTable):
        async def callback(interaction: discord.Interaction):
            public_view = PublicTableView(self.bot, table)
            table.public_view = public_view
            await interaction.response.edit_message(view=public_view)
            public_view.message = interaction.message
            if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and interaction.message:
                self.bot._connection._view_store.add_view(public_view, interaction.message.id)
        return callback

    async def _on_back(self, interaction: discord.Interaction):
        await self.view.render_home(interaction.user, self.guild_id)
        await interaction.response.edit_message(view=self.view)

    async def _on_host_table(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateTableModal(self.bot))

    async def _on_join_code(self, interaction: discord.Interaction):
        await interaction.response.send_modal(JoinCodeModal(self.bot))

    async def _on_refresh(self, interaction: discord.Interaction):
        await self.view.render_browser(interaction.user, self.guild_id, page=self.page)
        await interaction.response.edit_message(view=self.view)

    async def _on_prev(self, interaction: discord.Interaction):
        await self.view.render_browser(interaction.user, self.guild_id, page=self.page - 1)
        await interaction.response.edit_message(view=self.view)

    async def _on_next(self, interaction: discord.Interaction):
        await self.view.render_browser(interaction.user, self.guild_id, page=self.page + 1)
        await interaction.response.edit_message(view=self.view)


class BlackjackInfoContainer(ui.Container):
    def __init__(self, bot, user: discord.User, guild_id: Optional[int] = None):
        super().__init__()
        self.bot = bot
        self.user = user
        self.guild_id = guild_id

        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back

        title_display = ui.TextDisplay("### ℹ️ Casino Information & Guide\n-# Game rules, how to play, and table mechanics.")
        self.add_item(ui.Section(title_display, accessory=back_btn))
        self.add_item(ui.Separator())

        rules_text = (
            "**📖 Game Rules:**\n"
            "• **Objective:** Achieve a hand total higher than the dealer without exceeding 21.\n"
            "• **Card Values:** Cards 2–10 retain face value. Face cards (J, Q, K) count as 10. Aces count as 1 or 11.\n"
            "• **Dealer Play:** The dealer must draw cards up to 16 and stand on all 17s (hard and soft).\n"
            "• **Payouts:** Standard Win pays 1:1. Natural Blackjack (Ace + 10-value on initial deal) pays 3:2. Push ties refund your bet."
        )
        self.add_item(ui.TextDisplay(rules_text))
        self.add_item(ui.Separator())

        how_to_play_text = (
            "**🎮 How to Play:**\n"
            "1. Click **Play** from the main menu to open the Table Browser, or click **Host** to create a table.\n"
            "2. Click **Join** to spectate a table, then click **Take a seat** to join the active round.\n"
            "3. Place your wager using the chip buttons (+5€, +10€, +50€, +100€, or Custom) within the 10-second betting window.\n"
            "4. On your turn (20 seconds), select your move:\n"
            "   • **Hit:** Draw an additional card.\n"
            "   • **Stand:** Hold your total and finish your hand.\n"
            "   • **Double Down:** Double your wager, receive exactly one card, and stand.\n"
            "   • **Split:** Split identical pair cards into two separate hands with equal wagers."
        )
        self.add_item(ui.TextDisplay(how_to_play_text))
        self.add_item(ui.Separator())

        balance_text = (
            "**💰 Balance & Daily Reward:**\n"
            "• **Starting Wallet:** All new players begin with 1,000.00€.\n"
            "• **Daily Allowance:** Claim your daily reward once every 24 hours (100.00€ + 5.00€ bonus per consecutive streak day).\n"
            "• **Leaderboard:** Track top balances and gross casino winnings from the main menu."
        )
        self.add_item(ui.TextDisplay(balance_text))
        self.add_item(ui.Separator())

        tables_text = (
            "**🎰 Table Limits & Auto-Scaling:**\n"
            "• **Public Tables:** Guaranteed 7-seat tables for Bronze (5€), Silver (10€), Gold (20€), and Diamond (50€).\n"
            "• **Auto-Scaling:** Full tables automatically spawn duplicate rooms (#2, #3), keeping seats available.\n"
            "• **Inactivity:** Players with no bets placed for 2 consecutive rounds are automatically unseated."
        )
        self.add_item(ui.TextDisplay(tables_text))

    async def _on_back(self, interaction: discord.Interaction):
        await self.view.render_home(interaction.user, self.guild_id)
        await interaction.response.edit_message(view=self.view)


class BlackjackLeaderboardContainer(ui.Container):
    def __init__(self, bot, user: discord.User, boards: dict, guild_id: Optional[int] = None):
        super().__init__()
        self.bot = bot
        self.user = user
        self.boards = boards
        self.guild_id = guild_id

        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back

        title_display = ui.TextDisplay("### 🏆 Royal Casino Leaderboards\n-# Top players by balance and total winnings.")
        self.add_item(ui.Section(title_display, accessory=back_btn))
        self.add_item(ui.Separator())

        bal_lines = ["**💰 Top Balances:**"]
        for idx, (uid, bal, won) in enumerate(boards.get("top_balance", []), 1):
            bal_lines.append(f"{idx}. <@{uid}> — **€{bal:,.2f}**")
        self.add_item(ui.TextDisplay("\n".join(bal_lines)))
        self.add_item(ui.Separator())

        won_lines = ["**💸 Top Gross Winnings:**"]
        for idx, (uid, won, hwon, bwin) in enumerate(boards.get("top_winners", []), 1):
            won_lines.append(f"{idx}. <@{uid}> — **€{won:,.2f}** ({hwon} hands won)")
        self.add_item(ui.TextDisplay("\n".join(won_lines)))
        self.add_item(ui.Separator())

        bot_row = ui.ActionRow()
        refresh_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        refresh_btn.callback = self._on_refresh
        bot_row.add_item(refresh_btn)
        self.add_item(bot_row)

    async def _on_back(self, interaction: discord.Interaction):
        await self.view.render_home(interaction.user, self.guild_id)
        await interaction.response.edit_message(view=self.view)

    async def _on_refresh(self, interaction: discord.Interaction):
        await self.view.render_leaderboard(interaction.user, self.guild_id)
        await interaction.response.edit_message(view=self.view)


class BlackjackWalletContainer(ui.Container):
    def __init__(self, bot, user: discord.User, economy: dict, can_claim: bool, next_claim_ts: Optional[int], guild_id: Optional[int], parent_view):
        super().__init__()
        self.bot = bot
        self.user = user
        self.economy = economy
        self.can_claim = can_claim
        self.next_claim_ts = next_claim_ts
        self.guild_id = guild_id
        self.parent_view = parent_view
        self._build_ui()

    def _build_ui(self):
        # 1. Header with < Back button on top right
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back

        user_name = getattr(self.user, "display_name", str(self.user))
        header_section = ui.Section(
            ui.TextDisplay(f"# Wallet\n-# {user_name}"),
            accessory=back_btn
        )
        self.add_item(header_section)
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
        if self.can_claim:
            daily_display = ui.TextDisplay(
                f"**Daily Reward:** 🔥\n"
                f"Claim now!"
            )
            claim_btn = ui.Button(label="Claim", emoji="🎁", style=discord.ButtonStyle.success)
            claim_btn.callback = self._on_claim_daily
            self.add_item(ui.Section(daily_display, accessory=claim_btn))
        else:
            next_str = f"Next claim <t:{self.next_claim_ts}:R>" if self.next_claim_ts else "Claimed today"
            daily_display = ui.TextDisplay(
                f"**Daily Reward:** 🔥\n"
                f"{next_str}"
            )
            claimed_btn = ui.Button(label="Claim", emoji="🎁", style=discord.ButtonStyle.gray, disabled=True)
            self.add_item(ui.Section(daily_display, accessory=claimed_btn))

        # 4. Action Row Navigation
        self.add_item(ui.Separator())
        action_row = ui.ActionRow()

        leaderboard_btn = ui.Button(label="Wealth Leaderboard", emoji="🏆", style=discord.ButtonStyle.gray)
        leaderboard_btn.callback = self._on_view_wealth_leaderboard
        action_row.add_item(leaderboard_btn)

        self.add_item(action_row)

    async def _on_back(self, interaction: discord.Interaction):
        await self.parent_view.render_home(interaction.user, self.guild_id)
        await interaction.response.edit_message(view=self.parent_view)

    async def _on_claim_daily(self, interaction: discord.Interaction):
        await self.bot.db_manager.claim_daily(interaction.user.id)
        await self.parent_view.render_wallet(interaction.user, self.guild_id)
        await interaction.response.edit_message(view=self.parent_view)

    async def _on_view_wealth_leaderboard(self, interaction: discord.Interaction):
        await self.parent_view.render_wealth_leaderboard(interaction.user, self.guild_id)
        await interaction.response.edit_message(view=self.parent_view)


class BlackjackWealthLeaderboardContainer(ui.Container):
    def __init__(self, leaderboard_data: list, bot, user: discord.User, guild_id: Optional[int], parent_view):
        super().__init__()
        self.leaderboard_data = leaderboard_data
        self.bot = bot
        self.user = user
        self.guild_id = guild_id
        self.parent_view = parent_view
        self._build_ui()

    def _build_ui(self):
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back
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
                bal = entry.get("balance", 0.0)

                prefix = medals[idx] if idx < 3 else f"`#{idx + 1}`"
                lines.append(f"{prefix} {name} — **{bal:,.2f}€**")

            self.add_item(ui.TextDisplay("\n".join(lines)))

    async def _on_back(self, interaction: discord.Interaction):
        await self.parent_view.render_wallet(interaction.user, self.guild_id)
        await interaction.response.edit_message(view=self.parent_view)


class BlackjackLobbyView(ui.LayoutView):
    def __init__(self, bot, user: discord.User, guild_id: Optional[int] = None):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user
        self.guild_id = guild_id

    async def render_home(self, user: discord.User, guild_id: Optional[int] = None):
        self.clear_items()
        economy = await self.bot.db_manager.get_user_economy(user.id)
        is_eligible, next_ts = await self.bot.db_manager.check_daily_status(user.id)
        container = BlackjackHomeContainer(self.bot, user, economy, is_eligible, next_ts, guild_id)
        self.add_item(container)

    async def render_wallet(self, user: discord.User, guild_id: Optional[int] = None):
        self.clear_items()
        economy = await self.bot.db_manager.get_user_economy(user.id)
        can_claim, next_ts = await self.bot.db_manager.check_daily_status(user.id)
        container = BlackjackWalletContainer(self.bot, user, economy, can_claim, next_ts, guild_id, self)
        self.add_item(container)

    async def render_wealth_leaderboard(self, user: discord.User, guild_id: Optional[int] = None):
        self.clear_items()
        leaderboard_data = await self.bot.db_manager.get_wealth_leaderboard(limit=10)
        container = BlackjackWealthLeaderboardContainer(leaderboard_data, self.bot, user, guild_id, self)
        self.add_item(container)

    async def render_browser(self, user: discord.User, guild_id: Optional[int] = None, page: int = 0):
        self.clear_items()
        container = BlackjackBrowserContainer(self.bot, user, guild_id, page=page)
        self.add_item(container)

    async def render_info(self, user: discord.User, guild_id: Optional[int] = None):
        self.clear_items()
        container = BlackjackInfoContainer(self.bot, user, guild_id)
        self.add_item(container)

    async def render_leaderboard(self, user: discord.User, guild_id: Optional[int] = None):
        self.clear_items()
        boards = await self.bot.db_manager.get_blackjack_leaderboards(limit=5)
        container = BlackjackLeaderboardContainer(self.bot, user, boards, guild_id)
        self.add_item(container)


# =========================================================================
# --- PUBLIC SPECTATOR TABLE VIEW ---
# =========================================================================

class PublicTableContainer(ui.Container):
    """Container rendered in the public Discord channel for spectators and overview."""

    def __init__(self, bot, table: BlackjackTable, table_view):
        super().__init__()
        self.bot = bot
        self.table = table
        self.table_view = table_view
        self._build_ui()

    def _build_ui(self):
        priv_badge = f"🔒 Code: `{self.table.invite_code}`" if self.table.is_private else "🌐 Public"
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self._on_back_to_browser

        icon = "" if any(self.table.name.startswith(e) for e in ["🥉", "🥈", "🥇", "💎", "🔒", "🎰"]) else "🎰 "
        header_text = f"### {icon}{self.table.name}\n-# {priv_badge} • Min €{self.table.min_bet:.0f} • {self.table.seated_count}/{self.table.max_seats} Players"
        self.add_item(ui.Section(ui.TextDisplay(header_text), accessory=back_btn))
        self.add_item(ui.Separator())

        if self.table.phase == TablePhase.BETTING:
            self._build_betting_phase()
        elif self.table.phase == TablePhase.PLAYER_TURNS:
            self._build_player_turns_phase()
        elif self.table.phase == TablePhase.DEALER_TURN:
            self._build_dealer_phase()
        elif self.table.phase == TablePhase.PAYOUT:
            self._build_payout_phase()

    def _build_betting_phase(self):
        if self.table.phase_end_timestamp is not None:
            end_ts = int(self.table.phase_end_timestamp)
            timer_str = f"\n-# ⏱️ Betting closes <t:{end_ts}:R>"
        else:
            timer_str = "\n-# ⏱️ *Waiting for bets...*"

        desc = f"**Betting window open**\n-# Take a seat and bet to play this hand!{timer_str}"

        take_seat_btn = ui.Button(label="Take a seat", style=discord.ButtonStyle.green)
        take_seat_btn.callback = self._on_take_seat
        self.add_item(ui.Section(ui.TextDisplay(desc), accessory=take_seat_btn))
        self.add_item(ui.Separator())

        # Seated Players List
        seated_lines = []
        for p in self.table.players.values():
            seated_lines.append(f"• **{p.display_name}**: €{p.current_bet:.2f}")

        if seated_lines:
            self.add_item(ui.TextDisplay("**Seated Players:**\n" + "\n".join(seated_lines)))
        else:
            self.add_item(ui.TextDisplay("*No players seated yet. Click Take a seat to join!*"))

    def _build_player_turns_phase(self):
        info_text = f"**Players turns!**\n-# Active players are making their moves."
        self.add_item(ui.TextDisplay(info_text))
        self.add_item(ui.Separator())

        # Dealer cards
        dealer_cards = self.table.dealer_hand.render_cards()
        d_val = self.table.dealer_hand.display_value
        self.add_item(ui.TextDisplay(f"**Dealers hand:**\n{dealer_cards} • {d_val}"))
        self.add_item(ui.Separator())

        # Players cards list
        player_lines = []
        end_ts = int(self.table.phase_end_timestamp) if self.table.phase_end_timestamp else None
        for p in self.table.active_bettors:
            for idx, h in enumerate(p.hands):
                is_turn = (self.table.current_turn_user_id == p.user_id and p.active_hand_idx == idx)
                turn_tag = f" 👈 *(Turn <t:{end_ts}:R>)*" if (is_turn and end_ts) else ""
                double_tag = " *(2x Doubled)*" if h.is_doubled else ""
                player_lines.append(f"• **{p.display_name}**: {h.render_cards()} • {h.display_value}{double_tag}{turn_tag}")

        if player_lines:
            self.add_item(ui.TextDisplay("**Players:**\n" + "\n".join(player_lines)))
        else:
            self.add_item(ui.TextDisplay("**Players:**\n*No active players.*"))

    def _build_dealer_phase(self):
        info_text = "**Dealers turn**\n-# Dealer is revealing and drawing cards..."
        self.add_item(ui.TextDisplay(info_text))
        self.add_item(ui.Separator())

        dealer_cards = self.table.dealer_hand.render_cards()
        d_val = self.table.dealer_hand.display_value
        self.add_item(ui.TextDisplay(f"**Dealers hand:**\n{dealer_cards} • {d_val}"))
        self.add_item(ui.Separator())

        player_lines = []
        for p in self.table.active_bettors:
            for h in p.hands:
                player_lines.append(f"• **{p.display_name}**: {h.render_cards()} • {h.display_value}")

        if player_lines:
            self.add_item(ui.TextDisplay("**Players:**\n" + "\n".join(player_lines)))
        else:
            self.add_item(ui.TextDisplay("**Players:**\n*No active players.*"))

    def _build_payout_phase(self):
        end_ts = int(self.table.phase_end_timestamp) if self.table.phase_end_timestamp else None
        timer_str = f" <t:{end_ts}:R>" if end_ts else ""
        info_text = f"**Round Results**\n-# Next round opens{timer_str}"
        self.add_item(ui.TextDisplay(info_text))
        self.add_item(ui.Separator())

        dealer_cards = self.table.dealer_hand.render_cards()
        d_val = self.table.dealer_hand.display_value
        self.add_item(ui.TextDisplay(f"**Dealers hand:**\n{dealer_cards} • {d_val}"))
        self.add_item(ui.Separator())

        res_lines = []
        for r in self.table.last_results:
            p_name = r["display_name"]
            outcome = r["outcome"].upper()
            net = r["net_profit"]
            sign = "+" if net > 0 else ""
            score = r.get("display_score", f"**{r['player_val']}**")
            res_lines.append(f"• **{p_name}**: **{outcome}** ({sign}€{net:.2f}) • {score} — Bet €{r['bet']:.2f}")

        self.add_item(ui.TextDisplay("**Outcomes:**\n" + ("\n".join(res_lines) if res_lines else "*No results.*")))

    async def _on_take_seat(self, interaction: discord.Interaction):
        if interaction.user.id not in self.table.players:
            if self.table.seated_count >= self.table.max_seats:
                await interaction.response.send_message(f"❌ This table is full! ({self.table.max_seats}/{self.table.max_seats} seats taken)", ephemeral=True)
                return
            self.table.add_player(interaction.user.id, interaction.user.display_name)

        player = self.table.players[interaction.user.id]

        economy = await self.bot.db_manager.get_user_economy(interaction.user.id)
        seat_view = PlayerSeatView(self.bot, self.table, player, user_balance=economy["balance"])
        player.ephemeral_view = seat_view

        await interaction.response.send_message(view=seat_view, ephemeral=True)
        try:
            msg = await interaction.original_response()
            seat_view.message = msg
            if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and msg:
                self.bot._connection._view_store.add_view(seat_view, msg.id)
        except Exception:
            pass
        await self.table.broadcast_updates()

    async def _on_back_to_browser(self, interaction: discord.Interaction):
        if self.table.public_view is self.table_view:
            self.table.public_view = None
        self.table_view.message = None
        lobby_view = BlackjackLobbyView(self.bot, interaction.user, self.table.guild_id)
        await lobby_view.render_browser(interaction.user, self.table.guild_id, page=0)
        await interaction.response.edit_message(view=lobby_view)
        if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and interaction.message:
            self.bot._connection._view_store.add_view(lobby_view, interaction.message.id)


class PublicTableView(ui.LayoutView):
    """Persistent interactive view for a live Blackjack table in the public channel."""

    def __init__(self, bot, table: BlackjackTable):
        super().__init__(timeout=None)
        self.bot = bot
        self.table = table
        self.message: Optional[discord.Message] = None
        self._update_container()

    def _update_container(self):
        self.clear_items()
        container = PublicTableContainer(self.bot, self.table, self)
        self.add_item(container)

    async def refresh_message(self):
        self._update_container()
        if self.message:
            try:
                if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and self.message:
                    self.bot._connection._view_store.add_view(self, self.message.id)
                await self.message.edit(view=self)
                if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and self.message:
                    self.bot._connection._view_store.add_view(self, self.message.id)
            except Exception:
                pass


# =========================================================================
# --- EPHEMERAL PLAYER SEAT VIEW ---
# =========================================================================

class PlayerSeatContainer(ui.Container):
    """Container rendered inside the player's personal ephemeral interaction."""

    def __init__(self, bot, table: BlackjackTable, player: BlackjackPlayer, seat_view):
        super().__init__()
        self.bot = bot
        self.table = table
        self.player = player
        self.seat_view = seat_view
        self._build_ui()

    def _build_ui(self):
        priv_badge = f"🔒 Code: `{self.table.invite_code}`" if self.table.is_private else "🌐 Public"
        icon = "" if any(self.table.name.startswith(e) for e in ["🥉", "🥈", "🥇", "💎", "🔒", "🎰"]) else "🎰 "
        header_text = f"### {icon}{self.table.name}\n-# {priv_badge} • Min €{self.table.min_bet:.0f} • {self.table.seated_count}/{self.table.max_seats} Players"
        self.add_item(ui.TextDisplay(header_text))
        self.add_item(ui.Separator())

        if self.table.phase == TablePhase.BETTING:
            self._build_betting_phase()
        elif self.table.phase == TablePhase.PLAYER_TURNS:
            self._build_player_turns_phase()
        elif self.table.phase == TablePhase.DEALER_TURN:
            self._build_dealer_phase()
        elif self.table.phase == TablePhase.PAYOUT:
            self._build_payout_phase()

    def _build_betting_phase(self):
        if self.table.phase_end_timestamp is not None:
            end_ts = int(self.table.phase_end_timestamp)
            timer_str = f"\n-# ⏱️ Betting closes <t:{end_ts}:R>"
        else:
            timer_str = "\n-# ⏱️ *Waiting for bets...*"

        desc = f"**Betting window open**\n-# Place your bets below to play this hand!{timer_str}"

        leave_btn = ui.Button(label="Leave", style=discord.ButtonStyle.gray)
        leave_btn.callback = self._on_leave_seat
        self.add_item(ui.Section(ui.TextDisplay(desc), accessory=leave_btn))
        self.add_item(ui.Separator())

        # Balance small text above bet (always visible)
        bal_val = self.seat_view.user_balance if self.seat_view.user_balance is not None else 0.0
        bal_line = f"-# Balance: €{bal_val:,.2f}\n"

        # Your Bet Section with Clear button (only enabled if bet > 0)
        clear_btn = ui.Button(label="Clear", style=discord.ButtonStyle.red, disabled=(self.player.current_bet <= 0))
        clear_btn.callback = self._on_clear_bet

        bet_text = f"{bal_line}**Your bet**\n€{self.player.current_bet:.2f}"
        self.add_item(ui.Section(ui.TextDisplay(bet_text), accessory=clear_btn))

        # Chip Buttons Row (3 tier-scaled chips, Custom, All In)
        min_b = self.table.min_bet
        if min_b <= 5:
            chips = [5, 10, 25]
        elif min_b <= 10:
            chips = [10, 25, 50]
        elif min_b <= 20:
            chips = [20, 50, 100]
        elif min_b <= 50:
            chips = [50, 100, 250]
        else:
            chips = [int(min_b), int(min_b * 2), int(min_b * 5)]

        chip_row = ui.ActionRow()
        for amt in chips:
            btn = ui.Button(label=f"+{amt}€", style=discord.ButtonStyle.gray)
            btn.callback = self._make_bet_callback(amt)
            chip_row.add_item(btn)

        custom_btn = ui.Button(label="Custom", style=discord.ButtonStyle.gray)
        custom_btn.callback = self._on_custom_bet
        chip_row.add_item(custom_btn)

        all_in_btn = ui.Button(label="All In", style=discord.ButtonStyle.gray)
        all_in_btn.callback = self._on_all_in
        chip_row.add_item(all_in_btn)

        self.add_item(chip_row)
        self.add_item(ui.Separator())

        # Other Seated Players List (only other players)
        other_lines = []
        for p in self.table.players.values():
            if p.user_id != self.player.user_id:
                other_lines.append(f"• **{p.display_name}**: €{p.current_bet:.2f}")

        if other_lines:
            self.add_item(ui.TextDisplay("**Other Players & Bets:**\n" + "\n".join(other_lines)))
        else:
            self.add_item(ui.TextDisplay("*No other players at the table.*"))

    def _build_player_turns_phase(self):
        dealer_cards = self.table.dealer_hand.render_cards()
        d_val = self.table.dealer_hand.display_value
        self.add_item(ui.TextDisplay(f"**Dealers hand:**\n{dealer_cards} • {d_val}"))
        self.add_item(ui.Separator())

        is_my_turn = (self.table.current_turn_user_id == self.player.user_id)
        active_hand = self.player.active_hand

        if self.player.is_spectating or not self.player.hands:
            self.add_item(ui.TextDisplay("👀 **You are spectating this round.** (No bet placed)"))
        else:
            for idx, h in enumerate(self.player.hands):
                split_tag = f" Hand #{idx+1}" if len(self.player.hands) > 1 else ""
                double_tag = " *(2x Doubled)*" if h.is_doubled else ""
                self.add_item(ui.TextDisplay(f"**Your cards{split_tag}:**\n{h.render_cards()} • {h.display_value}{double_tag}"))

            if is_my_turn and active_hand and not (active_hand.is_standing or active_hand.is_busted):
                end_ts = int(self.table.phase_end_timestamp) if self.table.phase_end_timestamp else None
                timer_str = f" <t:{end_ts}:R>" if end_ts else ""
                self.add_item(ui.TextDisplay(f"-# Make your move{timer_str}"))

                act_row = ui.ActionRow()
                hit_btn = ui.Button(label="Hit", style=discord.ButtonStyle.gray)
                hit_btn.callback = self._on_hit
                act_row.add_item(hit_btn)

                stand_btn = ui.Button(label="Stand", style=discord.ButtonStyle.gray)
                stand_btn.callback = self._on_stand
                act_row.add_item(stand_btn)

                double_btn = ui.Button(label="Double Down", style=discord.ButtonStyle.gray, disabled=not active_hand.can_double)
                double_btn.callback = self._on_double
                act_row.add_item(double_btn)

                split_btn = ui.Button(label="Split", style=discord.ButtonStyle.gray, disabled=not active_hand.can_split)
                split_btn.callback = self._on_split
                act_row.add_item(split_btn)

                self.add_item(act_row)
            else:
                all_done = all(p.all_hands_finished for p in self.table.active_bettors)
                if all_done:
                    self.add_item(ui.TextDisplay("⏳ **Waiting for the dealer...**"))
                else:
                    self.add_item(ui.TextDisplay("⏳ **Waiting for other players...**"))

        self.add_item(ui.Separator())

        # Other Seated Players
        other_lines = []
        for p in self.table.active_bettors:
            if p.user_id != self.player.user_id:
                for h in p.hands:
                    other_lines.append(f"• **{p.display_name}**: {h.render_cards()} • {h.display_value}")

        if other_lines:
            self.add_item(ui.TextDisplay("**Other Players:**\n" + "\n".join(other_lines)))
        else:
            self.add_item(ui.TextDisplay("*No other players at the table.*"))

    def _build_dealer_phase(self):
        dealer_cards = self.table.dealer_hand.render_cards()
        d_val = self.table.dealer_hand.display_value
        self.add_item(ui.TextDisplay(f"**Dealers hand:**\n{dealer_cards} • {d_val}"))
        self.add_item(ui.Separator())

        if self.player.hands:
            for idx, h in enumerate(self.player.hands):
                split_tag = f" Hand #{idx+1}" if len(self.player.hands) > 1 else ""
                self.add_item(ui.TextDisplay(f"**Your cards{split_tag}:**\n{h.render_cards()} • {h.display_value}"))
            self.add_item(ui.TextDisplay("⏳ **Waiting for the dealer...**"))
        else:
            self.add_item(ui.TextDisplay("👀 **You are spectating this round.**"))

        self.add_item(ui.Separator())

        # Other Players
        other_lines = []
        for p in self.table.active_bettors:
            if p.user_id != self.player.user_id:
                for h in p.hands:
                    other_lines.append(f"• **{p.display_name}**: {h.render_cards()} • {h.display_value}")

        if other_lines:
            self.add_item(ui.TextDisplay("**Other Players:**\n" + "\n".join(other_lines)))
        else:
            self.add_item(ui.TextDisplay("*No other players at the table.*"))

    def _build_payout_phase(self):
        end_ts = int(self.table.phase_end_timestamp) if self.table.phase_end_timestamp else None
        timer_str = f" <t:{end_ts}:R>" if end_ts else ""
        dealer_cards = self.table.dealer_hand.render_cards()
        d_val = self.table.dealer_hand.display_value
        self.add_item(ui.TextDisplay(f"**Dealers hand:**\n{dealer_cards} • {d_val}"))
        self.add_item(ui.Separator())

        # Your Cards & Outcome Banner
        my_results = [r for r in self.table.last_results if r["user_id"] == self.player.user_id]
        if my_results:
            for r in my_results:
                net = r["net_profit"]
                outcome = r["outcome"]
                score = r.get("display_score", f"**{r['player_val']}**")
                if outcome == "blackjack":
                    banner = f"🃏 **Blackjack! +€{r['payout'] - r['bet']:.2f}**"
                elif outcome == "win":
                    banner = f"🎉 **You won! +€{net:.2f}**"
                elif outcome == "push":
                    banner = f"🤝 **Push (Tie)! Bet refunded.**"
                else:
                    banner = f"💥 **You lost! -€{r['bet']:.2f}**"

                hand_idx = r["hand_idx"]
                hand = self.player.hands[hand_idx] if hand_idx < len(self.player.hands) else None
                cards_str = hand.render_cards() if hand else r.get("cards_display", "")
                timer_line = f"\n-# ⏱️ Next hand opens{timer_str}" if timer_str else ""
                self.add_item(ui.TextDisplay(f"**Your cards:**\n{cards_str} • {score}\n{banner}{timer_line}"))
        else:
            timer_line = f"\n-# ⏱️ Next hand opens{timer_str}" if timer_str else ""
            self.add_item(ui.TextDisplay(f"👀 **You spectated this round.**{timer_line}"))

        self.add_item(ui.Separator())

        # Other Players Results
        other_res = []
        for r in self.table.last_results:
            if r["user_id"] != self.player.user_id:
                outcome = r["outcome"].upper()
                net = r["net_profit"]
                sign = "+" if net > 0 else ""
                score = r.get("display_score", f"**{r['player_val']}**")
                other_res.append(f"• **{r['display_name']}**: **{outcome}** ({sign}€{net:.2f}) • {score}")

        if other_res:
            self.add_item(ui.TextDisplay("**Other Players:**\n" + "\n".join(other_res)))
        else:
            self.add_item(ui.TextDisplay("*No other players at the table.*"))

    def _make_bet_callback(self, amt: float):
        async def callback(interaction: discord.Interaction):
            economy = await self.bot.db_manager.get_user_economy(interaction.user.id)
            ok, msg, cur = self.table.add_bet(interaction.user.id, amt, economy["balance"])
            if not ok:
                await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
                return

            self.seat_view.user_balance = economy["balance"]
            self.seat_view._update_container()
            await interaction.response.edit_message(view=self.seat_view)
            if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and interaction.message:
                self.bot._connection._view_store.add_view(self.seat_view, interaction.message.id)
            await self.table.broadcast_updates()
        return callback

    async def _on_clear_bet(self, interaction: discord.Interaction):
        self.table.clear_bet(interaction.user.id)
        economy = await self.bot.db_manager.get_user_economy(interaction.user.id)
        self.seat_view.user_balance = economy["balance"]
        self.seat_view._update_container()
        await interaction.response.edit_message(view=self.seat_view)
        if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and interaction.message:
            self.bot._connection._view_store.add_view(self.seat_view, interaction.message.id)
        await self.table.broadcast_updates()

    async def _on_custom_bet(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CustomBetModal(self.bot, self.table, self.seat_view))

    async def _on_all_in(self, interaction: discord.Interaction):
        economy = await self.bot.db_manager.get_user_economy(interaction.user.id)
        balance = economy.get("balance", 0.0)

        if balance < self.table.min_bet:
            await interaction.response.send_message(
                f"❌ You do not have enough balance to meet the table minimum bet (€{self.table.min_bet:.2f}).",
                ephemeral=True
            )
            return

        self.table.clear_bet(interaction.user.id)
        ok, msg, current_bet = self.table.add_bet(interaction.user.id, balance, balance)
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        self.seat_view.user_balance = balance
        self.seat_view._update_container()
        await interaction.response.edit_message(view=self.seat_view)
        if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and interaction.message:
            self.bot._connection._view_store.add_view(self.seat_view, interaction.message.id)
        await self.table.broadcast_updates()

    async def _on_hit(self, interaction: discord.Interaction):
        ok, msg = self.table.player_hit(interaction.user.id)
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        self.seat_view._update_container()
        await interaction.response.edit_message(view=self.seat_view)
        if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and interaction.message:
            self.bot._connection._view_store.add_view(self.seat_view, interaction.message.id)
        await self.table.broadcast_updates()

    async def _on_stand(self, interaction: discord.Interaction):
        ok, msg = self.table.player_stand(interaction.user.id)
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        self.seat_view._update_container()
        await interaction.response.edit_message(view=self.seat_view)
        if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and interaction.message:
            self.bot._connection._view_store.add_view(self.seat_view, interaction.message.id)
        await self.table.broadcast_updates()

    async def _on_double(self, interaction: discord.Interaction):
        economy = await self.bot.db_manager.get_user_economy(interaction.user.id)
        ok, msg = self.table.player_double(interaction.user.id, economy["balance"])
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        self.seat_view.user_balance = economy["balance"] - self.player.active_hand.bet
        self.seat_view._update_container()
        await interaction.response.edit_message(view=self.seat_view)
        if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and interaction.message:
            self.bot._connection._view_store.add_view(self.seat_view, interaction.message.id)
        await self.table.broadcast_updates()

    async def _on_split(self, interaction: discord.Interaction):
        economy = await self.bot.db_manager.get_user_economy(interaction.user.id)
        ok, msg = self.table.player_split(interaction.user.id, economy["balance"])
        if not ok:
            await interaction.response.send_message(f"❌ {msg}", ephemeral=True)
            return

        self.seat_view.user_balance = economy["balance"] - self.player.active_hand.bet
        self.seat_view._update_container()
        await interaction.response.edit_message(view=self.seat_view)
        if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and interaction.message:
            self.bot._connection._view_store.add_view(self.seat_view, interaction.message.id)
        await self.table.broadcast_updates()

    async def _on_leave_seat(self, interaction: discord.Interaction):
        self.table.remove_player(interaction.user.id)
        await self.table.broadcast_updates()
        try:
            await interaction.response.defer()
            await interaction.delete_original_response()
        except Exception:
            try:
                await interaction.response.edit_message(content="👋 You have left the table.", view=None)
            except Exception:
                pass


class PlayerSeatView(ui.LayoutView):
    """Personal interactive ephemeral view for a seated player."""

    def __init__(self, bot, table: BlackjackTable, player: BlackjackPlayer, user_balance: Optional[float] = None):
        super().__init__(timeout=None)
        self.bot = bot
        self.table = table
        self.player = player
        self.user_balance = user_balance
        self.message: Optional[discord.Message] = None
        self._update_container()

    def _update_container(self):
        self.clear_items()
        container = PlayerSeatContainer(self.bot, self.table, self.player, self)
        self.add_item(container)

    async def refresh_message(self):
        try:
            econ = await self.bot.db_manager.get_user_economy(self.player.user_id)
            self.user_balance = econ["balance"]
        except Exception:
            pass
        self._update_container()
        if self.message:
            try:
                if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and self.message:
                    self.bot._connection._view_store.add_view(self, self.message.id)
                await self.message.edit(view=self)
                if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and self.message:
                    self.bot._connection._view_store.add_view(self, self.message.id)
            except Exception:
                pass
