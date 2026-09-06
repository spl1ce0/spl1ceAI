import os
import time
import asyncio
import logging
import datetime
import typing
import discord
from discord import ui
from discord.ext import commands

from cogs.utils.exceptions import (
    AIError,
    AIRateLimitError,
    AIServiceUnavailableError,
    AISafetyBlockedError,
    AIConfigurationError,
    AIQuotaReachedError
)
from cogs.utils.constants import Emojis, ErrorMessages, SuccessMessages, InfoMessages, DefaultSettings
from .ai import ModelManager, ContextManager, ResponseHandler

logger = logging.getLogger(__name__)

# Errors and Emojis imported from cogs.utils.constants


class QuotaContainer(ui.Container):
    def __init__(self, bot, guild: discord.Guild, usage_data: dict, guild_settings: dict, checkout_url: typing.Optional[str] = None, portal_url: typing.Optional[str] = None):
        super().__init__()
        self.bot = bot
        self.guild = guild
        self.usage_data = usage_data
        self.guild_settings = guild_settings
        self.checkout_url = checkout_url
        self.portal_url = portal_url
        self._build_ui()

    def _build_ui(self):
        is_premium = bool(self.guild_settings.get("is_premium", 0))
        has_byok = bool(self.guild_settings.get("byok_enabled", DefaultSettings.BYOK_ENABLED)) and bool(
            self.guild_settings.get("byok_gemini_key") or 
            self.guild_settings.get("byok_xai_key") or 
            self.guild_settings.get("byok_openai_key") or 
            self.guild_settings.get("byok_anthropic_key") or
            self.guild_settings.get("byok_deepseek_key") or
            self.guild_settings.get("byok_glm_key")
        )

        if has_byok:
            plan_name = "Bring Your Own Key"
            token_limit = None
        elif is_premium:
            plan_name = "Premium Plan"
            token_limit = DefaultSettings.PREMIUM_WEEKLY_TOKEN_LIMIT
        else:
            plan_name = "Free Plan"
            token_limit = DefaultSettings.FREE_WEEKLY_TOKEN_LIMIT

        total_tokens = int(self.usage_data.get("total_tokens", 0))
        reset_ts = self.usage_data.get("next_reset_ts", int(time.time() + 86400 * 7))
        img_count = int(self.usage_data.get("image_count", 0))

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        days_elapsed = max(1, now_utc.weekday() + 1)
        daily_avg = int(total_tokens / days_elapsed)
        days_left = max(1, int((reset_ts - now_utc.timestamp()) / 86400))
        projected = total_tokens + (daily_avg * days_left)

        # ----------------------------------------------------
        # 1. HEADER: Title, Server Name, Plan
        # ----------------------------------------------------
        self.add_item(ui.TextDisplay(f"## AI Quota\n-# {self.guild.name} • {plan_name}"))
        self.add_item(ui.Separator())

        # ----------------------------------------------------
        # 2. USAGE: 2nd Title, Bar, Token Count, Image Gens, Image Reset
        # ----------------------------------------------------
        if token_limit:
            pct = min(100.0, (total_tokens / token_limit) * 100.0)
            filled = min(16, max(0, int(round((pct / 100.0) * 16))))
            bar = "█" * filled + "░" * (16 - filled)
            token_block = (
                f"{bar}\n"
                f"{total_tokens:,} / {token_limit:,} tokens ({pct:.1f}%)\n"
                f"-# Resets <t:{reset_ts}:R>"
            )
        else:
            pct = 0.0
            token_block = (
                f"{total_tokens:,} tokens consumed this week\n"
                f"-# Unlimited quota active via custom API keys"
            )

        if has_byok:
            img_block = (
                f"{img_count} images used (Unlimited)\n"
                f"-# Unmetered via custom API keys"
            )
        elif is_premium:
            pct_img = min(100.0, (img_count / 5.0) * 100.0)
            filled_img = min(16, max(0, int(round((pct_img / 100.0) * 16))))
            bar_img = "█" * filled_img + "░" * (16 - filled_img)
            img_block = (
                f"{bar_img}\n"
                f"{img_count} / 5 images used ({pct_img:.0f}%)\n"
                f"-# Resets <t:{reset_ts}:R>"
            )
        else:
            last_img = float(self.usage_data.get("last_image_ts", 0) or 0)
            if last_img > 0 and (time.time() - last_img < 14 * 86400):
                bar_img = "█" * 16
                next_img_ts = int(last_img + 14 * 86400)
                img_block = (
                    f"{bar_img}\n"
                    f"1 / 1 images used (100%)\n"
                    f"-# Resets <t:{next_img_ts}:R>"
                )
            else:
                bar_img = "░" * 16
                img_block = (
                    f"{bar_img}\n"
                    f"0 / 1 images used (0%)\n"
                    f"-# 1 generation included every 2 weeks"
                )

        usage_text = (
            f"### Usage\n"
            f"{token_block}\n\n"
            f"{img_block}"
        )
        self.add_item(ui.TextDisplay(usage_text))
        self.add_item(ui.Separator())

        # ----------------------------------------------------
        # 3. BURN RATE: Tokens Burn Rate & On-Track Metric
        # ----------------------------------------------------
        if token_limit:
            is_exhausted = total_tokens >= token_limit
            is_on_track = (projected <= token_limit) and (pct < 85.0)

            if is_exhausted:
                status_str = "🔴 Limit reached"
                status_desc = "\n-# Weekly token pool is exhausted until the reset."
            elif is_on_track:
                status_str = "🟢 Healthy"
                status_desc = ""
            else:
                status_str = "⚠️ High burn rate"
                status_desc = f"\n-# Projected to reach ~{projected:,} tokens before reset."

            burn_rate_text = (
                f"### Burn Rate\n"
                f"~{daily_avg:,} tokens/day • {status_str}"
                f"{status_desc}"
            )
        else:
            burn_rate_text = (
                f"### Burn Rate\n"
                f"~{daily_avg:,} tokens/day • 🟢 Unmetered"
            )

        self.add_item(ui.TextDisplay(burn_rate_text))

        # ----------------------------------------------------
        # 4. UPGRADE REMINDER: Shown when quota is almost over AND not on track
        # ----------------------------------------------------
        show_upgrade = (not is_premium) and (not has_byok) and ((pct >= 75.0) or (not is_on_track) or is_exhausted)
        if show_upgrade:
            self.add_item(ui.Separator())
            upgrade_text = (
                f"**Need More Capacity?**\n"
                f"-# Upgrade to Premium for 1,000,000 tokens/week, 30-message memory, and image vision."
            )
            self.add_item(ui.TextDisplay(upgrade_text))

        # ----------------------------------------------------
        # 5. BUTTON ACTIONS (Upgrade or Portal if available)
        # ----------------------------------------------------
        if show_upgrade and self.checkout_url:
            self.add_item(ui.Separator())
            action_row = ui.ActionRow()
            upgrade_btn = ui.Button(label="Upgrade Plan", emoji="👑", url=self.checkout_url, style=discord.ButtonStyle.link)
            action_row.add_item(upgrade_btn)
            self.add_item(action_row)
        elif is_premium and self.portal_url:
            self.add_item(ui.Separator())
            action_row = ui.ActionRow()
            portal_btn = ui.Button(label="Manage Subscription", emoji="⚙️", url=self.portal_url, style=discord.ButtonStyle.link)
            action_row.add_item(portal_btn)
            self.add_item(action_row)


class QuotaLayoutView(ui.LayoutView):
    def __init__(self, bot, guild: discord.Guild, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.guild = guild

    async def render_quota(self, guild: discord.Guild):
        self.clear_items()
        self.guild = guild
        guild_settings = self.bot.settings_cache.get(guild.id, {})
        usage_data = await self.bot.db_manager.get_guild_weekly_ai_usage(guild.id)
        
        checkout_url = None
        portal_url = None
        billing_cog = self.bot.get_cog("Billing")
        if billing_cog and hasattr(billing_cog, "billing_service") and billing_cog.billing_service.is_configured:
            try:
                checkout_url = await billing_cog.billing_service.create_checkout_session(
                    guild_id=guild.id,
                    user_id=guild.owner_id or 0,
                    guild_name=guild.name,
                    user_name="Owner"
                )
                sub = await self.bot.db_manager.get_subscription(guild.id)
                if sub and sub.get("customer_id"):
                    portal_url = billing_cog.billing_service.get_customer_portal_url(sub["customer_id"])
            except Exception:
                pass

        container = QuotaContainer(self.bot, guild, usage_data, guild_settings, checkout_url=checkout_url, portal_url=portal_url)
        self.add_item(container)


class AI(commands.Cog):
    CHAT_HISTORY_LIMIT = 20
    MONTHLY_GUILD_LIMIT_EUR = 5.00

    def __init__(self, bot):
        self.bot = bot
        self.model_manager = ModelManager()
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(current_dir, "models.json")
        self.model_manager.load_config(config_path)
        
        self.response_orchestrator = ResponseHandler(bot)
        
        self.active_summons = {}
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


    async def check_quota(self, guild_id: typing.Optional[int] = None, is_image: bool = False) -> typing.Tuple[bool, str, dict]:
        """Checks if the guild has remaining weekly quota for text or image generation."""
        if not guild_id:
            return True, "DM", {}
        guild_settings = self.bot.settings_cache.get(guild_id, {})
        return await self.bot.db_manager.check_ai_quota_allowance(guild_id, guild_settings, is_image=is_image)


    async def update_usage(self, response, guild_id: typing.Optional[int] = None, channel_id: typing.Optional[int] = None):
        if not hasattr(response, 'usage_metadata') or not response.usage_metadata:
            return
        
        in_tokens = response.usage_metadata.prompt_token_count or 0
        out_tokens = response.usage_metadata.candidates_token_count or 0
        is_img = bool(getattr(response, 'image_bytes', None))
        
        if guild_id:
            await self.bot.db_manager.record_guild_ai_usage(guild_id, in_tokens, out_tokens, is_image=is_img)
            
        if channel_id and channel_id in self.active_summons:
            self.active_summons[channel_id]['tokens'] += (in_tokens + out_tokens)


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

    
    async def _get_chat_history(self, ctx: commands.Context, channel_id: int, message_count: int, max_age_minutes: typing.Optional[int] = 45) -> list:
        message_list = []
        channel = await commands.TextChannelConverter().convert(ctx, str(channel_id))
        now = discord.utils.utcnow()
        try:
            async for message in channel.history(limit=message_count):
                if max_age_minutes is not None:
                    age_mins = (now - message.created_at).total_seconds() / 60.0
                    if age_mins > max_age_minutes:
                        break
                message_list.append(message)
        except Exception as e:
            logger.error(f"Failed to get message history: {e}")
            return []
        
        return message_list


    @commands.hybrid_command(name="quota", aliases=["usage", "aiquota", "budget"])
    @commands.guild_only()
    async def quota(self, ctx: commands.Context):
        """Displays the server's weekly AI token allowance, image generations, and current tier."""
        await ctx.defer()
        view = QuotaLayoutView(self.bot, ctx.guild)
        await view.render_quota(ctx.guild)
        await ctx.reply(view=view)


    @commands.hybrid_command(name="summarize", aliases=["tldr", "aint_readin_allat"])
    @commands.guild_only()
    async def summarize(self, ctx, limit: int):
        """Summarizes last N messages."""
        allowed, reason, usage = await self.check_quota(ctx.guild.id if ctx.guild else None)
        if not allowed:
            raise AIQuotaReachedError(message=reason, reset_ts=usage.get("next_reset_ts"))
            
        await ctx.defer(ephemeral=True)

        message_list = await self._get_chat_history(ctx, ctx.channel.id, int(limit), max_age_minutes=None)
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
            
        await self.update_usage(response, guild_id=ctx.guild.id if ctx.guild else None, channel_id=ctx.channel.id)

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
                estimated_cost=getattr(response, "estimated_cost", 0.0) or 0.0,
                latency_ms=latency_ms,
                context_messages_count=len(message_list),
                finish_reason="STOP",
                trigger_type="summarize",
                prompt_chars=len(prompt or ""),
                response_chars=len(response.text or ""),
                failover_occurred=getattr(response, "failover_occurred", False),
                failover_reason=getattr(response, "failover_reason", None),
                prompt_text=f"/summarize {limit} messages"
            )
        except Exception as log_err:
            logger.error(f"Failed to log AI transaction telemetry: {log_err}")

        response.text = f"### 📝 Summary\n{response.text}"
        await self.response_orchestrator.orchestrate_reply(ctx, response)


    @commands.hybrid_command(name="ask", aliases=["llm", "ai"])
    @commands.guild_only()
    async def ask(self, ctx, question: str, image: typing.Optional[discord.Attachment] = None):
        """Asks the AI a question. Optionally attach an image."""
        allowed, reason, usage = await self.check_quota(ctx.guild.id if ctx.guild else None)
        if not allowed:
            raise AIQuotaReachedError(message=reason, reset_ts=usage.get("next_reset_ts"))
            
        await ctx.defer()

        guild_settings = self.bot.settings_cache.get(ctx.guild.id, {})
        is_paid_or_byok = bool(
            guild_settings.get("is_premium") or 
            any(guild_settings.get(k) for k in ["byok_gemini_key", "byok_xai_key", "byok_openai_key", "byok_anthropic_key"])
        )

        # Context limits: Free = 5 msgs, Paid/BYOK = 30 msgs
        history_limit = 30 if is_paid_or_byok else 5
        enable_vision = is_paid_or_byok

        message_list = await self._get_chat_history(ctx, ctx.channel.id, history_limit)
        message_list.reverse()
        
        msg = ctx.message if hasattr(ctx, 'message') else None
        slash_attachments = [image] if image else None
        
        contents = await ContextManager.prepare_contents(
            msg,
            message_list,
            f"Reply to the user's question from {ctx.author.display_name}: {question}",
            slash_attachments=slash_attachments,
            enable_vision=enable_vision,
            bot_user=self.bot.user
        )

        logger.info(f"ask command trigger: contents contains {len(contents)} items (vision={enable_vision}, history={len(message_list)})")

        async def _check_img_quota():
            if not ctx.guild:
                return True, "DM", None
            allowed, reason, usage = await self.bot.db_manager.check_ai_quota_allowance(ctx.guild.id, guild_settings, is_image=True)
            reset_ts = usage.get("next_image_reset_ts") or usage.get("next_reset_ts")
            return allowed, reason, reset_ts

        start_time = time.perf_counter()
        async with ctx.typing():
            response = await self.model_manager.execute(
                guild_settings,
                contents,
                image_quota_checker=_check_img_quota
            )
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        response.latency_ms = latency_ms
        await self.update_usage(response, guild_id=ctx.guild.id if ctx.guild else None, channel_id=ctx.channel.id)

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
                estimated_cost=getattr(response, "estimated_cost", 0.0) or 0.0,
                latency_ms=latency_ms,
                context_messages_count=len(message_list),
                finish_reason="STOP",
                trigger_type="ask_vision" if image else "ask",
                prompt_chars=len(question or ""),
                response_chars=len(response.text or ""),
                failover_occurred=getattr(response, "failover_occurred", False),
                failover_reason=getattr(response, "failover_reason", None),
                prompt_text=question
            )
        except Exception as log_err:
            logger.error(f"Failed to log AI transaction telemetry: {log_err}")

        await self.response_orchestrator.orchestrate_reply(ctx, response)


    @commands.hybrid_command(name="summon")
    @commands.guild_only()
    async def summon(self, ctx, duration: str = "10m"):
        """Summons the AI to listen and respond in this channel for a duration (e.g. 5m, 1h)."""
        allowed, reason, usage = await self.check_quota(ctx.guild.id if ctx.guild else None)
        if not allowed:
            raise AIQuotaReachedError(message=reason, reset_ts=usage.get("next_reset_ts"))
            
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

        # 1. Must be in either the designated chatbot channel (CBC) OR actively summoned
        if not is_chatbot_channel and not is_summoned:
            return False, is_summoned, is_chatbot_channel

        # 2. Check if the bot was mentioned in the message
        is_mentioned = self.bot.user in message.mentions

        # 3. Check if the message is a reply to the bot
        is_reply_to_bot = False
        if message.reference and message.reference.message_id:
            try:
                ref_msg = message.reference.resolved
                if not ref_msg or isinstance(ref_msg, discord.DeletedReferencedMessage):
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                if ref_msg and ref_msg.author.id == self.bot.user.id:
                    is_reply_to_bot = True
            except Exception:
                pass

        # 4. In chatbot channel or summoned channel: only respond if mentioned or replied to
        if is_mentioned or is_reply_to_bot:
            return True, is_summoned, is_chatbot_channel

        return False, is_summoned, is_chatbot_channel

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

    async def _validate_quota_with_warnings(self, message: discord.Message, guild_id: typing.Optional[int], channel_id: int) -> bool:
        channel_data = self.warning_counters.setdefault(channel_id, {'quota': 0, 'busy': 0, 'chat_messages_since_busy_warning': 999})
        if 'chat_messages_since_busy_warning' not in channel_data:
            channel_data['chat_messages_since_busy_warning'] = 0
        channel_data['chat_messages_since_busy_warning'] += 1

        allowed, reason, usage = await self.check_quota(guild_id)
        if allowed:
            if channel_id in self.warning_counters:
                self.warning_counters[channel_id]['quota'] = 0
            return True

        if self._should_send_warning(channel_id, 'quota', interval=10):
            try:
                reset_ts = usage.get("next_reset_ts", int(time.time() + 86400 * 7))
                await message.reply(
                    f"{Emojis.AI_FROWN} **Weekly AI Token Quota Reached!**\n"
                    f"{reason} Resets <t:{reset_ts}:R> (Monday 00:00 UTC)."
                )
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
                guild_settings = self.bot.settings_cache.get(guild_id, {})
                is_paid_or_byok = bool(
                    guild_settings.get("is_premium") or 
                    any(guild_settings.get(k) for k in ["byok_gemini_key", "byok_xai_key", "byok_openai_key", "byok_anthropic_key"])
                )

                # Context limits: Free = 15 msgs, Paid/BYOK = 30 msgs
                history_limit = 30 if is_paid_or_byok else 15
                enable_vision = is_paid_or_byok

                ctx = await self.bot.get_context(message)
                message_list = await self._get_chat_history(ctx, message.channel.id, history_limit)
                message_list = [msg for msg in message_list if msg.id != message.id]
                message_list.reverse()
                
                prompt = f"Reply to this message from {message.author.display_name}: {message.content}"
                contents = await ContextManager.prepare_contents(message, message_list, prompt, enable_vision=enable_vision, bot_user=self.bot.user)

                logger.info(f"on_message trigger: contents contains {len(contents)} items (vision={enable_vision}, history={len(message_list)})")

                async def _check_img_quota():
                    if not guild_id:
                        return True, "DM", None
                    allowed, reason, usage = await self.bot.db_manager.check_ai_quota_allowance(guild_id, guild_settings, is_image=True)
                    reset_ts = usage.get("next_image_reset_ts") or usage.get("next_reset_ts")
                    return allowed, reason, reset_ts

                start_time = time.perf_counter()
                response = await self.model_manager.execute(
                    guild_settings,
                    contents,
                    image_quota_checker=_check_img_quota
                )
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                response.latency_ms = latency_ms
                
                await self.update_usage(response, guild_id=guild_id, channel_id=channel_id)

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
                        estimated_cost=getattr(response, "estimated_cost", 0.0) or 0.0,
                        latency_ms=latency_ms,
                        context_messages_count=len(message_list),
                        finish_reason="STOP",
                        trigger_type=trigger_type,
                        prompt_chars=len(message.content or ""),
                        response_chars=len(response.text or ""),
                        failover_occurred=getattr(response, "failover_occurred", False),
                        failover_reason=getattr(response, "failover_reason", None),
                        prompt_text=message.content
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

        # Ignore blacklisted users globally
        if message.author.id in getattr(self.bot, "blacklist_cache", set()):
            return

        channel_id = message.channel.id
        guild_id = message.guild.id if message.guild else None

        should_respond, is_summoned, is_chatbot_channel = await self._parse_message_triggers(message)
        if not should_respond:
            return

        if is_summoned and await self._check_summon_expiration(message, channel_id):
            return

        if not await self._validate_quota_with_warnings(message, guild_id, channel_id):
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
