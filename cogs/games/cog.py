from discord.ext import commands
from discord import ui
import discord
import logging
import datetime
import asyncio
import time
from random import randint
from concurrent.futures import ProcessPoolExecutor
from typing import Optional, List

from .connect4 import CFGame, run_mcts
from .c4_matchmaking import C4MatchmakingManager, C4MatchmakingTicket
from .blackjack import TableManager
from .blackjack_views import BlackjackLobbyView
from .wallet_views import WalletView
from cogs.utils.constants import Emojis

logger = logging.getLogger(__name__)


class CFMenuContainer(ui.Container):
    C4_LOGO = Emojis.C4_LOGO

    def __init__(self):
        super().__init__()
        self._make_container()

    def _make_container(self):
        titleDisplay = ui.TextDisplay(f"## {self.C4_LOGO} Connect Four")
        self.add_item(titleDisplay)
        self.add_item(ui.Separator())

        options = [
            discord.SelectOption(label="🎮 Play with a Friend", value="PvsP", description="Wait for someone in this channel to join"),
            discord.SelectOption(label="🌐 Find Match (Matchmaking)", value="Matchmaking", description="Pair with any player across servers"),
            discord.SelectOption(label="🤖 Play against AI", value="PvsAI", description="Challenge the intelligent AI engine"),
        ]

        selectMenu = ui.Select(placeholder="Click to choose a gamemode...", options=options, id=67)
        selectMenu.callback = self.gamemode_select_callback
        selectRow = ui.ActionRow()
        selectRow.add_item(selectMenu)
        self.add_item(selectRow)

        play_button = ui.Button(label="Play", style=discord.ButtonStyle.green)
        play_button.callback = self.play_button_callback

        lb_button = ui.Button(label="Leaderboard", style=discord.ButtonStyle.blurple, emoji="🏆")
        lb_button.callback = self.leaderboard_button_callback

        buttonRow = ui.ActionRow()
        buttonRow.add_item(play_button)
        buttonRow.add_item(lb_button)
        self.add_item(buttonRow)

    async def gamemode_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

    async def play_button_callback(self, interaction: discord.Interaction):
        select = self.find_item(67)
        if not select or len(select.values) == 0:
            await interaction.response.send_message("You need to choose a gamemode first.", ephemeral=True)
            return
        gamemode = select.values[0]
        view = self.view

        if gamemode == "PvsP":
            view.lobby_view()
            view.timeout = 300
            await interaction.response.edit_message(view=view)
            view._wait_for_player_task = asyncio.create_task(view.wait_for_player_task(interaction))

        elif gamemode == "Matchmaking":
            await view.start_matchmaking(interaction)

        elif gamemode == "PvsAI":
            view.ai_config_view()
            await interaction.response.edit_message(view=view)

    async def leaderboard_button_callback(self, interaction: discord.Interaction):
        await self.view.leaderboard_view(interaction)

    async def interaction_check(self, interaction: discord.Interaction):
        if self.view.author_id != interaction.user.id:
            await interaction.response.send_message("You can't use this button.\n-# Tip: Run `/connect_four` to start your own game.", ephemeral=True)
            return False
        return True


class CFWaitingContainer(ui.Container):
    C4_LOGO = Emojis.C4_LOGO

    def __init__(self, author_id, timeout_minutes=3):
        super().__init__()
        self.author_id = author_id
        self.timeout_minutes = timeout_minutes
        self._make_container()

    def _make_container(self):
        title_display = ui.TextDisplay(f"## {self.C4_LOGO} Connect Four")
        self.add_item(title_display)
        self.add_item(ui.Separator())

        join_display = ui.TextDisplay(f"<@{self.author_id}> is waiting for a player!")
        time_str = discord.utils.format_dt(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=self.timeout_minutes), style='R')
        time_display = ui.TextDisplay(f"-# Waiting room closes {time_str}.")

        join_button = ui.Button(label="Join Game", style=discord.ButtonStyle.green)
        join_button.callback = self.join_button_callback

        section = ui.Section(join_display, time_display, accessory=join_button)
        self.add_item(section)

        cancel_row = ui.ActionRow()
        cancel_button = ui.Button(label="Cancel", style=discord.ButtonStyle.gray)
        cancel_button.callback = self.cancel_button_callback
        cancel_row.add_item(cancel_button)
        self.add_item(cancel_row)

    async def join_button_callback(self, interaction: discord.Interaction):
        view = self.view
        if interaction.user.id == view.author_id:
            await interaction.response.send_message("You cannot play against yourself!", ephemeral=True)
            return

        view.assign_players(view.author_id, interaction.user.id)
        if view._wait_for_player_task is not None:
            view._wait_for_player_task.cancel()
        view.game = CFGame()
        view.gamemode = "PvsP"
        view.game_view()
        await interaction.response.edit_message(view=view)

    async def cancel_button_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.author_id:
            await interaction.response.send_message("Only the game host can cancel the lobby.", ephemeral=True)
            return
        self.view.main_menu_view()
        await interaction.response.edit_message(view=self.view)


class CFMatchmakingWaitingContainer(ui.Container):
    C4_LOGO = Emojis.C4_LOGO

    def __init__(self, author_id, joined_at: float):
        super().__init__()
        self.author_id = author_id
        self.joined_at = joined_at
        self._make_container()

    def _make_container(self):
        title_display = ui.TextDisplay(f"## {self.C4_LOGO} Connect Four — Matchmaking")
        self.add_item(title_display)
        self.add_item(ui.Separator())

        time_str = f"<t:{int(self.joined_at)}:R>"
        status_display = ui.TextDisplay(
            f"**🔍 Searching for an opponent...**\n"
            f"-# You joined the global queue {time_str}. Waiting for another player."
        )
        self.add_item(status_display)
        self.add_item(ui.Separator())

        cancel_row = ui.ActionRow()
        cancel_btn = ui.Button(label="Cancel Queue", style=discord.ButtonStyle.red)
        cancel_btn.callback = self.cancel_queue_callback
        cancel_row.add_item(cancel_btn)
        self.add_item(cancel_row)

    async def cancel_queue_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Only the queue owner can cancel.", ephemeral=True)
            return
        C4MatchmakingManager().dequeue(self.author_id)
        self.view.main_menu_view()
        await interaction.response.edit_message(view=self.view)


class CFAIConfigContainer(ui.Container):
    C4_LOGO = Emojis.C4_LOGO
    SELECT_ID = 67

    def __init__(self):
        super().__init__()
        self._make_container()

    def _make_container(self):
        titleDisplay = ui.TextDisplay(f"## {self.C4_LOGO} Connect Four — AI Match")
        self.add_item(titleDisplay)
        self.add_item(ui.Separator())

        options = [
            discord.SelectOption(label="Easy", value="11", description="Fast, basic moves"),
            discord.SelectOption(label="Medium", value="25", description="Balanced strategic opponent"),
            discord.SelectOption(label="Hard", value="500", description="Deep tree search (Advanced)"),
            discord.SelectOption(label="Impossible", value="2000", description="Maximum MCTS simulation depth (Grandmaster)")
        ]

        selectMenu = ui.Select(placeholder="Click to choose a difficulty...", options=options, id=self.SELECT_ID)
        selectMenu.callback = self.difficulty_select_callback
        selectRow = ui.ActionRow()
        selectRow.add_item(selectMenu)
        self.add_item(selectRow)

        start_button = ui.Button(label="Start Match", style=discord.ButtonStyle.green)
        start_button.callback = self.start_button_callback

        back_button = ui.Button(label="Back", style=discord.ButtonStyle.gray)
        back_button.callback = self.back_button_callback

        buttonRow = ui.ActionRow()
        buttonRow.add_item(start_button)
        buttonRow.add_item(back_button)
        self.add_item(buttonRow)

    async def difficulty_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

    async def start_button_callback(self, interaction: discord.Interaction):
        select = self.find_item(self.SELECT_ID)
        if not select or len(select.values) == 0:
            await interaction.response.send_message("You need to choose a difficulty first.", ephemeral=True)
            return

        difficulty = int(select.values[0])
        view = self.view
        view.bot_difficulty = difficulty
        view.gamemode = "PvsAI"
        view.game = CFGame()
        view.assign_players(view.author_id, view.bot_id)
        view.game_view(interaction=interaction)
        await interaction.response.edit_message(view=view)

    async def back_button_callback(self, interaction: discord.Interaction):
        self.view.main_menu_view()
        await interaction.response.edit_message(view=self.view)

    async def interaction_check(self, interaction: discord.Interaction):
        if self.view.author_id != interaction.user.id:
            await interaction.response.send_message("You can't use this button.\n-# Tip: Run `/connect_four` to play.", ephemeral=True)
            return False
        return True


class CFGameContainer(ui.Container):
    C4_LOGO = Emojis.C4_LOGO
    EMPTY = Emojis.EMPTY
    RED_PIECE = Emojis.RED_PIECE
    YELLOW_PIECE = Emojis.YELLOW_PIECE
    TO_MOVE_ARROW = Emojis.TO_MOVE_ARROW
    C4_VS = Emojis.C4_VS

    def __init__(self, red_id, yellow_id, game: CFGame, bot_turn: bool = False, selected_column: int = 3):
        super().__init__()
        self.red_id = red_id
        self.yellow_id = yellow_id
        self.game = game
        self.bot_turn = bot_turn
        self.selected_column = selected_column
        self._make_container()

    def _make_container(self):
        titleString = f"## {self.C4_LOGO}  Connect 4"
        titleDisplay = ui.TextDisplay(titleString)
        self.add_item(titleDisplay)
        self.add_item(ui.Separator())

        # Indicator piece above selected column
        piece_emoji = self.RED_PIECE if self.game.current_player == self.game.RED else self.YELLOW_PIECE

        rows = []
        select_row = [self.EMPTY] * 7
        select_row[self.selected_column] = piece_emoji
        select_row = "".join(select_row)

        turnString = f"**{'Yellow' if self.game.current_player == self.game.YELLOW else 'Red'}'s turn!**"
        rows.append(self.EMPTY + select_row + self.EMPTY + turnString)

        board_rows = self.game.render_board()
        rows.extend(board_rows)

        rows[3] = rows[3] + f"{self.EMPTY}{self.EMPTY if self.game.current_player == self.game.YELLOW else self.TO_MOVE_ARROW}{self.RED_PIECE} <@{self.red_id}>"
        rows[4] = rows[4] + f"{self.EMPTY}{self.EMPTY}{self.C4_VS}"
        rows[5] = rows[5] + f"{self.EMPTY}{self.EMPTY if self.game.current_player == self.game.RED else self.TO_MOVE_ARROW}{self.YELLOW_PIECE} <@{self.yellow_id}>"

        boardString = f"\n{self.EMPTY}".join(rows)
        gameDisplay = ui.TextDisplay(boardString)
        self.add_item(gameDisplay)
        self.add_item(ui.Separator())

        playerActionRow = ui.ActionRow()

        left_button = ui.Button(label=Emojis.ARROW_LEFT, style=discord.ButtonStyle.gray)
        left_button.callback = self.move_left
        playerActionRow.add_item(left_button)

        confirm_button = ui.Button(emoji=Emojis.SUCCESS, style=discord.ButtonStyle.green)
        confirm_button.callback = self.confirm_move
        playerActionRow.add_item(confirm_button)

        right_button = ui.Button(label=Emojis.ARROW_RIGHT, style=discord.ButtonStyle.gray)
        right_button.callback = self.move_right
        playerActionRow.add_item(right_button)

        resign_button = ui.Button(emoji=Emojis.FLAG, style=discord.ButtonStyle.red)
        resign_button.callback = self.resign
        playerActionRow.add_item(resign_button)

        botTextDisplay = ui.TextDisplay(f"## {Emojis.LOADING}  Bot is thinking...")

        if self.bot_turn:
            self.add_item(botTextDisplay)
        else:
            self.add_item(playerActionRow)

        self.accent_color = discord.Colour.yellow() if self.game.current_player == self.game.YELLOW else discord.Colour.red()

    async def move_left(self, interaction: discord.Interaction):
        self.selected_column = max(0, self.selected_column - 1)
        self.view.game_view(self.selected_column)
        await interaction.response.edit_message(view=self.view)

    async def confirm_move(self, interaction: discord.Interaction):
        view = self.view
        game = view.game
        move = self.selected_column

        if game.is_legal_move(move):
            game.make_move(move)

        view.game = game
        view.change_turn()
        await view.sync_game_state(interaction=interaction)

    async def move_right(self, interaction: discord.Interaction):
        self.selected_column = min(self.selected_column + 1, 6)
        self.view.game_view(self.selected_column)
        await interaction.response.edit_message(view=self.view)

    async def resign(self, interaction: discord.Interaction):
        view = self.view
        view.game.resign()
        await view.sync_game_state(interaction=interaction)

    async def interaction_check(self, interaction: discord.Interaction):
        # In a cross-server/channel matchmaking match, players can ONLY click on their own view!
        if self.view.linked_view is not None:
            if interaction.user.id != self.view.author_id:
                await interaction.response.send_message("You can only play on your own game board!", ephemeral=True)
                return False

        active_id = self.red_id if self.game.current_player == self.game.RED else self.yellow_id
        if interaction.user.id == active_id:
            return True
        if interaction.user.id in [self.red_id, self.yellow_id]:
            await interaction.response.send_message("It's not your turn yet.", ephemeral=True)
            return False
        await interaction.response.send_message("You're not playing in this game.\n-# Pro tip: Run `/connect_four` to play.", ephemeral=True)
        return False


class CFEndContainer(ui.Container):
    C4_LOGO = Emojis.C4_LOGO
    EMPTY = Emojis.EMPTY
    RED_PIECE = Emojis.RED_PIECE
    YELLOW_PIECE = Emojis.YELLOW_PIECE

    def __init__(self, red_id, yellow_id, game: CFGame, rematch_disabled: bool = False):
        super().__init__()
        self.red_id = red_id
        self.yellow_id = yellow_id
        self.game = game
        self.rematch_disabled = rematch_disabled
        self._make_container()

    def _make_container(self):
        titleString = f"## {self.C4_LOGO} Connect Four — Game Over"
        titleDisplay = ui.TextDisplay(titleString)
        self.add_item(titleDisplay)
        self.add_item(ui.Separator())

        if self.game.status == self.game.DRAW:
            turnString = "**It's a draw!**"
        else:
            turnString = f"**{'Yellow' if self.game.status == self.game.YELLOW_WIN else 'Red'} won!**"

        rows = []
        select_row = [self.EMPTY] * 7
        select_row = "".join(select_row)
        rows.append(self.EMPTY + select_row + turnString)

        board_rows = self.game.render_board()
        rows.extend(board_rows)

        if self.game.status == self.game.DRAW:
            rows[3] = rows[3] + f"{self.EMPTY}{Emojis.MINUS}{self.RED_PIECE} <@{self.red_id}>"
            rows[4] = rows[4] + f"{self.EMPTY}{self.EMPTY}{Emojis.HANDSHAKE}"
            rows[5] = rows[5] + f"{self.EMPTY}{Emojis.MINUS}{self.YELLOW_PIECE} <@{self.yellow_id}>"
        else:
            rows[3] = rows[3] + f"{self.EMPTY}{Emojis.CROWN if self.game.status == self.game.RED_WIN else Emojis.ERROR}{self.RED_PIECE} <@{self.red_id}>"
            rows[4] = rows[4] + f"{self.EMPTY}{self.EMPTY}{Emojis.C4_VS}"
            rows[5] = rows[5] + f"{self.EMPTY}{Emojis.CROWN if self.game.status == self.game.YELLOW_WIN else Emojis.ERROR}{self.YELLOW_PIECE} <@{self.yellow_id}>"

        boardString = f"{self.EMPTY}" + f"\n{self.EMPTY}".join(rows)
        gameDisplay = ui.TextDisplay(boardString)
        self.add_item(gameDisplay)
        self.add_item(ui.Separator())

        # Rematch button row
        action_row = ui.ActionRow()
        rematch_btn = ui.Button(
            label="Rematch",
            style=discord.ButtonStyle.green if not self.rematch_disabled else discord.ButtonStyle.gray,
            emoji="🔁",
            disabled=self.rematch_disabled
        )
        rematch_btn.callback = self.rematch_button_callback
        action_row.add_item(rematch_btn)

        menu_btn = ui.Button(label="Main Menu", style=discord.ButtonStyle.gray)
        menu_btn.callback = self.main_menu_callback
        action_row.add_item(menu_btn)

        self.add_item(action_row)

        self.accent_color = discord.Colour.red() if self.game.status == self.game.RED_WIN else discord.Colour.yellow()

    async def rematch_button_callback(self, interaction: discord.Interaction):
        await self.view.handle_rematch_request(interaction)

    async def main_menu_callback(self, interaction: discord.Interaction):
        self.view.main_menu_view()
        await interaction.response.edit_message(view=self.view)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id in [self.red_id, self.yellow_id, self.view.author_id]:
            return True
        await interaction.response.send_message("Only players in this match can interact.", ephemeral=True)
        return False


class CFRematchPromptContainer(ui.Container):
    """Container displayed to opponent when a player requests a rematch."""
    C4_LOGO = Emojis.C4_LOGO

    def __init__(self, requester_id: int, opponent_id: int):
        super().__init__()
        self.requester_id = requester_id
        self.opponent_id = opponent_id
        self._make_container()

    def _make_container(self):
        title_display = ui.TextDisplay(f"## {self.C4_LOGO} Rematch Requested!")
        self.add_item(title_display)
        self.add_item(ui.Separator())

        prompt_text = ui.TextDisplay(
            f"<@{self.requester_id}> is challenging you to a **Rematch**!\n"
            f"-# Do you accept the challenge?"
        )
        self.add_item(prompt_text)
        self.add_item(ui.Separator())

        action_row = ui.ActionRow()
        accept_btn = ui.Button(label="Accept", style=discord.ButtonStyle.green, emoji="✅")
        accept_btn.callback = self.accept_callback
        action_row.add_item(accept_btn)

        decline_btn = ui.Button(label="Decline", style=discord.ButtonStyle.red, emoji="❌")
        decline_btn.callback = self.decline_callback
        action_row.add_item(decline_btn)

        self.add_item(action_row)

    async def accept_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.opponent_id:
            await interaction.response.send_message("Only the challenged player can accept this rematch.", ephemeral=True)
            return
        await self.view.accept_rematch(interaction)

    async def decline_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.opponent_id:
            await interaction.response.send_message("Only the challenged player can decline this rematch.", ephemeral=True)
            return
        await self.view.decline_rematch(interaction)


class CFRematchWaitingContainer(ui.Container):
    """Container displayed to requester while waiting for opponent to accept."""
    C4_LOGO = Emojis.C4_LOGO

    def __init__(self, opponent_id: int):
        super().__init__()
        self.opponent_id = opponent_id
        self._make_container()

    def _make_container(self):
        title_display = ui.TextDisplay(f"## {self.C4_LOGO} Rematch Challenge Sent")
        self.add_item(title_display)
        self.add_item(ui.Separator())

        waiting_text = ui.TextDisplay(
            f"**⏳ Waiting for opponent...**\n"
            f"-# Sent rematch request to <@{self.opponent_id}>."
        )
        self.add_item(waiting_text)


class CFLeaderboardContainer(ui.Container):
    """Displays top Connect 4 players and personal stats."""
    C4_LOGO = Emojis.C4_LOGO

    def __init__(self, bot, user: discord.User, boards: dict, user_stats: dict):
        super().__init__()
        self.bot = bot
        self.user = user
        self.boards = boards
        self.user_stats = user_stats
        self._make_container()

    def _make_container(self):
        back_btn = ui.Button(label="< Back", style=discord.ButtonStyle.gray)
        back_btn.callback = self.back_callback

        title_display = ui.TextDisplay(f"### 🏆 Connect Four Leaderboards\n-# Global rankings and top player records.")
        self.add_item(ui.Section(title_display, accessory=back_btn))
        self.add_item(ui.Separator())

        # Top Wins
        wins_lines = ["**🥇 Top Champions (Most Wins):**"]
        top_wins = self.boards.get("top_wins", [])
        if top_wins:
            for idx, (uid, wins, losses, draws, played, wr) in enumerate(top_wins, 1):
                wins_lines.append(f"{idx}. <@{uid}> — **{wins} wins** ({played} matches • {wr}% WR)")
        else:
            wins_lines.append("-# No matches recorded yet.")
        self.add_item(ui.TextDisplay("\n".join(wins_lines)))
        self.add_item(ui.Separator())

        # Top Streaks
        streak_lines = ["**🔥 Top Win Streaks:**"]
        top_streaks = self.boards.get("top_streaks", [])
        if top_streaks:
            for idx, (uid, bstreak, cstreak, wins, played) in enumerate(top_streaks, 1):
                streak_lines.append(f"{idx}. <@{uid}> — **{bstreak} streak** (Current: {cstreak})")
        else:
            streak_lines.append("-# No active streaks.")
        self.add_item(ui.TextDisplay("\n".join(streak_lines)))
        self.add_item(ui.Separator())

        # Player Profile Stats
        stat_text = (
            f"**📊 Your Player Card (<@{self.user.id}>):**\n"
            f"• Matches: `{self.user_stats['games_played']}` • Wins: `{self.user_stats['wins']}` • Losses: `{self.user_stats['losses']}` • Draws: `{self.user_stats['draws']}`\n"
            f"• Win Rate: `{self.user_stats['win_rate']}%` • Best Streak: `🔥 {self.user_stats['best_streak']}` (Current: `{self.user_stats['current_streak']}`)"
        )
        self.add_item(ui.TextDisplay(stat_text))
        self.add_item(ui.Separator())

        action_row = ui.ActionRow()
        refresh_btn = ui.Button(emoji=Emojis.RELOAD, style=discord.ButtonStyle.gray)
        refresh_btn.callback = self.refresh_callback
        action_row.add_item(refresh_btn)
        self.add_item(action_row)

    async def back_callback(self, interaction: discord.Interaction):
        self.view.main_menu_view()
        await interaction.response.edit_message(view=self.view)

    async def refresh_callback(self, interaction: discord.Interaction):
        await self.view.leaderboard_view(interaction)


class CFView(ui.LayoutView):
    CF_EMOJI = Emojis.C4_LOGO

    def __init__(self, author_id, bot, guild_id=None, channel_id=None, *, timeout=None):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.game = None
        self.author_id = author_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.game_start_time = None
        self.telemetry_logged = False
        self.red_player_id = None
        self.yellow_player_id = None
        self.bot_id = bot.user.id
        self.bot_difficulty = None
        self.gamemode = None
        self.current_player_id = None
        self.bot_turn = False
        self._bot_turn_task = None
        self._wait_for_player_task = None
        self.linked_view: Optional[CFView] = None
        self.message: Optional[discord.Message] = None

        self.main_menu_view()

    def main_menu_view(self):
        menu_container = CFMenuContainer()
        self.clear_items()
        self.add_item(menu_container)

    def lobby_view(self):
        waiting_container = CFWaitingContainer(self.author_id, timeout_minutes=3)
        self.clear_items()
        self.add_item(waiting_container)

    def lobby_expired_view(self, time_str):
        titleDisplay = ui.TextDisplay(f"## {self.CF_EMOJI} Connect Four")
        separator = ui.Separator()
        message = ui.TextDisplay(f"### No one joined <@{self.author_id}>'s game {Emojis.YELLOW_ANGRY}\nWaiting room ended {time_str}.\n-# Pro tip: Run `/connect_four` to try again!")
        lobby_expired_container = ui.Container(titleDisplay, separator, message, accent_color=discord.Color.red())
        self.clear_items()
        self.add_item(lobby_expired_container)

    def ai_config_view(self):
        config_container = CFAIConfigContainer()
        self.clear_items()
        self.add_item(config_container)

    async def start_matchmaking(self, interaction: discord.Interaction):
        self.gamemode = "Matchmaking"
        joined_at = time.time()
        ticket = C4MatchmakingTicket(
            user_id=self.author_id,
            guild_id=self.guild_id or 0,
            channel_id=self.channel_id or 0,
            view=self,
            message_id=interaction.message.id if interaction.message else None
        )

        match = C4MatchmakingManager().enqueue(ticket)

        if match:
            # Pair found!
            t1, t2 = match
            v1: CFView = t1.view
            v2: CFView = t2.view

            v1.linked_view = v2
            v2.linked_view = v1

            shared_game = CFGame()
            v1.game = shared_game
            v2.game = shared_game

            v1.assign_players(t1.user_id, t2.user_id)
            v2.red_player_id = v1.red_player_id
            v2.yellow_player_id = v1.yellow_player_id
            v2.current_player_id = v1.current_player_id
            v2.game_start_time = v1.game_start_time

            v1.game_view()
            v2.game_view()

            # Edit message 2 (current interaction)
            await interaction.response.edit_message(view=v2)

            # Edit message 1
            if v1.message:
                try:
                    await v1.message.edit(view=v1)
                except Exception as e:
                    logger.error(f"Failed to update matched view 1: {e}")
        else:
            # Waiting in queue
            self.clear_items()
            self.add_item(CFMatchmakingWaitingContainer(self.author_id, joined_at))
            await interaction.response.edit_message(view=self)

    async def leaderboard_view(self, interaction: discord.Interaction):
        boards = await self.bot.db_manager.get_c4_leaderboards(limit=5)
        user_stats = await self.bot.db_manager.get_user_c4_stats(interaction.user.id)
        container = CFLeaderboardContainer(self.bot, interaction.user, boards, user_stats)
        self.clear_items()
        self.add_item(container)
        await interaction.response.edit_message(view=self)

    def assign_players(self, player1_id, player2_id):
        self.game_start_time = time.time()
        self.telemetry_logged = False

        if randint(0, 1) == 0:
            self.red_player_id = player1_id
            self.yellow_player_id = player2_id
        else:
            self.red_player_id = player2_id
            self.yellow_player_id = player1_id

        self.current_player_id = self.red_player_id
        self.bot_turn = (self.current_player_id == self.bot_id)

    def change_turn(self):
        if self.current_player_id == self.red_player_id:
            self.current_player_id = self.yellow_player_id
        else:
            self.current_player_id = self.red_player_id

        self.bot_turn = (self.current_player_id == self.bot_id)

    def game_view(self, selected_column: int = 3, interaction: discord.Interaction = None):
        if self.game.status != self.game.ONGOING:
            self.end_game_view()
            return

        game_container = CFGameContainer(
            self.red_player_id,
            self.yellow_player_id,
            self.game,
            bot_turn=self.bot_turn,
            selected_column=selected_column
        )

        if self.bot_turn:
            self._bot_turn_task = asyncio.create_task(self.bot_turn_task(interaction))

        self.clear_items()
        self.add_item(game_container)

    def end_game_view(self, rematch_disabled: bool = False):
        if not self.telemetry_logged and self.game:
            self.telemetry_logged = True
            turns = sum(self.game.heights)
            duration = int(time.time() - self.game_start_time) if self.game_start_time else 0
            if self.game.status == self.game.RED_WIN:
                winner_id = self.red_player_id
            elif self.game.status == self.game.YELLOW_WIN:
                winner_id = self.yellow_player_id
            else:
                winner_id = None

            asyncio.create_task(
                self.bot.db_manager.record_c4_match(
                    guild_id=self.guild_id,
                    channel_id=self.channel_id,
                    player1_id=self.red_player_id,
                    player2_id=self.yellow_player_id,
                    winner_id=winner_id,
                    turns_count=turns,
                    duration_seconds=duration,
                    is_ai=(self.gamemode == "PvsAI")
                )
            )

        end_container = CFEndContainer(
            self.red_player_id,
            self.yellow_player_id,
            self.game,
            rematch_disabled=rematch_disabled
        )
        self.clear_items()
        self.add_item(end_container)

    async def sync_game_state(self, interaction: discord.Interaction = None):
        """Synchronizes game updates across local or dual-matchmaking views."""
        self.game_view(interaction=interaction)

        if interaction and not interaction.response.is_done():
            await interaction.response.edit_message(view=self)
        elif self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

        if self.linked_view:
            self.linked_view.game = self.game
            self.linked_view.current_player_id = self.current_player_id
            self.linked_view.game_view()
            if self.linked_view.message:
                try:
                    await self.linked_view.message.edit(view=self.linked_view)
                except Exception as e:
                    logger.error(f"Failed to sync linked view: {e}")

    async def handle_rematch_request(self, interaction: discord.Interaction):
        requester_id = interaction.user.id
        opponent_id = self.yellow_player_id if requester_id == self.red_player_id else self.red_player_id

        # 1. Against Bot: Instant Restart
        if self.gamemode == "PvsAI" or opponent_id == self.bot_id:
            self.game = CFGame()
            self.assign_players(self.author_id, self.bot_id)
            self.game_view(interaction=interaction)
            await interaction.response.edit_message(view=self)
            return

        # 2. Local Same-Channel PvP
        if not self.linked_view:
            self.clear_items()
            self.add_item(CFRematchPromptContainer(requester_id, opponent_id))
            await interaction.response.edit_message(view=self)
            return

        # 3. Dual-View Matchmaking PvP
        self.clear_items()
        self.add_item(CFRematchWaitingContainer(opponent_id))
        await interaction.response.edit_message(view=self)

        if self.linked_view:
            self.linked_view.clear_items()
            self.linked_view.add_item(CFRematchPromptContainer(requester_id, opponent_id))
            if self.linked_view.message:
                try:
                    await self.linked_view.message.edit(view=self.linked_view)
                except Exception:
                    pass

    async def accept_rematch(self, interaction: discord.Interaction):
        shared_game = CFGame()
        self.game = shared_game

        # Swap colors on rematch
        p1 = self.yellow_player_id
        p2 = self.red_player_id
        self.assign_players(p1, p2)

        self.game_view(interaction=interaction)
        await interaction.response.edit_message(view=self)

        if self.linked_view:
            self.linked_view.game = shared_game
            self.linked_view.red_player_id = self.red_player_id
            self.linked_view.yellow_player_id = self.yellow_player_id
            self.linked_view.current_player_id = self.current_player_id
            self.linked_view.game_view()
            if self.linked_view.message:
                try:
                    await self.linked_view.message.edit(view=self.linked_view)
                except Exception:
                    pass

    async def decline_rematch(self, interaction: discord.Interaction):
        self.end_game_view(rematch_disabled=True)
        await interaction.response.edit_message(view=self)

        if self.linked_view:
            self.linked_view.end_game_view(rematch_disabled=True)
            if self.linked_view.message:
                try:
                    await self.linked_view.message.edit(view=self.linked_view)
                except Exception:
                    pass

    async def wait_for_player_task(self, interaction):
        time_target = discord.utils.utcnow() + datetime.timedelta(minutes=3)
        await discord.utils.sleep_until(time_target)
        self.lobby_expired_view(discord.utils.format_dt(time_target, style='R'))
        await interaction.edit_original_response(view=self)
        self.stop()

    async def bot_turn_task(self, interaction):
        time_target = discord.utils.utcnow() + datetime.timedelta(seconds=1.2)
        await discord.utils.sleep_until(time_target)

        game = self.game
        loop = asyncio.get_running_loop()
        games_cog = self.bot.get_cog("Games")
        bot_move = await loop.run_in_executor(
            games_cog.process_executor,
            run_mcts,
            game,
            self.bot_difficulty
        )

        game.make_move(bot_move)
        logger.info(f"Bot made move {bot_move} with difficulty {self.bot_difficulty}")

        self.game = game
        self.change_turn()
        self.game_view(interaction=interaction)

        if self.game.status != self.game.ONGOING:
            self.end_game_view()
            self.stop()

        await interaction.edit_original_response(view=self)

    def _cancel_tasks(self):
        if self._wait_for_player_task and not self._wait_for_player_task.done():
            self._wait_for_player_task.cancel()
        if self._bot_turn_task and not self._bot_turn_task.done():
            self._bot_turn_task.cancel()

    def stop(self):
        self._cancel_tasks()
        C4MatchmakingManager().dequeue(self.author_id)
        super().stop()

    async def on_timeout(self):
        self._cancel_tasks()
        C4MatchmakingManager().dequeue(self.author_id)


class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.process_executor = ProcessPoolExecutor()

    async def cog_load(self):
        TableManager().ensure_system_tables(self.bot)

    def cog_unload(self):
        self.process_executor.shutdown(wait=False)

    @commands.hybrid_command(name="connect_four", aliases=["connect4", "c4", "con4", "connectfour"])
    @commands.guild_only()
    async def connect_four(self, ctx: commands.Context):
        """Starts a Connect Four game, joins matchmaking, or views leaderboards."""
        view = CFView(
            ctx.author.id,
            ctx.bot,
            guild_id=ctx.guild.id if ctx.guild else None,
            channel_id=ctx.channel.id,
            timeout=None
        )
        msg = await ctx.reply(view=view)
        view.message = msg
        if hasattr(self.bot, '_connection') and hasattr(self.bot._connection, '_view_store') and msg:
            self.bot._connection._view_store.add_view(view, msg.id)

    @commands.hybrid_command(name="wallet", aliases=["bal", "balance", "money", "coins", "cash"])
    @discord.app_commands.describe(user="The user whose wallet to view (defaults to yourself)")
    async def wallet(self, ctx: commands.Context, user: Optional[discord.User] = None):
        """Displays your or another member's coin balance, streak, and daily rewards."""
        await ctx.defer()
        target_user = user or ctx.author
        view = WalletView(self.bot, ctx.author, target_user)
        await view.render_wallet()
        await ctx.reply(view=view)

    @commands.hybrid_command(name="daily")
    async def daily(self, ctx: commands.Context):
        """Claims your daily 100 🪙 reward (+5 🪙 per consecutive day streak)."""
        await ctx.defer(ephemeral=True)
        success, res = await self.bot.db_manager.claim_daily(ctx.author.id)
        if success:
            reward = res["reward"]
            new_bal = res["new_balance"]
            streak = res["streak"]
            next_ts = res["next_claim_timestamp"]
            await ctx.reply(
                f"🎉 **Daily Reward Claimed!**\n"
                f"• Received: **+{reward:,.2f} 🪙** (Streak: 🔥 {streak} days)\n"
                f"• Wallet Balance: **{new_bal:,.2f} 🪙**\n"
                f"• Next claim available <t:{next_ts}:R>.",
                ephemeral=True
            )
        else:
            next_ts = res["next_claim_timestamp"]
            await ctx.reply(
                f"⏱️ You already claimed your daily reward today!\nNext reward available <t:{next_ts}:R> (in <t:{next_ts}:t>).",
                ephemeral=True
            )

    @commands.hybrid_command(name="blackjack", aliases=["bj", "casino"])
    @commands.guild_only()
    async def blackjack(self, ctx: commands.Context):
        """Opens the Blackjack Casino Lounge & Table Browser."""
        await ctx.defer()
        view = BlackjackLobbyView(self.bot, ctx.author, guild_id=ctx.guild.id if ctx.guild else None)
        await view.render_home(ctx.author, guild_id=ctx.guild.id if ctx.guild else None)
        await ctx.reply(view=view)


async def setup(bot):
    await bot.add_cog(Games(bot))
