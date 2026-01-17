"""Service-layer exceptions."""


class FactoryError(Exception):
    """Raised when a runtime entity cannot be created."""


class SaveLoadError(Exception):
    """Raised when save or load operations fail."""


class TravelBlockedError(Exception):
    """Raised when travel is blocked by story progression locks."""




