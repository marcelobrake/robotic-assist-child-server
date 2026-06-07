class DomainError(Exception):
    """Base class for expected, structured application errors."""

    code = "domain_error"
    http_status = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class PromptNotFoundError(DomainError):
    code = "prompt_not_found"
    http_status = 404


class PromptsNotLoadedError(DomainError):
    code = "prompts_not_loaded"
    http_status = 503


class UnsafeContentError(DomainError):
    code = "unsafe_content"
    http_status = 422
