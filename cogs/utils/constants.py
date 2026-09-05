class Emojis:
    # Generic status & reactions
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    ROBOT = "🤖"
    RELOAD = "🔄"
    
    # Custom AI emojis
    AI_FROWN = "<:sAI_frown:1513642744394944722>"
    AI_HIGH_DEMAND = "<:sAI_high_demand:1513623669308657766>"
    AI_HAND_LIMIT = "<:sAI_hand_limit:1513659143456559235>"
    
    # Custom provider icons
    GEMINI = "<:sAI_gemini:1515921338106380369>"
    CHATGPT = "<:sAI_chatgpt:1515922050739601418>"
    CLAUDE = "<:sAI_claude:1515922404671754411>"
    DEEPSEEK = "<:sAI_deepseek:1515922761732849664>"
    GROK = "<:sAI_grok:1516602717290893383>"
    GLM = "🇨🇳"
    COIN = "🪙"
    
    # Custom fun & system emojis
    YELLOW_LOOK = "<:CC_yellow_look:1440119405991166186>"
    YELLOW_ANGRY = "<:CC_yellow_angry:1441249440622182410>"
    EMPTY = "<:empty:1454324278010056744>"
    
    # Connect 4 logo and vs
    C4_LOGO = "<:sAI_C4L:1462459349137096775>"
    C4_VS = "<:sAI_VS:1471123115126947901>"
    
    # Connect 4 board elements
    BOARD_EMPTY = "<:sAI_ME:1462171398192496917>"
    BOARD_RED = "<:sAI_MR:1462200144350019754>"
    BOARD_YELLOW = "<:sAI_MY:1462200170065297520>"
    BOARD_LEFT_EMPTY = "<:sAI_CLE:1462174611813695548>"
    BOARD_LEFT_RED = "<:sAI_CLR:1462199928511271063>"
    BOARD_LEFT_YELLOW = "<:sAI_CLY:1462199963004965027>"
    BOARD_RIGHT_EMPTY = "<:sAI_CRE:1462175903030312981>"
    BOARD_RIGHT_RED = "<:sAI_CRR:1462200012355408135>"
    BOARD_RIGHT_YELLOW = "<:sAI_CRY:1462200075945250957>"
    BOARD_BASE_LEFT = "<:sAI_LB:1462454097083891884>"
    BOARD_BASE_MIDDLE = "<:sAI_MB:1462453987369291867>"
    BOARD_BASE_RIGHT = "<:sAI_RB:1462454152960409801>"
    
    # Connect 4 pieces & state
    RED_PIECE = "<:sAI_PR:1462200246129004835>"
    YELLOW_PIECE = "<:sAI_PY:1462200211186254009>"
    TO_MOVE_ARROW = "<a:sAI_rightarrow:1471523709981294709>"
    LOADING = "<a:sAI_loading:1476194991809237152>"
    CROWN = "👑"
    
    # Custom fun & banned emojis
    BANNED = "<a:sAI_banned:1478422889668542545>"
    
    # Settings buttons emojis (placeholders)
    ON = "<:sAI_on:1524517702041997434>"
    OFF = "<:sAI_off:1524512020945440981>"
    EDIT = "<:sAI_edit:1524892990395515022>"
    
    # Custom UI emojis
    ARROW = "<:sAI_arrow:1537962369060315236>"
    
    # Generic emojis
    BRAIN = "🧠"
    CRY = "😢"
    FLAG = "🏳️"
    MINUS = "➖"
    HANDSHAKE = "🤝"
    ARROW_LEFT = "◀"
    ARROW_RIGHT = "▶"

class ErrorMessages:
    QUOTA_REACHED = f"{Emojis.AI_FROWN} Weekly AI token quota reached! Please check `/quota` or `/upgrade`."
    BUSY_OR_LIMIT = f"{Emojis.AI_HIGH_DEMAND} AI service is too busy or rate limited! Please try again in a moment."
    SAFETY_BLOCKED = "🛡️ Response blocked by AI safety filters."
    UNEXPECTED = f"{Emojis.WARNING} An unexpected error occurred while processing your request."

    @staticmethod
    def image_process_failed(error_msg: str) -> str:
        return f"{Emojis.WARNING} Failed to process attachment image: {error_msg}"

    @staticmethod
    def attachment_not_image() -> str:
        return f"{Emojis.WARNING} Attached file is not an image."

    @staticmethod
    def already_listening() -> str:
        return f"{Emojis.WARNING} I'm already listening in this channel!"

    @staticmethod
    def invalid_duration() -> str:
        return f"{Emojis.WARNING} Invalid duration. Use '30m', '1h', etc."

    # Fun cog errors & text
    TIKTOK_NO_VIDEOS = f"Could not find any videos in the collection! {Emojis.CRY}"
    
    @staticmethod
    def tiktok_failed(last_error: str) -> str:
        return f"All attempts failed. Last error: `{last_error}`"

    @staticmethod
    def tiktok_general_error(command_name: str, emoji: str, error: str) -> str:
        return f"Something went wrong while fetching the {command_name}! {emoji}\n`{error}`"

    QUOTE_MEMBER_NOT_FOUND = f"User not found.\n-# Mention the user or provide their ID."
    QUOTE_BAD_ARGUMENT = "Please provide a message ID, a message link, or reply to a message."
    QUOTE_LINK_FETCH_FAILED = "Could not fetch the message from the provided link. Make sure the bot has access to that channel."
    QUOTE_ID_FETCH_FAILED = "Could not find a message with that ID in this channel."
    QUOTE_INVALID_FORMAT = "Invalid message ID or link format."

    @staticmethod
    def quote_fetch_error(error_msg: str) -> str:
        return f"An error occurred while fetching the message: `{error_msg}`"

    @staticmethod
    def quote_gen_failed(error_msg: str) -> str:
        return f"{Emojis.ERROR} Failed to generate quote card image: `{error_msg}`"

    QUOTE_ATTACHMENT_PLACEHOLDER = "*(Image/Attachment)*"
    QUOTE_NO_TEXT_PLACEHOLDER = "*(No text)*"

    # YouTube downloader errors
    YT_INVALID_URL = f"{Emojis.WARNING} Invalid YouTube URL. Please provide a valid link."
    YT_TOO_LONG = f"{Emojis.WARNING} Video is too long! The maximum allowed duration is 15 minutes."
    YT_DOWNLOAD_FAILED = f"{Emojis.ERROR} Failed to download or convert the video."


class SuccessMessages:
    @staticmethod
    def summon_success(time_str: str) -> str:
        return f"**spl1ceAI summoned.** I will answer mentions and replies.\n-# Ends {time_str}"


class InfoMessages:
    @staticmethod
    def summon_ended(tokens: int) -> str:
        return f"⌛ **spl1ceAI summon ended.** I am no longer listening.\n-# Session used `{tokens}` tokens."

    @staticmethod
    def usage_stats(day: str, requests: int, tokens: int, limit: int, in_tokens: int, out_tokens: int) -> str:
        return f"📊 **AI Usage Today ({day})**\n- Requests: `{requests}`\n- Tokens: `{tokens} / {limit}`\n  - In: `{in_tokens}`\n  - Out: `{out_tokens}`"

    @staticmethod
    def usage_none(day: str) -> str:
        return f"📊 **AI Usage Today ({day})**\nNo usage recorded today."


class URLs:
    WEBSITE = "https://spl1ceai.com"
    PORTAL = "https://polar.sh/spl1ceai/portal"
    INVITE = "https://spl1ceai.com/invite"
    SUPPORT = "https://discord.gg"


class DefaultSettings:
    PREFIX = "!"
    CBC = None
    LOG_CHANNEL = None
    LLM_PRIMARY = "gemini-3.7-flash"
    LLM_BACKUP1 = "gemini-2.5-flash"
    LLM_BACKUP2 = "grok-4.3"
    LLM_BACKUP3 = "disabled"
    LLM_TIMEOUT = 15
    SHOW_MODEL = 1
    FOOTER_SHOW_ICON = 1
    FOOTER_SHOW_NAME = 1
    FOOTER_SHOW_TOKENS = 1
    FOOTER_SHOW_LATENCY = 1
    REPLY_PING = 1
    IS_PREMIUM = 0
    CUSTOM_PROMPT = None
    BYOK_GEMINI_KEY = None
    BYOK_XAI_KEY = None
    BYOK_OPENAI_KEY = None
    BYOK_ANTHROPIC_KEY = None
    BYOK_DEEPSEEK_KEY = None
    BYOK_GLM_KEY = None
    BYOK_PRIMARY_MODEL = "gemini-3.7-flash"
    BYOK_FALLBACK_MODEL = "gemini-3.6-flash"
    BYOK_ENABLED = 1
    FREE_WEEKLY_TOKEN_LIMIT = 100_000
    PREMIUM_WEEKLY_TOKEN_LIMIT = 1_000_000
    FREE_IMAGE_GEN_LIMIT_BIWEEKLY = 1
    PREMIUM_IMAGE_GEN_LIMIT_WEEKLY = 5
    PREMIUM_PRICE_EUR = "2.99€"
    POLAR_ORGANIZATION_SLUG = "spl1ceai"
    WEBHOOK_PORT = 8080
    STRIPE_WEBHOOK_PORT = 8080  # Backward-compatible alias

