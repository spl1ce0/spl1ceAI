# Games Subsystem (`cogs/games/`)

This package provides interactive multiplayer Discord games with responsive button-based user interfaces.

---

## 📁 Files & Structure

* **`cog.py` (`Games`)**: Discord Cog exposing `/connect4` (`/c4`), game lobbies, gamemode selection (PvP vs PvE), matchmaking, turn timeouts, and rematch handling.
* **`connect4.py` (`CFGame`, `run_mcts`)**: Connect 4 game engine containing NumPy grid representation, win-condition matrix checks, Monte Carlo Tree Search (MCTS) with Upper Confidence Bound for Trees (UCT) for AI moves, and custom emoji grid rendering.

---

## 🎮 Features & Mechanics

* **Gamemodes**:
  * **PvP (Player vs Player)**: Play against another server member in the channel.
  * **PvAI (Player vs AI)**: Challenge the bot AI running Monte Carlo Tree Search (MCTS) in a background `ProcessPoolExecutor`.
* **Interactive UI**: ActionRow button views with drop columns (`1` through `7`) and custom emojis representing pieces and the board frame.
* **Turn & Timeout Management**: Automatic turn timer tracking, forfeit on timeout, and rematch buttons.
