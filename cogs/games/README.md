# Games Subsystem (`cogs/games/`)

This package provides interactive multiplayer Discord games with responsive button-based user interfaces and integrated economy.

---

## 📁 Files & Structure

* **`cog.py` (`Games`)**: Discord Cog exposing `/connect4` (`/c4`), `/blackjack` (`/bj`), `/daily`, `/givemoney` (dev-only balance grant), game lobbies, matchmaking, turn timeouts, and rematch handling.
* **`connect4.py` (`CFGame`, `run_mcts`)**: Connect 4 game engine containing NumPy grid representation, win-condition matrix checks, Monte Carlo Tree Search (MCTS) with Upper Confidence Bound for Trees (UCT) for AI moves, and custom emoji grid rendering.
* **`blackjack.py` (`BlackjackTable`, `TableManager`, `Card`, `Shoe`, `Hand`)**: European Blackjack game engine with 6-deck shoe, soft/hard total evaluation, natural 21 (3:2 payout), split hands, double down, dealer AI rules, and bot-wide public/private room management.
* **`blackjack_views.py`**: Discord UI component containers for Casino Lobby browser, stackable chip betting interface (`+5€`, `+10€`, `+50€`, `+100€`), live multiplayer card tables, and payout evaluation.

---

## 🎮 Features & Games

### 1. Connect 4 (`/connect_four`, `/c4`)
* **PvP & PvAI Modes**: Play against friends or challenge the MCTS AI running in background worker processes.
* **Drop Column Buttons**: Interactive buttons (`1`–`7`) with real-time board rendering.
* **Telemetry**: Automatically records match winner, turns, duration, and participant IDs to `game_telemetry`.

### 2. Royal Casino Blackjack (`/blackjack`, `/daily`)
* **Live Multiplayer Tables**: Continuous room loop with betting countdown (10s), single table hosting limit per user, 7-seat casino standard capacity, simultaneous card dealing, and sequential player action turns (`Hit`, `Stand`, `Double Down`, `Split` with 20s timers).
* **Guaranteed Public Tiers & Auto-Scaling**: Bot automatically provisions 4 standard public table tiers (Bronze `5€`, Silver `10€`, Gold `20€`, Diamond `50€`), automatically spawning `#2`, `#3` overflow rooms when a tier reaches 7/7 seats, and pruning empty duplicates.
* **Public & Private Rooms**: Public tables discoverable in the server lobby browser; Private tables joinable via 4-character invite code (`Join by Code`).
* **Wallet & Chip Economy**: 1,000€ starting balance for all users, stackable chip wagers (`+5€`, `+10€`, `+50€`, `+100€`, `Custom`), table minimum bets, and `/daily` reward (100€ + 5€ per consecutive streak day).
* **Statistics & Telemetry Audit**: Tracks user balances, lifetime wagers/wins, leaderboards, and logs every individual resolved hand to `blackjack_hand_telemetry` (recording cards, scores, bets, payouts, splits, and doubles).
