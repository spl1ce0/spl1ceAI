import discord
from discord.ext import commands
from google import genai
from google.genai import types
import os
import asyncio
import logging
import datetime
import re
import io
import PIL.Image
import typing

logger = logging.getLogger(__name__)


ERROR_QUOTA_REACHED = "⚠️ Daily AI token quota reached! Please try again tomorrow."
ERROR_BUSY_OR_LIMIT = "⏳ Gemini is busy or rate-limited! Please try again in a moment."
ERROR_SAFETY_BLOCKED = "🛡️ Response blocked by Gemini safety filters."
ERROR_UNEXPECTED = "❌ An unexpected error occurred while processing your request."
ERROR_IMAGE_GEN_FAILED = "*(⚠️ Failed to generate image)*"

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
        self.warning_counters = {}


    def _should_send_warning(self, channel_id: int, warning_type: str, interval: int = 10) -> bool:
        channel_data = self.warning_counters.setdefault(channel_id, {'quota': 0, 'busy': 0})
        count = channel_data[warning_type]
        
        # Increment failure counter
        channel_data[warning_type] += 1
        
        # Warn on the 1st failure (count == 0) and then every X failures
        if count == 0 or (count % interval == 0):
            return True
        return False


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
            "If a message is pure spam or you think it doesn't need a reply, reply with '[IGNORE]'. "
            "IMAGE GENERATION: If the user asks you to draw/show/generate an image, or if you feel it's a perfect context to show an image, you can generate one by appending `[GENERATE_IMAGE: <detailed prompt>]` to the end of your message. "
            "Write the image prompt in English, describing the scene with rich detail (styles, subjects, lighting, etc.) so it looks great. Avoid using text inside the generated image."
        )


    async def _handle_potential_image_generation(self, response_text: str):
        # We look for "[GENERATE_IMAGE: <prompt>]"
        pattern = r"\[GENERATE_IMAGE:\s*(.*?)\]"
        match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
        
        file = None
        clean_text = response_text
        
        if match:
            image_prompt = match.group(1).strip()
            # Remove the tag from the text
            clean_text = re.sub(pattern, "", response_text, flags=re.IGNORECASE | re.DOTALL).strip()
            if not clean_text:
                clean_text = None
            
            try:
                logger.info(f"Generating image for prompt: {image_prompt}")
                image_response = await asyncio.to_thread(
                    self.client.models.generate_images,
                    model='imagen-4.0-generate-001',
                    prompt=image_prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=1,
                        output_mime_type='image/jpeg'
                    )
                )
                
                if image_response and image_response.generated_images:
                    img_bytes = image_response.generated_images[0].image.image_bytes
                    file = discord.File(io.BytesIO(img_bytes), filename="generated_image.jpg")
            except Exception as e:
                logger.error(f"Image generation failed: {e}")
                if clean_text:
                    clean_text += f"\n\n{ERROR_IMAGE_GEN_FAILED}"
                else:
                    clean_text = ERROR_IMAGE_GEN_FAILED
                
        return clean_text, file


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
    

    async def _get_chat_history(self, ctx: commands.Context, channel_id: int, message_count: int) -> list:
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
            content = message.content or ""
            
            # Check attachments
            attachments_str = ""
            if message.attachments:
                att_types = []
                for att in message.attachments:
                    if self._is_image(att):
                        att_types.append("[Image]")
                    else:
                        att_types.append(f"[{att.filename}]")
                attachments_str = " " + " ".join(att_types)

            if message.reference is not None:
                ref_message = message.reference.resolved
                if ref_message is not None and not isinstance(ref_message, discord.DeletedReferencedMessage): 
                    ref_author = ref_message.author 
                    ref_content = ref_message.content or ""
                    
                    # Check reference attachments
                    ref_attachments_str = ""
                    if ref_message.attachments:
                        ref_att_types = []
                        for att in ref_message.attachments:
                            if self._is_image(att):
                                ref_att_types.append("[Image]")
                            else:
                                ref_att_types.append(f"[{att.filename}]")
                        ref_attachments_str = " " + " ".join(ref_att_types)
                        
                    ref_text = (ref_content + ref_attachments_str).strip() or "[Attachment/Embed]"
                    if len(ref_text) > 100:                                                                                                  
                        ref_text = ref_text[:97] + "..."                                                                                  
                    result += f"> [{ref_author}]: \"{ref_text}\"\n"    
            
            msg_text = (content + attachments_str).strip()
            result += f"[{sender}]: {msg_text}\n"
        return result


    async def _get_llm_request(self, contents: typing.Union[str, list], tools: list = None):
        config = types.GenerateContentConfig(
            system_instruction=self._get_system_instructions(),
            tools=tools
        )
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model_name,
            contents=contents,
            config=config
        )
        return response


    def _is_image(self, attachment):
        if attachment.content_type:
            return attachment.content_type.startswith("image/")
        filename = attachment.filename.lower()
        return filename.endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif', '.heic', '.bmp'))

    def _get_mime_type(self, attachment):
        if attachment.content_type:
            return attachment.content_type
        filename = attachment.filename.lower()
        if filename.endswith('.png'): return 'image/png'
        if filename.endswith(('.jpg', '.jpeg')): return 'image/jpeg'
        if filename.endswith('.webp'): return 'image/webp'
        if filename.endswith('.gif'): return 'image/gif'
        if filename.endswith('.heic'): return 'image/heic'
        if filename.endswith('.bmp'): return 'image/bmp'
        return 'image/jpeg'


    @commands.hybrid_command(name="summarize", aliases=["tldr", "aint_readin_allat"])
    @commands.guild_only()
    async def summarize(self, ctx, limit: int):
        """Summarizes last N messages."""
        if not await self.check_quota():
            await ctx.reply(ERROR_QUOTA_REACHED, ephemeral=True)
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
            if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str or "503" in error_str or "UNAVAILABLE" in error_str:
                await ctx.reply(ERROR_BUSY_OR_LIMIT, ephemeral=True)
            else:
                logger.error(f"Summarize failed: {e}")
                if ctx.interaction:
                    try:
                        await ctx.interaction.followup.send(ERROR_UNEXPECTED, ephemeral=True)
                    except:
                        pass
                else:
                    try:
                        await ctx.message.add_reaction('❌')
                    except:
                        pass


    @commands.hybrid_command(name="ask", aliases=["llm", "ai"])
    @commands.guild_only()
    async def ask(self, ctx, question: str, image: typing.Optional[discord.Attachment] = None):
        """Asks the AI a question. Optionally attach an image."""
        if not await self.check_quota():
            await ctx.reply(ERROR_QUOTA_REACHED, ephemeral=True)
            return
            
        await ctx.defer()

        contents = []
        if image:
            if self._is_image(image):
                try:
                    img_bytes = await image.read()
                    contents.append(types.Part.from_bytes(data=img_bytes, mime_type=self._get_mime_type(image)))
                except Exception as e:
                    await ctx.reply(f"⚠️ Failed to process attachment image: {e}", ephemeral=True)
                    return
            else:
                await ctx.reply("⚠️ Attached file is not an image.", ephemeral=True)
                return

        # Check if replying to a message with an image
        if ctx.message and ctx.message.reference and ctx.message.reference.message_id:
            try:
                ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                for attachment in ref_msg.attachments:
                    if self._is_image(attachment):
                        img_bytes = await attachment.read()
                        contents.append(types.Part.from_bytes(data=img_bytes, mime_type=self._get_mime_type(attachment)))
            except:
                pass

        message_list = await self._get_chat_history(ctx, ctx.channel.id, 20)
        message_list.reverse()
        formatted_context = self._format_messages(message_list)
        prompt = f"Here's the chat:\n{formatted_context}\n\nReply to the user's question: {question}"
        contents.append(prompt)

        logger.info(f"ask command trigger: contents contains {len(contents)} items (images: {len(contents) - 1})")

        try:
            async with ctx.typing():
                response = await self._get_llm_request(
                    contents, 
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            await self.update_usage(response)

            if not response.text:
                await ctx.reply(ERROR_SAFETY_BLOCKED)
                return

            clean_text, file = await self._handle_potential_image_generation(response.text)
            if file:
                await ctx.reply(clean_text, file=file)
            else:
                if len(clean_text) > 2000:
                    parts = [clean_text[i:i+1900] for i in range(0, len(clean_text), 1900)]
                    for part in parts:
                        await ctx.send(part)
                else:
                    await ctx.reply(clean_text)

        except Exception as e:
            error_str = str(e).upper()
            if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str or "503" in error_str or "UNAVAILABLE" in error_str:
                await ctx.reply(ERROR_BUSY_OR_LIMIT, ephemeral=True)
            else:
                logger.exception("Ask command failed")
                if ctx.interaction:
                    try:
                        await ctx.interaction.followup.send(ERROR_UNEXPECTED, ephemeral=True)
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
            await ctx.reply(ERROR_QUOTA_REACHED, ephemeral=True)
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
        is_chatbot_channel = guild_id and self.bot.settings_cache.get(guild_id, {}).get("cbc") == channel_id
        
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

        quota_ok = await self.check_quota()
        if quota_ok:
            if channel_id in self.warning_counters:
                self.warning_counters[channel_id]['quota'] = 0
        else:
            if self._should_send_warning(channel_id, 'quota', interval=10):
                try:
                    await message.reply(ERROR_QUOTA_REACHED)
                except:
                    pass
            else:
                try:
                    await message.add_reaction('🚫')
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

                contents = []
                # Check for images in the current message
                for attachment in message.attachments:
                    if self._is_image(attachment):
                        try:
                            img_bytes = await attachment.read()
                            contents.append(types.Part.from_bytes(data=img_bytes, mime_type=self._get_mime_type(attachment)))
                        except Exception as e:
                            logger.error(f"Failed to read message attachment image: {e}")

                # Check if replying to a message with images
                if message.reference and message.reference.message_id:
                    try:
                        ref_msg = await message.channel.fetch_message(message.reference.message_id)
                        for attachment in ref_msg.attachments:
                            if self._is_image(attachment):
                                img_bytes = await attachment.read()
                                contents.append(types.Part.from_bytes(data=img_bytes, mime_type=self._get_mime_type(attachment)))
                    except Exception as e:
                        logger.error(f"Failed to read reply referenced image: {e}")

                prompt = f"Recent Chat:\n{formatted_context}\n\nReply to this message from {message.author.display_name}: {message.content}"
                contents.append(prompt)

                logger.info(f"on_message trigger: contents contains {len(contents)} items (images: {len(contents) - 1})")

                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = await self._get_llm_request(
                            contents,
                            tools=[types.Tool(google_search=types.GoogleSearch())]
                        )
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        await asyncio.sleep(1)
                
                await self.update_usage(response, channel_id)
                # Success! Reset the busy warning counter
                if channel_id in self.warning_counters:
                    self.warning_counters[channel_id]['busy'] = 0
                
                if not response.text:
                    await message.reply(ERROR_SAFETY_BLOCKED)
                    return
                
                if "[IGNORE]" in response.text:
                    return

                clean_text, file = await self._handle_potential_image_generation(response.text)
                if file:
                    await message.reply(clean_text, file=file)
                else:
                    if len(clean_text) > 2000:
                        parts = [clean_text[i:i+1900] for i in range(0, len(clean_text), 1900)]
                        for part in parts:
                            await message.channel.send(part)
                    else:
                        await message.reply(clean_text)
            except Exception as e:
                error_str = str(e).upper()
                if any(code in error_str for code in ["RESOURCE_EXHAUSTED", "429", "503", "UNAVAILABLE"]):
                    if self._should_send_warning(channel_id, 'busy', interval=10):
                        try:
                            await message.reply(ERROR_BUSY_OR_LIMIT)
                        except:
                            pass
                    else:
                        try:
                            await message.add_reaction('⏳')
                        except:
                            pass
                else:
                    logger.exception("Summon response failed")
                    try:
                        await message.add_reaction('⚠️')
                        await message.add_reaction('🤖')
                    except:
                        pass


async def setup(bot):
    await bot.add_cog(AI(bot))
