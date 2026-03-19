
from discord.ext import commands
from discord import ui

from .connect4 import CFGame
from .connect4 import MCTSPlayer

import discord
import logging
import datetime
import asyncio
from random import randint

logger = logging.getLogger(__name__)


class CFMenuContainer(ui.Container):
    C4_LOGO = "<:sAI_C4L:1462459349137096775>"

    def __init__(self):
        super().__init__()

        self._make_container()


    def _make_container(self):
        """
        Builds the discord UI conatiner with the main menu.
        """

        ##############
        #  TITLE
        titleDisplay = ui.TextDisplay(f"## {self.C4_LOGO} Connect Four ")
        self.add_item(titleDisplay)
        ##############

        self.add_item(ui.Separator())

        ##############
        # SELECT MENU
        options = [
            discord.SelectOption(label="Play against someone else", value="PvsP"),
            discord.SelectOption(label="Play against AI", value = "PvsAI"),
        ]

        selectMenu = ui.Select(placeholder="Click to choose a gamemode", options=options, id=67)
        selectMenu.callback = self.gamemode_select_callback
        selectRow = ui.ActionRow()
        selectRow.add_item(selectMenu)
        self.add_item(selectRow)
        ##############

        ##############
        # BUTTONS
        play_button = ui.Button(label="Play", style=discord.ButtonStyle.green)
        play_button.callback = self.play_button_callback

        buttonRow = ui.ActionRow()
        buttonRow.add_item(play_button)
        self.add_item(buttonRow)
        ##############


    async def gamemode_select_callback(self, interaction: discord.Interaction):
        """
        Defines the gamemode select menu callback.
        """
        await interaction.response.defer()


    async def play_button_callback(self, interaction: discord.Interaction):
        """
        Defines the play button callback based on the selected option from the select menu.
        """
        select = self.find_item(67)
        if len(select.values) == 0:
            await interaction.response.send_message("You need to choose a gamemode first." ,ephemeral=True)
            return
        gamemode = select.values[0]
        view = self.view

        if gamemode == "PvsP":
            view.lobby_view()
            view.timeout = 300
            await interaction.response.edit_message(view=view)
            view._wait_for_player_task = asyncio.create_task(view.wait_for_player_task(interaction))

        elif gamemode == "PvsAI":
            view.ai_config_view()
            await interaction.response.edit_message(view=view)

        else:
            logger.error('Connect Four gamemode select menu: Unexpected selected value')

    
    async def cancel_button_callback(self, interaction: discord.Interaction):
        """
        Defines the cancel button callback.
        """

        view = self.view 
        view.stop()
        await interaction.delete_original_response()


    async def interaction_check(self, interaction: discord.Interaction):
        """
        Defines the interaction check of every component in the container.
        Checks if the interaction user is the command author.
        """
        if self.view.author_id != interaction.user.id:
            await interaction.response.send_message("You can't use that button.\n#- Tip: Run `/connect_four` to use it", ephemeral=True)
            return False
        return True




class CFWaitingContainer(ui.Container):

    C4_LOGO = "<:sAI_C4L:1462459349137096775>"

    def __init__(self, author_id, timeout_minutes = 3):
        super().__init__()

        self.author_id=author_id
        self.timeout_minutes = timeout_minutes
        self._make_container()


    def _make_container(self):
        """
        Builds the discord UI conatiner with the waiting lobby.
        """

        ###############
        #  TITLE
        title_display = ui.TextDisplay(f"## {self.C4_LOGO} Connect Four")
        self.add_item(title_display)
        ###############

        self.add_item(ui.Separator())

        ###############
        # JOIN SECTION
        join_display = ui.TextDisplay(f"<@{self.author_id}> is waiting for a player!")

        time = discord.utils.format_dt(datetime.datetime.now() + datetime.timedelta(minutes = self.timeout_minutes), style='R')
        time_display = ui.TextDisplay(f"-# Waiting room ends {time}.")
    
        join_button = ui.Button(label="Join the game", style=discord.ButtonStyle.green)
        join_button.callback = self.join_button_callback

        section = ui.Section(join_display, time_display, accessory=join_button)
        self.add_item(section)
        ################


    async def join_button_callback(self, interaction: discord.Interaction):
        """
        Defines the join button callback.
        """
        view = self.view
        view.assign_players(view.author_id, interaction.user.id)

        if view._wait_for_player_task is not None:
            view._wait_for_player_task.cancel()
        view.game = CFGame()

        view.game_view()

        await interaction.response.edit_message(view=view)


    async def interaction_check(self, interaction: discord.Interaction):
        """
        Interaction check for the components in the container.
        """
        return True



class CFAIConfigContainer(ui.Container):

    C4_LOGO = "<:sAI_C4L:1462459349137096775>"

    SELECT_ID = 67

    def __init__(self):
        super().__init__()

        self._make_container()


    def _make_container(self):

        #############
        #  TITLE
        titleString = f"## {self.C4_LOGO}  Connect 4"
        titleDisplay = ui.TextDisplay(titleString)
        self.add_item(titleDisplay)
        #############
        
        self.add_item(ui.Separator())

        #############
        #  DIFFICULTY SELECT
        options = [
            discord.SelectOption(label="Easy", value="11"),
            discord.SelectOption(label="Medium", value = "25"),
            discord.SelectOption(label="Hard", value = "500"),
            discord.SelectOption(label="Impossible", value = "2000")
        ]

        selectMenu = ui.Select(placeholder="Click to choose a difficulty", options=options, id=self.SELECT_ID)
        selectMenu.callback = self.difficulty_select_callback

        selectRow = ui.ActionRow()
        selectRow.add_item(selectMenu)
        
        self.add_item(selectRow)
        #############

        #self.add_item(ui.Separator())

        #############
        #  BUTTONS
        start_button = ui.Button(label="Start", style=discord.ButtonStyle.green)
        start_button.callback = self.start_button_callback

        back_button = ui.Button(label="Back")
        back_button.callback = self.back_button_callback
        
        buttonRow = ui.ActionRow()
        buttonRow.add_item(start_button)
        buttonRow.add_item(back_button)

        self.add_item(buttonRow)
        #############


    async def difficulty_select_callback(self, interaction: discord.Interaction):
        """
        Defines the difficulty select menu callback.
        """
        await interaction.response.defer()


    async def start_button_callback(self, interaction: discord.Interaction):

        select = self.find_item(self.SELECT_ID)
        if len(select.values) == 0:
            await interaction.response.send_message("You need to choose a difficulty first.", ephemeral=True)
            return
        
        view = self.view

        view.assign_players(view.author_id, view.bot_id)
        view.bot_difficulty = int(select.values[0])
        view.game = CFGame()
        view.mcts_player = MCTSPlayer()
        view.game_view(interaction=interaction)

        await interaction.response.edit_message(view=view)


    async def back_button_callback(self, interaction: discord.Interaction):
        view = self.view
        view.main_menu_view()

        await interaction.response.edit_message(view=view)


    async def interaction_check(self, interaction: discord.Interaction):
        """
        Defines the interaction check of every component in the container.
        Checks if the interaction user is the command author.
        """
        if self.view.author_id != interaction.user.id:
            await interaction.response.send_message("You can't use that button.\n-# Tip: Run `/connect_four` to use it", ephemeral=True)
            return False
        return True




class CFGameContainer(ui.Container):
    C4_LOGO = "<:sAI_C4L:1462459349137096775>"
    
    BOARD_EMPTY = "<:sAI_ME:1462171398192496917>"
    BOARD_RED = "<:sAI_MR:1462200144350019754>"
    BOARD_YELLOW = "<:sAI_MY:1462200170065297520>"
    BOARD_LEFT_EMPTY = "<:sAI_CLE:1462174611813695548>"
    BOARD_LEFT_RED = "<:sAI_CLR:1462199928511271063>"
    BOARD_LEFT_YELLOW = "<:sAI_CLY:1462199963004965027>"
    BOARD_RIGHT_EMPTY = "<:sAI_CRE:1462175903030312981>"
    BOARD_RIGHT_RED = "<:sAI_CRR:1462200012355408135>"
    BOARD_RIGHT_YELLOW = "<:sAI_CRY:1462200075945250957>"
    BOARD_BASE_LEFT = "<:sAI_LB:1462454097083891884>"
    BOARD_BASE_MIDDLE = "<:sAI_MB:1462453987369291867>"
    BOARD_BASE_RIGHT = "<:sAI_RB:1462454152960409801>"

    EMPTY = "<:empty:1454324278010056744>"
    RED_PIECE = "<:sAI_PR:1462200246129004835>"
    YELLOW_PIECE = "<:sAI_PY:1462200211186254009>"

    TO_MOVE_ARROW = "<a:sAI_rightarrow:1471523709981294709>"

    SELECT_ROW_ID = 32

    def __init__(self, player1_id, player2_id, game: CFGame, bot_turn: bool, selected_column: int = 0):
        super().__init__(id=123)

        self.red_id = player1_id
        self.yellow_id = player2_id
        self.game = game
        self.selected_column = selected_column
        self.bot_turn = bot_turn

        self.piece_emoji = self.YELLOW_PIECE
        if self.game.current_player == game.RED:
            self.piece_emoji = self.RED_PIECE

        self._make_container()
        

    def _make_container(self):
        """
        Builds the discord UI container that contains the game display.
        """

        #############
        #  TITLE
        titleString = f"## {self.C4_LOGO}  Connect 4"
        titleDisplay = ui.TextDisplay(titleString)
        self.add_item(titleDisplay)
        #############

        self.add_item(ui.Separator())

        #############
        # TURN THING
        turnString = f"**{"Yellow" if self.game.current_player == self.game.YELLOW else "Red"}'s turn!**"
        #############

        #############
        # SELECT ROW
        rows = []
        select_row = [self.EMPTY] * 7
        select_row[self.selected_column] = self.piece_emoji
        select_row = "".join(select_row)
        rows.append(self.EMPTY+select_row+self.EMPTY+turnString)
        #############


        #############
        # BOARD
        board_rows = self.game.render_board()
        rows.extend(board_rows)
        #############


        #############
        # PLAYERS DISPLAY
        # TODO make the move arrow indicator
        rows[3] = rows[3] + f"{self.EMPTY}{self.EMPTY if self.game.current_player == self.game.YELLOW else self.TO_MOVE_ARROW}{self.RED_PIECE} <@{self.red_id}>"
        rows[4] = rows[4] + f"{self.EMPTY}{self.EMPTY}<:sAI_VS:1471123115126947901>"
        rows[5] = rows[5] + f"{self.EMPTY}{self.EMPTY if self.game.current_player == self.game.RED else self.TO_MOVE_ARROW}{self.YELLOW_PIECE} <@{self.yellow_id}>"
        #############


        #############
        # BOARD DISPLAY
        boardString = f"\n{self.EMPTY}".join(rows)
        gameDisplay = ui.TextDisplay(boardString)
        self.add_item(gameDisplay)
        #############

        self.add_item(ui.Separator())

        #############
        # BUTTONS 
        
        playerActionRow = ui.ActionRow()
        
        left_button = ui.Button(label="◀")
        left_button.callback = self.move_left
        playerActionRow.add_item(left_button)

        confirm_button = ui.Button(emoji="✅", style=discord.ButtonStyle.green)
        confirm_button.callback = self.confirm_move
        playerActionRow.add_item(confirm_button)

        right_button = ui.Button(label="▶")
        right_button.callback = self.move_right
        playerActionRow.add_item(right_button)

        resign_button = ui.Button(emoji="🏳️", style=discord.ButtonStyle.red)
        resign_button.callback = self.resign
        playerActionRow.add_item(resign_button)

        botTextDisplay = ui.TextDisplay("## <a:sAI_loading:1476194991809237152>  Bot is thinking...")

        if (self.bot_turn):
            self.add_item(botTextDisplay)
        else:
            self.add_item(playerActionRow)
        #############

        self.accent_color = discord.Colour.yellow()

        if self.game.current_player == self.game.RED:
            self.accent_color = discord.Colour.red()

    
    async def move_left(self, interaction: discord.Interaction):
        """
        Defines the move left button callback.
        Moves the players cursor one square to the left.
        """

        view = self.view

        self.selected_column = max(0, self.selected_column-1)
        view.game_view(self.selected_column)

        await interaction.response.edit_message(view=view)


    async def confirm_move(self, interaction: discord.Interaction):
        """
        Defines the confirm move button callback.
        Makes the move selected by the player cursor.
        """

        view = self.view
        game = view.game
        move = self.selected_column
        
        if game.is_legal_move(move):
            game.make_move(move)

        view.game = game
        #view.game_view(self.selected_column)
        view.change_turn()
        view.game_view(interaction=interaction)

        await interaction.response.edit_message(view=view)


    async def move_right(self, interaction: discord.Interaction):
        """
        Defines the move right button callback.
        Moves the players cursor one square to the right.
        """
        view = self.view

        self.selected_column = min(self.selected_column+1, 6)
        view.game_view(self.selected_column)

        await interaction.response.edit_message(view=view)


    async def resign(self, interaction: discord.Interaction):
        
        view = self.view
        game = view.game
        
        game.resign()

        view.game = game
        view.end_game_view()
        view.stop()
        
        await interaction.response.edit_message(view=view)


    async def interaction_check(self, interaction: discord.Interaction):
        """
        Ensures strict turn-based access.
        
        1. Allows interaction if it is the user's turn.
        2. Denies (ephemeral) if it is the opponent's turn.
        3. Denies (ephemeral) if the user is a spectator.
        """
        if interaction.user.id == (self.red_id if self.game.current_player==self.game.RED else self.yellow_id):
            return True
        if interaction.user.id == self.red_id or interaction.user.id == self.yellow_id:
            await interaction.response.send_message("It's not your turn yet.", ephemeral=True)
            return False
        await interaction.response.send_message("You're not playing in this game.\n-# Pro tip: Run `/connect_four` to play.", ephemeral=True)
        return False




class CFEndContainer(ui.Container):
    C4_LOGO = "<:sAI_C4L:1462459349137096775>"
    EMPTY = "<:empty:1454324278010056744>"
    RED_PIECE = "<:sAI_PR:1462200246129004835>"
    YELLOW_PIECE = "<:sAI_PY:1462200211186254009>"

    def __init__(self, author_id, other_id, game: CFGame):
        super().__init__()
        self.author_id = author_id
        self.other_id = other_id
        self.game = game
        self._make_container()

    
    def _make_container(self):

        titleString = f"## {self.C4_LOGO}  Connect 4"
        titleDisplay = ui.TextDisplay(titleString)
        self.add_item(titleDisplay)

        self.add_item(ui.Separator())


        #############
        # WIN THING
        if self.game.status == self.game.DRAW:
            turnString = "**It's a draw!**"
        else:
            turnString = f"**{f"Yellow" if self.game.status == self.game.YELLOW_WIN else f"Red"} won!**"
        #############


        rows = []
        #############
        # WIN ROW
        select_row = [self.EMPTY] * 7
        select_row = "".join(select_row)
        rows.append(self.EMPTY+select_row+turnString)
        #############
        

        #############
        # BOARD
        board_rows = self.game.render_board()
        rows.extend(board_rows)
        #############

        #############
        # PLAYERS DISPLAY
        if (self.game.status == self.game.DRAW):
            rows[3] = rows[3] + f"{self.EMPTY}➖{self.RED_PIECE} <@{self.author_id}>"
            rows[4] = rows[4] + f"{self.EMPTY}{self.EMPTY}🤝"
            rows[5] = rows[5] + f"{self.EMPTY}➖{self.YELLOW_PIECE} <@{self.other_id}>"
        else:
            rows[3] = rows[3] + f"{self.EMPTY}{"👑" if self.game.status == self.game.RED_WIN else "❌"}{self.RED_PIECE} <@{self.author_id}>"
            #rows[4] = rows[4] + f"{self.EMPTY}{self.EMPTY}<:sAI_VS:1471123115126947901>"
            rows[5] = rows[5] + f"{self.EMPTY}{"👑" if self.game.status == self.game.YELLOW_WIN else "❌"}{self.YELLOW_PIECE} <@{self.other_id}>"
        #############

        #############
        # BOARD DISPLAY
        boardString = f"{self.EMPTY}" + f"\n{self.EMPTY}".join(rows)
        gameDisplay = ui.TextDisplay(boardString)
        self.add_item(gameDisplay)
        #############


        self.accent_color = discord.Colour.yellow()

        if self.game.status == self.game.RED_WIN:
            self.accent_color = discord.Colour.red()


    async def interaction_check(self, interaction: discord.Interaction):
        return True




class CFView(discord.ui.LayoutView):
    CF_EMOJI = "<:sAI_C4L:1462459349137096775>"
    

    def __init__(self, author_id, bot_id, *, timeout = None):
        super().__init__(timeout=timeout)
        
        self.game = None
        self.author_id = author_id
        self.red_player_id = None
        self.yellow_player_id = None
        self.bot_id = bot_id
        self.bot_difficulty = None
        self.gamemode = None
        self.current_player_id = None
        self.bot_turn = False
        self.mcts_player = None
        self._bot_turn_task = None
        self._wait_for_player_task = None

        self.main_menu_view()


    def main_menu_view(self):
        """
        Swaps the view to the main menu container.
        """
        menu_container = CFMenuContainer()
        self.clear_items()
        self.add_item(menu_container)


    def lobby_view(self):
        """
        Swaps the view to the waiting lobby container.
        """
        waiting_container = CFWaitingContainer(self.author_id, timeout_minutes=3)

        self.clear_items()
        self.add_item(waiting_container)


    def lobby_expired_view(self, time):
        """
        Swaps the view to the lobby expired container.
        """
        titleDisplay = ui.TextDisplay(f"## {self.CF_EMOJI} Connect Four")
        separator = ui.Separator()
        message = ui.TextDisplay(f"### No one joined <@{self.author_id}>'s game <:CC_yellow_angry:1441249440622182410>\nWaiting room ended {time}.\n-# Pro tip: do `/connect_four` to try again!")
        lobby_expired_container = ui.Container(titleDisplay, separator, message, accent_color=discord.Color.red())

        self.clear_items()
        self.add_item(lobby_expired_container)


    def ai_config_view(self):
        config_container = CFAIConfigContainer()

        self.clear_items()
        self.add_item(config_container)


    def assign_players(self, player1_id, player2_id):

        if randint(0, 1) == 0:
            self.red_player_id = player1_id
            self.yellow_player_id = player2_id
        else:
            self.red_player_id = player2_id
            self.yellow_player_id = player1_id

        self.current_player_id = self.red_player_id
        if self.current_player_id == self.bot_id:
            self.bot_turn = True


    def change_turn(self):
        if self.current_player_id == self.red_player_id:
            self.current_player_id = self.yellow_player_id
        else:
            self.current_player_id = self.red_player_id

        if self.current_player_id == self.bot_id:
            self.bot_turn = True
        else:
            self.bot_turn = False
    

    def game_view(self, selected_column: int = 3, interaction: discord.Interaction = None):
        """
        Swaps the view to the game display container.
        """
        
        if (self.game.status != self.game.ONGOING):
            self.end_game_view()
            return

        if (self.bot_turn):
            game_container = CFGameContainer(
                self.red_player_id,
                self.yellow_player_id,
                self.game,
                bot_turn = True,
                selected_column = selected_column
            )
            self._bot_turn_task = asyncio.create_task(self.bot_turn_task(interaction))

        else:
            game_container = CFGameContainer(
                self.red_player_id,
                self.yellow_player_id,
                self.game,
                bot_turn = False,
                selected_column = selected_column
            )

        self.clear_items()
        self.add_item(game_container)


    def end_game_view(self):
        """
        Swaps the view to the end game container.
        """

        end_container = CFEndContainer(
            self.red_player_id,
            self.yellow_player_id,
            self.game
        )

        self.clear_items()
        self.add_item(end_container)


    async def wait_for_player_task(self, interaction):
        """
        Background task: Waits for 3 minutes. If no one joins, updates the view to an expired lobby.
        """
        time = discord.utils.utcnow() + datetime.timedelta(minutes=3)
        await discord.utils.sleep_until(time)

        self.lobby_expired_view(discord.utils.format_dt(time, style='R'))
        await interaction.edit_original_response(view=self)
        self.stop()


    async def bot_turn_task(self, interaction):
        """
        Background task: Makes the bot play its turn after a short delay.
        """

        time = discord.utils.utcnow() + datetime.timedelta(minutes=0.05)
        await discord.utils.sleep_until(time)

        
        view = self
        game = view.game

        loop = asyncio.get_running_loop()
        bot_move = await loop.run_in_executor(
            None, 
            view.mcts_player.choose_move, 
            game, 
            view.bot_difficulty
        )

        game.make_move(bot_move)
                
        logger.info(f"Bot made move with difficulty {view.bot_difficulty}")
        
        view.game = game
        view.change_turn()
        view.game_view(interaction=interaction)


        if (view.game.status != view.game.ONGOING):
            view.end_game_view()
            view.stop()


        await interaction.edit_original_response(view=view)


    def _cancel_tasks(self):
        """Helper method to clean up background tasks to prevent memory leaks."""
        if self._wait_for_player_task and not self._wait_for_player_task.done():
            self._wait_for_player_task.cancel()
        if self._bot_turn_task and not self._bot_turn_task.done():
            self._bot_turn_task.cancel()

    
    def stop(self):
        """Override standard stop to ensure tasks are cancelled."""
        self._cancel_tasks()
        super().stop()


    async def on_timeout(self):
        """Ensure tasks are cancelled if the view times out naturally."""
        self._cancel_tasks()



class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.hybrid_command(name="connect_four", aliases=["connect4", "c4", "con4", "connectfour"])
    @commands.guild_only()
    async def connect_four(self, ctx):
        """
        Starts a Connect Four game.
        """

        view = CFView(ctx.author.id, ctx.bot.user.id, timeout=None)

        await ctx.reply(view=view)

async def setup(bot):
    await bot.add_cog(Games(bot))