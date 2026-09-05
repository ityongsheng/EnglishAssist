class EnglishAssistError(Exception):
    code = "english_assist_error"


class ConfigurationError(EnglishAssistError):
    code = "configuration_error"


class AuthenticationError(EnglishAssistError):
    code = "authentication_error"


class NetworkError(EnglishAssistError):
    code = "network_error"


class RateLimitError(EnglishAssistError):
    code = "rate_limit_error"


class APIError(EnglishAssistError):
    code = "api_error"


class InvalidResponseError(EnglishAssistError):
    code = "invalid_response"
