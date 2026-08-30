# Games Subsystem (`cogs/games/`)

This package provides interactive multiplayer Discord games with responsive button-based user interfaces and integrated economy.

---

## 📁 Files & Structure

* **`cog.py` (`Games`)**: Discord Cog exposing `/wallet`, `/daily`, `/connect_four` (`/c4`), `/blackjack` (`/bj`), game lobbies, matchmaking, turn timeouts, and rematch handling.
* **`wallet_views.py` (`WalletContainer`, `LeaderboardContainer`, `WalletView`)**: Interactive wallet cards, streak trackers, 1-click daily reward claimers, and global wealth leaderboard.
* **`c4_matchmaking.py` (`C4MatchmakingManager`, `C4MatchmakingTicket`)**: Thread-safe global matchmaking queue manager pairing players across servers.
* **`connect4.py` (`CFGame`, `run_mcts`)**: Connect 4 game engine containing NumPy grid representation, win-condition matrix checks, Monte Carlo Tree Search (MCTS) with Upper Confidence Bound for Trees (UCT) for AI moves, and custom emoji grid rendering.
* **`blackjack.py` (`BlackjackTable`, `TableManager`, `Card`, `Shoe`, `Hand`)**: European Blackjack game engine with 6-deck shoe, soft/hard total evaluation, natural 21 (3:2 payout), split hands, double down, dealer AI rules, and bot-wide public/private room management.
* **`blackjack_views.py`**: Discord UI component containers for Casino Lobby browser, embedded Wallet and Wealth Leaderboard screens, stackable chip betting interface, live multiplayer card tables, and payout evaluation.

---

## 🎮 Features & Games

### 1. Connect 4 (`/connect_four`, `/c4`)
* **Gamemodes**:
  * **🎮 Local Friend Lobby (PvsP)**: Play against a friend in the same channel.
  * **🌐 Global Matchmaking**: Queue up and get paired with any player across all servers.
  * **🤖 MCTS AI (PvsAI)**: 4 difficulty levels (`Easy`, `Medium`, `Hard`, `Grandmaster / 2000 simulations`).
  * **🏆 Global Leaderboards**: Live rankings of top players by total wins, win streaks, and personal player cards.
* **🔁 Interactive Rematch System**:
  * **Against Bot**: Instant 1-click rematch restart.
  * **PvP (Same View)**: Prompts opponent with `✅ Accept` / `❌ Decline`.
  * **Matchmaking (Dual-View)**: Real-time cross-channel rematch synchronization.
* **Telemetry & Stats**: Automatically records match winner, turns, duration, win streaks, and personal stats to `c4_stats` and `game_telemetry`.

### 2. Royal Casino Blackjack (`/blackjack`, `/daily`)
* **Live Multiplayer Tables**: Continuous room loop with betting countdown (10s), single table hosting limit per user, 7-seat casino standard capacity, simultaneous card dealing, and sequential player action turns (`Hit`, `Stand`, `Double Down`, `Split` with 20s timers).
* **Guaranteed Public Tiers & Auto-Scaling**: Bot automatically provisions 4 distinct public table tiers with visual badges (🥉 Bronze `5€`, 🥈 Silver `10€`, 🥇 Gold `20€`, 💎 Diamond `50€`), automatically spawning `#2`, `#3` overflow rooms when a tier reaches 7/7 seats, and pruning empty duplicates.
* **Public & Private Rooms**: Public tables discoverable in the server lobby browser; Private tables joinable via 4-character invite code (`Join by Code`).
* **Wallet & Dynamic Chip Economy**: 1,000€ starting balance for all users, 5-button dynamic betting pad (3 tier-scaled chips + `Custom` + `All In`), table minimum bets, and `/daily` reward (100€ + 5€ per consecutive streak day).
* **Statistics & Telemetry Audit**: Tracks user balances, lifetime wagers/wins, leaderboards, and logs every individual resolved hand to `blackjack_hand_telemetry` (recording cards, scores, bets, payouts, splits, and doubles).
