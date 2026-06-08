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


class SpeechTranscriptionError(DomainError):
    code = "speech_transcription_failed"
    http_status = 503


class UnsafeContentError(DomainError):
    code = "unsafe_content"
    http_status = 422


class UserAlreadyExistsError(DomainError):
    code = "user_already_exists"
    http_status = 409


class InvalidCredentialsError(DomainError):
    code = "invalid_credentials"
    http_status = 401


class AuthenticationRequiredError(DomainError):
    code = "authentication_required"
    http_status = 401
