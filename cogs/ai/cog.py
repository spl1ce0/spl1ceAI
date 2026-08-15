import os
import time
import asyncio
import logging
import datetime
import typing
import discord
from discord.ext import commands

from cogs.utils.exceptions import (
    AIError,
    AIRateLimitError,
    AIServiceUnavailableError,
    AISafetyBlockedError,
    AIConfigurationError,
    AIQuotaReachedError
)
from cogs.utils.constants import Emojis, ErrorMessages, SuccessMessages, InfoMessages
from .ai import ModelManager, ContextManager, ResponseHandler

logger = logging.getLogger(__name__)

# Errors and Emojis imported from cogs.utils.constants

class AI(commands.Cog):
    CHAT_HISTORY_LIMIT = 20

    def __init__(self, bot):
        self.bot = bot
        self.model_manager = ModelManager()
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "models.json")
        self.model_manager.load_config(config_path)
        
        self.response_orchestrator = ResponseHandler(bot)
        
        self.active_summons = {}
        self.DAILY_TOKEN_LIMIT = 1000000
        self.warning_counters = {}


    def _should_send_warning(self, channel_id: int, warning_type: str, interval: int = 10) -> bool:
        channel_data = self.warning_counters.setdefault(channel_id, {'quota': 0, 'busy': 0})
        count = channel_data[warning_type]
        
        channel_data[warning_type] += 1
        if count == 0 or (count % interval == 0):
            return True
        return False


    def _should_send_busy_warning(self, channel_id: int) -> bool:
        channel_data = self.warning_counters.setdefault(channel_id, {'quota': 0, 'busy': 0, 'chat_messages_since_busy_warning': 999})
        if channel_data.get('chat_messages_since_busy_warning', 999) >= 20:
            channel_data['chat_messages_since_busy_warning'] = 0
            return True
        return False


    async def cog_load(self):
        rows = await self.bot.db_manager.get_all_summons()
        for row in rows:
            self.active_summons[row[0]] = {'expiry': row[1], 'tokens': 0}
        logger.info(f"Loaded {len(self.active_summons)} active summons.")


    async def check_quota(self):
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        usage = await self.bot.db_manager.get_daily_usage(today)
        if usage:
            in_tok, out_tok, _ = usage
            total_tokens = in_tok + out_tok
            if total_tokens >= self.DAILY_TOKEN_LIMIT:
                return False
        return True


    async def update_usage(self, response, channel_id=None):
        if not hasattr(response, 'usage_metadata') or not response.usage_metadata:
            return
        
        in_tokens = response.usage_metadata.prompt_token_count or 0
        out_tokens = response.usage_metadata.candidates_token_count or 0
        total = in_tokens + out_tokens
        
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        await self.bot.db_manager.record_ai_usage(today, in_tokens, out_tokens)
            
        if channel_id and channel_id in self.active_summons:
            self.active_summons[channel_id]['tokens'] += total


    def parse_time(self, time_str):
        """Parses strings like '10m', '1h', '30s' into seconds."""
        import re
        match = re.match(r"(\d+)([smh])", time_str.lower())
        if not match:
            return None
        amount, unit = match.groups()
        amount = int(amount)
        if unit == 's': return amount
        if unit == 'm': return amount * 60
        if unit == 'h': return amount * 3600
        return None

    
    async def _get_chat_history(self, ctx: commands.Context, channel_id: int, message_count: int) -> list:
        message_list = []
        channel = await commands.TextChannelConverter().convert(ctx, str(channel_id))
        try:
            message_list = [message async for message in channel.history(limit=message_count)]
        except Exception as e:
            logger.error(f"Failed to get message history: {e}")
            return []
        
        return message_list


    @commands.hybrid_command(name="summarize", aliases=["tldr", "aint_readin_allat"])
    @commands.guild_only()
    async def summarize(self, ctx, limit: int):
        """Summarizes last N messages."""
        if not await self.check_quota():
            raise AIQuotaReachedError()
            
        await ctx.defer(ephemeral=True)

        message_list = await self._get_chat_history(ctx, ctx.channel.id, int(limit))
        if not message_list:
            await ctx.reply("No messages found to summarize.")
            return

        message_list.reverse()
        formatted_context = ContextManager.format_history(message_list)

        prompt = f"Summarize the following Discord conversation concisely. Use bullet points for key topics. Keep it brief and avoid unnecessary detail:\n\n{formatted_context}"

        start_time = time.perf_counter()
        async with ctx.typing():
            guild_settings = self.bot.settings_cache.get(ctx.guild.id, {})
            response = await self.model_manager.execute(guild_settings, [prompt])
        latency_ms = int((time.perf_counter() - start_time) * 1000)
            
        await self.update_usage(response)

        try:
            in_tokens = response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0
            out_tokens = response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0
            await self.bot.db_manager.log_ai_transaction(
                guild_id=ctx.guild.id if ctx.guild else None,
                channel_id=ctx.channel.id,
                user_id=ctx.author.id,
                model_name=response.model_name or "unknown",
                provider=getattr(response, "provider", "unknown") or "unknown",
                input_tokens=in_tokens or 0,
                output_tokens=out_tokens or 0,
                estimated_cost=0.0,
                latency_ms=latency_ms,
                context_messages_count=len(message_list),
                finish_reason="STOP",
                trigger_type="summarize",
                prompt_chars=len(prompt or ""),
                response_chars=len(response.text or ""),
                failover_occurred=getattr(response, "failover_occurred", False),
                failover_reason=getattr(response, "failover_reason", None)
            )
        except Exception as log_err:
            logger.error(f"Failed to log AI transaction telemetry: {log_err}")

        response.text = f"### 📝 Summary\n{response.text}"
        await self.response_orchestrator.orchestrate_reply(ctx, response)


    @commands.hybrid_command(name="ask", aliases=["llm", "ai"])
    @commands.guild_only()
    async def ask(self, ctx, question: str, image: typing.Optional[discord.Attachment] = None):
        """Asks the AI a question. Optionally attach an image."""
        if not await self.check_quota():
            raise AIQuotaReachedError()
            
        await ctx.defer()

        message_list = await self._get_chat_history(ctx, ctx.channel.id, self.CHAT_HISTORY_LIMIT)
        message_list.reverse()
        
        msg = ctx.message if hasattr(ctx, 'message') else None
        slash_attachments = [image] if image else None
        
        contents = await ContextManager.prepare_contents(
            msg,
            message_list,
            f"Reply to the user's question: {question}",
            slash_attachments=slash_attachments
        )

        logger.info(f"ask command trigger: contents contains {len(contents)} items")

        start_time = time.perf_counter()
        async with ctx.typing():
            guild_settings = self.bot.settings_cache.get(ctx.guild.id, {})
            response = await self.model_manager.execute(
                guild_settings,
                contents
            )
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        await self.update_usage(response)

        try:
            in_tokens = response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0
            out_tokens = response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0
            await self.bot.db_manager.log_ai_transaction(
                guild_id=ctx.guild.id if ctx.guild else None,
                channel_id=ctx.channel.id,
                user_id=ctx.author.id,
                model_name=response.model_name or "unknown",
                provider=getattr(response, "provider", "unknown") or "unknown",
                input_tokens=in_tokens or 0,
                output_tokens=out_tokens or 0,
                estimated_cost=0.0,
                latency_ms=latency_ms,
                context_messages_count=len(message_list),
                finish_reason="STOP",
                trigger_type="ask_vision" if image else "ask",
                prompt_chars=len(question or ""),
                response_chars=len(response.text or ""),
                failover_occurred=getattr(response, "failover_occurred", False),
                failover_reason=getattr(response, "failover_reason", None)
            )
        except Exception as log_err:
            logger.error(f"Failed to log AI transaction telemetry: {log_err}")

        await self.response_orchestrator.orchestrate_reply(ctx, response)


    @commands.hybrid_command(name="summon")
    @commands.guild_only()
    async def summon(self, ctx, duration: str = "10m"):
        """Summons the AI to listen and respond in this channel for a duration (e.g. 5m, 1h)."""
        if not await self.check_quota():
            raise AIQuotaReachedError()
            
        if ctx.channel.id in self.active_summons:
            await ctx.reply(ErrorMessages.already_listening(), ephemeral=True)
            return

        seconds = self.parse_time(duration)
        if not seconds:
            await ctx.reply(ErrorMessages.invalid_duration(), ephemeral=True)
            return
        
        expiry = datetime.datetime.now().timestamp() + seconds
        
        await self.bot.db_manager.save_summon(ctx.channel.id, expiry)
        
        self.active_summons[ctx.channel.id] = {'expiry': expiry, 'tokens': 0}
        time_str = discord.utils.format_dt(datetime.datetime.fromtimestamp(expiry), style='R')
        await ctx.reply(SuccessMessages.summon_success(time_str))


    async def _parse_message_triggers(self, message: discord.Message) -> tuple:
        channel_id = message.channel.id
        guild_id = message.guild.id if message.guild else None
        
        is_summoned = channel_id in self.active_summons
        is_chatbot_channel = bool(guild_id and self.bot.settings_cache.get(guild_id, {}).get("cbc") == channel_id)
        
        if not is_summoned and not is_chatbot_channel:
            return False, is_summoned, is_chatbot_channel

        is_mentioned = self.bot.user in message.mentions
        is_reply_to_bot = False
        if message.reference and message.reference.message_id:
            try:
                ref_msg = message.reference.resolved
                if not ref_msg or isinstance(ref_msg, discord.DeletedReferencedMessage):
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                if ref_msg and ref_msg.author.id == self.bot.user.id:
                    is_reply_to_bot = True
            except:
                pass

        if not is_mentioned and not is_reply_to_bot:
            return False, is_summoned, is_chatbot_channel

        return True, is_summoned, is_chatbot_channel

    async def _check_summon_expiration(self, message: discord.Message, channel_id: int) -> bool:
        now = datetime.datetime.now().timestamp()
        if now > self.active_summons[channel_id]['expiry']:
            tokens_used = self.active_summons[channel_id]['tokens']
            del self.active_summons[channel_id]
            await self.bot.db_manager.delete_summon(channel_id)
            
            try:
                await message.channel.send(InfoMessages.summon_ended(tokens_used))
            except:
                pass
            return True
        return False

    async def _validate_quota_with_warnings(self, message: discord.Message, channel_id: int) -> bool:
        channel_data = self.warning_counters.setdefault(channel_id, {'quota': 0, 'busy': 0, 'chat_messages_since_busy_warning': 999})
        if 'chat_messages_since_busy_warning' not in channel_data:
            channel_data['chat_messages_since_busy_warning'] = 0
        channel_data['chat_messages_since_busy_warning'] += 1

        quota_ok = await self.check_quota()
        if quota_ok:
            if channel_id in self.warning_counters:
                self.warning_counters[channel_id]['quota'] = 0
            return True

        if self._should_send_warning(channel_id, 'quota', interval=10):
            try:
                await message.reply(ErrorMessages.QUOTA_REACHED)
            except:
                pass
        else:
            try:
                await message.add_reaction(Emojis.AI_HAND_LIMIT)
            except:
                pass
        return False

    async def _generate_message_reply(self, message: discord.Message, guild_id: int, channel_id: int, trigger_type: str = "mention"):
        async with message.channel.typing():
            try:
                ctx = await self.bot.get_context(message)
                message_list = await self._get_chat_history(ctx, message.channel.id, self.CHAT_HISTORY_LIMIT)
                message_list = [msg for msg in message_list if msg.id != message.id]
                message_list.reverse()
                
                prompt = f"Reply to this message from {message.author.display_name}: {message.content}"
                contents = await ContextManager.prepare_contents(message, message_list, prompt)

                logger.info(f"on_message trigger: contents contains {len(contents)} items")

                start_time = time.perf_counter()
                guild_settings = self.bot.settings_cache.get(guild_id, {})
                response = await self.model_manager.execute(
                    guild_settings,
                    contents
                )
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                
                await self.update_usage(response, channel_id)

                try:
                    in_tokens = response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0
                    out_tokens = response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0
                    await self.bot.db_manager.log_ai_transaction(
                        guild_id=guild_id,
                        channel_id=channel_id,
                        user_id=message.author.id,
                        model_name=response.model_name or "unknown",
                        provider=getattr(response, "provider", "unknown") or "unknown",
                        input_tokens=in_tokens or 0,
                        output_tokens=out_tokens or 0,
                        estimated_cost=0.0,
                        latency_ms=latency_ms,
                        context_messages_count=len(message_list),
                        finish_reason="STOP",
                        trigger_type=trigger_type,
                        prompt_chars=len(message.content or ""),
                        response_chars=len(response.text or ""),
                        failover_occurred=getattr(response, "failover_occurred", False),
                        failover_reason=getattr(response, "failover_reason", None)
                    )
                except Exception as log_err:
                    logger.error(f"Failed to log AI transaction telemetry: {log_err}")

                if channel_id in self.warning_counters:
                    self.warning_counters[channel_id]['busy'] = 0
                    self.warning_counters[channel_id]['chat_messages_since_busy_warning'] = 999
                
                await self.response_orchestrator.orchestrate_reply(message, response)
                
            except (AIRateLimitError, AIServiceUnavailableError):
                if self._should_send_busy_warning(channel_id):
                    try:
                        await message.reply(ErrorMessages.BUSY_OR_LIMIT)
                    except:
                        pass
                else:
                    try:
                        await message.add_reaction(Emojis.AI_HIGH_DEMAND)
                    except:
                        pass
            except AISafetyBlockedError:
                try:
                    await message.reply(ErrorMessages.SAFETY_BLOCKED)
                except:
                    pass
            except Exception as e:
                logger.exception("Summon response failed")
                try:
                    import traceback
                    tb_string = "".join(traceback.format_exception(type(e), e, e.__traceback__))
                    await self.bot.db_manager.log_error(
                        guild_id=guild_id,
                        channel_id=channel_id,
                        user_id=message.author.id,
                        command_name="on_message",
                        error_type=e.__class__.__name__,
                        error_message=str(e),
                        traceback=tb_string
                    )
                except Exception as db_err:
                    logger.error(f"Failed to log on_message error telemetry: {db_err}")

                try:
                    await message.add_reaction(Emojis.WARNING)
                    await message.add_reaction(Emojis.ROBOT)
                except:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        channel_id = message.channel.id
        guild_id = message.guild.id if message.guild else None

        should_respond, is_summoned, is_chatbot_channel = await self._parse_message_triggers(message)
        if not should_respond:
            return

        if is_summoned and await self._check_summon_expiration(message, channel_id):
            return

        if not await self._validate_quota_with_warnings(message, channel_id):
            return

        # Determine trigger type
        if is_summoned:
            trigger_type = "summon"
        elif is_chatbot_channel:
            trigger_type = "cbc"
        elif message.reference and message.reference.message_id:
            trigger_type = "reply"
        else:
            trigger_type = "mention"

        await self._generate_message_reply(message, guild_id, channel_id, trigger_type=trigger_type)
