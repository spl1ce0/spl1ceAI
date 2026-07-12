import os
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
    AIConfigurationError
)
from cogs.utils.constants import Emojis, ErrorMessages, SuccessMessages, InfoMessages
from .ai import ModelManager, ContextManager, ResponseHandler

logger = logging.getLogger(__name__)

# Errors and Emojis imported from cogs.utils.constants

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.model_manager = ModelManager()
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "models.json")
        self.model_manager.load_config(config_path)
        
        self.response_orchestrator = ResponseHandler()
        
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

    async def _execute_failover_pipeline(self, guild_id: int, contents: list):
        guild_settings = self.bot.settings_cache.get(guild_id, {})
        raw_stack = [
            guild_settings.get("llm_primary", "gemini-flash-lite-latest"),
            guild_settings.get("llm_backup1", "gpt-5.4-mini"),
            guild_settings.get("llm_backup2", "claude-haiku-4-5-20251001")
        ]
        
        legacy_map = {
            "gemini": "gemini-flash-lite-latest",
            "openai": "gpt-5.4-mini",
            "anthropic": "claude-haiku-4-5-20251001",
            "grok": "grok-4.3"
        }
        
        execution_stack = []
        for provider in raw_stack:
            if provider and provider != "disabled":
                mapped = legacy_map.get(provider, provider)
                execution_stack.append(mapped)
                
        if not execution_stack:
            execution_stack = ["gemini-flash-lite-latest"]
            
        llm_timeout = float(guild_settings.get("llm_timeout", 15))
        
        return await self.model_manager.execute_pipeline(
            model_names=execution_stack,
            contents=contents,
            timeout=llm_timeout
        )

    @commands.hybrid_command(name="summarize", aliases=["tldr", "aint_readin_allat"])
    @commands.guild_only()
    async def summarize(self, ctx, limit: int):
        """Summarizes last N messages."""
        if not await self.check_quota():
            await ctx.reply(ErrorMessages.QUOTA_REACHED, ephemeral=True)
            return
            
        await ctx.defer(ephemeral=True)

        message_list = await self._get_chat_history(ctx, ctx.channel.id, int(limit))
        if not message_list:
            await ctx.reply("No messages found to summarize.")
            return

        message_list.reverse()
        formatted_context = ContextManager.format_history(message_list)

        try:
            prompt = f"Summarize the following Discord conversation concisely. Use bullet points for key topics. Keep it brief and avoid unnecessary detail:\n\n{formatted_context}"

            async with ctx.typing():
                response = await self._execute_failover_pipeline(ctx.guild.id, [prompt])
            await self.update_usage(response)
            response.text = f"### 📝 Summary\n{response.text}"
            await self.response_orchestrator.orchestrate_reply(ctx, response)

        except (AIRateLimitError, AIServiceUnavailableError):
            await ctx.reply(ErrorMessages.BUSY_OR_LIMIT, ephemeral=True)
        except AISafetyBlockedError:
            await ctx.reply(ErrorMessages.SAFETY_BLOCKED, ephemeral=True)
        except Exception as e:
            logger.error(f"Summarize failed: {e}")
            if ctx.interaction:
                try:
                    await ctx.interaction.followup.send(ErrorMessages.UNEXPECTED, ephemeral=True)
                except:
                    pass
            else:
                try:
                    await ctx.message.add_reaction(Emojis.ERROR)
                except:
                    pass

    @commands.hybrid_command(name="ask", aliases=["llm", "ai"])
    @commands.guild_only()
    async def ask(self, ctx, question: str, image: typing.Optional[discord.Attachment] = None):
        """Asks the AI a question. Optionally attach an image."""
        if not await self.check_quota():
            await ctx.reply(ErrorMessages.QUOTA_REACHED, ephemeral=True)
            return
            
        await ctx.defer()

        message_list = await self._get_chat_history(ctx, ctx.channel.id, 20)
        message_list.reverse()
        
        contents = []
        if image:
            if image.content_type and image.content_type.startswith("image/"):
                try:
                    img_bytes = await image.read()
                    contents.append({"data": img_bytes, "mime_type": image.content_type})
                except Exception as e:
                    await ctx.reply(ErrorMessages.image_process_failed(str(e)), ephemeral=True)
                    return
            else:
                await ctx.reply(ErrorMessages.attachment_not_image(), ephemeral=True)
                return

        msg = ctx.message if hasattr(ctx, 'message') else None
        if msg:
            reply_contents = await ContextManager.prepare_contents(msg, message_list, f"Reply to the user's question: {question}")
            contents = contents + reply_contents
        else:
            formatted_history = ContextManager.format_history(message_list)
            contents.append(f"Recent Chat:\n{formatted_history}\n\nReply to the user's question: {question}")

        logger.info(f"ask command trigger: contents contains {len(contents)} items")

        try:
            async with ctx.typing():
                response = await self._execute_failover_pipeline(
                    ctx.guild.id,
                    contents
                )
            await self.update_usage(response)

            await self.response_orchestrator.orchestrate_reply(ctx, response)

        except (AIRateLimitError, AIServiceUnavailableError):
            await ctx.reply(ErrorMessages.BUSY_OR_LIMIT, ephemeral=True)
        except AISafetyBlockedError:
            await ctx.reply(ErrorMessages.SAFETY_BLOCKED)
        except Exception as e:
            logger.exception("Ask command failed")
            if ctx.interaction:
                try:
                    await ctx.interaction.followup.send(ErrorMessages.UNEXPECTED, ephemeral=True)
                except:
                    pass
            else:
                try:
                    await ctx.message.add_reaction(Emojis.WARNING)
                    await ctx.message.add_reaction(Emojis.ROBOT)
                except:
                    pass

    @commands.hybrid_command(name="summon")
    @commands.guild_only()
    async def summon(self, ctx, duration: str = "10m"):
        """Summons the AI to listen and respond in this channel for a duration (e.g. 5m, 1h)."""
        if not await self.check_quota():
            await ctx.reply(ErrorMessages.QUOTA_REACHED, ephemeral=True)
            return
            
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

    @commands.group(name="stats", invoke_without_command=True)
    async def stats_group(self, ctx):
        """AI related statistics."""
        pass

    @stats_group.command(name="usage")
    async def usage(self, ctx):
        """Shows today's AI usage statistics."""
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        usage = await self.bot.db_manager.get_daily_usage(today)
        if usage:
            in_tok, out_tok, reqs = usage
            total = in_tok + out_tok
            await ctx.reply(InfoMessages.usage_stats(today, reqs, total, self.DAILY_TOKEN_LIMIT, in_tok, out_tok))
        else:
            await ctx.reply(InfoMessages.usage_none(today))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        channel_id = message.channel.id
        guild_id = message.guild.id if message.guild else None
        
        is_summoned = channel_id in self.active_summons
        is_chatbot_channel = guild_id and self.bot.settings_cache.get(guild_id, {}).get("cbc") == channel_id
        
        if not is_summoned and not is_chatbot_channel:
            return

        channel_data = self.warning_counters.setdefault(channel_id, {'quota': 0, 'busy': 0, 'chat_messages_since_busy_warning': 999})
        if 'chat_messages_since_busy_warning' not in channel_data:
            channel_data['chat_messages_since_busy_warning'] = 0
        channel_data['chat_messages_since_busy_warning'] += 1

        if is_summoned:
            now = datetime.datetime.now().timestamp()
            if now > self.active_summons[channel_id]['expiry']:
                tokens_used = self.active_summons[channel_id]['tokens']
                del self.active_summons[channel_id]
                await self.bot.db_manager.delete_summon(channel_id)
                
                try:
                    await message.channel.send(InfoMessages.summon_ended(tokens_used))
                except:
                    pass
                return

        is_mentioned = self.bot.user in message.mentions
        is_reply_to_bot = False
        if message.reference and message.reference.message_id:
            try:
                ref_msg = await message.channel.fetch_message(message.reference.message_id)
                if ref_msg.author.id == self.bot.user.id:
                    is_reply_to_bot = True
            except:
                pass

        if not is_mentioned and not is_reply_to_bot:
            return

        quota_ok = await self.check_quota()
        if quota_ok:
            if channel_id in self.warning_counters:
                self.warning_counters[channel_id]['quota'] = 0
        else:
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
            return

        async with message.channel.typing():
            try:
                ctx = await self.bot.get_context(message)
                message_list = await self._get_chat_history(ctx, message.channel.id, 30)
                message_list = [msg for msg in message_list if msg.id != message.id]
                message_list.reverse()
                
                prompt = f"Reply to this message from {message.author.display_name}: {message.content}"
                contents = await ContextManager.prepare_contents(message, message_list, prompt)

                logger.info(f"on_message trigger: contents contains {len(contents)} items")

                response = await self._execute_failover_pipeline(
                    guild_id,
                    contents
                )
                
                await self.update_usage(response, channel_id)
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
                    await message.add_reaction(Emojis.WARNING)
                    await message.add_reaction(Emojis.ROBOT)
                except:
                    pass
