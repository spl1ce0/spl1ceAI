from typing import TYPE_CHECKING
import logging

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from bot import Spl1ceAI 

async def setup(bot: 'Spl1ceAI') -> None:

    from .cog import Games

    await bot.add_cog(Games(bot))