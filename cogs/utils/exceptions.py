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
    """Raised when the bot's daily token quota is reached."""
    pass
