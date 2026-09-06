import io
import re
import base64
import logging
import asyncio
import json
import os
import datetime
from abc import ABC, abstractmethod
import discord
from google.genai import types
from google.genai.errors import APIError
import openai
import anthropic
from xai_sdk.chat import user, system, image

from cogs.utils.exceptions import (
    AIError,
    AIRateLimitError,
    AIServiceUnavailableError,
    AISafetyBlockedError,
    AIConfigurationError
)
from cogs.utils.constants import Emojis, DefaultSettings

logger = logging.getLogger(__name__)

class AIUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int):
        self.prompt_token_count = prompt_tokens
        self.candidates_token_count = completion_tokens

class AIResponse:
    def __init__(
        self,
        text: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        model_name: str = None,
        provider: str = None,
        image_bytes: bytes = None,
        image_filename: str = None,
        failover_occurred: bool = False,
        failover_reason: str = None,
        estimated_cost: float = 0.0,
        display_name: str = None
    ):
        self.text = text
        self.usage_metadata = AIUsage(prompt_tokens, completion_tokens)
        self.model_name = model_name
        self.display_name = display_name or model_name
        self.provider = provider
        self.image_bytes = image_bytes
        self.image_filename = image_filename
        self.failover_occurred = failover_occurred
        self.failover_reason = failover_reason
        self.estimated_cost = estimated_cost

class Model(ABC):
    """Represents a specific configured LLM (e.g. 'gpt-5-mini')."""
    
    def __init__(self, name: str, config: dict, clients: dict, default_instruction: str = ""):
        self.name = name
        self.provider = config["provider"]
        self.model_id = config["model_id"]
        self.supports_vision = config.get("supports_vision", False)
        self.supports_search = config.get("supports_search", False)
        self.supports_image_gen = config.get("supports_image_gen", False)
        self.display_name = config.get("name", name)
        self.provider_display_name = config.get("provider_name", self.provider.capitalize())
        self.input_cost_per_m = float(config.get("input_cost_per_m", 0.15))
        self.output_cost_per_m = float(config.get("output_cost_per_m", 0.60))
        self.image_cost = float(config.get("image_cost", 0.035))
        
        # Resolve prompt inheritance
        override = config.get("system_instruction_override")
        additions = config.get("system_instruction_additions")
        
        if override is not None:
            system_inst = override
        elif additions is not None:
            add_str = "\n".join(additions) if isinstance(additions, list) else additions
            system_inst = f"{default_instruction}\n{add_str}".strip()
        else:
            system_inst = default_instruction
            
        if isinstance(system_inst, list):
            self.system_instruction_template = "\n".join(system_inst)
        else:
            self.system_instruction_template = system_inst
        self.clients = clients
        
    def _get_system_instructions(self, custom_prompt: typing.Optional[str] = None) -> str:
        today_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
        base = self.system_instruction_template.format(today_str=today_str) if self.system_instruction_template else ""
        if custom_prompt:
            base += f"\n\nSERVER CUSTOM INSTRUCTIONS:\n{custom_prompt.strip()}"
        return base

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int, has_image: bool = False) -> float:
        p_tok = prompt_tokens or 0
        c_tok = completion_tokens or 0
        in_cost = (p_tok / 1_000_000.0) * self.input_cost_per_m
        out_cost = (c_tok / 1_000_000.0) * self.output_cost_per_m
        img_cost = self.image_cost if has_image else 0.0
        return round(in_cost + out_cost + img_cost, 6)

    @abstractmethod
    async def _execute_query(self, contents: list, timeout: float = 15.0, custom_prompt: typing.Optional[str] = None, custom_key: typing.Optional[str] = None) -> AIResponse:
        pass


    async def query(self, contents: list, timeout: float = 15.0, custom_prompt: typing.Optional[str] = None, image_quota_checker: typing.Optional[typing.Callable] = None, custom_key: typing.Optional[str] = None) -> AIResponse:
        # 1. Run provider-specific text query
        response = await self._execute_query(contents, timeout, custom_prompt=custom_prompt, custom_key=custom_key)
        response.model_name = self.name
        response.display_name = self.display_name
        response.provider = self.provider
        
        # 2. Check for image generation tags
        if response.text:
            pattern = r"\[GENERATE_IMAGE:\s*(.*?)\]"
            match = re.search(pattern, response.text, re.IGNORECASE | re.DOTALL)
            
            if match:
                image_prompt = match.group(1).strip()
                # Strip the tag from the text
                stripped_text = re.sub(pattern, "", response.text, flags=re.IGNORECASE | re.DOTALL).strip()
                response.text = stripped_text if stripped_text else None
                    
                # Call image generation (only if supported)
                if self.supports_image_gen:
                    if image_quota_checker:
                        allowed, reason, reset_ts = await image_quota_checker()
                        if not allowed:
                            logger.info(f"Image generation blocked due to quota: {reason}")
                            reset_str = f" Next available <t:{reset_ts}:R>." if reset_ts else ""
                            limit_note = f"\n-# ⚠️ **Image generation limit reached:** {reason}{reset_str}"
                            response.text = (response.text or "") + limit_note
                            return response

                    logger.info(f"Image generation request detected in model response: {image_prompt}")
                    img_bytes, filename = await self._generate_image(image_prompt)
                    if img_bytes:
                        response.image_bytes = img_bytes
                        response.image_filename = filename
                    else:
                        raise AIError(f"Image generation failed for prompt: {image_prompt}")
                    
        # 3. Calculate and attach cost metadata
        in_tok = response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0
        out_tok = response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') and response.usage_metadata else 0
        response.estimated_cost = self.calculate_cost(in_tok, out_tok, has_image=bool(response.image_bytes))

        return response


    async def _generate_image(self, prompt: str) -> tuple:
        """Generates image using Grok Imagine (cost-optimized at $0.010), falling back to provider fallback."""
        client = self.clients.get("grok_openai")
        if client:
            try:
                logger.info(f"Generating image via Grok Imagine for prompt: {prompt}")
                response = await client.images.generate(
                    model="grok-imagine-image",
                    prompt=prompt,
                    n=1
                )
                if response and response.data:
                    item = response.data[0]
                    img_b64 = getattr(item, "b64_json", None)
                    if img_b64:
                        img_bytes = base64.b64decode(img_b64)
                        return img_bytes, "generated_image.png"
                    img_url = getattr(item, "url", None)
                    if img_url:
                        logger.info(f"Downloading generated image from: {img_url}")
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            async with session.get(img_url) as resp:
                                if resp.status == 200:
                                    img_bytes = await resp.read()
                                    return img_bytes, "generated_image.png"
                                else:
                                    logger.error(f"Failed to download image: HTTP {resp.status}")
            except Exception as e:
                logger.error(f"Grok Imagine failed, attempting native provider fallback: {e}")

        return await self._generate_image_fallback(prompt)

    async def _generate_image_fallback(self, prompt: str) -> tuple:
        """Override in subclasses that support native provider image generation as fallback."""
        return None, None

class GeminiModel(Model):
    
    async def _execute_query(self, contents: list, timeout: float = 15.0, custom_prompt: typing.Optional[str] = None, custom_key: typing.Optional[str] = None) -> AIResponse:
        if custom_key:
            from google import genai
            client = genai.Client(api_key=custom_key)
        else:
            client = self.clients.get("gemini")
            
        if not client:
            raise AIConfigurationError("Gemini client is not configured/available.")
            
        # 1. Filter vision
        if not self.supports_vision:
            query_contents = [item for item in contents if isinstance(item, str)]
        else:
            query_contents = contents

        # 2. Search grounding
        config_tools = None
        if self.supports_search:
            config_tools = [types.Tool(google_search=types.GoogleSearch())]
            
        try:
            config = types.GenerateContentConfig(
                system_instruction=self._get_system_instructions(custom_prompt),
                tools=config_tools,
                max_output_tokens=800
            )
            
            gemini_contents = []
            for item in query_contents:
                if isinstance(item, dict) and "data" in item:
                    gemini_contents.append(
                        types.Part.from_bytes(data=item["data"], mime_type=item.get("mime_type", "image/jpeg"))
                    )
                else:
                    gemini_contents.append(item)
            
            response = await client.aio.models.generate_content(
                model=self.model_id,
                contents=gemini_contents,
                config=config
            )
            
            if not response.text:
                raise AISafetyBlockedError("Gemini response blocked by safety filters.")
                
            prompt_tokens = (response.usage_metadata.prompt_token_count or 0) if response.usage_metadata else 0
            completion_tokens = (response.usage_metadata.candidates_token_count or 0) if response.usage_metadata else 0
            return AIResponse(response.text, prompt_tokens, completion_tokens, model_name=self.display_name, provider=self.provider)
            
        except APIError as e:
            code = getattr(e, 'code', None)
            msg = str(e)
            if code == 429 or "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                raise AIRateLimitError("Gemini API rate limit exceeded") from e
            elif code == 503 or code == 500 or "503" in msg or "UNAVAILABLE" in msg:
                raise AIServiceUnavailableError("Gemini service unavailable") from e
            else:
                raise AIError(f"Gemini API error: {e}") from e
        except AISafetyBlockedError as e:
            raise e
        except Exception as e:
            raise AIError(f"Unexpected error in Gemini provider: {e}") from e

    async def _generate_image_fallback(self, prompt: str) -> tuple:
        client = self.clients.get("gemini")
        if not client:
            return None, None
        try:
            logger.info(f"Generating image via Gemini for prompt: {prompt}")
            response = await client.aio.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=prompt
            )
            if response and response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if getattr(part, "inline_data", None) and part.inline_data.data:
                        img_bytes = part.inline_data.data
                        mime = getattr(part.inline_data, "mime_type", "image/png")
                        ext = "png" if "png" in mime.lower() else "jpg"
                        return img_bytes, f"generated_image.{ext}"
        except Exception as e:
            logger.error(f"Gemini Image generation failed: {e}")
        return None, None

class OpenAIModel(Model):
    def _convert_prompt(self, contents: list, is_responses_api: bool = False, custom_prompt: typing.Optional[str] = None) -> list:
        messages = [
            {"role": "system", "content": self._get_system_instructions(custom_prompt)}
        ]
        openai_contents = []
        for item in contents:
            if isinstance(item, str):
                if item and item.strip():
                    text_type = "input_text" if is_responses_api else "text"
                    openai_contents.append({"type": text_type, "text": item})
            elif hasattr(item, 'inline_data') and item.inline_data:
                img_base64 = base64.b64encode(item.inline_data.data).decode('utf-8')
                mime_type = item.inline_data.mime_type
                if is_responses_api:
                    openai_contents.append({
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{img_base64}"
                    })
                else:
                    openai_contents.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{img_base64}"
                        }
                    })
            elif isinstance(item, dict) and "data" in item:
                img_base64 = base64.b64encode(item["data"]).decode('utf-8')
                mime_type = item.get("mime_type", "image/jpeg")
                if is_responses_api:
                    openai_contents.append({
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{img_base64}"
                    })
                else:
                    openai_contents.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{img_base64}"
                        }
                    })
        if not openai_contents:
            text_type = "input_text" if is_responses_api else "text"
            openai_contents.append({"type": text_type, "text": "Analyze this."})
        messages.append({"role": "user", "content": openai_contents})
        return messages

    async def _execute_query(self, contents: list, timeout: float = 15.0, custom_prompt: typing.Optional[str] = None, custom_key: typing.Optional[str] = None) -> AIResponse:
        if custom_key:
            import openai
            client = openai.AsyncOpenAI(api_key=custom_key)
        else:
            client = self.clients.get("openai")
            
        if not client:
            raise AIConfigurationError("OpenAI client is not configured/available.")

        if not self.supports_vision:
            query_contents = [item for item in contents if isinstance(item, str)]
        else:
            query_contents = contents

        try:
            # Use Responses API if web search is enabled and supported by the SDK version
            if self.supports_search and hasattr(client, "responses"):
                messages = self._convert_prompt(query_contents, is_responses_api=True)
                response = await client.responses.create(
                    model=self.model_id,
                    input=messages,
                    tools=[{"type": "web_search"}]
                )
                text = response.output_text
                prompt_tokens = response.usage.input_tokens if hasattr(response, 'usage') and response.usage else 0
                completion_tokens = response.usage.output_tokens if hasattr(response, 'usage') and response.usage else 0
            else:
                messages = self._convert_prompt(query_contents, is_responses_api=False, custom_prompt=custom_prompt)
                response = await client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    max_completion_tokens=800,
                    temperature=0.6
                )
                text = response.choices[0].message.content
                prompt_tokens = response.usage.prompt_tokens if response.usage else 0
                completion_tokens = response.usage.completion_tokens if response.usage else 0
            
            if not text:
                raise AISafetyBlockedError("OpenAI response blocked by safety filters.")
            
            return AIResponse(text, prompt_tokens, completion_tokens, model_name=self.display_name, provider=self.provider)
        except openai.RateLimitError as e:
            raise AIRateLimitError("OpenAI rate limit exceeded") from e
        except (openai.APIConnectionError, openai.APITimeoutError) as e:
            raise AIServiceUnavailableError("OpenAI connection or timeout error") from e
        except openai.AuthenticationError as e:
            raise AIConfigurationError("OpenAI invalid API key or configuration") from e
        except openai.APIStatusError as e:
            if e.status_code == 429:
                raise AIRateLimitError("OpenAI rate limit exceeded") from e
            elif e.status_code >= 500:
                raise AIServiceUnavailableError(f"OpenAI service unavailable (status {e.status_code})") from e
            else:
                raise AIError(f"OpenAI API status error: {e}") from e
        except AISafetyBlockedError as e:
            raise e
        except Exception as e:
            raise AIError(f"Unexpected error in OpenAI provider: {e}") from e

    async def _generate_image_fallback(self, prompt: str) -> tuple:
        client = self.clients.get("openai")
        if not client:
            return None, None
        
        try:
            logger.info(f"Generating image via OpenAI gpt-image-2 for prompt: {prompt}")
            dalle_response = await client.images.generate(
                model="gpt-image-2",
                prompt=prompt,
                n=1
            )
            if dalle_response and dalle_response.data:
                item = dalle_response.data[0]
                
                # Check for b64_json first (default for gpt-image-2)
                img_b64 = getattr(item, "b64_json", None)
                if img_b64:
                    img_bytes = base64.b64decode(img_b64)
                    return img_bytes, "generated_image.png"
                
                # Fallback to url if provided
                img_url = getattr(item, "url", None)
                if img_url:
                    logger.info(f"Downloading generated image from: {img_url}")
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(img_url) as resp:
                            if resp.status == 200:
                                img_bytes = await resp.read()
                                return img_bytes, "generated_image.png"
                            else:
                                logger.error(f"Failed to download image: HTTP {resp.status}")
        except Exception as e:
            logger.error(f"OpenAI Image generation failed: {e}")
            
        return None, None

class AnthropicModel(Model):
    def _convert_prompt(self, contents: list) -> list:
        anthropic_contents = []
        for item in contents:
            if isinstance(item, str):
                if item and item.strip():
                    anthropic_contents.append({"type": "text", "text": item})
            elif hasattr(item, 'inline_data') and item.inline_data:
                img_base64 = base64.b64encode(item.inline_data.data).decode('utf-8')
                mime_type = item.inline_data.mime_type
                anthropic_contents.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": img_base64
                    }
                })
            elif isinstance(item, dict) and "data" in item:
                img_base64 = base64.b64encode(item["data"]).decode('utf-8')
                mime_type = item.get("mime_type", "image/jpeg")
                anthropic_contents.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": img_base64
                    }
                })
        messages = []
        if not anthropic_contents:
            anthropic_contents.append({"type": "text", "text": "Analyze this."})
        messages.append({"role": "user", "content": anthropic_contents})
        return messages

    async def _execute_query(self, contents: list, timeout: float = 15.0, custom_prompt: typing.Optional[str] = None, custom_key: typing.Optional[str] = None) -> AIResponse:
        if custom_key:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=custom_key)
        else:
            client = self.clients.get("anthropic")
            
        if not client:
            raise AIConfigurationError("Anthropic client is not configured/available.")

        if not self.supports_vision:
            query_contents = [item for item in contents if isinstance(item, str)]
        else:
            query_contents = contents

        try:
            messages = self._convert_prompt(query_contents)
            config_tools = []
            if self.supports_search:
                config_tools.append({
                    "type": "web_search_20250305",
                    "name": "web_search"
                })
                
            response = await client.messages.create(
                model=self.model_id,
                system=self._get_system_instructions(custom_prompt),
                messages=messages,
                max_tokens=800,
                temperature=0.6,
                tools=config_tools if config_tools else None
            )
            
            text = ""
            for block in response.content:
                if block.type == "text":
                    text += block.text
                    
            if not text:
                raise AISafetyBlockedError("Anthropic response blocked by safety filters.")
            prompt_tokens = response.usage.input_tokens if response.usage else 0
            completion_tokens = response.usage.output_tokens if response.usage else 0
            
            return AIResponse(text, prompt_tokens, completion_tokens, model_name=self.display_name, provider=self.provider)
        except anthropic.RateLimitError as e:
            raise AIRateLimitError("Anthropic rate limit exceeded") from e
        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as e:
            raise AIServiceUnavailableError("Anthropic connection or timeout error") from e
        except anthropic.AuthenticationError as e:
            raise AIConfigurationError("Anthropic invalid API key or configuration") from e
        except anthropic.APIStatusError as e:
            if e.status_code == 429:
                raise AIRateLimitError("Anthropic rate limit exceeded") from e
            elif e.status_code >= 500:
                raise AIServiceUnavailableError(f"Anthropic service unavailable (status {e.status_code})") from e
            else:
                raise AIError(f"Anthropic API status error: {e}") from e
        except AISafetyBlockedError as e:
            raise e
        except Exception as e:
            raise AIError(f"Unexpected error in Anthropic provider: {e}") from e

class GrokModel(Model):
    async def _execute_query(self, contents: list, timeout: float = 15.0, custom_prompt: typing.Optional[str] = None, custom_key: typing.Optional[str] = None) -> AIResponse:
        if custom_key:
            import openai
            client = openai.AsyncOpenAI(api_key=custom_key, base_url="https://api.x.ai/v1")
            # Fallback to OpenAI-compatible interface for custom keys
            messages = [
                {"role": "system", "content": self._get_system_instructions(custom_prompt)}
            ]
            for item in contents:
                if isinstance(item, str):
                    messages.append({"role": "user", "content": item})
            try:
                response = await client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    max_completion_tokens=800,
                    temperature=0.6
                )
                text = response.choices[0].message.content
                prompt_tokens = response.usage.prompt_tokens if response.usage else 0
                completion_tokens = response.usage.completion_tokens if response.usage else 0
                return AIResponse(text, prompt_tokens, completion_tokens, model_name=self.display_name, provider=self.provider)
            except Exception as e:
                raise AIError(f"Grok custom key query failed: {e}") from e

        client = self.clients.get("grok")
        if not client:
            raise AIConfigurationError("Grok client is not configured/available.")

        if not self.supports_vision:
            query_contents = [item for item in contents if isinstance(item, str)]
        else:
            query_contents = contents

        try:
            config_tools = []
            if self.supports_search:
                try:
                    from xai_sdk.tools import web_search
                    config_tools.append(web_search())
                except ImportError:
                    logger.warning("xai_sdk.tools.web_search import failed. Search disabled for Grok.")

            chat = client.chat.create(
                model=self.model_id,
                tools=config_tools if config_tools else None
            )
            chat.append(system(self._get_system_instructions(custom_prompt)))
            
            user_args = []
            for item in query_contents:
                if isinstance(item, str):
                    user_args.append(item)
                elif isinstance(item, dict) and "data" in item:
                    img_base64 = base64.b64encode(item["data"]).decode('utf-8')
                    mime_type = item.get("mime_type", "image/jpeg")
                    user_args.append(image(image_url=f"data:{mime_type};base64,{img_base64}"))
                    
            chat.append(user(*user_args))
            response = await chat.sample()
            
            text = response.content
            if not text:
                raise AISafetyBlockedError("Grok response blocked by safety filters.")
            prompt_tokens = response.usage.prompt_tokens if hasattr(response, 'usage') and response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            
            return AIResponse(text, prompt_tokens, completion_tokens, model_name=self.display_name, provider=self.provider)
        except Exception as e:
            msg = str(e)
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                raise AIRateLimitError("Grok rate limit exceeded") from e
            elif "UNAVAILABLE" in msg or "DEADLINE_EXCEEDED" in msg or "503" in msg:
                raise AIServiceUnavailableError("Grok service connection error or timeout") from e
            elif "UNAUTHENTICATED" in msg or "PERMISSION_DENIED" in msg:
                raise AIConfigurationError("Grok invalid API key or configuration") from e
            else:
                raise AIError(f"Grok API error: {e}") from e

    async def _generate_image_fallback(self, prompt: str) -> tuple:
        client = self.clients.get("grok_openai")
        if not client:
            return None, None
        
        try:
            logger.info(f"Generating image via Grok Imagine for prompt: {prompt}")
            response = await client.images.generate(
                model="grok-imagine-image",
                prompt=prompt,
                n=1
            )
            if response and response.data:
                item = response.data[0]
                
                # Check for b64_json first
                img_b64 = getattr(item, "b64_json", None)
                if img_b64:
                    img_bytes = base64.b64decode(img_b64)
                    return img_bytes, "generated_image.png"
                
                # Check for url (standard for grok-imagine-image)
                img_url = getattr(item, "url", None)
                if img_url:
                    logger.info(f"Downloading generated image from: {img_url}")
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(img_url) as resp:
                            if resp.status == 200:
                                img_bytes = await resp.read()
                                return img_bytes, "generated_image.png"
                            else:
                                logger.error(f"Failed to download image: HTTP {resp.status}")
        except Exception as e:
            logger.error(f"Grok Image generation failed: {e}")
            
        return None, None

class DeepSeekModel(OpenAIModel):
    """DeepSeek LLM Integration via OpenAI-compatible endpoint."""
    async def _execute_query(self, contents: list, timeout: float = 15.0, custom_prompt: typing.Optional[str] = None, custom_key: typing.Optional[str] = None) -> AIResponse:
        if custom_key:
            import openai
            client = openai.AsyncOpenAI(api_key=custom_key, base_url="https://api.deepseek.com")
        else:
            client = self.clients.get("deepseek")
            
        if not client:
            raise AIConfigurationError("DeepSeek client is not configured/available.")
        
        query_contents = contents if self.supports_vision else [item for item in contents if isinstance(item, str)]
        try:
            messages = self._convert_prompt(query_contents, is_responses_api=False, custom_prompt=custom_prompt)
            response = await client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                max_completion_tokens=800,
                temperature=0.6
            )
            text = response.choices[0].message.content
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            
            if not text:
                raise AISafetyBlockedError("DeepSeek response blocked or empty.")
            
            return AIResponse(text, prompt_tokens, completion_tokens, model_name=self.display_name, provider=self.provider)
        except openai.RateLimitError as e:
            raise AIRateLimitError("DeepSeek rate limit exceeded") from e
        except (openai.APIConnectionError, openai.APITimeoutError) as e:
            raise AIServiceUnavailableError("DeepSeek connection or timeout error") from e
        except openai.AuthenticationError as e:
            raise AIConfigurationError("DeepSeek invalid API key or configuration") from e
        except openai.APIStatusError as e:
            if e.status_code == 429:
                raise AIRateLimitError("DeepSeek rate limit exceeded") from e
            elif e.status_code >= 500:
                raise AIServiceUnavailableError(f"DeepSeek service unavailable (status {e.status_code})") from e
            else:
                raise AIError(f"DeepSeek API status error: {e}") from e
        except Exception as e:
            raise AIError(f"Unexpected error in DeepSeek provider: {e}") from e


class GLMModel(OpenAIModel):
    """GLM (Z.ai / Zhipu) LLM Integration via OpenAI-compatible endpoint."""
    async def _execute_query(self, contents: list, timeout: float = 15.0, custom_prompt: typing.Optional[str] = None, custom_key: typing.Optional[str] = None) -> AIResponse:
        if custom_key:
            import openai
            client = openai.AsyncOpenAI(api_key=custom_key, base_url="https://open.bigmodel.cn/api/paas/v4")
        else:
            client = self.clients.get("glm")
            
        if not client:
            raise AIConfigurationError("GLM client is not configured/available.")
        
        query_contents = contents if self.supports_vision else [item for item in contents if isinstance(item, str)]
        try:
            messages = self._convert_prompt(query_contents, is_responses_api=False, custom_prompt=custom_prompt)
            response = await client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                max_completion_tokens=800,
                temperature=0.6
            )
            text = response.choices[0].message.content
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            
            if not text:
                raise AISafetyBlockedError("GLM response blocked or empty.")
            
            return AIResponse(text, prompt_tokens, completion_tokens, model_name=self.display_name, provider=self.provider)
        except openai.RateLimitError as e:
            raise AIRateLimitError("GLM rate limit exceeded") from e
        except (openai.APIConnectionError, openai.APITimeoutError) as e:
            raise AIServiceUnavailableError("GLM connection or timeout error") from e
        except openai.AuthenticationError as e:
            raise AIConfigurationError("GLM invalid API key or configuration") from e
        except openai.APIStatusError as e:
            if e.status_code == 429:
                raise AIRateLimitError("GLM rate limit exceeded") from e
            elif e.status_code >= 500:
                raise AIServiceUnavailableError(f"GLM service unavailable (status {e.status_code})") from e
            else:
                raise AIError(f"GLM API status error: {e}") from e
        except Exception as e:
            raise AIError(f"Unexpected error in GLM provider: {e}") from e


PROVIDER_MAP = {
    "gemini": GeminiModel,
    "openai": OpenAIModel,
    "anthropic": AnthropicModel,
    "grok": GrokModel,
    "deepseek": DeepSeekModel,
    "glm": GLMModel
}

class ModelManager:
    """Holds active API client objects and performs the failover loop."""
    def __init__(self):
        self.clients = {}
        self.models = {}
        self.pipeline = []
        
        # Initialize Google Client
        gemini_key = os.getenv("GEMINI_API_KEY")
        gemini_proxy_url = os.getenv("GEMINI_PROXY_URL") or os.getenv("GEMINI_BASE_URL")
        if gemini_key:
            from google import genai
            http_opts = {"base_url": gemini_proxy_url.rstrip("/")} if gemini_proxy_url else None
            self.clients["gemini"] = genai.Client(api_key=gemini_key, http_options=http_opts)
        else:
            logger.error("GEMINI_API_KEY not found in environment variables.")

        # Initialize OpenAI Client
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            import openai
            self.clients["openai"] = openai.AsyncOpenAI(api_key=openai_key)
        else:
            logger.warning("OPENAI_API_KEY not found in environment variables.")

        # Initialize Anthropic Client
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            import anthropic
            self.clients["anthropic"] = anthropic.AsyncAnthropic(api_key=anthropic_key)
        else:
            logger.warning("ANTHROPIC_API_KEY not found in environment variables.")

        # Initialize Grok Client
        grok_key = os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")
        if grok_key:
            import xai_sdk
            self.clients["grok"] = xai_sdk.AsyncClient(api_key=grok_key)
            import openai
            self.clients["grok_openai"] = openai.AsyncOpenAI(api_key=grok_key, base_url="https://api.x.ai/v1")
        else:
            logger.warning("GROK_API_KEY / XAI_API_KEY not found in environment variables.")

        # Initialize DeepSeek Client
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            import openai
            self.clients["deepseek"] = openai.AsyncOpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
        else:
            logger.warning("DEEPSEEK_API_KEY not found in environment variables.")

        # Initialize GLM Client
        glm_key = os.getenv("GLM_API_KEY") or os.getenv("ZHIPU_API_KEY") or os.getenv("ZAI_API_KEY")
        if glm_key:
            import openai
            self.clients["glm"] = openai.AsyncOpenAI(api_key=glm_key, base_url="https://open.bigmodel.cn/api/paas/v4")
        else:
            logger.warning("GLM_API_KEY / ZHIPU_API_KEY not found in environment variables.")
            
        default_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.json")
        if os.path.exists(default_config):
            self.load_config(default_config)

    def load_config(self, filepath: str):
        with open(filepath, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            
        self.models = {}
        self.pipeline = config_data.get("pipeline", ["gemini-3.8-flash", "gemini-3.7-flash"])
        default_inst_list = config_data.get("default_instruction", [])
        default_inst = "\n".join(default_inst_list) if isinstance(default_inst_list, list) else default_inst_list
        
        for name, config in config_data.items():
            if name in ["default_instruction", "pipeline"]:
                continue
            provider = config.get("provider")
            model_class = PROVIDER_MAP.get(provider)
            if not model_class:
                logger.warning(f"Unsupported or missing provider '{provider}' for model '{name}'. Skipping.")
                continue
            self.models[name] = model_class(name, config, self.clients, default_instruction=default_inst)

    async def execute(self, guild_settings: dict, contents: list, image_quota_checker: typing.Optional[typing.Callable] = None) -> AIResponse:
        """Consolidates dynamic resilient failover pipeline execution (with BYOK support)."""
        from cogs.utils.exceptions import (
            AIError,
            AIRateLimitError,
            AIServiceUnavailableError,
            AISafetyBlockedError,
            AIConfigurationError
        )
        
        # 1. Custom server prompt add-on (for Premium / BYOK)
        has_byok = bool(guild_settings.get("byok_enabled", DefaultSettings.BYOK_ENABLED)) and any(guild_settings.get(k) for k in ["byok_gemini_key", "byok_xai_key", "byok_openai_key", "byok_anthropic_key", "byok_deepseek_key", "byok_glm_key"])
        custom_prompt = guild_settings.get("custom_prompt") if (guild_settings.get("is_premium") or has_byok) else None
        
        # 2. Configurable Dynamic Pipeline (Custom 2-Model BYOK Pipeline or Default Managed Pipeline)
        if has_byok and (guild_settings.get("byok_primary_model") or guild_settings.get("byok_fallback_model")):
            model_names = []
            if guild_settings.get("byok_primary_model"):
                model_names.append(guild_settings["byok_primary_model"])
            if guild_settings.get("byok_fallback_model") and guild_settings["byok_fallback_model"] not in model_names:
                model_names.append(guild_settings["byok_fallback_model"])
            if not model_names:
                model_names = self.pipeline if self.pipeline else ["gemini-3.8-flash", "gemini-3.7-flash"]
        else:
            model_names = self.pipeline if self.pipeline else ["gemini-3.8-flash", "gemini-3.7-flash"]
        
        timeout = float(guild_settings.get("llm_timeout", 15))
        
        provider_key_map = {
            "gemini": "byok_gemini_key",
            "openai": "byok_openai_key",
            "anthropic": "byok_anthropic_key",
            "grok": "byok_xai_key",
            "deepseek": "byok_deepseek_key",
            "glm": "byok_glm_key"
        }
        
        last_exception = None
        for name in model_names:
            model = self.models.get(name)
            if not model:
                logger.warning(f"Model '{name}' requested but not found in registry. Skipping.")
                continue
                
            try:
                custom_key_col = provider_key_map.get(model.provider)
                custom_key = guild_settings.get(custom_key_col) if (has_byok and custom_key_col) else None

                actual_timeout = timeout + 90.0 if model.supports_image_gen else timeout
                logger.info(f"Attempting response using model: {name} (timeout: {actual_timeout}s, byok={'yes' if custom_key else 'no'})")
                response = await asyncio.wait_for(
                    model.query(contents, timeout=actual_timeout, custom_prompt=custom_prompt, image_quota_checker=image_quota_checker, custom_key=custom_key),
                    timeout=float(actual_timeout)
                )
                if name != model_names[0]:
                    response.failover_occurred = True
                    response.failover_reason = str(last_exception) if last_exception else f"Primary model '{model_names[0]}' failed"
                return response
            except asyncio.TimeoutError as e:
                last_exception = AIServiceUnavailableError(f"Model '{name}' timed out after {actual_timeout}s", original_error=e)
                logger.warning(f"Model '{name}' timed out. Trying next backup...")
            except (AIRateLimitError, AIServiceUnavailableError) as e:
                last_exception = e
                logger.warning(f"Model '{name}' failed with transient error: {e}. Trying next backup...")
            except (AISafetyBlockedError, AIConfigurationError) as e:
                logger.error(f"Model '{name}' failed with critical error: {e}. Aborting failover.")
                raise e
            except Exception as e:
                last_exception = AIError(f"Model '{name}' failed with unexpected error: {e}")
                logger.warning(f"Model '{name}' failed with unexpected error: {e}. Trying next backup...")
                
        raise last_exception or AIError("No configured models succeeded in the pipeline.")

class ContextManager:
    """Formats chat transcripts and extracts file attachments as raw bytes."""
    HISTORY_ATTACHMENT_LIMIT = 3
    
    @staticmethod
    def _is_image(attachment: discord.Attachment) -> bool:
        if attachment.content_type:
            return attachment.content_type.startswith("image/")
        filename = attachment.filename.lower()
        return filename.endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif', '.heic', '.bmp'))

    @staticmethod
    def _is_text_file(attachment: discord.Attachment) -> bool:
        if attachment.content_type:
            if attachment.content_type.startswith("text/"):
                return True
            if attachment.content_type in ["application/json", "application/javascript"]:
                return True
        filename = attachment.filename.lower()
        text_extensions = (
            '.txt', '.py', '.js', '.ts', '.json', '.csv', '.md', '.html', 
            '.css', '.yml', '.yaml', '.ini', '.xml', '.log', '.sh', '.bat', '.sql'
        )
        return filename.endswith(text_extensions)

    @staticmethod
    def _get_mime_type(attachment: discord.Attachment) -> str:
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

    @classmethod
    def format_history(cls, message_list: list, bot_user: typing.Optional[typing.Union[discord.User, discord.ClientUser]] = None) -> str:
        result = []
        bot_id = bot_user.id if bot_user else None
        bot_name = getattr(bot_user, "display_name", "spl1ceAI") if bot_user else "spl1ceAI"
        
        for message in message_list:
            author_id = getattr(message.author, "id", None)
            sender = getattr(message.author, "display_name", str(message.author))
            content = message.content or ""
            
            # Explicitly mark bot's own past responses vs other human users
            is_self = (author_id == bot_id) if bot_id else getattr(message.author, "bot", False)
            speaker_tag = f"You ({bot_name})" if is_self else f"User: {sender}"
            
            attachments_str = ""
            if message.attachments:
                att_types = []
                for att in message.attachments:
                    if cls._is_image(att):
                        att_types.append("[Image Attachment]")
                    else:
                        att_types.append(f"[{att.filename}]")
                attachments_str = " " + " ".join(att_types)

            reply_note = ""
            if message.reference is not None:
                ref_message = message.reference.resolved
                if ref_message is not None and not isinstance(ref_message, discord.DeletedReferencedMessage): 
                    ref_author = getattr(ref_message.author, "display_name", str(ref_message.author))
                    reply_note = f" (replying to {ref_author})"
            
            msg_text = (content + attachments_str).strip()
            if msg_text:
                result.append(f"[{speaker_tag}]{reply_note}: {msg_text}")
        return "\n".join(result)

    @classmethod
    async def prepare_contents(cls, message: discord.Message, history: list, prompt: str, slash_attachments: list = None, enable_vision: bool = True, bot_user: typing.Optional[typing.Union[discord.User, discord.ClientUser]] = None) -> list:
        contents = []
        processed_ids = set()
        
        # 1. Gather all attachments to inspect
        attachments_to_read = []
        
        # Add slash command parameters
        if slash_attachments:
            attachments_to_read.extend(slash_attachments)
            
        # Add trigger message attachments
        if message and message.attachments:
            attachments_to_read.extend(message.attachments)
            
        # Add referenced reply message attachments
        if message and message.reference and message.reference.message_id:
            try:
                ref_msg = message.reference.resolved
                if not ref_msg or isinstance(ref_msg, discord.DeletedReferencedMessage):
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                if ref_msg and ref_msg.attachments:
                    attachments_to_read.extend(ref_msg.attachments)
            except Exception as e:
                logger.error(f"Failed to resolve reply reference: {e}")
                
        # Add attachments from recent history (only if vision enabled)
        if enable_vision:
            recent_history = history[-cls.HISTORY_ATTACHMENT_LIMIT:] if history else []
            for h_msg in recent_history:
                if h_msg.attachments:
                    attachments_to_read.extend(h_msg.attachments)

        # 2. Process gathered attachments (de-duplicating by ID)
        for att in attachments_to_read:
            att_id = getattr(att, "id", None)
            if att_id:
                if att_id in processed_ids:
                    continue
                processed_ids.add(att_id)
            
            # Case A: Image attachment (only process if vision is enabled)
            if cls._is_image(att):
                if enable_vision:
                    try:
                        img_bytes = await att.read()
                        contents.append({"data": img_bytes, "mime_type": cls._get_mime_type(att)})
                    except Exception as e:
                        logger.error(f"Failed to read image attachment {att.filename}: {e}")
                    
            # Case B: Text / Code attachment (.py, .txt, .json, etc.)
            elif cls._is_text_file(att):
                try:
                    file_bytes = await att.read()
                    file_text = file_bytes.decode('utf-8', errors='ignore')
                    # Prepend/append text file context directly to prompt
                    contents.append(
                        f"\n--- Attached File Context: {att.filename} ---\n"
                        f"{file_text}\n"
                        f"--------------------------------------------\n"
                    )
                except Exception as e:
                    logger.error(f"Failed to read text attachment {att.filename}: {e}")
                    
        # 3. Add the formatted context and prompt with clean structure
        formatted_history = cls.format_history(history, bot_user=bot_user)
        if formatted_history:
            full_prompt = (
                f"<conversation_history>\n"
                f"{formatted_history}\n"
                f"</conversation_history>\n\n"
                f"{prompt}"
            )
        else:
            full_prompt = prompt
            
        contents.append(full_prompt)
        
        return contents

class ResponseHandler:
    """Manages output formatting, character limit enforcement, and Discord reply delivery."""
    def __init__(self, bot=None):
        self.bot = bot

    async def orchestrate_reply(self, message_or_ctx, response: AIResponse):
        if response.text and "[IGNORE]" in response.text:
            logger.info("Ignored message because model returned [IGNORE]")
            return
            
        clean_text = response.text
        
        footer_show_icon = DefaultSettings.FOOTER_SHOW_ICON
        footer_show_name = DefaultSettings.FOOTER_SHOW_NAME
        footer_show_tokens = DefaultSettings.FOOTER_SHOW_TOKENS
        footer_show_latency = DefaultSettings.FOOTER_SHOW_LATENCY
        reply_ping = True

        guild_id = message_or_ctx.guild.id if getattr(message_or_ctx, 'guild', None) else None
        if self.bot and guild_id:
            guild_settings = self.bot.settings_cache.get(guild_id, {})
            footer_show_icon = guild_settings.get("footer_show_icon", DefaultSettings.FOOTER_SHOW_ICON)
            footer_show_name = guild_settings.get("footer_show_name", DefaultSettings.FOOTER_SHOW_NAME)
            footer_show_tokens = guild_settings.get("footer_show_tokens", DefaultSettings.FOOTER_SHOW_TOKENS)
            footer_show_latency = guild_settings.get("footer_show_latency", DefaultSettings.FOOTER_SHOW_LATENCY)
            reply_ping = guild_settings.get("reply_ping", DefaultSettings.REPLY_PING) == 1

        file = None
        if response.image_bytes:
            file = discord.File(io.BytesIO(response.image_bytes), filename=response.image_filename or "generated_image.jpg")

        if clean_text:
            # 1. Resolve Provider Icon
            provider = (getattr(response, "provider", "") or "").lower()
            model_name_lower = (response.model_name or "").lower()
            if "gemini" in provider or "gemini" in model_name_lower or "google" in provider:
                provider_icon = Emojis.GEMINI
            elif "openai" in provider or "gpt" in model_name_lower or "chatgpt" in provider:
                provider_icon = Emojis.CHATGPT
            elif "anthropic" in provider or "claude" in model_name_lower:
                provider_icon = Emojis.CLAUDE
            elif "xai" in provider or "grok" in model_name_lower:
                provider_icon = Emojis.GROK
            elif "deepseek" in provider or "deepseek" in model_name_lower:
                provider_icon = Emojis.DEEPSEEK
            else:
                provider_icon = "🤖"

            # 2. Format Latency
            latency_ms = getattr(response, "latency_ms", None)
            latency_str = ""
            if latency_ms is not None and latency_ms > 0:
                if latency_ms >= 1000:
                    latency_str = f"{latency_ms / 1000.0:.1f}s"
                else:
                    latency_str = f"{latency_ms}ms"

            # 3. Format Token Count
            in_tok = 0
            out_tok = 0
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                in_tok = response.usage_metadata.prompt_token_count or 0
                out_tok = response.usage_metadata.candidates_token_count or 0
            total_tok = in_tok + out_tok
            token_str = f"{total_tok:,} tokens" if total_tok > 0 else ""

            # 4. Construct Footer Elements based on active toggles
            parts = []
            display_model = getattr(response, "display_name", None) or response.model_name
            name_part = display_model if (display_model and footer_show_name == 1) else ""
            icon_part = provider_icon if (footer_show_icon == 1) else ""

            if icon_part and name_part:
                parts.append(f"{icon_part} {name_part}")
            elif icon_part:
                parts.append(f"{icon_part}")
            elif name_part:
                parts.append(f"{name_part}")

            if token_str and footer_show_tokens == 1:
                parts.append(token_str)
            if latency_str and footer_show_latency == 1:
                parts.append(latency_str)

            footer_text = " • ".join(parts)
            suffix = f"\n-# {footer_text}" if footer_text else ""
            max_body = 2000 - len(suffix)
            if len(clean_text) > max_body:
                clean_text = clean_text[:max_body - 3] + "..."
            clean_text = f"{clean_text}{suffix}"

            await message_or_ctx.reply(clean_text, file=file, mention_author=reply_ping)
        elif file:
            await message_or_ctx.reply(file=file, mention_author=reply_ping)
