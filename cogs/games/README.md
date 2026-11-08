# Games Subsystem (`cogs/games/`)

This package provides interactive multiplayer Discord games with responsive button-based user interfaces and integrated economy.

---

## 📁 Files & Structure

* **`cog.py` (`Games`)**: Slash names `wallet`, `daily`, `connect_four`, `blackjack`. Prefix aliases: `wallet` → `bal`, `balance`, `money`, `coins`, `cash`; `connect_four` → `connect4`, `c4`, `con4`, `connectfour`; `blackjack` → `bj`, `casino`. Also the lobby, matchmaking, and rematch views.
* **`wallet_views.py` (`WalletContainer`, `LeaderboardContainer`, `WalletView`)**: Wallet card, streak, and daily claim. The leaderboard button calls `DatabaseManager.get_wealth_leaderboard`, which is not defined.
* **`c4_matchmaking.py` (`C4MatchmakingManager`, `C4MatchmakingTicket`)**: Process-local singleton list. Pairing is immediate when someone else is queued. Entries older than 5 minutes are dropped. There is no lock; it assumes the bot's asyncio loop.
* **`connect4.py` (`CFGame`, `MCTSPlayer`, `run_mcts`)**: Board is a Python list of columns, not an `ndarray`. NumPy is used for UCT (`np.sqrt`, `np.log`) and random playouts. Win checks walk the list grid. The emoji board is rendered in `cog.py`.
* **`blackjack.py` (`BlackjackTable`, `TableManager`, `Card`, `Shoe`, `Hand`)**: 6-deck shoe, soft/hard totals, split, double down, public and private tables. The dealer is dealt one face-up card and one face-down card, then hits while the total is under 17 (stands on 17, including soft 17). Natural blackjack pays `bet + bet * 1.5` when the dealer does not also have blackjack. A normal win pays `bet * 2` (1:1 profit). A push returns the stake.
* **`blackjack_views.py`**: Lobby browser, wallet and wealth-leaderboard screens, chip pad, table view, and payout text. The wealth screen uses the same missing `get_wealth_leaderboard` method.

---

## 🎮 Features & Games

### 1. Connect 4 (`connect_four`, prefix alias `c4`)
* **Gamemodes**:
  * **🎮 Local Friend Lobby (PvsP)**: Play against a friend in the same channel.
  * **🌐 Global Matchmaking**: Queue up and get paired with any player across all servers.
  * **MCTS AI (PvsAI)**: select values are iteration counts passed to `run_mcts`: Easy `11`, Medium `25`, Hard `500`, Impossible `2000`. The Impossible option's description text says "Grandmaster".
  * **Leaderboard view**: the UI calls `get_c4_leaderboards` and `get_user_c4_stats`. Neither method exists on `DatabaseManager`, and there is no `c4_stats` table.
* **🔁 Interactive Rematch System**:
  * **Against Bot**: Instant 1-click rematch restart.
  * **PvP (Same View)**: Prompts opponent with `✅ Accept` / `❌ Decline`.
  * **Matchmaking (Dual-View)**: Real-time cross-channel rematch synchronization.
* **End of match**: `CFView.end_game_view` schedules `record_c4_match(...)`. That method is not implemented, so winner, turns, and duration are not written. `log_game_result` can insert into `game_telemetry`, but Connect 4 does not call it.

### 2. Blackjack (`/blackjack`) and `/daily`

* **Tables**: Loop waits until someone bets, then runs a 10-second countdown (cleared bets restart the wait). One hosted table per user. 7 seats. Turns are sequential (`Hit`, `Stand`, `Double Down`, `Split`) with a 20-second timer that stands on timeout. Dealing is two cards each, dealer hole card face down.
* **Public tiers**: `TableManager` keeps Bronze 5, Silver 10, Gold 20, and Diamond 50 minimums, adds another room when every table of that tier is full, and closes an empty overflow room whose name does not end in `#1`.
* **Private rooms**: 4-character code from uppercase letters and digits (`Join by Code`).
* **Wallet**: `user_economy.balance` defaults to `1000.0`. Chip row is three amounts scaled from the table minimum, plus `Custom` and `All In` (five buttons, Discord's row limit).
* **`/daily`**: `claim_daily` pays `100 + 5 * (streak - 1)` euros. Cooldown is 24 hours. The streak increments when the last claim was within 48 hours; otherwise it resets to 1. The first claim is 100, the second inside the window is 105.
* **Hands**: `record_blackjack_hand` updates `user_economy`, `blackjack_stats`, and `blackjack_hand_telemetry` (cards, scores, bet, payout, split, double). The wealth leaderboard button is wired to a method that is not implemented.
