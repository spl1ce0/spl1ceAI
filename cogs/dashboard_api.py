import logging
import json
import discord
from aiohttp import web
from typing import Optional
from cogs.utils.constants import DefaultSettings

logger = logging.getLogger(__name__)


@web.middleware
async def cors_middleware(request: web.Request, handler):
    """Handles CORS preflight and headers for web dashboard integration."""
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        try:
            response = await handler(request)
        except web.HTTPException as ex:
            response = ex
        except Exception as e:
            logger.error(f"Unhandled error in dashboard API handler: {e}", exc_info=True)
            response = web.json_response({"error": "Internal server error"}, status=500)

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept"
    return response


async def verify_user_guild_admin(token: str, guild_id: int, bot) -> bool:
    """Verifies that the user holding the Discord OAuth2 bearer token has Administrator or Manage Guild permissions, or is the bot owner."""
    if not token:
        return False

    try:
        # Check if the user is the bot owner
        try:
            async with bot.web_client.get(
                "https://discord.com/api/v10/users/@me",
                headers={"Authorization": f"Bearer {token}"}
            ) as me_resp:
                if me_resp.status == 200:
                    user_info = await me_resp.json()
                    user_id = int(user_info.get("id", 0))
                    if getattr(bot, "owner_id", None) and user_id == bot.owner_id:
                        return True
                    if getattr(bot, "owner_ids", None) and user_id in bot.owner_ids:
                        return True
                    if hasattr(bot, "is_owner"):
                        try:
                            if await bot.is_owner(discord.Object(id=user_id)):
                                return True
                        except Exception:
                            pass
        except Exception as e:
            logger.debug(f"Bot owner check failed: {e}")

        # Check through Discord API using user's bearer token
        async with bot.web_client.get(
            "https://discord.com/api/v10/users/@me/guilds",
            headers={"Authorization": f"Bearer {token}"}
        ) as resp:
            if resp.status != 200:
                logger.warning(f"Failed to verify Discord token: status {resp.status}")
                return False
            guilds = await resp.json()
            for g in guilds:
                if str(g.get("id")) == str(guild_id):
                    perms = int(g.get("permissions", 0))
                    is_admin = bool(perms & 0x8)
                    is_manage = bool(perms & 0x20)
                    is_owner = bool(g.get("owner", False))
                    return is_admin or is_manage or is_owner
            return False
    except Exception as e:
        logger.error(f"Error validating user guild permissions: {e}")
        return False


async def get_guild_settings_dict(bot, guild_id: int) -> dict:
    """Retrieves live settings for a guild, ensuring sync with SQLite database."""
    try:
        data = await bot.db_manager.get_guild_settings(guild_id)
        if data:
            bot.settings_cache[guild_id] = data
            return data
    except Exception as e:
        logger.error(f"Error fetching settings for guild {guild_id} from DB: {e}")

    settings = bot.settings_cache.get(guild_id)
    if not settings:
        settings = DefaultSettings.get_defaults_dict()
        bot.settings_cache[guild_id] = settings
    return settings


async def handle_settings_schema(request: web.Request) -> web.Response:
    """Returns the canonical settings schema for dynamic dashboard rendering."""
    schema = {
        "version": "1.0.0",
        "defaults": DefaultSettings.get_defaults_dict(),
        "categories": [
            {"id": "general", "label": "General", "icon": "Sliders"},
            {"id": "ai", "label": "AI", "icon": "Bot"},
            {"id": "logs", "label": "Chat Logs", "icon": "FileText"},
            {"id": "plan", "label": "Server Plan", "icon": "Crown"},
        ],
        "settings": [
            {
                "id": "prefix",
                "category": "general",
                "name": "Command Prefix",
                "description": "Prefix used to trigger bot commands.",
                "type": "text_modal",
                "default": DefaultSettings.PREFIX,
                "subpage": "prefix",
                "accessoryLabel": "Edit",
                "accessoryIcon": "Edit3",
            },
            {
                "id": "cbc_enabled",
                "channelKey": "cbc_channel",
                "category": "ai",
                "name": "Chat Bot Channel",
                "description": "Responds automatically to messages in this channel without needing mentions.",
                "type": "channel_toggle",
                "default": False,
                "defaultChannel": "general",
            },
            {
                "id": "custom_prompt",
                "category": "ai",
                "name": "System Instructions",
                "description": "Set custom system instructions or guidelines for the AI.",
                "type": "subpage_button",
                "subpage": "prompt",
                "accessoryLabel": "Configure",
                "accessoryIcon": "ChevronRight",
            },
            {
                "id": "byok",
                "category": "ai",
                "name": "Bring Your Own Key (BYOK)",
                "description": "Use your own API keys for unmetered AI usage and custom models.",
                "type": "subpage_button",
                "subpage": "byok",
                "accessoryLabel": "Manage",
                "accessoryIcon": "ChevronRight",
            },
            {
                "id": "footer",
                "category": "ai",
                "name": "AI Reply Footer",
                "description": "Customize the metadata displayed in AI response footers.",
                "type": "subpage_button",
                "subpage": "footer",
                "accessoryLabel": "Customize",
                "accessoryIcon": "ChevronRight",
            },
            {
                "id": "reply_ping",
                "category": "ai",
                "name": "Reply Ping",
                "description": "Mentions the user when replying.",
                "type": "toggle",
                "default": bool(DefaultSettings.REPLY_PING),
            },
            {
                "id": "log_enabled",
                "channelKey": "log_channel",
                "category": "logs",
                "name": "Chat Logs Channel",
                "description": "Channel where message edits and deletions are logged.",
                "type": "channel_toggle",
                "default": False,
                "defaultChannel": "chat-logs",
            },
        ],
    }
    return web.json_response(schema)


async def handle_get_guild_settings(request: web.Request) -> web.Response:
    """Fetches live settings for a specific guild."""
    guild_id_str = request.match_info.get("guild_id")
    try:
        guild_id = int(guild_id_str)
    except ValueError:
        return web.json_response({"error": "Invalid guild ID"}, status=400)

    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    bot = request.app["bot"]

    is_allowed = await verify_user_guild_admin(token, guild_id, bot)
    if not is_allowed:
        return web.json_response({"error": "Unauthorized or not admin in guild"}, status=403)

    settings = await get_guild_settings_dict(bot, guild_id)

    # Formatted response for frontend consumption
    data = {
        "prefix": settings.get("prefix", DefaultSettings.PREFIX),
        "cbc_enabled": settings.get("cbc") is not None,
        "cbc_channel": str(settings.get("cbc")) if settings.get("cbc") else "",
        "reply_ping": bool(settings.get("reply_ping", 1)),
        "custom_prompt": settings.get("custom_prompt", "") or "",
        "log_enabled": settings.get("log_channel") is not None,
        "log_channel": str(settings.get("log_channel")) if settings.get("log_channel") else "",
        "footer_show_icon": bool(settings.get("footer_show_icon", DefaultSettings.FOOTER_SHOW_ICON)),
        "footer_show_name": bool(settings.get("footer_show_name", DefaultSettings.FOOTER_SHOW_NAME)),
        "footer_show_tokens": bool(settings.get("footer_show_tokens", DefaultSettings.FOOTER_SHOW_TOKENS)),
        "footer_show_latency": bool(settings.get("footer_show_latency", DefaultSettings.FOOTER_SHOW_LATENCY)),
        "byok_enabled": bool(settings.get("byok_enabled", 0)),
        "byok_primary_model": settings.get("byok_primary_model", "gemini-3.8-flash"),
        "byok_gemini_key": settings.get("byok_gemini_key", "") or "",
        "byok_xai_key": settings.get("byok_xai_key", "") or "",
        "byok_openai_key": settings.get("byok_openai_key", "") or "",
        "byok_anthropic_key": settings.get("byok_anthropic_key", "") or "",
        "byok_deepseek_key": settings.get("byok_deepseek_key", "") or "",
        "is_premium": bool(settings.get("is_premium", 0)),
    }

    # Also include available text channels and bot permissions if bot is in guild
    guild = bot.get_guild(guild_id)
    channels = []
    bot_in_guild = guild is not None
    bot_has_permissions = False
    missing_permissions = []

    REQUIRED_PERMISSIONS = {
        "view_channel": "View Channels",
        "send_messages": "Send Messages",
        "embed_links": "Embed Links",
        "read_message_history": "Read Message History",
    }

    if guild:
        channels = [{"id": str(c.id), "name": c.name} for c in guild.text_channels]
        me = guild.me
        if me:
            perms = me.guild_permissions
            if perms.administrator:
                bot_has_permissions = True
            else:
                for perm_attr, perm_name in REQUIRED_PERMISSIONS.items():
                    if not getattr(perms, perm_attr, False):
                        missing_permissions.append(perm_name)
                bot_has_permissions = (len(missing_permissions) == 0)
        else:
            bot_has_permissions = True
    else:
        missing_permissions = list(REQUIRED_PERMISSIONS.values())

    return web.json_response({
        "success": True,
        "settings": data,
        "channels": channels,
        "bot_in_guild": bot_in_guild,
        "bot_has_permissions": bot_has_permissions,
        "missing_permissions": missing_permissions
    })


async def handle_get_guild_quota(request: web.Request) -> web.Response:
    """Fetches live AI quota telemetry for a specific guild."""
    guild_id_str = request.match_info.get("guild_id")
    try:
        guild_id = int(guild_id_str)
    except ValueError:
        return web.json_response({"error": "Invalid guild ID"}, status=400)

    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    bot = request.app["bot"]

    is_allowed = await verify_user_guild_admin(token, guild_id, bot)
    if not is_allowed:
        return web.json_response({"error": "Unauthorized or not admin in guild"}, status=403)

    settings = await get_guild_settings_dict(bot, guild_id)

    usage = await bot.db_manager.get_guild_weekly_ai_usage(guild_id)
    is_premium = bool(settings.get("is_premium", 0))
    token_limit = DefaultSettings.PREMIUM_WEEKLY_TOKEN_LIMIT if is_premium else DefaultSettings.FREE_WEEKLY_TOKEN_LIMIT
    image_limit = DefaultSettings.PREMIUM_IMAGE_GEN_LIMIT_WEEKLY if is_premium else 1

    has_byok = bool(settings.get("byok_enabled", DefaultSettings.BYOK_ENABLED)) and bool(
        settings.get("byok_gemini_key") or
        settings.get("byok_xai_key") or
        settings.get("byok_openai_key") or
        settings.get("byok_anthropic_key") or
        settings.get("byok_deepseek_key") or
        settings.get("byok_glm_key")
    )

    return web.json_response({
        "success": True,
        "token_usage": usage.get("total_tokens", 0),
        "token_limit": token_limit,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "image_usage": usage.get("image_count", 0),
        "image_limit": image_limit,
        "next_reset_ts": usage.get("next_reset_ts"),
        "prompt_count": usage.get("prompt_count", 0),
        "is_premium": is_premium,
        "has_byok": has_byok,
    })


async def handle_save_guild_settings(request: web.Request) -> web.Response:
    """Updates and commits settings changes to the bot's database and memory cache."""
    guild_id_str = request.match_info.get("guild_id")
    try:
        guild_id = int(guild_id_str)
    except ValueError:
        return web.json_response({"error": "Invalid guild ID"}, status=400)

    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip()
    bot = request.app["bot"]

    is_allowed = await verify_user_guild_admin(token, guild_id, bot)
    if not is_allowed:
        return web.json_response({"error": "Unauthorized or not admin in guild"}, status=403)

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON body"}, status=400)

    # Translate frontend schema keys to DB column names
    db_updates = {}

    if "prefix" in body:
        db_updates["prefix"] = str(body["prefix"])[:10]
    if "reply_ping" in body:
        db_updates["reply_ping"] = 1 if body["reply_ping"] else 0
    if "custom_prompt" in body:
        db_updates["custom_prompt"] = str(body["custom_prompt"])[:2000] if body["custom_prompt"] else None
    
    # CBC channel logic
    if "cbc_enabled" in body:
        if not body["cbc_enabled"]:
            db_updates["cbc"] = None
        elif "cbc_channel" in body:
            try:
                db_updates["cbc"] = int(body["cbc_channel"])
            except ValueError:
                # If channel name string passed, resolve or keep
                pass

    # Log channel logic
    if "log_enabled" in body:
        if not body["log_enabled"]:
            db_updates["log_channel"] = None
        elif "log_channel" in body:
            try:
                db_updates["log_channel"] = int(body["log_channel"])
            except ValueError:
                pass

    # Footer toggles
    for f in ["footer_show_icon", "footer_show_name", "footer_show_tokens", "footer_show_latency"]:
        if f in body:
            db_updates[f] = 1 if body[f] else 0

    # BYOK keys
    for k in ["byok_gemini_key", "byok_xai_key", "byok_openai_key", "byok_anthropic_key", "byok_deepseek_key"]:
        if k in body:
            db_updates[k] = str(body[k]).strip() if body[k] else None

    if "byok_primary_model" in body:
        db_updates["byok_primary_model"] = str(body["byok_primary_model"])

    # Persist all updates to DatabaseManager
    for key, val in db_updates.items():
        try:
            await bot.db_manager.update_guild_setting(guild_id, key, val)
            bot.settings_cache.setdefault(guild_id, {})[key] = val
        except Exception as e:
            logger.error(f"Failed to update setting {key} for guild {guild_id}: {e}")

    return web.json_response({
        "success": True,
        "message": "Settings updated successfully",
        "updated": list(db_updates.keys())
    })


async def handle_get_bot_guilds(request: web.Request) -> web.Response:
    """Returns a map of all guilds the bot is currently in and their permission status."""
    bot = request.app["bot"]
    REQUIRED_PERMISSIONS = {
        "view_channel": "View Channels",
        "send_messages": "Send Messages",
        "embed_links": "Embed Links",
        "read_message_history": "Read Message History",
    }

    result = {}
    for guild in getattr(bot, "guilds", []):
        me = guild.me
        if not me:
            result[str(guild.id)] = {
                "in_guild": True,
                "has_permissions": False,
                "missing_permissions": list(REQUIRED_PERMISSIONS.values())
            }
            continue

        perms = me.guild_permissions
        if perms.administrator:
            has_perms = True
            missing = []
        else:
            missing = [label for key, label in REQUIRED_PERMISSIONS.items() if not getattr(perms, key, False)]
            has_perms = (len(missing) == 0)

        result[str(guild.id)] = {
            "in_guild": True,
            "has_permissions": has_perms,
            "missing_permissions": missing
        }

    return web.json_response({
        "success": True,
        "guilds": result
    })


def setup_dashboard_routes(app: web.Application, bot):
    """Mounts dashboard API routes and CORS middleware on the aiohttp application."""
    app["bot"] = bot
    app.middlewares.append(cors_middleware)

    app.router.add_get("/api/settings/schema", handle_settings_schema)
    app.router.add_get("/api/bot/guilds", handle_get_bot_guilds)
    app.router.add_get("/api/guilds/{guild_id}/settings", handle_get_guild_settings)
    app.router.add_post("/api/guilds/{guild_id}/settings", handle_save_guild_settings)
    app.router.add_get("/api/guilds/{guild_id}/quota", handle_get_guild_quota)

    # Preflight routes
    app.router.add_route("OPTIONS", "/api/settings/schema", lambda r: web.Response(status=204))
    app.router.add_route("OPTIONS", "/api/bot/guilds", lambda r: web.Response(status=204))
    app.router.add_route("OPTIONS", "/api/guilds/{guild_id}/settings", lambda r: web.Response(status=204))
    app.router.add_route("OPTIONS", "/api/guilds/{guild_id}/quota", lambda r: web.Response(status=204))

    logger.info("Dashboard REST API routes mounted successfully.")
