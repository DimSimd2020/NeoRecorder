"""Domain exceptions for studio scene management."""


class StudioError(RuntimeError):
    """Base studio domain error."""


class SceneNotFoundError(StudioError):
    """Raised when a scene does not exist."""


class SourceNotFoundError(StudioError):
    """Raised when a source does not exist."""


class InvalidSceneConfigurationError(StudioError):
    """Raised when a scene cannot be translated into a recording request."""
