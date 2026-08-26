import random
import string
import enum
import time
import asyncio
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

SUIT_SYMBOLS = {
    "Spades": "♠",
    "Hearts": "♥",
    "Diamonds": "♦",
    "Clubs": "♣"
}

CARD_RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]

# Official public tiers guaranteed by the system
SYSTEM_TIERS = [
    {"min_bet": 5.0, "name_prefix": "🥉 Bronze Table"},
    {"min_bet": 10.0, "name_prefix": "🥈 Silver Table"},
    {"min_bet": 20.0, "name_prefix": "🥇 Gold Table"},
    {"min_bet": 50.0, "name_prefix": "💎 Diamond Table"},
]


class TablePhase(enum.Enum):
    BETTING = "betting"
    PLAYER_TURNS = "player_turns"
    DEALER_TURN = "dealer_turn"
    PAYOUT = "payout"
    CLOSED = "closed"


class Card:
    """Represents a single playing card."""

    def __init__(self, rank: str, suit: str, face_up: bool = True):
        self.rank = rank
        self.suit = suit
        self.face_up = face_up

    @property
    def value(self) -> int:
        if self.rank in ("J", "Q", "K"):
            return 10
        if self.rank == "A":
            return 11
        return int(self.rank)

    @property
    def symbol(self) -> str:
        return SUIT_SYMBOLS.get(self.suit, self.suit)

    def to_display(self) -> str:
        if not self.face_up:
            return "`[ 🂠 ]`"
        return f"`[{self.rank}{self.symbol}]`"

    def __repr__(self) -> str:
        return f"{self.rank}{self.symbol}" if self.face_up else "[HIDDEN]"


class Shoe:
    """Represents a 6-deck shoe with shuffle penetration."""

    def __init__(self, num_decks: int = 6):
        self.num_decks = num_decks
        self.cards: List[Card] = []
        self.shuffle()

    def shuffle(self) -> None:
        self.cards.clear()
        for _ in range(self.num_decks):
            for suit in SUIT_SYMBOLS.keys():
                for rank in CARD_RANKS:
                    self.cards.append(Card(rank, suit))
        random.shuffle(self.cards)

    def draw(self, face_up: bool = True) -> Card:
        if len(self.cards) < 52:
            self.shuffle()
        card = self.cards.pop()
        card.face_up = face_up
        return card


class Hand:
    """Represents a player or dealer's hand of cards."""

    def __init__(self, bet: float = 0.0):
        self.cards: List[Card] = []
        self.bet = bet
        self.is_doubled = False
        self.is_split = False
        self.is_standing = False
        self.is_busted = False

    def add_card(self, card: Card) -> None:
        self.cards.append(card)
        val, _ = self.calculate_value()
        if val > 21:
            self.is_busted = True
            self.is_standing = True

    def calculate_value(self) -> Tuple[int, bool]:
        """Calculates total hand value and whether it is a soft hand (Ace as 11)."""
        visible_cards = [c for c in self.cards if c.face_up]
        total = sum(c.value for c in visible_cards)
        aces = sum(1 for c in visible_cards if c.rank == "A")

        is_soft = False
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1

        if any(c.rank == "A" for c in visible_cards) and total <= 21 and aces > 0:
            is_soft = True

        return total, is_soft

    @property
    def display_value(self) -> str:
        val, is_soft = self.calculate_value()
        # If any card is hidden, only show the visible total without spoiling Blackjack
        if any(not c.face_up for c in self.cards):
            if is_soft and val < 21:
                return f"**{val}** *(Soft)*"
            return f"**{val}**"

        if self.is_busted:
            return f"**{val}** *(Bust!)*"
        if self.is_blackjack:
            return "**21** *(Blackjack!)*"
        if is_soft and val < 21:
            return f"**{val}** *(Soft)*"
        return f"**{val}**"

    @property
    def is_blackjack(self) -> bool:
        if any(not c.face_up for c in self.cards):
            return False
        if len(self.cards) == 2 and not self.is_split:
            total = sum(c.value for c in self.cards)
            aces = sum(1 for c in self.cards if c.rank == "A")
            while total > 21 and aces > 0:
                total -= 10
                aces -= 1
            return total == 21
        return False

    @property
    def can_split(self) -> bool:
        return len(self.cards) == 2 and self.cards[0].value == self.cards[1].value and not self.is_split

    @property
    def can_double(self) -> bool:
        return len(self.cards) == 2 and not self.is_doubled

    def render_cards(self) -> str:
        return " ".join(c.to_display() for c in self.cards)


class BlackjackPlayer:
    """Represents a seated player at a Blackjack table."""

    def __init__(self, user_id: int, display_name: str):
        self.user_id = user_id
        self.display_name = display_name
        self.current_bet = 0.0
        self.hands: List[Hand] = []
        self.active_hand_idx = 0
        self.is_spectating = False
        self.missed_rounds = 0
        self.ephemeral_view = None
        self.turn_action_event = asyncio.Event()

    @property
    def active_hand(self) -> Optional[Hand]:
        if 0 <= self.active_hand_idx < len(self.hands):
            return self.hands[self.active_hand_idx]
        return None

    @property
    def all_hands_finished(self) -> bool:
        if not self.hands:
            return True
        return all(h.is_standing or h.is_busted for h in self.hands)

    def advance_to_next_hand(self) -> None:
        self.active_hand_idx += 1


class BlackjackTable:
    """Manages a single Blackjack table session with autonomous game loop."""

    def __init__(
        self,
        table_id: str,
        name: str,
        guild_id: Optional[int],
        channel_id: int,
        host_id: int,
        bot,
        is_private: bool = False,
        min_bet: float = 10.0,
        max_seats: int = 7,
        is_system: bool = False
    ):
        self.table_id = table_id
        self.name = name
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.host_id = host_id
        self.bot = bot
        self.is_private = is_private
        self.is_system = is_system
        self.invite_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4)) if is_private else None
        self.min_bet = min_bet
        self.max_seats = max_seats

        self.shoe = Shoe(num_decks=6)
        self.dealer_hand = Hand()
        self.players: Dict[int, BlackjackPlayer] = {}
        self.phase = TablePhase.BETTING
        self.current_turn_user_id: Optional[int] = None
        self.round_number = 1
        self.phase_end_timestamp: Optional[float] = None
        self.last_results: List[dict] = []

        self.public_view = None
        self.loop_task: Optional[asyncio.Task] = None
        self.is_running = True

    @property
    def seated_count(self) -> int:
        return len(self.players)

    @property
    def active_bettors(self) -> List[BlackjackPlayer]:
        return [p for p in self.players.values() if p.current_bet >= self.min_bet]

    def add_player(self, user_id: int, display_name: str) -> bool:
        if len(self.players) >= self.max_seats and user_id not in self.players:
            return False
        if user_id not in self.players:
            self.players[user_id] = BlackjackPlayer(user_id, display_name)
            # If a system table hits capacity, automatically provision overflow room
            if self.is_system and len(self.players) >= self.max_seats:
                TableManager().ensure_system_tables(self.bot, self.guild_id)
        return True

    def remove_player(self, user_id: int) -> bool:
        if user_id in self.players:
            player = self.players.pop(user_id)
            if player.ephemeral_view:
                try:
                    player.ephemeral_view.stop()
                except Exception:
                    pass

            if self.is_system:
                # If an overflow system room (not #1) becomes empty, prune it
                if self.seated_count == 0 and not self.name.endswith("#1"):
                    same_tier_tables = [
                        t for t in TableManager().tables.values()
                        if t.is_system and t.min_bet == self.min_bet and t.table_id != self.table_id and t.phase != TablePhase.CLOSED
                    ]
                    if any(t.seated_count < t.max_seats for t in same_tier_tables):
                        self.close()
                        TableManager().remove_table(self.table_id)
                        logger.info(f"Closed empty overflow system table {self.table_id} ({self.name})")
            else:
                # User-hosted table
                if user_id == self.host_id:
                    if self.players:
                        new_host = random.choice(list(self.players.values()))
                        self.host_id = new_host.user_id
                        logger.info(f"Host transferred to {new_host.display_name} ({new_host.user_id}) on table {self.table_id}")
                    else:
                        self.close()
                        TableManager().remove_table(self.table_id)
                        logger.info(f"Table {self.table_id} deleted because all players left.")
                elif not self.players:
                    self.close()
                    TableManager().remove_table(self.table_id)
                    logger.info(f"Table {self.table_id} deleted because all players left.")

            return True
        return False

    def add_bet(self, user_id: int, amount: float, max_balance: float) -> Tuple[bool, str, float]:
        if self.phase != TablePhase.BETTING:
            return False, "Bets can only be placed during the betting window.", 0.0

        player = self.players.get(user_id)
        if not player:
            return False, "You must take a seat at the table first.", 0.0

        new_bet = player.current_bet + amount
        if new_bet > max_balance:
            return False, f"Insufficient balance! You have €{max_balance:.2f}.", player.current_bet

        player.current_bet = round(new_bet, 2)
        return True, f"Bet updated to €{player.current_bet:.2f}.", player.current_bet

    def clear_bet(self, user_id: int) -> float:
        if user_id in self.players and self.phase == TablePhase.BETTING:
            self.players[user_id].current_bet = 0.0
        return 0.0

    async def broadcast_updates(self) -> None:
        """Refreshes the public message and all connected ephemeral player views."""
        # 1. Update public view
        if self.public_view:
            try:
                await self.public_view.refresh_message()
            except Exception as e:
                logger.debug(f"Error refreshing public table view: {e}")

        # 2. Update player ephemeral views
        for player in list(self.players.values()):
            if player.ephemeral_view:
                try:
                    await player.ephemeral_view.refresh_message()
                except Exception as e:
                    logger.debug(f"Error refreshing player view for {player.user_id}: {e}")

    def start_table_loop(self) -> None:
        """Spawns the continuous background state machine loop."""
        if self.loop_task is None or self.loop_task.done():
            self.loop_task = asyncio.create_task(self._table_state_machine())

    async def _table_state_machine(self) -> None:
        """Main game state machine loop."""
        try:
            while self.is_running and self.phase != TablePhase.CLOSED:
                # ---------------------------------------------
                # 1. BETTING PHASE (10-second countdown once first bet placed)
                # ---------------------------------------------
                self.phase = TablePhase.BETTING
                self.phase_end_timestamp = None
                await self.broadcast_updates()

                # Wait until at least 1 player has placed a valid bet
                while self.is_running and self.phase == TablePhase.BETTING:
                    if self.active_bettors:
                        break
                    await asyncio.sleep(0.5)

                if not self.is_running or self.phase != TablePhase.BETTING:
                    break

                # Start 10-second countdown
                self.phase_end_timestamp = time.time() + 10.0
                await self.broadcast_updates()

                # Count down 10 seconds, pausing/resetting if all bets are removed
                while self.is_running and self.phase == TablePhase.BETTING:
                    now = time.time()
                    if not self.active_bettors:
                        # All players cleared bets, reset timer and wait again
                        self.phase_end_timestamp = None
                        await self.broadcast_updates()
                        while self.is_running and self.phase == TablePhase.BETTING:
                            if self.active_bettors:
                                self.phase_end_timestamp = time.time() + 10.0
                                await self.broadcast_updates()
                                break
                            await asyncio.sleep(0.5)
                        now = time.time()

                    if self.phase_end_timestamp and now >= self.phase_end_timestamp:
                        break

                    await asyncio.sleep(0.5)

                if not self.is_running or self.phase == TablePhase.CLOSED:
                    break

                # Handle idle players & kick after 2 consecutive rounds without bet
                to_kick = []
                for p in list(self.players.values()):
                    if p.current_bet < self.min_bet:
                        p.missed_rounds += 1
                        if p.missed_rounds >= 2:
                            to_kick.append(p.user_id)
                    else:
                        p.missed_rounds = 0

                for uid in to_kick:
                    self.remove_player(uid)

                # Check if anyone bet
                bettors = self.active_bettors
                if not bettors:
                    await self.broadcast_updates()
                    continue

                # Deduct bets from players' bankrolls in DB
                for p in bettors:
                    await self.bot.db_manager.adjust_user_balance(p.user_id, -p.current_bet)

                # ---------------------------------------------
                # 2. INITIAL DEAL & PLAYER TURNS PHASE
                # ---------------------------------------------
                self.phase = TablePhase.PLAYER_TURNS
                self.dealer_hand = Hand()
                self.last_results.clear()

                # Setup player hands
                for p in self.players.values():
                    p.hands.clear()
                    p.active_hand_idx = 0
                    if p.current_bet >= self.min_bet:
                        p.hands.append(Hand(bet=p.current_bet))
                        p.is_spectating = False
                    else:
                        p.is_spectating = True

                # Deal 2 cards to each active bettor
                for _ in range(2):
                    for p in bettors:
                        p.hands[0].add_card(self.shoe.draw(face_up=True))

                # Deal 2 cards to dealer (1 face up, 1 face down)
                self.dealer_hand.add_card(self.shoe.draw(face_up=True))
                self.dealer_hand.add_card(self.shoe.draw(face_up=False))

                # Sequential player turns (20s turn timer per action)
                for p in bettors:
                    while p.active_hand and not (p.active_hand.is_standing or p.active_hand.is_busted or p.active_hand.is_blackjack):
                        self.current_turn_user_id = p.user_id
                        self.phase_end_timestamp = time.time() + 20.0
                        p.turn_action_event.clear()

                        await self.broadcast_updates()

                        # Wait for player action or 20s timeout
                        try:
                            await asyncio.wait_for(p.turn_action_event.wait(), timeout=20.0)
                        except asyncio.TimeoutError:
                            # Timeout: automatically stand
                            if p.active_hand:
                                p.active_hand.is_standing = True

                        # If active hand is finished, advance
                        if p.active_hand and (p.active_hand.is_standing or p.active_hand.is_busted or p.active_hand.is_blackjack):
                            p.advance_to_next_hand()

                    await self.broadcast_updates()

                self.current_turn_user_id = None

                # ---------------------------------------------
                # 3. DEALER TURN PHASE (2.0s per card draw)
                # ---------------------------------------------
                self.phase = TablePhase.DEALER_TURN
                # Reveal dealer hole card
                for c in self.dealer_hand.cards:
                    c.face_up = True

                await self.broadcast_updates()
                await asyncio.sleep(2.0)

                # Check if all player hands busted; if all busted, dealer does not need to draw
                all_busted = all(all(h.is_busted for h in p.hands) for p in bettors)

                if not all_busted:
                    d_val, _ = self.dealer_hand.calculate_value()
                    while d_val < 17:
                        new_card = self.shoe.draw(face_up=True)
                        self.dealer_hand.add_card(new_card)
                        await self.broadcast_updates()
                        await asyncio.sleep(2.0)
                        d_val, _ = self.dealer_hand.calculate_value()

                # Additional 2s pause to view final dealer hand before results
                await asyncio.sleep(2.0)

                # ---------------------------------------------
                # 4. PAYOUT PHASE (12 seconds celebration)
                # ---------------------------------------------
                self.phase = TablePhase.PAYOUT
                self.phase_end_timestamp = time.time() + 12.0
                self._evaluate_and_settle_payouts()

                await self.broadcast_updates()
                await asyncio.sleep(12.0)

                # Reset for next round
                self._reset_round_data()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in blackjack table loop {self.table_id}: {e}", exc_info=True)

    def _evaluate_and_settle_payouts(self) -> None:
        """Calculates hand outcomes and credits winnings in DB."""
        dealer_val, _ = self.dealer_hand.calculate_value()
        dealer_busted = self.dealer_hand.is_busted
        dealer_bj = self.dealer_hand.is_blackjack

        results = []
        for p in self.active_bettors:
            for hand_idx, hand in enumerate(p.hands):
                p_val, _ = hand.calculate_value()
                bet = hand.bet
                payout = 0.0
                outcome = "loss"

                if hand.is_busted:
                    outcome = "loss"
                    payout = 0.0
                elif hand.is_blackjack:
                    if dealer_bj:
                        outcome = "push"
                        payout = bet
                    else:
                        outcome = "blackjack"
                        payout = bet + (bet * 1.5)
                elif dealer_bj:
                    outcome = "loss"
                    payout = 0.0
                elif dealer_busted:
                    outcome = "win"
                    payout = bet * 2.0
                elif p_val > dealer_val:
                    outcome = "win"
                    payout = bet * 2.0
                elif p_val == dealer_val:
                    outcome = "push"
                    payout = bet
                else:
                    outcome = "loss"
                    payout = 0.0

                net_profit = payout - bet
                res_dict = {
                    "user_id": p.user_id,
                    "display_name": p.display_name,
                    "hand_idx": hand_idx,
                    "bet": bet,
                    "payout": payout,
                    "net_profit": net_profit,
                    "outcome": outcome,
                    "is_blackjack": hand.is_blackjack,
                    "player_val": p_val,
                    "display_score": hand.display_value,
                    "cards_display": hand.render_cards(),
                    "dealer_val": dealer_val
                }
                results.append(res_dict)

                # Schedule DB write
                asyncio.create_task(
                    self.bot.db_manager.record_blackjack_hand(
                        user_id=p.user_id,
                        bet_amount=bet,
                        payout_amount=payout,
                        result_type=outcome,
                        is_blackjack=hand.is_blackjack,
                        guild_id=self.guild_id,
                        table_id=self.table_id,
                        table_name=self.name,
                        player_cards=hand.render_cards(),
                        player_val=p_val,
                        dealer_cards=self.dealer_hand.render_cards(),
                        dealer_val=dealer_val,
                        is_doubled=hand.is_doubled,
                        is_split=(len(p.hands) > 1)
                    )
                )

        self.last_results = results

    def _reset_round_data(self) -> None:
        """Prepares table state for the next betting phase."""
        self.phase = TablePhase.BETTING
        self.dealer_hand = Hand()
        self.current_turn_user_id = None
        self.phase_end_timestamp = None
        self.round_number += 1

        for p in self.players.values():
            p.hands.clear()
            p.active_hand_idx = 0
            p.current_bet = 0.0
            p.is_spectating = False

    def player_hit(self, user_id: int) -> Tuple[bool, str]:
        if self.phase != TablePhase.PLAYER_TURNS or self.current_turn_user_id != user_id:
            return False, "It's not your turn!"

        player = self.players.get(user_id)
        if not player or not player.active_hand:
            return False, "No active hand found."

        card = self.shoe.draw(face_up=True)
        player.active_hand.add_card(card)

        # Notify turn event so table advances or re-prompts
        player.turn_action_event.set()
        return True, "Hit"

    def player_stand(self, user_id: int) -> Tuple[bool, str]:
        if self.phase != TablePhase.PLAYER_TURNS or self.current_turn_user_id != user_id:
            return False, "It's not your turn!"

        player = self.players.get(user_id)
        if not player or not player.active_hand:
            return False, "No active hand found."

        player.active_hand.is_standing = True
        player.turn_action_event.set()
        return True, "Stand"

    def player_double(self, user_id: int, user_balance: float) -> Tuple[bool, str]:
        if self.phase != TablePhase.PLAYER_TURNS or self.current_turn_user_id != user_id:
            return False, "It's not your turn!"

        player = self.players.get(user_id)
        if not player or not player.active_hand or not player.active_hand.can_double:
            return False, "Cannot double down on this hand."

        additional_bet = player.active_hand.bet
        if user_balance < additional_bet:
            return False, f"Insufficient funds to double! Need €{additional_bet:.2f}."

        player.active_hand.bet += additional_bet
        player.active_hand.is_doubled = True

        # Deduct doubled bet from wallet
        asyncio.create_task(self.bot.db_manager.adjust_user_balance(user_id, -additional_bet))

        card = self.shoe.draw(face_up=True)
        player.active_hand.add_card(card)
        player.active_hand.is_standing = True

        player.turn_action_event.set()
        return True, "Double Down"

    def player_split(self, user_id: int, user_balance: float) -> Tuple[bool, str]:
        if self.phase != TablePhase.PLAYER_TURNS or self.current_turn_user_id != user_id:
            return False, "It's not your turn!"

        player = self.players.get(user_id)
        if not player or not player.active_hand or not player.active_hand.can_split:
            return False, "Cannot split this hand."

        split_bet = player.active_hand.bet
        if user_balance < split_bet:
            return False, f"Insufficient funds to split! Need €{split_bet:.2f}."

        # Deduct split bet from wallet
        asyncio.create_task(self.bot.db_manager.adjust_user_balance(user_id, -split_bet))

        first_hand = player.active_hand
        second_card = first_hand.cards.pop()

        second_hand = Hand(bet=split_bet)
        second_hand.is_split = True
        first_hand.is_split = True

        second_hand.add_card(second_card)

        # Draw card for each split hand
        first_hand.add_card(self.shoe.draw(face_up=True))
        second_hand.add_card(self.shoe.draw(face_up=True))

        player.hands.insert(player.active_hand_idx + 1, second_hand)
        player.turn_action_event.set()
        return True, "Split"

    def close(self) -> None:
        """Closes table and stops background loop."""
        self.is_running = False
        self.phase = TablePhase.CLOSED
        if self.loop_task and not self.loop_task.done():
            self.loop_task.cancel()


class TableManager:
    """Singleton managing active Blackjack tables across servers."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TableManager, cls).__new__(cls)
            cls._instance.tables: Dict[str, BlackjackTable] = {}
            cls._instance._next_id = 1
        return cls._instance

    def create_table(
        self,
        name: str,
        guild_id: Optional[int],
        channel_id: int,
        host_id: int,
        bot,
        is_private: bool = False,
        min_bet: float = 10.0,
        max_seats: int = 7,
        is_system: bool = False
    ) -> BlackjackTable:
        table_id = f"table_{self._next_id}"
        self._next_id += 1

        table = BlackjackTable(
            table_id=table_id,
            name=name,
            guild_id=guild_id,
            channel_id=channel_id,
            host_id=host_id,
            bot=bot,
            is_private=is_private,
            min_bet=min_bet,
            max_seats=max_seats,
            is_system=is_system
        )
        self.tables[table_id] = table
        table.start_table_loop()
        return table

    def ensure_system_tables(self, bot, guild_id: Optional[int] = None) -> List[BlackjackTable]:
        """Ensures all 4 public tiers exist (5€, 10€, 20€, 50€) and auto-spawns overflow tables when full."""
        host_id = bot.user.id if bot and bot.user else 0

        for tier in SYSTEM_TIERS:
            min_bet = tier["min_bet"]
            prefix = tier["name_prefix"]

            tier_tables = [
                t for t in self.tables.values()
                if t.is_system and t.min_bet == min_bet and t.phase != TablePhase.CLOSED
            ]

            if not tier_tables:
                self.create_table(
                    name=f"{prefix} #1",
                    guild_id=None,
                    channel_id=0,
                    host_id=host_id,
                    bot=bot,
                    is_private=False,
                    min_bet=min_bet,
                    max_seats=7,
                    is_system=True
                )
            else:
                # If all rooms for this tier are full, provision the next overflow room
                if all(t.seated_count >= t.max_seats for t in tier_tables):
                    next_num = len(tier_tables) + 1
                    self.create_table(
                        name=f"{prefix} #{next_num}",
                        guild_id=None,
                        channel_id=0,
                        host_id=host_id,
                        bot=bot,
                        is_private=False,
                        min_bet=min_bet,
                        max_seats=7,
                        is_system=True
                    )

        return self.get_public_tables(guild_id)

    def get_table(self, table_id: str) -> Optional[BlackjackTable]:
        return self.tables.get(table_id)

    def get_table_by_code(self, code: str) -> Optional[BlackjackTable]:
        upper_code = code.strip().upper()
        for t in self.tables.values():
            if t.is_private and t.invite_code == upper_code:
                return t
        return None

    def get_public_tables(self, guild_id: Optional[int] = None, bot=None) -> List[BlackjackTable]:
        if bot:
            self.ensure_system_tables(bot, guild_id)
        return [
            t for t in self.tables.values()
            if not t.is_private and (guild_id is None or t.guild_id is None or t.guild_id == guild_id) and t.phase != TablePhase.CLOSED
        ]

    def get_player_table(self, user_id: int) -> Optional[BlackjackTable]:
        for t in self.tables.values():
            if user_id in t.players and t.phase != TablePhase.CLOSED:
                return t
        return None

    def get_table_by_host(self, host_id: int) -> Optional[BlackjackTable]:
        for t in self.tables.values():
            if t.host_id == host_id and not t.is_system and t.phase != TablePhase.CLOSED:
                return t
        return None

    def remove_table(self, table_id: str) -> None:
        if table_id in self.tables:
            table = self.tables.pop(table_id)
            table.close()
