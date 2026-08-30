import time
import asyncio
import logging
from typing import Optional, Tuple, List
import discord

logger = logging.getLogger(__name__)

class C4MatchmakingTicket:
    def __init__(self, user_id: int, guild_id: int, channel_id: int, view, message_id: Optional[int] = None):
        self.user_id = user_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.view = view
        self.message_id = message_id
        self.joined_at = time.time()

class C4MatchmakingManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(C4MatchmakingManager, cls).__new__(cls)
            cls._instance.queue: List[C4MatchmakingTicket] = []
        return cls._instance

    def enqueue(self, ticket: C4MatchmakingTicket) -> Optional[Tuple[C4MatchmakingTicket, C4MatchmakingTicket]]:
        """Adds a player to queue. If another player is waiting, pairs them immediately."""
        # Clean expired tickets older than 5 minutes or duplicate tickets
        now = time.time()
        self.queue = [t for t in self.queue if (now - t.joined_at < 300) and (t.user_id != ticket.user_id)]

        if self.queue:
            opponent_ticket = self.queue.pop(0)
            logger.info(f"Connect4 Matchmaking: Paired {ticket.user_id} with {opponent_ticket.user_id}")
            return opponent_ticket, ticket
        else:
            self.queue.append(ticket)
            logger.info(f"Connect4 Matchmaking: User {ticket.user_id} joined queue (Queue size: {len(self.queue)})")
            return None

    def dequeue(self, user_id: int) -> bool:
        """Removes a user from the matchmaking queue."""
        initial_len = len(self.queue)
        self.queue = [t for t in self.queue if t.user_id != user_id]
        return len(self.queue) < initial_len

    def is_queued(self, user_id: int) -> bool:
        """Checks if a user is currently waiting in the matchmaking queue."""
        return any(t.user_id == user_id for t in self.queue)

    def get_queue_size(self) -> int:
        return len(self.queue)
