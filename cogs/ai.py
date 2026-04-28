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
        self.DAILY_TOKEN_LIMIT = 1000000

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



    @commands.hybrid_command(name="summarize")
    @commands.guild_only()
    async def summarize(self, ctx, limit: str):
        """Summarizes last N messages or M minutes. Example: !summarize 50 or !summarize 10m"""
        if ctx.guild.id != 1027212609608491148:
            await ctx.reply("AI commands are only available in the test guild.", ephemeral=True)
            return
        
        if not await self.check_quota():
            await ctx.reply("⚠️ Daily AI token quota reached! Please try again tomorrow.", ephemeral=True)
            return
            
        await ctx.defer(ephemeral=True)

        messages = []
        try:
            if limit.isdigit():
                count = int(limit)
                if count > 100: count = 100 # Safety limit
                async for msg in ctx.channel.history(limit=count + 1):
                    if msg.id == ctx.message.id: continue
                    messages.append(msg)
            else:
                seconds = self.parse_time(limit)
                if seconds:
                    after_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=seconds)
                    async for msg in ctx.channel.history(after=after_time, limit=100):
                        if msg.id == ctx.message.id: continue
                        messages.append(msg)
                else:
                    await ctx.reply("Invalid format. Use a number (e.g. 50) or time (e.g. 10m).")
                    return

            if not messages:
                await ctx.reply("No messages found to summarize.")
                return

            messages.reverse() # History is newest first
            
            formatted_history = []
            for m in messages:
                content = m.clean_content if m.content else "[Embed/Attachment]"
                formatted_history.append(f"{m.author.display_name}: {content}")

            history_text = "\n".join(formatted_history)
            prompt = f"Summarize the following Discord conversation concisely. Use bullet points for key topics. Keep it brief and avoid unnecessary detail:\n\n{history_text}"

            async with ctx.typing():
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model_name,
                    contents=prompt
                )
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
        if ctx.guild.id != 1027212609608491148:
            await ctx.reply("AI commands are only available in the test guild.", ephemeral=True)
            return
            
        if not await self.check_quota():
            await ctx.reply("⚠️ Daily AI token quota reached! Please try again tomorrow.", ephemeral=True)
            return
            
        await ctx.defer()

        history = []
        
        if ctx.message.reference:
            try:
                current_msg = ctx.message
                depth = 0
                while current_msg.reference and depth < 5: # Limit depth to 5 for speed
                    ref = current_msg.reference
                    if ref.message_id:
                        msg = await ctx.channel.fetch_message(ref.message_id)
                        role = "model" if msg.author.id == self.bot.user.id else "user"
                        # New SDK uses 'parts' with 'text' objects
                        history.insert(0, types.Content(
                            role=role, 
                            parts=[types.Part(text=f"{msg.author.display_name}: {msg.content}")]
                        ))
                        current_msg = msg
                        depth += 1
                    else:
                        break
            except Exception as e:
                logger.warning(f"Failed to fetch reply chain: {e}")

        try:
            today_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
            async with ctx.typing():
                chat = self.client.chats.create(
                    model=self.model_name, 
                    history=history,
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(google_search=types.GoogleSearch())],
                        system_instruction=(
                            f"You are spl1ceAI, a chill Discord bot in a group chat, you're interested in tech and complex problems. "
                            "CRITICAL TONE CONSTRAINT: NEVER yap. Be extremely concise. Give brief, direct answers. Avoid paragraphs unless explicitly asked for detail. "
                            "ADAPT YOUR TONE: First, detect user intent. "
                            "IF TROLLING/BANTER: Match the energy. Be funny, dismissive, or insensitive as part of the vibe. Use very few words. "
                            "IF SERIOUS/TECHNICAL/REAL TALK: Be helpful, extremely valuable, and coherent, but keep it as brief as possible. "
                            "Always match the energy of the user. Reply conversationally and if there's not much to say, don't say much. "
                            "Do NOT prefix your message with your name or 'spl1ceAI:'. Just answer directly. "
                            "If a message is pure nonsensical spam, reply with '[IGNORE]'."
                            f"Current date: {today_str}."
                        )
                    )

                )
                
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = await asyncio.to_thread(chat.send_message, message=question)
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        await asyncio.sleep(1)
            
            await self.update_usage(response)
            
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
        if ctx.guild.id != 1027212609608491148:
            await ctx.reply("AI commands are only available in the test guild.", ephemeral=True)
            return
            
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
        if channel_id not in self.active_summons:
            return

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

        if is_mentioned or is_reply_to_bot:
            if not await self.check_quota():
                try:
                    await message.reply("⚠️ Daily AI token quota reached! Please try again tomorrow.")
                except:
                    pass
                return
                
            async with message.channel.typing():
                try:
                    today_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
                    # Fetch context (last 20 messages)
                    history_msgs = []
                    async for msg in message.channel.history(limit=25):
                        if msg.id == message.id: continue
                        role = "model" if msg.author.id == self.bot.user.id else "user"
                        history_msgs.insert(0, types.Content(
                            role=role, 
                            parts=[types.Part(text=f"{msg.author.display_name}: {msg.content}")]
                        ))
                    
                    chat = self.client.chats.create(
                        model=self.model_name, 
                        history=history_msgs,
                        config=types.GenerateContentConfig(
                            tools=[types.Tool(google_search=types.GoogleSearch())],
                            system_instruction=(
                                f"You are spl1ceAI, a chill Discord bot in a group chat, you're interested in tech and complex problems. "
                                f"Your creator and owner is spl1ce. Current date: {today_str}. "
                                "CRITICAL TONE CONSTRAINT: NEVER yap. Be extremely concise. Give brief, direct answers. Avoid paragraphs unless explicitly asked for detail. "
                                "ADAPT YOUR TONE: First, detect user intent. "
                                "IF TROLLING/BANTER: Match the energy. Be funny, dismissive, or insensitive as part of the vibe. Use very few words. "
                                "IF SERIOUS/TECHNICAL/REAL TALK: Be helpful, extremely valuable, and coherent, but keep it as brief as possible. "
                                "Reply to the SPECIFIC message. "
                                "Do NOT address the whole room unless necessary. "
                                "Do NOT prefix your message with your name or 'spl1ceAI:'. Just answer directly. "
                                "If the message is pure nonsensical spam, reply with '[IGNORE]'."
                            )
                        )
                    )
                    
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            response = await asyncio.to_thread(chat.send_message, message=f"Reply to this specific message from {message.author.display_name}: {message.content}")
                            break
                        except Exception as e:
                            if attempt == max_retries - 1:
                                raise e
                            await asyncio.sleep(1)
                    
                    await self.update_usage(response, channel_id)
                    
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
