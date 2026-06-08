import discord
from discord.ext import commands
from google import genai
from google.genai import types
import os
import asyncio
import logging
import datetime
import re

logger = logging.getLogger(__name__)

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found in environment variables.")
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = 'gemini-flash-latest'
        self.active_summons = {}
        self.DAILY_TOKEN_LIMIT = 100000


    def _get_system_instructions(self):
        today_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
        return (
            f"You are spl1ceAI, a chill Discord bot in a group chat, interested in tech and complex problems. "
            f"Your creator and owner is spl1ce. Current date: {today_str}. "
            "TONE: Conversational, relaxed, and brief. Don't be a robot. "
            "Be extremely informal. Use lowercase and minimal punctuation (like a normal Discord user). "
            "NEVER yap. Keep answers short and direct, but keep the personality. "
            "IF TROLLING/BANTER: Match the energy. Be funny, dismissive, or slightly toxic if that's the vibe. "
            "IF SERIOUS/TECHNICAL: Be helpful and coherent, informative and get straight to the point. "
            "Do NOT prefix messages with your name. "
            "If a message is pure spam, reply with '[IGNORE]'."
        )


    async def cog_load(self):
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT channel_id, expiry FROM ai_summon")
            rows = await cursor.fetchall()
            for row in rows:
                self.active_summons[row[0]] = {'expiry': row[1], 'tokens': 0}
        logger.info(f"Loaded {len(self.active_summons)} active summons.")


    async def check_quota(self):
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT input_tokens, output_tokens FROM ai_usage WHERE day = ?", (today,))
            row = await cursor.fetchone()
            if row:
                total_tokens = row[0] + row[1]
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
        
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO ai_usage (day, request_count, input_tokens, output_tokens) VALUES (?, 1, ?, ?) "
                "ON CONFLICT(day) DO UPDATE SET request_count = request_count + 1, "
                "input_tokens = input_tokens + excluded.input_tokens, "
                "output_tokens = output_tokens + excluded.output_tokens",
                (today, in_tokens, out_tokens)
            )
            await self.bot.db.commit()
            
        if channel_id and channel_id in self.active_summons:
            self.active_summons[channel_id]['tokens'] += total


    def parse_time(self, time_str):
        """Parses strings like '10m', '1h', '30s' into seconds."""
        match = re.match(r"(\d+)([smh])", time_str.lower())
        if not match:
            return None
        amount, unit = match.groups()
        amount = int(amount)
        if unit == 's': return amount
        if unit == 'm': return amount * 60
        if unit == 'h': return amount * 3600
        return None
    

    async def _get_chat_history(self, ctx: discord.Context, channel_id: int, message_count: int) -> list:
        message_list = []
        channel = await commands.TextChannelConverter().convert(ctx, str(channel_id))
        try:
            message_list = [message async for message in channel.history(limit=message_count)]
        except:
            logger.error("Failed to get message history")
            return
        
        return message_list
    

    def _format_messages(self, message_list: list) -> str:

        result = ""

        for message in message_list:
            sender = message.author
            content = message.content
            if message.reference != None:
                ref_message = message.reference.resolved
                if ref_message is not None and not isinstance(ref_message, discord.DeletedReferencedMessage): 
                    ref_author = ref_message.author 
                    ref_content = ref_message.content or "[Attachment/Embed]"
                    if len(ref_content) > 100:                                                                                                  
                        ref_content = ref_content[:97] + "..."                                                                                  
                    result += f"> [{ref_author}]: \"{ref_content}\"\n"    
            result += f"[{sender}]: {content}\n"
        return result


    async def _get_llm_request(self, prompt: str, tools: list = None):
        config = types.GenerateContentConfig(
            system_instruction=self._get_system_instructions(),
            tools=tools
        )
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model_name,
            contents=prompt,
            config=config
        )
        return response


    @commands.hybrid_command(name="summarize", aliases=["tldr", "aint_readin_allat"])
    @commands.guild_only()
    async def summarize(self, ctx, limit: int):
        """Summarizes last N messages."""
        if not await self.check_quota():
            await ctx.reply("⚠️ Daily AI token quota reached! Please try again tomorrow.", ephemeral=True)
            return
            
        await ctx.defer(ephemeral=True)

        message_list = await self._get_chat_history(ctx, ctx.channel.id, int(limit))

        if not message_list:
            await ctx.reply("No messages found to summarize.")
            return

        message_list.reverse()

        formatted_context = self._format_messages(message_list)


        try:
            prompt = f"Summarize the following Discord conversation concisely. Use bullet points for key topics. Keep it brief and avoid unnecessary detail:\n\n{formatted_context}"

            async with ctx.typing():
                response = await self._get_llm_request(prompt)
            await self.update_usage(response)
            await ctx.reply(f"### 📝 Summary\n{response.text}")

        except Exception as e:
            error_str = str(e).upper()
            if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                await ctx.reply("⚠️ I'm being rate-limited! Please try again in a bit. <:CC_yellow_look:1440119405991166186>")
            else:
                logger.error(f"Summarize failed: {e}")
                if ctx.interaction:
                    try:
                        await ctx.interaction.followup.send("⚠️ An error occurred while processing your request.", ephemeral=True)
                    except:
                        pass
                else:
                    try:
                        await ctx.message.add_reaction('❌')
                    except:
                        pass


    @commands.hybrid_command(name="ask", aliases=["llm", "ai"])
    @commands.guild_only()
    async def ask(self, ctx, *, question: str):
        """Asks the AI a question. Responds with context if you reply to a message."""
        if not await self.check_quota():
            await ctx.reply("⚠️ Daily AI token quota reached! Please try again tomorrow.", ephemeral=True)
            return
            
        await ctx.defer()

        message_list = await self._get_chat_history(ctx, ctx.channel.id, 50)
        message_list.reverse()
        formatted_context = self._format_messages(message_list)
        prompt = f"Here's the chat:\n{formatted_context}\n\nReply to the user's question: {question}"

        try:
            async with ctx.typing():
                response = await self._get_llm_request(
                    prompt, 
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                    )
            await self.update_usage(response)

            if not response.text:
                await ctx.reply("⚠️ Gemini returned an empty response.")
                return

            if len(response.text) > 2000:
                parts = [response.text[i:i+1900] for i in range(0, len(response.text), 1900)]
                for part in parts:
                    await ctx.send(part)
            else:
                await ctx.reply(response.text)


        except Exception as e:
            error_str = str(e).upper()
            if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                await ctx.reply("⚠️ I'm being rate-limited! Please try again in a bit. <:CC_yellow_look:1440119405991166186>")
            elif "503" in error_str or "UNAVAILABLE" in error_str:
                await ctx.reply("⚠️ High demand spike! Gemini is currently busy. Please try again in a moment. 🤖")
            else:
                logger.error(f"Ask command failed: {e}")
                if ctx.interaction:
                    try:
                        await ctx.interaction.followup.send("⚠️ An error occurred while processing your request.", ephemeral=True)
                    except:
                        pass
                else:
                    try:
                        await ctx.message.add_reaction('⚠️')
                        await ctx.message.add_reaction('🤖')
                    except:
                        pass


    @commands.hybrid_command(name="summon")
    @commands.guild_only()
    async def summon(self, ctx, duration: str = "10m"):
        """Summons the AI to listen and respond in this channel for a duration (e.g. 5m, 1h)."""
        if not await self.check_quota():
            await ctx.reply("⚠️ Daily AI token quota reached! Please try again tomorrow.", ephemeral=True)
            return
            
        if ctx.channel.id in self.active_summons:
            await ctx.reply("⚠️ I'm already listening in this channel!", ephemeral=True)
            return

        seconds = self.parse_time(duration)
        if not seconds:
            await ctx.reply("Invalid duration. Use '30m', '1h', etc.")
            return
        
        expiry = datetime.datetime.now().timestamp() + seconds
        
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "INSERT OR REPLACE INTO ai_summon (channel_id, expiry) VALUES (?, ?)",
                (ctx.channel.id, expiry)
            )
            await self.bot.db.commit()
        
        self.active_summons[ctx.channel.id] = {'expiry': expiry, 'tokens': 0}
        time_str = discord.utils.format_dt(datetime.datetime.fromtimestamp(expiry), style='R')
        await ctx.reply(f"**spl1ceAI summoned.** I will answer mentions and replies.\n-# Ends {time_str}")


    @commands.group(name="stats", invoke_without_command=True)
    async def stats_group(self, ctx):
        """AI related statistics."""
        pass


    @stats_group.command(name="usage")
    async def usage(self, ctx):
        """Shows today's AI usage statistics."""
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("SELECT request_count, input_tokens, output_tokens FROM ai_usage WHERE day = ?", (today,))
            row = await cursor.fetchone()
            if row:
                reqs, in_tok, out_tok = row
                total = in_tok + out_tok
                await ctx.reply(f"📊 **AI Usage Today ({today})**\n- Requests: `{reqs}`\n- Tokens: `{total} / {self.DAILY_TOKEN_LIMIT}`\n  - In: `{in_tok}`\n  - Out: `{out_tok}`")
            else:
                await ctx.reply(f"📊 **AI Usage Today ({today})**\nNo usage recorded today.")


    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        channel_id = message.channel.id
        guild_id = message.guild.id if message.guild else None
        
        is_summoned = channel_id in self.active_summons
        is_chatbot_channel = guild_id and self.bot.settings_cache.get(guild_id).get("cbc") == channel_id
        
        if not is_summoned and not is_chatbot_channel:
            return

        if is_summoned:
            now = datetime.datetime.now().timestamp()
            if now > self.active_summons[channel_id]['expiry']:
                tokens_used = self.active_summons[channel_id]['tokens']
                del self.active_summons[channel_id]
                async with self.bot.db.cursor() as cursor:
                    await cursor.execute("DELETE FROM ai_summon WHERE channel_id = ?", (channel_id,))
                    await self.bot.db.commit()
                
                try:
                    await message.channel.send(f"⌛ **spl1ceAI summon ended.** I am no longer listening.\n-# Session used `{tokens_used}` tokens.")
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

        if not await self.check_quota():
            try:
                await message.reply("⚠️ Daily AI token quota reached! Please try again tomorrow.")
            except:
                pass
            return
            

        async with message.channel.typing():
            try:
                ctx = await self.bot.get_context(message)
                message_list = await self._get_chat_history(ctx, message.channel.id, 75)
                message_list = [msg for msg in message_list if msg.id != message.id]
                message_list.reverse()
                
                formatted_context = self._format_messages(message_list)

                prompt = f"Recent Chat:\n{formatted_context}\n\nReply to this message from {message.author.display_name}: {message.content}"

                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = await self._get_llm_request(
                            prompt,
                            tools=[types.Tool(google_search=types.GoogleSearch())]
    				    )
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        await asyncio.sleep(1)
                
                await self.update_usage(response, channel_id)
                
                if not response.text:
                    await message.reply("⚠️ I couldn't generate a response (it may have been blocked by safety filters).")
                    return
                
                if "[IGNORE]" in response.text:
                    return

                if len(response.text) > 2000:
                    parts = [response.text[i:i+1900] for i in range(0, len(response.text), 1900)]
                    for part in parts:
                        await message.channel.send(part)
                else:
                    await message.reply(response.text)
            except Exception as e:
                error_str = str(e).upper()
                if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
                    await message.reply("⚠️ I'm being rate-limited! Please try again in a bit. <:CC_yellow_look:1440119405991166186>")
                elif "503" in error_str or "UNAVAILABLE" in error_str:
                    await message.reply("⚠️ High demand spike! Gemini is currently busy. Please try again in a moment. 🤖")
                else:
                    logger.error(f"Summon response failed: {e}")
                    try:
                        await message.add_reaction('⚠️')
                        await message.add_reaction('🤖')
                    except:
                        pass


async def setup(bot):
    await bot.add_cog(AI(bot))
