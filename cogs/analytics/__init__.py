import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from bot import Spl1ceAI


async def setup(bot: 'Spl1ceAI') -> None:
    from .cog import Analytics
    await bot.add_cog(Analytics(bot))
