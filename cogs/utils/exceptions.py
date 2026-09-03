import typing

class BotError(Exception):
    """Base exception class for all custom errors in Spl1ceAI."""
    pass

class AIError(BotError):
    """Base exception for all AI-related errors."""
    pass

class AIRateLimitError(AIError):
    """Raised when the AI provider rate limits us or we exceed our daily quota."""
    def __init__(self, message: str = "Rate limit exceeded or quota reached", retry_after: typing.Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after

class AIServiceUnavailableError(AIError):
    """Raised when the AI provider is down, times out, or returns a service error."""
    def __init__(self, message: str = "AI service is currently unavailable", original_error: typing.Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error

class AISafetyBlockedError(AIError):
    """Raised when the AI provider flags safety blocks on the prompt or response."""
    pass

class AIConfigurationError(AIError):
    """Raised when AI provider keys or settings are missing/invalid."""
    pass

class AIQuotaReachedError(AIError):
    """Raised when the bot's weekly token or image generation quota is reached."""
    def __init__(self, message: str = "Weekly AI token quota reached!", reset_ts: typing.Optional[int] = None, is_image: bool = False):
        super().__init__(message)
        self.reset_ts = reset_ts
        self.is_image = is_image


# =========================================================================
# --- ECONOMY & CASINO ERRORS ---
# =========================================================================

class EconomyError(BotError):
    """Base exception for all economy, casino, and wallet errors."""
    pass


class InsufficientBalanceError(EconomyError):
    """Raised when a user attempts an action without enough coins."""
    def __init__(self, current_balance: float = 0.0, required_amount: float = 0.0):
        self.current_balance = current_balance
        self.required_amount = required_amount
        super().__init__(f"Insufficient funds: Have {current_balance:.2f}, need {required_amount:.2f}")


class DailyAlreadyClaimedError(EconomyError):
    """Raised when a user attempts to claim their daily reward too early."""
    def __init__(self, next_claim_ts: int):
        self.next_claim_ts = next_claim_ts
        super().__init__(f"Daily already claimed. Next claim available at {next_claim_ts}")


# =========================================================================
# --- TOOLS & MEDIA ERRORS ---
# =========================================================================

class ToolError(BotError):
    """Base exception for utility and media tool failures."""
    pass


class InvalidURLError(ToolError):
    """Raised when a supplied URL is invalid or malformed."""
    def __init__(self, message: str = "Invalid URL provided."):
        super().__init__(message)


class MediaTooLongError(ToolError):
    """Raised when a video/audio exceeds the maximum processing duration."""
    def __init__(self, max_minutes: int = 15):
        self.max_minutes = max_minutes
        super().__init__(f"Media duration exceeds maximum limit of {max_minutes} minutes.")


class MediaDownloadError(ToolError):
    """Raised when downloading or converting media fails."""
    def __init__(self, message: str = "Failed to download or process media file."):
        super().__init__(message)

