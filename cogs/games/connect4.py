"""
================================================================================
 Project:      Connect Four AI (MCTS Implementation)
 Author:       Lehmee
 Created:      2025
 Dependencies: numpy
--------------------------------------------------------------------------------
 Description:
 A Python implementation of the classic Connect Four game, featuring an 
 intelligent AI opponent powered by Monte Carlo Tree Search (MCTS) with 
 Upper Confidence Bound (UCT) logic.
================================================================================
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)

class CFGame:
    """
    Represents a Connect Four Game.
    """

    # Board constants
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

    # Some constants that I want to use to fill the board.
    RED = 1
    YELLOW = -1
    EMPTY = 0
    # Game status constants
    RED_WIN = 1
    YELLOW_WIN = -1
    DRAW = 0
    ONGOING = -17  # Completely arbitrary
    
    def __init__(self):
        self.board = [[self.EMPTY for _ in range(6)] for _ in range(7)] # The board is a matrix of -1, 0 and 1

        # Board representation:
        #
        # 5 | | | | | | | |
        # 4 | | | | | | | |
        # 3 | | | | | | | |
        # 2 | | | | | | | |
        # 1 | | | | | | | |
        # 0 | | | | | | | |
        #    0 1 2 3 4 5 6

        self.heights = [0 for _ in range(7)]                            # The column heights in the board.
        self.current_player = self.RED                                          # Red starts
        self.status = self.ONGOING                                      

    def legal_moves(self):
        return [i for i in range(7) if self.heights[i] < 6]
    
    def is_legal_move(self, move):
        return move in self.legal_moves()

    def make_move(self, move):  # Assumes that 'move' is a legal move
        """
        Makes a move on the board.
        Assumes the given move is legal.
        """
        self.board[move][self.heights[move]] = self.current_player
        self.heights[move] += 1
        # Check if the current move results in a winner:
        if self.winning_move(move):
            self.status = self.current_player
        elif len(self.legal_moves()) == 0:
            self.status = self.DRAW
        else:
            self.current_player = self.other_player(self.current_player)

    def other_player(self, player):
        """
        Changes turns.
        """
        return self.RED if player == self.YELLOW else self.YELLOW

    def undo_move(self, move):
        """
        Undoes a given move.
        """
        self.heights[move] -= 1
        self.board[move][self.heights[move]] = self.EMPTY
        self.current_player = self.other_player(self.current_player)
        self.status = self.ONGOING

    def clone(self):
        """
        Creates a clone of the game and returns it.
        """
        clone = CFGame()
        clone.board = [col[:] for col in self.board]  # Deep copy columns
        clone.heights = self.heights[:]  # Deep copy heights
        clone.current_player = self.current_player
        clone.status = self.status
        return clone

    def winning_move(self, move):
        """
        Checks if the move that was just made wins the game.
        Assumes that the player who made the move is still the current player.
        """
        col = move
        row = self.heights[col] - 1  # Row of the last placed piece
        player = self.board[col][row]  # Current player's piece

        # Check all four directions: horizontal, vertical, and two diagonals
        # Directions: (dx, dy) pairs for all 4 possible win directions
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dx, dy in directions:
            count = 0
            x, y = col + dx, row + dy
            while 0 <= x < 7 and 0 <= y < 6 and self.board[x][y] == player:
                count += 1
                x += dx
                y += dy
            x, y = col - dx, row - dy
            while 0 <= x < 7 and 0 <= y < 6 and self.board[x][y] == player:
                count += 1
                x -= dx
                y -= dy
            if count >= 3:
                return True
        return False

    def resign(self):
        """
        Current player resigns. The game ends, and the opponent wins.
        """
        if self.current_player == self.RED:
            self.status = self.YELLOW_WIN
        else:
            self.status = self.RED_WIN


    def render_board(self):
        boardMatrix = self.board
        rows = []

        width = len(boardMatrix)       
        height = len(boardMatrix[0])
        for r in range(height - 1, -1, -1):
            row = []
            for c in range(width):
                is_red = (boardMatrix[c][r] == self.RED)
                is_yellow = (boardMatrix[c][r] == self.YELLOW)
                is_top_row = (r == height - 1)

                if is_top_row and c == 0:
                    if is_red:
                        row.append(self.BOARD_LEFT_RED)
                    elif is_yellow:
                        row.append(self.BOARD_LEFT_YELLOW)
                    else:
                        row.append(self.BOARD_LEFT_EMPTY)

                elif is_top_row and c == width - 1:
                    if is_red:
                        row.append(self.BOARD_RIGHT_RED)
                    elif is_yellow:
                        row.append(self.BOARD_RIGHT_YELLOW)
                    else:
                        row.append(self.BOARD_RIGHT_EMPTY)

                else:
                    if is_red:
                        row.append(self.BOARD_RED)
                    elif is_yellow:
                        row.append(self.BOARD_YELLOW)
                    else:
                        row.append(self.BOARD_EMPTY)

            rows.append("".join(row))

        base_row = []
        base_row.append(self.BOARD_BASE_LEFT)
        for _ in range(width - 2): 
            base_row.append(self.BOARD_BASE_MIDDLE)
        base_row.append(self.BOARD_BASE_RIGHT)

        rows.append("".join(base_row))
        return rows


class MCTSNode:
    def __init__(self, parent=None):
        self.parent = parent
        self.children = {}
        self.untriedMoves = set()
        self.Q = 0.0
        self.N = 1

    def leaf(self, board):
        return len(self.children) != len(board.legal_moves())

class MCTSPlayer:

    def __init__(self):
        self.root = None

    C = 0.7  # Exploration parameter for MCTS

    # MCTS methods (selection, expansion, simulation, backpropagation)

    def UCT(self, node, parent_log_N, board):
        return board.current_player * node.Q + self.C * np.sqrt(parent_log_N / (node.N))

    def choose_move(self, board, iterations, is_self_play=False):
        self.root = MCTSNode()  # Reset the root for each move decision
        self.root.untriedMoves = {pos for pos in board.legal_moves()}
        for _ in range(iterations):  # Number of MCTS iterations

            work_board = board.clone()

            # 1. Selection
            leaf = self.selection(work_board)
            
            # 2. Expansion & 3. Simulation
            if work_board.status == CFGame.ONGOING:
                leaf = self.expansion(leaf, work_board)
                outcome = self.simulation(work_board)
            else:
                # If selection led to a terminal state, that is the outcome
                outcome = work_board.status
            
            # 4. Backpropagation
            self.backpropagation(leaf, outcome)

        # Choose the move with the highest visit count
        best_move = None
        max_visits = -1
        for child, move in self.root.children.items():
            if child.N > max_visits:
                max_visits = child.N
                best_move = move
        return best_move


    def selection(self, board):
        cur = self.root
        while not cur.leaf(board):
            maxUCT = -float('inf')
            best_child = None
            cur_move = None
            
            # Pre-calculate log factor once for all children of this node
            log_N_parent = np.log(cur.N) 
            
            for child, move in cur.children.items():
                # Standard UCT but using the pre-calculated log
                uct_value = self.UCT(child, log_N_parent, board)
                
                if uct_value > maxUCT:
                    maxUCT = uct_value
                    best_child = child
                    cur_move = move
                    
            board.make_move(cur_move)
            if board.status != CFGame.ONGOING:
                return best_child
            cur = best_child
        return cur
    
    def expansion(self, node, board):
        move = node.untriedMoves.pop()
        board.make_move(move)
        child_node = MCTSNode(parent=node)
        node.children[child_node] = move
        child_node.untriedMoves = {pos for pos in board.legal_moves()}
        return child_node

    
    def simulation(self, board):
        simulation_board = board.clone()

        while simulation_board.status == simulation_board.ONGOING:
            possible_moves = simulation_board.legal_moves()
            for move in possible_moves:
                simulation_board.make_move(move)
                if simulation_board.status != simulation_board.ONGOING:
                    return simulation_board.status
                simulation_board.undo_move(move)
            move = np.random.choice(possible_moves)
            simulation_board.make_move(move)
        return simulation_board.status
        
    
    def backpropagation(self, node, outcome):
        cur = node
        while cur is not None:
            cur.N += 1
            cur.Q += (outcome - cur.Q) / cur.N
            cur = cur.parent
